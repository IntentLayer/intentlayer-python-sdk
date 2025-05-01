"""
Utility functions for the IntentLayer SDK.
"""
import hashlib
import json
import logging
import os
import warnings
from typing import Dict, Any, Union, Optional

import base58
from web3 import Web3

from .exceptions import EnvelopeError

# Setup logger
logger = logging.getLogger(__name__)

def create_envelope_hash(payload: Dict[str, Any]) -> bytes:
    """
    Create deterministic hash of envelope payload
    
    Args:
        payload: Dictionary with envelope data
        
    Returns:
        bytes32 hash of the envelope
        
    Raises:
        TypeError: If payload is not a dictionary
        ValueError: If the payload cannot be serialized to JSON
    """
    if not isinstance(payload, dict):
        raise TypeError(f"Payload must be a dictionary, got {type(payload).__name__}")
        
    try:
        # Sort keys and remove whitespace for deterministic representation
        canonical_json = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
        return Web3.keccak(canonical_json)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Failed to serialize payload to JSON: {str(e)}")

def sha256_hex(data: Union[bytes, str]) -> str:
    """
    Return hex-encoded SHA-256 hash of bytes/str
    
    Args:
        data: Input data as bytes or string
        
    Returns:
        Hex-encoded SHA-256 hash
        
    Raises:
        TypeError: If data is neither bytes nor string
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    elif not isinstance(data, bytes):
        raise TypeError(f"Expected bytes or string, got {type(data).__name__}")
        
    return hashlib.sha256(data).hexdigest()

def ipfs_cid_to_bytes(cid: str, allow_utf8_fallback: bool = False, max_bytes: int = 32) -> bytes:
    """
    Convert IPFS CID string to bytes for contract use
    
    Args:
        cid: IPFS CID string
        allow_utf8_fallback: Whether to allow fallback to UTF-8 encoding if base58 fails
        max_bytes: Maximum allowed length of the resulting bytes (defaults to 32 for Solidity bytes32)
        
    Returns:
        Raw bytes representation of CID
        
    Notes:
        - If the resulting bytes are longer than max_bytes (default: 32), 
          they will be truncated to fit Solidity's bytes32 constraint.
        - Truncation is lossy - the original CID can't be fully reconstructed from truncated bytes.
        - A warning is emitted when truncation occurs.
        
    Raises:
        EnvelopeError: If the CID cannot be converted to bytes
    """
    if not isinstance(cid, str):
        raise EnvelopeError(f"CID must be a string, got {type(cid).__name__}")
    
    # If already a hex string, convert directly
    if cid.startswith('0x'):
        try:
            result = bytes.fromhex(cid[2:])
        except ValueError as e:
            raise EnvelopeError(f"Invalid hex CID format: {str(e)}")
    else:
        # Try to decode as base58
        try:
            result = base58.b58decode(cid)
        except Exception as e:
            logger.warning(f"Failed to decode CID as base58: {str(e)}")
            
            # Only fall back to UTF-8 if explicitly allowed
            if allow_utf8_fallback:
                warnings.warn(
                    f"CID '{cid}' is not in hex or base58 format. Falling back to UTF-8 encoding, "
                    "but this may not be valid for contract interaction.",
                    category=UserWarning
                )
                result = cid.encode('utf-8')
            else:
                raise EnvelopeError(
                    f"Failed to decode CID '{cid}' as base58: {str(e)}. "
                    "Set allow_utf8_fallback=True to enable UTF-8 fallback (not recommended)."
                )
                
    # Verify and truncate to max_bytes if necessary
    if len(result) > max_bytes:
        warnings.warn(
            f"CID byte length ({len(result)}) exceeds maximum ({max_bytes}). "
            "Truncating to prevent contract reversion."
        )
        return result[:max_bytes]
    
    return result


def get_auto_did_enabled(override: Optional[bool] = None) -> bool:
    """
    Check if the AUTO-DID feature is enabled.
    
    Args:
        override: Override value for the AUTO-DID setting
        
    Returns:
        True if AUTO-DID is enabled, False otherwise
    """
    # First check for explicit override
    if override is not None:
        return override
        
    # Then check environment variable
    auto_did_env = os.environ.get("INTENT_AUTO_DID", "").lower()
    if auto_did_env in ("false", "0", "no"):
        return False
    if auto_did_env in ("true", "1", "yes"):
        return True
        
    # Default to True (auto-DID enabled)
    return True