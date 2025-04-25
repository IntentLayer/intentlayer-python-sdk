"""
IntentClient - Main client for the IntentLayer protocol.
"""
import json
import hashlib
import logging
import time
import urllib.parse
from typing import Dict, Any, Optional, Union, Tuple, cast, Protocol, Callable, TypeVar, Type

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from web3 import Web3
from web3.exceptions import Web3Exception
from web3.types import TxReceipt as Web3TxReceipt
from eth_account import Account
from eth_account.signers.base import BaseAccount

from .models import TxReceipt, CallEnvelope
from .exceptions import IntentLayerError, PinningError, TransactionError, EnvelopeError
from .utils import ipfs_cid_to_bytes

# Type variable for improved type hinting
T = TypeVar('T')

class Signer(Protocol):
    """Protocol for custom signers"""
    address: str
    
    def sign_transaction(self, transaction_dict: Dict[str, Any]) -> Any:
        """Sign transaction and return signed tx object"""
        ...

class IntentClient:
    """
    Client for interacting with the IntentLayer protocol.
    
    This client handles:
    1. Pinning data to IPFS
    2. Recording intents on the blockchain
    
    To use this client, you'll need:
    - An Ethereum RPC endpoint 
    - An IPFS pinner service URL
    - Either a private key or a custom signer
    - For blockchain operations: a contract address
    """
    
    # ABI for IntentRecorder contract
    INTENT_RECORDER_ABI = [
        {
            "inputs": [
                {"internalType": "bytes32", "name": "envelopeHash", "type": "bytes32"},
                {"internalType": "bytes", "name": "cid", "type": "bytes"}
            ],
            "name": "recordIntent",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "MIN_STAKE_WEI",
            "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]
    
    def __init__(
        self, 
        rpc_url: str, 
        pinner_url: str,
        min_stake_wei: int,
        priv_key: Optional[str] = None,
        signer: Optional[Signer] = None,
        contract_address: Optional[str] = None,
        retry_count: int = 3,
        timeout: int = 30,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the IntentClient
        
        Args:
            rpc_url: Ethereum RPC endpoint URL (e.g., "https://sepolia.era.zksync.dev")
            pinner_url: IPFS pinner service URL (e.g., "https://pin.myapp.com")
            min_stake_wei: Minimum stake required in wei
            priv_key: Ethereum private key (optional if signer provided)
            signer: Custom signer object (optional if priv_key provided)
            contract_address: IntentRecorder contract address (required for on-chain operations)
            retry_count: Number of retries for HTTP requests
            timeout: Timeout for HTTP requests in seconds
            logger: Optional logger instance to use for debug/info logging
            
        Raises:
            ValueError: If neither priv_key nor signer is provided
            ValueError: If the URLs don't use https (unless they're localhost/127.0.0.1)
        """
        if not priv_key and not signer:
            raise ValueError("Either priv_key or signer must be provided")
            
        # Validate URLs for security
        for url_name, url in [("rpc_url", rpc_url), ("pinner_url", pinner_url)]:
            parsed = urllib.parse.urlparse(url)
            # Check if it's a localhost or 127.0.0.1 address (with or without port)
            netloc_parts = parsed.netloc.split(':')
            host = netloc_parts[0] if netloc_parts else ''
            is_local = host in ('localhost', '127.0.0.1')
            if parsed.scheme != 'https' and not is_local:
                raise ValueError(f"{url_name} must use https:// for security (got: {parsed.scheme}://)")
            
        self.rpc_url = rpc_url
        self.pinner_url = pinner_url.rstrip('/')  # Remove trailing slash if present
        self.min_stake_wei = min_stake_wei
        self.contract_address = contract_address
        self.logger = logger or logging.getLogger(__name__)
        
        # Set up Web3
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # Setup account
        self.account: Optional[BaseAccount] = None
        self.signer = signer
        if priv_key:
            self.account = Account.from_key(priv_key)
            
        # Setup contract if address provided
        self.contract = None
        if contract_address:
            self.contract = self.w3.eth.contract(
                address=contract_address,
                abi=self.INTENT_RECORDER_ABI
            )
            
        # Setup HTTP session with retries
        self.session = requests.Session()
        retries = Retry(
            total=retry_count,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            # Also retry on connection errors
            raise_on_status=False,
            # Retry for connection errors and read timeouts
            connect=retry_count,
            read=retry_count,
            other=retry_count
        )
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.timeout = timeout
        
    @property
    def address(self) -> str:
        """
        Get the account address
        
        Returns:
            Ethereum address as string
            
        Raises:
            ValueError: If no account or signer is available
        """
        if self.account:
            return self.account.address
        elif self.signer:
            return self.signer.address
        else:
            raise ValueError("No account or signer available")
    
    def pin_to_ipfs(self, payload: Dict[str, Any]) -> str:
        """
        Submit payload to IPFS pinner service
        
        Args:
            payload: Dictionary payload to pin
            
        Returns:
            CID string from the pinner service
            
        Raises:
            PinningError: If pinning fails or returns invalid data
            ValueError: If the payload is invalid or missing required fields
        """
        # Log the request (excluding sensitive data)
        safe_payload = self._sanitize_payload(payload)
        self.logger.debug(f"Pinning payload to IPFS: {safe_payload}")
        
        # Manual implementation of retry logic
        max_retries = 3
        retry_count = 0
        backoff_factor = 0.5
        
        while True:
            try:
                response = self.session.post(
                    f"{self.pinner_url}/pin",
                    json=payload,
                    timeout=self.timeout
                )
                
                # If response is successful, process it
                if response.status_code < 500:
                    # For 4xx errors, we don't retry but raise immediately
                    response.raise_for_status()
                    
                    # Check content type before attempting JSON parsing
                    content_type = response.headers.get('Content-Type', '')
                    if 'application/json' not in content_type:
                        self.logger.warning(f"Unexpected Content-Type: {content_type} (expected application/json)")
                    
                    result = response.json()
                    self.logger.debug(f"Pinner response: {result}")
                    
                    if "cid" not in result:
                        raise PinningError(f"Missing CID in pinner response: {result}")
                    
                    return result["cid"]
                
                # For 5xx errors, retry if we have retries left
                elif retry_count < max_retries - 1:
                    retry_count += 1
                    wait_time = backoff_factor * (2 ** (retry_count - 1))
                    self.logger.warning(f"Retrying after {wait_time}s due to server error: {response.status_code}")
                    time.sleep(wait_time)
                    continue
                else:
                    # No more retries, raise the error
                    response.raise_for_status()
                
            except requests.RequestException as e:
                if isinstance(e, requests.HTTPError) and e.response.status_code >= 500 and retry_count < max_retries - 1:
                    # For 5xx errors, retry if we have retries left
                    retry_count += 1
                    wait_time = backoff_factor * (2 ** (retry_count - 1))
                    self.logger.warning(f"Retrying after {wait_time}s due to server error: {e}")
                    time.sleep(wait_time)
                    continue
                
                self.logger.error(f"IPFS pinning request failed: {e}")
                raise PinningError(f"IPFS pinning failed: {str(e)}")
            except ValueError as e:
                self.logger.error(f"Invalid JSON response from pinner: {e}")
                raise PinningError(f"Invalid JSON response from pinner: {str(e)}")
    
    def send_intent(
        self, 
        envelope_hash: str, 
        payload_dict: Dict[str, Any],
        gas: Optional[int] = None,
        gas_price_override: Optional[int] = None,
        poll_interval: Optional[float] = None,
        wait_for_receipt: bool = True
    ) -> TxReceipt:
        """
        Record intent on the blockchain
        
        Args:
            envelope_hash: Hash of the envelope (hex string with or without 0x prefix)
            payload_dict: Dictionary with the full payload data
            gas: Gas limit to use (if None, will be estimated or use default)
            gas_price_override: Gas price to use (if None, will use current network price)
            poll_interval: How often to poll for receipt (in seconds, default=0.1)
            wait_for_receipt: Whether to wait for the transaction receipt (default=True)
            
        Returns:
            Transaction receipt object
            
        Raises:
            PinningError: If IPFS pinning fails
            EnvelopeError: If envelope data is invalid
            TransactionError: If blockchain transaction fails
            ValueError: If contract address was not provided during initialization
            Web3Exception: If there's an error with Web3 operations
        """
        if not self.contract:
            raise ValueError("Contract address not provided during initialization")
            
        if not self.account and not self.signer:
            raise ValueError("Neither account nor signer is available")
            
        try:
            # Validate payload has required fields
            self._validate_payload(payload_dict)
            
            # 1. Pin the payload to IPFS
            cid = self.pin_to_ipfs(payload_dict)
            try:
                cid_bytes = ipfs_cid_to_bytes(cid)
            except Exception as e:
                raise EnvelopeError(f"Failed to convert CID to bytes: {str(e)}")
            
            # 2. Ensure envelope_hash is bytes32
            if isinstance(envelope_hash, str):
                if envelope_hash.startswith('0x'):
                    envelope_hash = envelope_hash[2:]
                try:
                    envelope_hash = bytes.fromhex(envelope_hash)
                except ValueError as e:
                    raise EnvelopeError(f"Invalid envelope hash format: {str(e)}")
            
            # 3. Prepare transaction
            from_address = self.account.address if self.account else self.signer.address
            nonce = self.w3.eth.get_transaction_count(from_address)
            
            # 4. Gas estimation if needed
            if gas is None:
                try:
                    gas = self.contract.functions.recordIntent(
                        envelope_hash,
                        cid_bytes
                    ).estimate_gas({
                        'from': from_address,
                        'value': self.min_stake_wei
                    })
                    # Add 10% buffer to gas estimate
                    gas = int(gas * 1.1)
                    self.logger.debug(f"Estimated gas: {gas}")
                except Exception as e:
                    # Fallback to default gas if estimation fails
                    gas = 300000
                    self.logger.warning(f"Gas estimation failed, using default: {gas}. Error: {e}")
            
            # 5. Build transaction
            tx_params = {
                'from': from_address,
                'nonce': nonce,
                'gas': gas,
                'value': self.min_stake_wei,
            }
            
            # Add gas price if specified
            if gas_price_override is not None:
                tx_params['gasPrice'] = gas_price_override
            else:
                tx_params['gasPrice'] = self.w3.eth.gas_price
                
            tx = self.contract.functions.recordIntent(
                envelope_hash,
                cid_bytes
            ).build_transaction(tx_params)
            
            # 6. Sign transaction
            signed_tx = None
            try:
                if self.account:
                    signed_tx = self.account.sign_transaction(tx)
                else:
                    signed_tx = self.signer.sign_transaction(tx)
            except Exception as e:
                self.logger.error(f"Transaction signing failed: {e}")
                raise TransactionError(f"Failed to sign transaction: {str(e)}")
                
            # 7. Send transaction
            try:
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                self.logger.info(f"Transaction sent: {tx_hash.hex()}")
            except Exception as e:
                self.logger.error(f"Failed to send transaction: {e}")
                if isinstance(e, Web3Exception):
                    raise  # Re-raise Web3 exceptions directly
                raise TransactionError(f"Failed to send transaction: {str(e)}")
            
            # 8. Wait for receipt if requested
            if wait_for_receipt:
                receipt = self.w3.eth.wait_for_transaction_receipt(
                    tx_hash, 
                    timeout=120,  # 2 minute timeout
                    poll_latency=poll_interval or 0.1
                )
                return self._convert_receipt(receipt)
            else:
                # Create a minimal receipt with just the transaction hash
                return TxReceipt(
                    transactionHash=tx_hash.hex() if isinstance(tx_hash, bytes) else tx_hash,
                    blockNumber=0,
                    blockHash="0x0000000000000000000000000000000000000000000000000000000000000000",
                    status=0,  # Status unknown yet
                    gasUsed=0,
                    logs=[]
                )
            
        except PinningError:
            # Re-raise pinning errors
            raise
        except EnvelopeError:
            # Re-raise envelope errors
            raise
        except Web3Exception as e:
            # Re-raise Web3 exceptions directly
            self.logger.error(f"Web3 error: {e}")
            raise
        except TransactionError:
            # Re-raise transaction errors
            raise
        except Exception as e:
            # Convert other errors to TransactionError
            self.logger.error(f"Unexpected error during send_intent: {e}")
            raise TransactionError(f"Transaction failed: {str(e)}")
            
    def _convert_receipt(self, web3_receipt: Web3TxReceipt) -> TxReceipt:
        """
        Convert Web3 receipt to our TxReceipt model
        
        Args:
            web3_receipt: The Web3 transaction receipt
            
        Returns:
            Our TxReceipt model
        """
        receipt_dict = dict(web3_receipt)
        
        # Convert bytes to hex strings
        for key, value in list(receipt_dict.items()):
            if isinstance(value, bytes):
                receipt_dict[key] = '0x' + value.hex()
                
        return TxReceipt.model_validate(receipt_dict)
        
    def _validate_payload(self, payload: Dict[str, Any]) -> None:
        """
        Validate payload has required fields
        
        Args:
            payload: Dictionary payload to validate
            
        Raises:
            EnvelopeError: If payload is missing required fields
        """
        # Ensure payload is a dictionary
        if not isinstance(payload, dict):
            raise EnvelopeError(f"Payload must be a dictionary, got {type(payload).__name__}")
            
        # Ensure envelope is present
        if 'envelope' not in payload:
            raise EnvelopeError("Payload must contain 'envelope' dictionary")
            
        # Check required envelope fields
        required_fields = ["did", "model_id", "prompt_sha256", "tool_id", "timestamp_ms", "stake_wei", "sig_ed25519"]
        envelope = payload.get('envelope', {})
        
        if not isinstance(envelope, dict):
            raise EnvelopeError(f"'envelope' must be a dictionary, got {type(envelope).__name__}")
            
        missing_fields = [field for field in required_fields if field not in envelope]
        if missing_fields:
            raise EnvelopeError(f"Envelope missing required fields: {', '.join(missing_fields)}")
    
    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive data from payload for logging
        
        Args:
            payload: Dictionary payload to sanitize
            
        Returns:
            Sanitized payload for safe logging
        """
        if not isinstance(payload, dict):
            return {"type": str(type(payload))}
            
        result = payload.copy()
        
        # Redact prompt content
        if "prompt" in result:
            result["prompt"] = f"[REDACTED - {len(str(result['prompt']))} chars]"
            
        # Sanitize envelope if present
        if "envelope" in result and isinstance(result["envelope"], dict):
            env = result["envelope"].copy()
            if "sig_ed25519" in env:
                env["sig_ed25519"] = f"[REDACTED - {len(str(env['sig_ed25519']))} chars]"
            result["envelope"] = env
            
        return result