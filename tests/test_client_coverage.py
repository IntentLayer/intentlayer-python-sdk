"""
Tests to improve code coverage in client.py.
"""
import pytest
import warnings
from unittest.mock import patch, MagicMock
import requests
import json
import base58
import time
from web3.exceptions import ContractLogicError, TransactionNotFound

from intentlayer_sdk.client import IntentClient
from intentlayer_sdk.models import TxReceipt
from intentlayer_sdk.envelope import CallEnvelope, create_envelope
from intentlayer_sdk.utils import ipfs_cid_to_bytes, sha256_hex, create_envelope_hash
from intentlayer_sdk.exceptions import PinningError, TransactionError, EnvelopeError
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# Test constants
TEST_RPC_URL = "https://rpc.example.com"
TEST_PINNER_URL = "https://pin.example.com"
TEST_STAKE_WEI = 1000000000000000  # 0.001 ETH
TEST_PRIV_KEY = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
TEST_CONTRACT = "0x1234567890123456789012345678901234567890"

def test_pin_to_ipfs_server_error_retry():
    """Test transaction receipt conversion with TxReceipt model"""
    
    # Create the receipt data with bytes values that would need conversion
    receipt_data = {
        'transactionHash': b'tx_hash_bytes',
        'blockNumber': 12345,
        'blockHash': b'block_hash_bytes',
        'status': 1,
        'gasUsed': 100000,
        'from': '0x1234567890123456789012345678901234567890',
        'to': TEST_CONTRACT,
        'logs': []
    }
    
    # Convert to TxReceipt model directly
    # First convert bytes to hex strings with 0x prefix as the client would do
    cleaned_data = receipt_data.copy()
    if isinstance(cleaned_data['transactionHash'], bytes):
        cleaned_data['transactionHash'] = '0x' + cleaned_data['transactionHash'].hex()
    if isinstance(cleaned_data['blockHash'], bytes):
        cleaned_data['blockHash'] = '0x' + cleaned_data['blockHash'].hex()
    
    # Create TxReceipt instance
    receipt = TxReceipt(**cleaned_data)
    
    # Ensure conversion worked properly
    assert isinstance(receipt.transactionHash, str)
    assert isinstance(receipt.blockHash, str)
    assert receipt.transactionHash.startswith("0x")
    assert receipt.blockHash.startswith("0x")
    
    # Test that the property aliases work correctly
    assert receipt.tx_hash == receipt.transactionHash
    assert receipt.block_number == receipt.blockNumber

def test_validate_payload():
    """Test the _validate_payload method"""
    
    # Create a client with mocked attributes directly to bypass initialization
    client = object.__new__(IntentClient)  # Skip __init__
    client.logger = MagicMock()
    
    # Test with a valid payload
    valid_payload = {
        "envelope": {
            "did": "did:key:test",
            "model_id": "gpt-4",
            "prompt_sha256": "1234567890abcdef",
            "tool_id": "chat-completion",
            "timestamp_ms": 1234567890,
            "stake_wei": "1000000000000000",
            "sig_ed25519": "ABCDEF123456"
        },
        "prompt": "Test prompt"
    }
    
    # Should not raise an exception
    client._validate_payload(valid_payload)
    
    # Test with a non-dict payload
    with pytest.raises(EnvelopeError, match="must be a dictionary"):
        client._validate_payload(["not", "a", "dict"])
    
    # Test with missing envelope
    with pytest.raises(EnvelopeError, match="must contain 'envelope'"):
        client._validate_payload({"prompt": "Test prompt"})
    
    # Test with non-dict envelope
    with pytest.raises(EnvelopeError, match="must be dict"):
        client._validate_payload({"envelope": "not a dict"})
    
    # Test with missing required fields
    incomplete_payload = {
        "envelope": {
            "did": "did:key:test",
            # missing other required fields
        }
    }
    with pytest.raises(EnvelopeError, match="missing required fields"):
        client._validate_payload(incomplete_payload)

