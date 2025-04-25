"""
IntentClient - Main client for the IntentLayer protocol.
"""
import json
import hashlib
import logging
import time
import urllib.parse
from inspect import signature
from typing import Dict, Any, Optional, Union, List, cast

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from web3 import Web3
from web3.exceptions import Web3Exception
from web3.types import TxReceipt as Web3TxReceipt

from .envelope import CallEnvelope
from .exceptions import (
    PinningError, TransactionError, EnvelopeError, NetworkError,
    AlreadyRegisteredError, InactiveDIDError
)
from .utils import ipfs_cid_to_bytes
from .config import NetworkConfig
from .signer import Signer
from .signer.local import LocalSigner

class IntentClient:
    """
    Client for interacting with the IntentLayer protocol.
    Handles IPFS pinning, intent recording, and DID registration.
    """

    # ABI for IntentRecorder contract
    INTENT_RECORDER_ABI = [
        {
            "inputs": [
                {"internalType": "bytes32", "name": "envelopeHash", "type": "bytes32"},
                {"internalType": "bytes", "name": "cid", "type": "bytes"},
            ],
            "name": "recordIntent",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "MIN_STAKE_WEI",
            "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
            "stateMutability": "view",
            "type": "function",
        },
    ]
    
    # ABI for DIDRegistry contract
    DID_REGISTRY_ABI = [
        {
            "inputs": [
                {"internalType": "string", "name": "did", "type": "string"}
            ],
            "name": "register",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "string", "name": "did", "type": "string"}
            ],
            "name": "resolve",
            "outputs": [
                {"internalType": "address", "name": "owner", "type": "address"},
                {"internalType": "bool", "name": "active", "type": "bool"}
            ],
            "stateMutability": "view",
            "type": "function",
        }
    ]

    @classmethod
    def from_network(
        cls,
        network: str,
        pinner_url: str,
        signer: Union[Signer, str],
        rpc_url: Optional[str] = None,
        retry_count: int = 3,
        timeout: int = 30,
        logger: Optional[logging.Logger] = None,
    ) -> "IntentClient":
        """
        Create an IntentClient from a network configuration.
        
        Args:
            network: Network name from networks.json (e.g., "zksync-era-sepolia")
            pinner_url: URL of the IPFS pinning service
            signer: Either a Signer instance or a private key string
            rpc_url: Optional RPC URL override
            retry_count: Number of retries for HTTP requests
            timeout: Timeout in seconds for HTTP requests
            logger: Optional logger instance
            
        Returns:
            Configured IntentClient instance
            
        Raises:
            NetworkError: If the network configuration cannot be loaded
        """
        try:
            # Get network configuration
            net_config = NetworkConfig.get_network(network)
            
            # Determine RPC URL
            effective_rpc = NetworkConfig.get_rpc_url(network, rpc_url)
            
            # Create a signer if given a private key
            if isinstance(signer, str):
                signer = LocalSigner(signer)
            
            # Create the client
            client = cls(
                rpc_url=effective_rpc,
                pinner_url=pinner_url,
                signer=signer,
                recorder_address=net_config["intentRecorder"],
                did_registry_address=net_config["didRegistry"],
                retry_count=retry_count,
                timeout=timeout,
                logger=logger,
            )
            
            # Store network info for chain ID validation
            client._network_name = network
            client._expected_chain_id = int(net_config["chainId"])
            
            return client
            
        except Exception as e:
            raise NetworkError(f"Failed to initialize client from network '{network}': {str(e)}")

    def __init__(
        self,
        rpc_url: str,
        pinner_url: str,
        signer: Signer,
        recorder_address: str,
        did_registry_address: Optional[str] = None,
        min_stake_wei: Optional[int] = None,
        *,
        expected_chain_id: Optional[int] = None,
        retry_count: int = 3,
        timeout: int = 30,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the IntentClient.
        
        Args:
            rpc_url: Ethereum RPC URL
            pinner_url: IPFS pinning service URL
            signer: Signer instance for signing transactions
            recorder_address: IntentRecorder contract address
            did_registry_address: DIDRegistry contract address (optional)
            min_stake_wei: Manual override for minimum stake (auto-queried if None)
            expected_chain_id: Expected chain ID for safety checks (recommended)
            retry_count: Number of retries for HTTP requests
            timeout: Timeout in seconds for HTTP requests
            logger: Optional logger instance
            
        Note:
            It's strongly recommended to provide expected_chain_id to prevent 
            accidental transactions on the wrong network.
        """
        # Validate URLs
        for name, url in [("rpc_url", rpc_url), ("pinner_url", pinner_url)]:
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname or ""
            is_local = host in ("localhost", "127.0.0.1")
            if parsed.scheme != "https" and not is_local:
                raise ValueError(
                    f"{name} must use https:// for security (got: {parsed.scheme}://)"
                )

        self.rpc_url = rpc_url
        self.pinner_url = pinner_url.rstrip("/")
        self.recorder_address = Web3.to_checksum_address(recorder_address)
        self.did_registry_address = Web3.to_checksum_address(did_registry_address) if did_registry_address else None
        self.logger = logger or logging.getLogger(__name__)
        self._network_name = None
        self._expected_chain_id = expected_chain_id
        self._min_stake_wei = min_stake_wei
        # Use timestamp of 0 to mark manually set values
        self._min_stake_wei_timestamp = None if min_stake_wei is None else 0

        # Web3 setup
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        try:
            self._default_gas_price = self.w3.eth.gas_price
        except Exception:
            self._default_gas_price = None

        # Ensure signer is never None
        if signer is None:
            raise ValueError("signer must be provided")
        self.signer = signer

        # Contract binding
        self.recorder_contract = self.w3.eth.contract(
            address=self.recorder_address, abi=self.INTENT_RECORDER_ABI
        )
        
        # DID registry contract (if address provided)
        self.did_registry_contract = None
        if self.did_registry_address:
            self.did_registry_contract = self.w3.eth.contract(
                address=self.did_registry_address, abi=self.DID_REGISTRY_ABI
            )

        # HTTP session with retry logic
        self.session = requests.Session()
        
        # Simple retry configuration with compatibility 
        # for different urllib3 versions
        retry_kwargs = {
            "total": retry_count,
            "backoff_factor": 0.5,
            "status_forcelist": [500, 502, 503, 504],
            "connect": retry_count,
            "read": retry_count,
        }
        
        # Pick whichever kw-arg the current urllib3 supports
        init_params = signature(Retry.__init__).parameters
        if "allowed_methods" in init_params:
            retry_kwargs["allowed_methods"] = frozenset({"GET", "POST"})
        elif "method_whitelist" in init_params:
            retry_kwargs["method_whitelist"] = frozenset({"GET", "POST"})
        # (else: neither present -> we're on some exotic fork, just skip)
            
        retries = Retry(**retry_kwargs)
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.timeout = timeout

    @property
    def address(self) -> str:
        """Get the address associated with the signer."""
        if self.signer is None:
            raise ValueError("No signer available")
        return self.signer.address

    @property
    def min_stake_wei(self) -> int:
        """
        Get the minimum stake required by the IntentRecorder contract.
        
        Returns:
            Minimum stake in wei as an integer
            
        Raises:
            TransactionError: If the contract call fails
            
        Note:
            The minimum stake value is cached for 15 minutes to reduce RPC calls.
            Value won't auto-refresh if manually provided in constructor.
            Use refresh_min_stake() to force a refresh.
        """
        # Cache expiration: 15 minutes
        CACHE_EXPIRY_SECONDS = 900
        
        # Don't auto-refresh if manually set in constructor
        manually_set = self._min_stake_wei is not None and self._min_stake_wei_timestamp == 0
        if manually_set:
            return self._min_stake_wei
        
        current_time = time.time()
        cache_expired = (self._min_stake_wei_timestamp is None or 
                         current_time - self._min_stake_wei_timestamp > CACHE_EXPIRY_SECONDS)
                         
        if self._min_stake_wei is None or cache_expired:
            try:
                self._min_stake_wei = self.recorder_contract.functions.MIN_STAKE_WEI().call()
                self._min_stake_wei_timestamp = current_time
                self.logger.debug(f"Updated min_stake_wei to {self._min_stake_wei}")
            except Exception as e:
                raise TransactionError(f"Failed to get minimum stake: {e}")
        return self._min_stake_wei
        
    def refresh_min_stake(self) -> int:
        """
        Force refresh the minimum stake value from the contract.
        
        Returns:
            Updated minimum stake in wei
            
        Raises:
            TransactionError: If the contract call fails
        """
        try:
            self._min_stake_wei = self.recorder_contract.functions.MIN_STAKE_WEI().call()
            self._min_stake_wei_timestamp = time.time()
            self.logger.debug(f"Refreshed min_stake_wei to {self._min_stake_wei}")
            return self._min_stake_wei
        except Exception as e:
            raise TransactionError(f"Failed to refresh minimum stake: {e}")

    def assert_chain_id(self) -> None:
        """
        Assert that the connected chain matches the expected chain ID.
        
        Raises:
            NetworkError: If the chain ID doesn't match or _expected_chain_id is not set
        """
        if self._expected_chain_id is None:
            self.logger.warning("No expected chain ID set, skipping chain ID validation")
            return
            
        try:
            actual_chain_id = self.w3.eth.chain_id
            if actual_chain_id != self._expected_chain_id:
                network_name = self._network_name or "unknown"
                raise NetworkError(
                    f"Chain ID mismatch: expected {self._expected_chain_id} ({network_name}), "
                    f"got {actual_chain_id}"
                )
        except Exception as e:
            if isinstance(e, NetworkError):
                raise
            raise NetworkError(f"Failed to validate chain ID: {e}")

    def register_did(
        self, 
        did: str,
        gas: Optional[int] = None,
        gas_price_override: Optional[int] = None,
        wait_for_receipt: bool = True,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Register a DID on the DIDRegistry contract.
        
        Args:
            did: Decentralized Identifier to register
            gas: Gas limit for the transaction (optional)
            gas_price_override: Gas price in wei (optional)
            wait_for_receipt: Whether to wait for the transaction receipt
            force: If True, attempts registration even if the DID is already registered
                  but inactive. Has no effect if the DID is already registered and active.
            
        Returns:
            Transaction receipt as dictionary
            
        Raises:
            ValueError: If DIDRegistry contract address is not set
            AlreadyRegisteredError: If the DID is already registered and active
            InactiveDIDError: If the DID exists but is inactive and force=False
            TransactionError: If the transaction fails
        """
        if not self.did_registry_contract:
            raise ValueError("DIDRegistry contract address not set")
            
        # Verify chain ID
        self.assert_chain_id()
        
        # Check if DID already exists
        try:
            owner, active = self.resolve_did(did)
            if active:
                raise AlreadyRegisteredError(did, owner)
            elif not force:
                raise InactiveDIDError(did, owner)
            # If force=True and the DID exists but is inactive, proceed with registration
            self.logger.warning(f"Re-registering inactive DID '{did}' (previously owned by {owner})")
        except TransactionError:
            # If resolve_did fails, it likely means the DID doesn't exist,
            # so we can proceed with registration
            pass
        
        try:
            # Get nonce
            nonce = self.w3.eth.get_transaction_count(self.signer.address)
            
            # Estimate gas if not provided
            if gas is None:
                try:
                    est = self.did_registry_contract.functions.register(did).estimate_gas(
                        {"from": self.signer.address}
                    )
                    gas = int(est * 1.1)
                    self.logger.debug(f"Estimated gas for DID registration: {gas}")
                except Exception as e:
                    gas = 250_000
                    self.logger.warning(f"Gas estimate failed, fallback to {gas}: {e}")
            
            # Build transaction parameters
            tx_params = {
                "from": self.signer.address,
                "nonce": nonce,
                "gas": gas,
            }
            
            # Set gas price if provided
            if gas_price_override is not None:
                tx_params["gasPrice"] = gas_price_override
            else:
                tx_params["gasPrice"] = (
                    self._default_gas_price
                    if self._default_gas_price is not None
                    else self.w3.eth.gas_price
                )
            
            # Build transaction
            tx = self.did_registry_contract.functions.register(did).build_transaction(tx_params)
            
            # Sign transaction
            try:
                signed = self.signer.sign_transaction(tx)
            except Exception as e:
                self.logger.error(f"Signing failed: {e}")
                raise TransactionError(f"Failed to sign transaction: {e}")
            
            # Send transaction
            try:
                if hasattr(signed, "rawTransaction"):
                    raw_bytes = signed.rawTransaction
                elif hasattr(signed, "raw_transaction"):
                    raw_bytes = signed.raw_transaction
                else:
                    raise TransactionError("Signed transaction missing raw bytes")
                    
                tx_hash = self.w3.eth.send_raw_transaction(raw_bytes)
                self.logger.info(f"Sent DID registration tx: {tx_hash.hex()}")
            except Exception as e:
                self.logger.error(f"Send failed: {e}")
                if isinstance(e, Web3Exception):
                    raise
                raise TransactionError(f"Failed to send transaction: {e}")
            
            # Wait for receipt
            if wait_for_receipt:
                receipt = self.w3.eth.wait_for_transaction_receipt(
                    tx_hash, timeout=120, poll_latency=0.1
                )
                return dict(receipt)
            else:
                return {"transactionHash": "0x" + tx_hash.hex() if isinstance(tx_hash, bytes) else tx_hash}
                
        except (TransactionError, AlreadyRegisteredError, InactiveDIDError, Web3Exception):
            # Re-raise known exceptions
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in DID registration: {e}")
            raise TransactionError(f"DID registration failed: {e}")

    def resolve_did(self, did: str) -> tuple[str, bool]:
        """
        Resolve a DID to its associated Ethereum address and active status.
        
        Args:
            did: Decentralized Identifier to resolve
            
        Returns:
            Tuple of (owner_address, active_flag) where:
              - owner_address: Ethereum address of the DID owner (checksummed)
              - active_flag: Boolean indicating if the DID is active
              
            If the DID is not registered, returns (ZERO_ADDRESS, False)
            
        Raises:
            ValueError: If DIDRegistry contract address is not set
            TransactionError: If there's an RPC or contract error
        """
        if not self.did_registry_contract:
            raise ValueError("DIDRegistry contract address not set")
        
        ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
            
        try:
            owner, active = self.did_registry_contract.functions.resolve(did).call()
            return Web3.to_checksum_address(owner), active
        except ValueError as e:
            # Check if this is a "revert" error which usually indicates the DID doesn't exist
            if "revert" in str(e).lower():
                self.logger.debug(f"DID '{did}' not found (contract reverted)")
                return ZERO_ADDRESS, False
            # Re-raise other ValueErrors as TransactionError
            raise TransactionError(f"Failed to resolve DID: {e}")
        except Exception as e:
            # Re-raise other exceptions as TransactionError
            raise TransactionError(f"Failed to resolve DID: {e}")

    def pin_to_ipfs(self, payload: Dict[str, Any]) -> str:
        """
        Pin data to IPFS via the pinning service.
        
        Args:
            payload: Data to pin to IPFS
            
        Returns:
            IPFS CID for the pinned content
            
        Raises:
            PinningError: If pinning fails
        """
        safe = self._sanitize_payload(payload)
        self.logger.debug(f"Pinning payload to IPFS: {safe}")

        max_retries = 3
        attempt = 0
        backoff = 0.5

        while True:
            try:
                resp = self.session.post(
                    f"{self.pinner_url}/pin", json=payload, timeout=self.timeout
                )
                if resp.status_code < 500:
                    resp.raise_for_status()
                    ct = resp.headers.get("Content-Type", "")
                    if "application/json" not in ct:
                        self.logger.warning(f"Unexpected Content-Type: {ct}")
                    try:
                        result = resp.json()
                        if "cid" not in result:
                            raise PinningError(
                                f"Missing CID in pinner response: {result}"
                            )
                        return result["cid"]
                    except ValueError as e:
                        self.logger.error(f"Invalid JSON from pinner: {e}")
                        raise PinningError(f"Invalid JSON from pinner: {e}")
                if attempt < max_retries - 1:
                    attempt += 1
                    wait = backoff * (2 ** (attempt - 1))
                    self.logger.warning(f"Retrying in {wait}s (server {resp.status_code})")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
            except requests.RequestException as e:
                if (
                    isinstance(e, requests.HTTPError)
                    and e.response.status_code >= 500
                    and attempt < max_retries - 1
                ):
                    attempt += 1
                    wait = backoff * (2 ** (attempt - 1))
                    self.logger.warning(f"Retrying in {wait}s due to HTTPError: {e}")
                    time.sleep(wait)
                    continue
                self.logger.error(f"IPFS pinning failed: {e}")
                raise PinningError(f"IPFS pinning failed: {e}")
            except ValueError as e:
                self.logger.error(f"Invalid JSON from pinner: {e}")
                raise PinningError(f"Invalid JSON from pinner: {e}")

    def send_intent(
        self,
        envelope_hash: Union[str, bytes],
        payload_dict: Dict[str, Any],
        stake_wei: Optional[int] = None,
        gas: Optional[int] = None,
        gas_price_override: Optional[int] = None,
        poll_interval: Optional[float] = None,
        wait_for_receipt: bool = True,
    ) -> Dict[str, Any]:
        """
        Send an intent to be recorded on-chain.
        
        This method:
        1. Validates the payload format
        2. Pins the payload to IPFS
        3. Records the intent on-chain with the envelope hash and IPFS CID
        4. Optionally waits for transaction confirmation
        
        Args:
            envelope_hash: Hash of the envelope (bytes32 or hex string)
            payload_dict: Payload dictionary with envelope data
            stake_wei: Amount to stake (defaults to min_stake_wei)
            gas: Gas limit for the transaction (optional)
            gas_price_override: Gas price in wei (optional)
            poll_interval: Polling interval for receipt (optional)
            wait_for_receipt: Whether to wait for the transaction receipt
            
        Returns:
            Transaction receipt as dictionary
            
        Raises:
            EnvelopeError: If the envelope is invalid
            PinningError: If IPFS pinning fails
            TransactionError: If the transaction fails
            InactiveDIDError: If the envelope's DID exists but is inactive
        """
        # Verify chain ID
        self.assert_chain_id()
        
        try:
            # 1. Validate payload
            self._validate_payload(payload_dict)
            
            # 1.5 Verify DID is active if we have a DID registry
            if self.did_registry_contract and "envelope" in payload_dict and isinstance(payload_dict["envelope"], dict):
                did = payload_dict["envelope"].get("did")
                if did:
                    try:
                        owner, active = self.resolve_did(did)
                        if not active:
                            raise InactiveDIDError(did, owner)
                    except TransactionError:
                        # If DID doesn't exist, that's fine - it will get caught during contract execution
                        pass

            # 2. Normalize envelope hash BEFORE any network calls
            if isinstance(envelope_hash, str):
                h = (
                    envelope_hash[2:]
                    if envelope_hash.startswith("0x")
                    else envelope_hash
                )
                try:
                    envelope_hash = bytes.fromhex(h)
                except ValueError as e:
                    raise EnvelopeError(f"Invalid envelope hash format: {e}")

            # Use default stake if not provided
            if stake_wei is None:
                stake_wei = self.min_stake_wei

            # 3. Pin to IPFS
            cid = self.pin_to_ipfs(payload_dict)
            try:
                cid_bytes = ipfs_cid_to_bytes(cid)
            except Exception as e:
                raise EnvelopeError(f"Failed to convert CID: {e}")

            # 4. Nonce
            nonce = self.w3.eth.get_transaction_count(self.signer.address)

            # 5. Gas estimate
            if gas is None:
                try:
                    est = (
                        self.recorder_contract.functions.recordIntent(
                            envelope_hash, cid_bytes
                        )
                        .estimate_gas(
                            {"from": self.signer.address, "value": stake_wei}
                        )
                    )
                    gas = int(est * 1.1)
                    self.logger.debug(f"Estimated gas: {gas}")
                except Exception as e:
                    gas = 300_000
                    self.logger.warning(f"Gas estimate failed, fallback to {gas}: {e}")
                    
                    # If this was due to min_stake changing, re-query it
                    if "insufficient funds" in str(e).lower():
                        self.refresh_min_stake()
                        stake_wei = self.min_stake_wei

            # 6. Build tx params
            tx_params = {
                "from": self.signer.address,
                "nonce": nonce,
                "gas": gas,
                "value": stake_wei,
            }
            if gas_price_override is not None:
                tx_params["gasPrice"] = gas_price_override
            else:
                tx_params["gasPrice"] = (
                    self._default_gas_price
                    if self._default_gas_price is not None
                    else self.w3.eth.gas_price
                )

            tx = self.recorder_contract.functions.recordIntent(
                envelope_hash, cid_bytes
            ).build_transaction(tx_params)

            # 7. Sign
            try:
                signed = self.signer.sign_transaction(tx)
            except Exception as e:
                self.logger.error(f"Signing failed: {e}")
                raise TransactionError(f"Failed to sign transaction: {e}")

            # 8. Send
            try:
                if hasattr(signed, "rawTransaction"):
                    raw_bytes = signed.rawTransaction
                elif hasattr(signed, "raw_transaction"):
                    raw_bytes = signed.raw_transaction
                else:
                    raise TransactionError("Signed transaction missing raw bytes")
                tx_hash = self.w3.eth.send_raw_transaction(raw_bytes)
                self.logger.info(f"Sent intent tx: {tx_hash.hex()}")
            except Exception as e:
                self.logger.error(f"Send failed: {e}")
                if isinstance(e, Web3Exception):
                    raise
                raise TransactionError(f"Failed to send transaction: {e}")

            # 9. Receipt
            if wait_for_receipt:
                receipt = self.w3.eth.wait_for_transaction_receipt(
                    tx_hash, timeout=120, poll_latency=poll_interval or 0.1
                )
                return dict(receipt)
            else:
                # Return minimal receipt
                return {"transactionHash": "0x" + tx_hash.hex() if isinstance(tx_hash, bytes) else tx_hash}

        except (PinningError, EnvelopeError, TransactionError, Web3Exception, AlreadyRegisteredError, InactiveDIDError):
            # re-raise known exceptions including DID-specific errors
            raise
        except Exception as e:
            self.logger.error(f"Unexpected send error: {e}")
            raise TransactionError(f"Transaction failed: {e}")
    
    # No aliases - using clean API

    def tx_url(self, tx_hash: Union[str, bytes]) -> str:
        """
        Get block explorer URL for a transaction.
        
        Args:
            tx_hash: Transaction hash (hex string or bytes)
            
        Returns:
            Block explorer URL for the transaction
        """
        # Convert bytes to hex string if needed
        if isinstance(tx_hash, bytes):
            tx_hash_str = "0x" + tx_hash.hex()
        elif isinstance(tx_hash, str) and not tx_hash.startswith("0x"):
            tx_hash_str = "0x" + tx_hash
        else:
            tx_hash_str = tx_hash
            
        # Get network-specific explorer URL
        if self._network_name == "zksync-era-sepolia":
            return f"https://sepolia.explorer.zksync.io/tx/{tx_hash_str}"
        else:
            # Generic fallback for other networks
            chain_id = self._expected_chain_id or self.w3.eth.chain_id
            if chain_id == 1:
                return f"https://etherscan.io/tx/{tx_hash_str}"
            elif chain_id == 11155111:
                return f"https://sepolia.etherscan.io/tx/{tx_hash_str}"
            elif chain_id == 300:
                return f"https://sepolia.explorer.zksync.io/tx/{tx_hash_str}"
            else:
                return f"https://blockscan.com/tx/{tx_hash_str}"

    def _validate_payload(self, payload: Any) -> None:
        """
        Validate intent payload format.
        
        Args:
            payload: Payload to validate
            
        Raises:
            EnvelopeError: If payload is invalid
        """
        if not isinstance(payload, dict):
            raise EnvelopeError(
                f"Payload must be a dictionary, got {type(payload).__name__}"
            )
        if "envelope" not in payload:
            raise EnvelopeError("Payload must contain 'envelope' dictionary")
        env = payload["envelope"]
        if not isinstance(env, dict):
            raise EnvelopeError(
                f"'envelope' must be dict, got {type(env).__name__}"
            )
        required = [
            "did",
            "model_id",
            "prompt_sha256",
            "tool_id",
            "timestamp_ms",
            "stake_wei",
            "sig_ed25519",
        ]
        missing = [f for f in required if f not in env]
        if missing:
            raise EnvelopeError(
                f"Envelope missing required fields: {', '.join(missing)}"
            )

    def _sanitize_payload(self, payload: Any) -> Any:
        """
        Sanitize payload for logging (remove sensitive data).
        
        Args:
            payload: Payload to sanitize
            
        Returns:
            Sanitized payload for logging
        """
        if not isinstance(payload, dict):
            return {"type": str(type(payload))}
        safe = payload.copy()
        if "prompt" in safe:
            safe["prompt"] = f"[REDACTED - {len(str(safe['prompt']))} chars]"
        if "envelope" in safe and isinstance(safe["envelope"], dict):
            e = safe["envelope"].copy()
            if "sig_ed25519" in e:
                e["sig_ed25519"] = f"[REDACTED - {len(str(e['sig_ed25519']))} chars]"
            safe["envelope"] = e
        return safe