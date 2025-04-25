"""
Envelope models and utilities for the IntentLayer SDK.
"""
import hashlib
import json
import time
from typing import Dict, Any, Optional, Union

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, Field, field_validator
from base64 import urlsafe_b64encode
from web3 import Web3

class CallEnvelope(BaseModel):
    """
    CallEnvelope represents a signed intent to make an API call.
    
    This is the standardized format used for recording intents on-chain.
    """
    did: str
    model_id: str
    prompt_sha256: str
    tool_id: str
    timestamp_ms: int
    stake_wei: str
    sig_ed25519: str
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator('did')
    @classmethod
    def validate_did(cls, v: str) -> str:
        """Validate DID format"""
        if not v.startswith("did:"):
            raise ValueError("DID must start with 'did:'")
        return v
    
    @field_validator('prompt_sha256')
    @classmethod
    def validate_prompt_hash(cls, v: str) -> str:
        """Validate prompt hash format"""
        if len(v) != 64:
            raise ValueError("prompt_sha256 must be a 64-character hex string")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("prompt_sha256 must be a hex string")
        return v
    
    def hash(self) -> bytes:
        """
        Generate the envelope hash used for on-chain recording.
        
        Returns:
            bytes32 keccak hash of the canonical envelope representation
        """
        # Create a copy without the signature
        envelope_dict = self.model_dump(exclude={"sig_ed25519"})
        
        # Sort keys and remove whitespace for deterministic representation
        canonical_json = json.dumps(envelope_dict, separators=(',', ':'), sort_keys=True).encode('utf-8')
        return Web3.keccak(canonical_json)
    
    def hex_hash(self) -> str:
        """
        Generate the envelope hash as a hex string.
        
        Returns:
            0x-prefixed hex string of the envelope hash
        """
        return "0x" + self.hash().hex()


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
    Create a signed call envelope.
    
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
    
    # Generate prompt hash
    prompt_sha256 = hashlib.sha256(
        prompt.encode("utf-8") if isinstance(prompt, str) else prompt
    ).hexdigest()
    
    # Set timestamp if not provided
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    
    # Convert stake_wei to string
    stake_wei_str = str(stake_wei)
    
    # Create envelope without signature
    envelope_data = {
        "did": did,
        "model_id": model_id,
        "prompt_sha256": prompt_sha256,
        "tool_id": tool_id,
        "timestamp_ms": timestamp_ms,
        "stake_wei": stake_wei_str,
    }
    
    # Add metadata if provided
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise TypeError(f"metadata must be a dictionary, got {type(metadata).__name__}")
        envelope_data["metadata"] = metadata
    
    # Create canonical representation
    canonical = json.dumps(envelope_data, separators=(',', ':'), sort_keys=True).encode('utf-8')
    
    # Sign the canonical representation
    signature = private_key.sign(canonical)
    
    # Convert signature to URL-safe base64
    sig_b64 = urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    
    # Add signature to the envelope
    envelope_data["sig_ed25519"] = sig_b64
    
    # Create and return the envelope
    return CallEnvelope(**envelope_data)