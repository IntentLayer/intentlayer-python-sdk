"""
IntentClient - Main client for the IntentLayer protocol.
"""
import json
import hashlib
import logging
import time
import urllib.parse
from typing import Dict, Any, Optional, Protocol

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from web3 import Web3
from web3.exceptions import Web3Exception
from web3.types import TxReceipt as Web3TxReceipt
from eth_account import Account
from eth_account.signers.base import BaseAccount

from .models import TxReceipt, CallEnvelope
from .exceptions import PinningError, TransactionError, EnvelopeError
from .utils import ipfs_cid_to_bytes

# Protocol for a custom signer
class Signer(Protocol):
    address: str
    def sign_transaction(self, transaction_dict: Dict[str, Any]) -> Any:
        ...

class IntentClient:
    """
    Client for interacting with the IntentLayer protocol.
    Handles IPFS pinning and on-chain intent recording.
    """

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
        logger: Optional[logging.Logger] = None,
    ):
        if not priv_key and not signer:
            raise ValueError("Either priv_key or signer must be provided")

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
        self.min_stake_wei = min_stake_wei
        self.contract_address = contract_address
        self.logger = logger or logging.getLogger(__name__)

        # Web3 setup and cache the first gas price
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        try:
            self._default_gas_price = self.w3.eth.gas_price
        except Exception:
            self._default_gas_price = None

        # Account or custom signer
        self.account: Optional[BaseAccount] = None
        self.signer = signer
        if priv_key:
            self.account = Account.from_key(priv_key)

        # Contract binding
        self.contract = None
        if contract_address:
            self.contract = self.w3.eth.contract(
                address=contract_address, abi=self.INTENT_RECORDER_ABI
            )

        # HTTP session with retry logic
        self.session = requests.Session()
        retries = Retry(
            total=retry_count,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
            connect=retry_count,
            read=retry_count,
            other=retry_count,
        )
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.timeout = timeout

    @property
    def address(self) -> str:
        if self.account:
            return self.account.address
        if self.signer:
            return self.signer.address
        raise ValueError("No account or signer available")

    def pin_to_ipfs(self, payload: Dict[str, Any]) -> str:
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
        envelope_hash: str,
        payload_dict: Dict[str, Any],
        gas: Optional[int] = None,
        gas_price_override: Optional[int] = None,
        poll_interval: Optional[float] = None,
        wait_for_receipt: bool = True,
    ) -> TxReceipt:
        if not self.contract:
            raise ValueError("Contract address not provided during initialization")
        if not self.account and not self.signer:
            raise ValueError("Neither account nor signer is available")

        try:
            # 1. Validate payload
            self._validate_payload(payload_dict)

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

            # 3. Pin to IPFS
            cid = self.pin_to_ipfs(payload_dict)
            try:
                cid_bytes = ipfs_cid_to_bytes(cid)
            except Exception as e:
                raise EnvelopeError(f"Failed to convert CID: {e}")

            # 4. Nonce & from
            from_addr = self.account.address if self.account else self.signer.address
            nonce = self.w3.eth.get_transaction_count(from_addr)

            # 5. Gas estimate
            if gas is None:
                try:
                    est = (
                        self.contract.functions.recordIntent(
                            envelope_hash, cid_bytes
                        )
                        .estimate_gas(
                            {"from": from_addr, "value": self.min_stake_wei}
                        )
                    )
                    gas = int(est * 1.1)
                    self.logger.debug(f"Estimated gas: {gas}")
                except Exception as e:
                    gas = 300_000
                    self.logger.warning(f"Gas estimate failed, fallback to {gas}: {e}")

            # 6. Build tx params
            tx_params = {
                "from": from_addr,
                "nonce": nonce,
                "gas": gas,
                "value": self.min_stake_wei,
            }
            if gas_price_override is not None:
                tx_params["gasPrice"] = gas_price_override
            else:
                tx_params["gasPrice"] = (
                    self._default_gas_price
                    if self._default_gas_price is not None
                    else self.w3.eth.gas_price
                )

            tx = self.contract.functions.recordIntent(
                envelope_hash, cid_bytes
            ).build_transaction(tx_params)

            # 7. Sign
            try:
                signed = (
                    self.account.sign_transaction(tx)
                    if self.account
                    else self.signer.sign_transaction(tx)
                )
            except Exception as e:
                self.logger.error(f"Signing failed: {e}")
                raise TransactionError(f"Failed to sign transaction: {e}")

            # 8. Send — check CamelCase first, then snake_case
            try:
                if hasattr(signed, "rawTransaction"):
                    raw_bytes = signed.rawTransaction
                elif hasattr(signed, "raw_transaction"):
                    raw_bytes = signed.raw_transaction
                else:
                    raise TransactionError("Signed transaction missing raw bytes")
                tx_hash = self.w3.eth.send_raw_transaction(raw_bytes)
                self.logger.info(f"Sent tx: {tx_hash.hex()}")
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
                return self._convert_receipt(receipt)
            else:
                # Ensure tx_hash is a properly formatted hex string with 0x prefix
                if isinstance(tx_hash, bytes):
                    tx_hash_str = "0x" + tx_hash.hex()
                elif isinstance(tx_hash, str) and not tx_hash.startswith("0x"):
                    tx_hash_str = "0x" + tx_hash
                else:
                    tx_hash_str = tx_hash
                    
                return TxReceipt(
                    transactionHash=tx_hash_str,
                    blockNumber=0,
                    blockHash="0x" + "0" * 64,
                    status=0,
                    gasUsed=0,
                    logs=[],
                    from_address=from_addr,
                    to_address=self.contract_address if hasattr(self, 'contract_address') else ""
                )

        except (PinningError, EnvelopeError, TransactionError, Web3Exception):
            # re-raise known exceptions
            raise
        except Exception as e:
            self.logger.error(f"Unexpected send error: {e}")
            raise TransactionError(f"Transaction failed: {e}")

    def _convert_receipt(self, web3_receipt: Web3TxReceipt) -> TxReceipt:
        rd = dict(web3_receipt)
        for k, v in list(rd.items()):
            if isinstance(v, bytes):
                rd[k] = "0x" + v.hex()
                
        # Ensure required fields exist
        if 'from' not in rd and hasattr(self, 'address'):
            rd['from'] = self.address
        if 'to' not in rd and hasattr(self, 'contract_address'):
            rd['to'] = self.contract_address
            
        return TxReceipt.model_validate(rd)

    def _validate_payload(self, payload: Any) -> None:
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