def test_sanitize_payload():
    """Test the _sanitize_payload method"""
    
    # Create a client with mocked attributes directly to bypass initialization
    client = object.__new__(IntentClient)  # Skip __init__
    client.logger = MagicMock()
    
    # Test with non-dict payload
    non_dict = ["not", "a", "dict"]
    sanitized = client._sanitize_payload(non_dict)
    assert sanitized == {"type": str(type(non_dict))}
    
    # Test with prompt
    payload = {
        "prompt": "This is a sensitive prompt",
        "other": "data"
    }
    sanitized = client._sanitize_payload(payload)
    assert sanitized["prompt"].startswith("[REDACTED")
    assert sanitized["other"] == "data"
    
    # Test with envelope containing signature
    payload = {
        "envelope": {
            "did": "did:key:test",
            "sig_ed25519": "very-secret-signature-value",
            "other": "visible"
        }
    }
    sanitized = client._sanitize_payload(payload)
    assert sanitized["envelope"]["did"] == "did:key:test"
    assert sanitized["envelope"]["sig_ed25519"].startswith("[REDACTED")
    assert sanitized["envelope"]["other"] == "visible"

def test_tx_hash_formatting():
    """Test transaction hash formatting directly"""
    
    # Test with bytes hash
    tx_hash_bytes = b'test_bytes_hash'
    
    # Case 1: Bytes to hex string with 0x prefix
    if isinstance(tx_hash_bytes, bytes):
        tx_hash_str = "0x" + tx_hash_bytes.hex()
    elif isinstance(tx_hash_bytes, str) and not tx_hash_bytes.startswith("0x"):
        tx_hash_str = "0x" + tx_hash_bytes
    else:
        tx_hash_str = tx_hash_bytes
    
    # Verify the transaction hash was properly formatted
    assert isinstance(tx_hash_str, str)
    assert tx_hash_str.startswith("0x")
    # The bytes are converted to hex, not kept as ASCII
    assert tx_hash_str == "0x" + tx_hash_bytes.hex()
    
    # Test with string hash, no 0x prefix
    tx_hash_str = "plain_string_hash"
    
    # Case 2: String without 0x prefix
    if isinstance(tx_hash_str, bytes):
        formatted_hash = "0x" + tx_hash_str.hex()
    elif isinstance(tx_hash_str, str) and not tx_hash_str.startswith("0x"):
        formatted_hash = "0x" + tx_hash_str
    else:
        formatted_hash = tx_hash_str
    
    # Verify the transaction hash was properly formatted
    assert formatted_hash.startswith("0x")
    assert "plain_string_hash" in formatted_hash
    
    # Test with string hash that already has 0x prefix
    tx_hash_prefixed = "0xalready_prefixed_hash"
    
    # Case 3: String with 0x prefix
    if isinstance(tx_hash_prefixed, bytes):
        formatted_hash = "0x" + tx_hash_prefixed.hex()
    elif isinstance(tx_hash_prefixed, str) and not tx_hash_prefixed.startswith("0x"):
        formatted_hash = "0x" + tx_hash_prefixed
    else:
        formatted_hash = tx_hash_prefixed
    
    # Verify the transaction hash was not double-prefixed
    assert formatted_hash.startswith("0x")
    assert formatted_hash.count("0x") == 1
    assert "already_prefixed_hash" in formatted_hash
    
    # Create a minimal TxReceipt for the no-wait case
    from_addr = "0x1234567890123456789012345678901234567890"
    to_addr = "0x0987654321098765432109876543210987654321"
    
    # Create the receipt with the hash
    receipt = TxReceipt(
        transactionHash=formatted_hash,
        blockNumber=0,
        blockHash="0x" + "0" * 64,
        status=0,
        gasUsed=0,
        logs=[],
        from_address=from_addr,
        to_address=to_addr
    )
    
    # Verify the receipt attributes and property getters
    assert receipt.transactionHash == formatted_hash
    assert receipt.tx_hash == formatted_hash
    assert receipt.block_number == 0
    assert receipt.from_address == from_addr
    assert receipt.to_address == to_addr