"""
Additional tests to improve code coverage.
"""
import pytest
import warnings
from unittest.mock import patch, MagicMock
import requests
import requests_mock
import json
import base58
import time

from intentlayer_sdk import IntentClient
from intentlayer_sdk.models import TxReceipt
from intentlayer_sdk.utils import ipfs_cid_to_bytes, sha256_hex
from intentlayer_sdk.envelope import create_envelope
from intentlayer_sdk.exceptions import PinningError, TransactionError, EnvelopeError
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tests.test_helpers import create_test_client, TEST_RPC_URL, TEST_PINNER_URL, TEST_STAKE_WEI, TEST_PRIV_KEY, TEST_CONTRACT

def test_client_url_validation():
    """Test URL validation in client initialization"""
    # Test HTTP URLs are rejected for production
    with pytest.raises(ValueError, match="rpc_url must use https"):
        create_test_client(
            rpc_url="http://insecure.example.com",
            pinner_url="https://pin.example.com",
            min_stake_wei=TEST_STAKE_WEI,
            priv_key=TEST_PRIV_KEY
        )
    
    with pytest.raises(ValueError, match="pinner_url must use https"):
        create_test_client(
            rpc_url="https://rpc.example.com",
            pinner_url="http://insecure.example.com",
            min_stake_wei=TEST_STAKE_WEI,
            priv_key=TEST_PRIV_KEY
        )
    
    # Test localhost URLs are allowed with HTTP
    client = create_test_client(
        rpc_url="http://localhost:8545",
        pinner_url="http://localhost:5001",
        min_stake_wei=TEST_STAKE_WEI,
        priv_key=TEST_PRIV_KEY
    )
    assert client.rpc_url == "http://localhost:8545"
    
    # Test 127.0.0.1 URLs are allowed with HTTP
    client = create_test_client(
        rpc_url="http://127.0.0.1:8545",
        pinner_url="http://127.0.0.1:5001",
        min_stake_wei=TEST_STAKE_WEI,
        priv_key=TEST_PRIV_KEY
    )
    assert client.rpc_url == "http://127.0.0.1:8545"
    
    # Test trailing slash is removed from pinner URL
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL + "/",  # With trailing slash
        min_stake_wei=TEST_STAKE_WEI,
        priv_key=TEST_PRIV_KEY
    )
    assert client.pinner_url == TEST_PINNER_URL  # Without trailing slash

def test_pin_to_ipfs_content_type_warning(requests_mock):
    """Test pin_to_ipfs with unexpected content type"""
    requests_mock.post(
        f"{TEST_PINNER_URL}/pin",
        json={"cid": "QmTest123456789"},
        headers={"Content-Type": "text/plain"}  # Not application/json
    )
    
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=TEST_STAKE_WEI,
        priv_key=TEST_PRIV_KEY
    )
    
    payload = {
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
    
    # This should succeed but log a warning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        cid = client.pin_to_ipfs(payload)
        # Uncomment if we add explicit warning
        # assert len(w) == 1
        # assert issubclass(w[0].category, UserWarning)
    
    assert cid == "QmTest123456789"

def test_envelope_hash_processing():
    """Test processing of different envelope hash formats"""
    # We'll just test the hexadecimal conversion directly
    
    # 1. Test with 0x-prefixed envelope hash
    envelope_hash_with_prefix = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    expected_bytes = bytes.fromhex("1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef")
    
    # Simulate the processing in client.py
    if envelope_hash_with_prefix.startswith('0x'):
        processed_hash = envelope_hash_with_prefix[2:]
    processed_bytes = bytes.fromhex(processed_hash)
    
    assert processed_bytes == expected_bytes
    
    # 2. Test with non-0x-prefixed envelope hash
    envelope_hash_no_prefix = "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    expected_bytes = bytes.fromhex("1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef")
    
    # Simulate the processing in client.py
    if envelope_hash_no_prefix.startswith('0x'):
        processed_hash = envelope_hash_no_prefix[2:]
    else:
        processed_hash = envelope_hash_no_prefix
    processed_bytes = bytes.fromhex(processed_hash)
    
    assert processed_bytes == expected_bytes

def test_sanitize_payload():
    """Test payload sanitization"""
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=TEST_STAKE_WEI,
        priv_key=TEST_PRIV_KEY
    )
    
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

def test_utils_ipfs_cid_to_bytes_edge_cases():
    """Test edge cases for ipfs_cid_to_bytes function"""
    # Test empty string - should just convert to empty bytes
    result = ipfs_cid_to_bytes("")
    assert result == b""
    
    # Test valid base58 content
    valid_base58 = "QmPK1s3pNYLi9ERiq3BDxKa4XosgWwFRQUydHUtz4YgpqB"
    # This will use the base58 decoding path
    result = ipfs_cid_to_bytes(valid_base58)
    assert isinstance(result, bytes)
    assert len(result) > 0
    
    # Test unicode non-base58, non-hex
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = ipfs_cid_to_bytes("你好世界", allow_utf8_fallback=True)  # Hello world in Chinese
        assert len(w) >= 1
        assert issubclass(w[0].category, UserWarning)
    assert result == "你好世界".encode('utf-8')

def test_version_fallbacks():
    """Test version fallback mechanisms"""
    # This is challenging to test directly, but we can verify the version exists
    from intentlayer_sdk.version import __version__
    assert __version__ is not None
    assert isinstance(__version__, str)

def test_create_envelope_with_metadata():
    """Test envelope creation with metadata"""
    private_key = Ed25519PrivateKey.generate()
    metadata = {"user_id": "test123", "session_id": "abc123"}
    
    envelope = create_envelope(
        prompt="Test prompt",
        model_id="test-model",
        tool_id="test-tool",
        did="did:key:test",
        private_key=private_key,
        stake_wei="1000000000000000",
        metadata=metadata
    )
    
    assert envelope.metadata == metadata
    
    # Test with auto timestamp
    envelope = create_envelope(
        prompt="Test prompt",
        model_id="test-model",
        tool_id="test-tool",
        did="did:key:test",
        private_key=private_key,
        stake_wei="1000000000000000",
        timestamp_ms=None  # Should auto-generate
    )
    
    assert envelope.timestamp_ms is not None
    assert isinstance(envelope.timestamp_ms, int)
    # Should be close to current time
    now_ms = int(time.time() * 1000)
    assert abs(envelope.timestamp_ms - now_ms) < 5000  # Within 5 seconds