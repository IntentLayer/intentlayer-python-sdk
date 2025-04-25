"""
Utility functions for the IntentLayer SDK.
"""
import hashlib
import json
import logging
import time
import warnings
from typing import Dict, Any, Union, Optional

import base58
from web3 import Web3
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from base64 import urlsafe_b64encode

from .models import CallEnvelope
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

def create_envelope(
    prompt: str,
    model_id: str,
    tool_id: str,
    did: str,
    private_key: Ed25519PrivateKey,
    stake_wei: Union[int, str],
    timestamp_ms: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> CallEnvelope:
    """
    Create a signed call envelope
    
    Args:
        prompt: The raw user prompt
        model_id: AI model identifier
        tool_id: Tool/API identifier
        did: W3C Decentralized Identifier
        private_key: Ed25519 private key for signing
        stake_wei: Amount staked (in wei)
        timestamp_ms: Optional timestamp (defaults to current time)
        metadata: Optional metadata to include in the envelope
        
    Returns:
        Complete signed envelope
        
    Raises:
        ValueError: If any parameters are invalid
        TypeError: If any parameters have incorrect types
    """
    # Validate required parameters
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    
    if not isinstance(model_id, str) or not model_id:
        raise ValueError("model_id must be a non-empty string")
        
    if not isinstance(tool_id, str) or not tool_id:
        raise ValueError("tool_id must be a non-empty string")
        
    if not isinstance(did, str) or not did:
        raise ValueError("did must be a non-empty string")
        
    # Convert timestamp to int
    if timestamp_ms is not None:
        timestamp_ms = int(timestamp_ms)
    else:
        timestamp_ms = int(time.time() * 1000)
        
    # Convert stake_wei to string
    stake_wei_str = str(stake_wei)
    
    # Create the envelope body
    body = {
        "did": did,
        "model_id": model_id,
        "prompt_sha256": sha256_hex(prompt),
        "tool_id": tool_id,
        "timestamp_ms": timestamp_ms,
        "stake_wei": stake_wei_str,
    }
    
    # Add optional metadata if provided
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise TypeError(f"metadata must be a dictionary, got {type(metadata).__name__}")
        body["metadata"] = metadata
    
    try:
        # Sign canonical representation
        canonical_body = json.dumps(body, separators=(',', ':'), sort_keys=True).encode('utf-8')
        sig = private_key.sign(canonical_body)
        
        # Get base64 signature
        sig_b64 = urlsafe_b64encode(sig).decode("ascii").rstrip("=")
        
        # Add signature to envelope
        body["sig_ed25519"] = sig_b64
        
        # Create and return envelope model
        return CallEnvelope(**body)
    except Exception as e:
        raise EnvelopeError(f"Failed to create envelope: {str(e)}")

def ipfs_cid_to_bytes(cid: str) -> bytes:
    """
    Convert IPFS CID string to bytes for contract use
    
    Args:
        cid: IPFS CID string
        
    Returns:
        Raw bytes representation of CID
        
    Raises:
        EnvelopeError: If the CID cannot be converted to bytes
    """
    if not isinstance(cid, str):
        raise EnvelopeError(f"CID must be a string, got {type(cid).__name__}")
        
    # If already a hex string, convert directly
    if cid.startswith('0x'):
        try:
            return bytes.fromhex(cid[2:])
        except ValueError as e:
            raise EnvelopeError(f"Invalid hex CID format: {str(e)}")
        
    # Try to decode as base58
    try:
        return base58.b58decode(cid)
    except Exception as e:
        logger.warning(f"Failed to decode CID as base58: {str(e)}")
        
        # Fall back to UTF-8 bytes, but warn
        warnings.warn(
            f"CID '{cid}' is not in hex or base58 format. Falling back to UTF-8 encoding, "
            "but this may not be valid for contract interaction.",
            category=UserWarning
        )
        return cid.encode('utf-8')