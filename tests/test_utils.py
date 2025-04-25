"""
Tests for utility functions.
"""
import pytest
from unittest.mock import patch
import json
import base58
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from intentlayer_sdk.utils import (
    create_envelope_hash, 
    sha256_hex, 
    create_envelope, 
    ipfs_cid_to_bytes
)

def test_sha256_hex():
    """Test SHA-256 hash calculation"""
    # Test with string
    result_str = sha256_hex("test")
    assert result_str == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
    
    # Test with bytes
    result_bytes = sha256_hex(b"test")
    assert result_bytes == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

@patch("web3.Web3.keccak")
def test_create_envelope_hash(mock_keccak):
    """Test envelope hash creation"""
    mock_keccak.return_value = b"test_hash"
    
    # Test envelope payload
    payload = {
        "did": "did:key:test",
        "model_id": "test-model",
        "prompt_sha256": "1234567890abcdef",
        "tool_id": "test-tool",
        "timestamp_ms": 1234567890,
        "stake_wei": "1000000000000000"
    }
    
    result = create_envelope_hash(payload)
    assert result == b"test_hash"
    
    # Verify canonical JSON was created correctly
    expected_json = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
    mock_keccak.assert_called_once_with(expected_json)

def test_ipfs_cid_to_bytes():
    """Test IPFS CID conversion to bytes"""
    # Test with hex format
    hex_cid = "0x1234567890abcdef"
    hex_result = ipfs_cid_to_bytes(hex_cid)
    assert hex_result == bytes.fromhex("1234567890abcdef")
    
    # Test with base58 format
    # Create a dummy base58 string
    sample_bytes = bytes.fromhex("1220a1b2c3d4e5f6")
    base58_cid = base58.b58encode(sample_bytes).decode('utf-8')
    base58_result = ipfs_cid_to_bytes(base58_cid)
    assert base58_result == sample_bytes
    
    # Test with fallback
    fallback_cid = "not-base58-or-hex"
    fallback_result = ipfs_cid_to_bytes(fallback_cid)
    assert fallback_result == b"not-base58-or-hex"

def test_create_envelope():
    """Test envelope creation"""
    # Generate a test private key
    private_key = Ed25519PrivateKey.generate()
    
    # Create envelope
    envelope = create_envelope(
        prompt="Test prompt",
        model_id="test-model",
        tool_id="test-tool",
        did="did:key:test",
        private_key=private_key,
        stake_wei=1000000000000000,
        timestamp_ms=1234567890
    )
    
    # Verify envelope fields
    assert envelope.did == "did:key:test"
    assert envelope.model_id == "test-model"
    assert envelope.prompt_sha256 == sha256_hex("Test prompt")
    assert envelope.tool_id == "test-tool"
    assert envelope.timestamp_ms == 1234567890
    assert envelope.stake_wei == "1000000000000000"
    assert envelope.sig_ed25519 is not None
    
    # Ensure signature is present and in the right format
    assert len(envelope.sig_ed25519) > 50  # Ed25519 signatures are ~86 chars in base64url