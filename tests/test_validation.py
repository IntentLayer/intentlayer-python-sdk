"""
Tests for payload validation and edge cases.
"""
import pytest
import requests_mock
from unittest.mock import patch, MagicMock

from intentlayer_sdk import IntentClient
from intentlayer_sdk.exceptions import EnvelopeError, PinningError
from intentlayer_sdk.signer.local import LocalSigner
from tests.test_helpers import create_test_client, TEST_RPC_URL, TEST_PINNER_URL, TEST_STAKE_WEI, TEST_PRIV_KEY, TEST_CONTRACT

@patch('intentlayer_sdk.client.Web3', autospec=True)
def test_missing_envelope(MockWeb3, mock_w3, mock_account):
    """Test validation of payload missing envelope"""
    # Setup mocks
    MockWeb3.return_value = mock_w3
    
    # Setup client
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=TEST_STAKE_WEI,
        priv_key=mock_account.key.hex(),
        recorder_address=TEST_CONTRACT
    )
    
    # Test with payload missing envelope
    envelope_hash = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    payload_missing_envelope = {
        "prompt": "Test prompt",
        "metadata": {"user": "test"}
    }
    
    with pytest.raises(EnvelopeError, match="must contain 'envelope' dictionary"):
        client.send_intent(envelope_hash, payload_missing_envelope)

@patch('intentlayer_sdk.client.Web3', autospec=True)
def test_missing_envelope_fields(MockWeb3, mock_w3, mock_account):
    """Test validation of envelope missing required fields"""
    # Setup mocks
    MockWeb3.return_value = mock_w3
    
    # Setup client
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=TEST_STAKE_WEI,
        priv_key=mock_account.key.hex(),
        recorder_address=TEST_CONTRACT
    )
    
    # Test with envelope missing required fields
    envelope_hash = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    payload_incomplete_envelope = {
        "prompt": "Test prompt",
        "envelope": {
            "did": "did:key:test",
            "model_id": "test-model"
            # Missing required fields
        }
    }
    
    with pytest.raises(EnvelopeError, match="Envelope missing required fields"):
        client.send_intent(envelope_hash, payload_incomplete_envelope)

@patch('intentlayer_sdk.client.Web3', autospec=True)
def test_invalid_envelope_hash(MockWeb3, mock_w3, mock_account, test_payload, requests_mock):
    """Test validation of invalid envelope hash format"""
    # Setup mocks
    MockWeb3.return_value = mock_w3
    
    # Mock the pinner service to prevent real HTTP requests
    requests_mock.post(
        "https://pin.example.com/pin",
        json={"cid": "QmExample123456789"},
        status_code=200
    )
    
    # Setup client
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=TEST_STAKE_WEI,
        priv_key=mock_account.key.hex(),
        recorder_address=TEST_CONTRACT
    )
    
    # Test with invalid envelope hash
    invalid_hash = "0xNOTAVALIDHEX"
    
    with pytest.raises(EnvelopeError, match="Invalid envelope hash format"):
        client.send_intent(invalid_hash, test_payload)

def test_malformed_payload():
    """Test validation of non-dictionary payload"""
    # Setup client
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=TEST_STAKE_WEI,
        priv_key=TEST_PRIV_KEY,
        recorder_address=TEST_CONTRACT
    )
    
    # Test with non-dictionary payload
    envelope_hash = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    
    with pytest.raises(EnvelopeError, match="Payload must be a dictionary"):
        client.send_intent(envelope_hash, "not a dictionary")

def test_url_validation():
    """Test URL validation for security"""
    # Test with non-HTTPS URL
    with pytest.raises(ValueError, match="must use https://"):
        create_test_client(
            rpc_url="http://rpc.example.com",  # HTTP not HTTPS
            pinner_url="https://pin.example.com",
            min_stake_wei=TEST_STAKE_WEI,
            priv_key=TEST_PRIV_KEY,
            recorder_address=TEST_CONTRACT
        )
    
    # Local URLs should be allowed
    client = create_test_client(
        rpc_url="http://localhost:8545",
        pinner_url="http://127.0.0.1:5000",
        min_stake_wei=TEST_STAKE_WEI,
        priv_key=TEST_PRIV_KEY,
        recorder_address=TEST_CONTRACT
    )
    assert client.rpc_url == "http://localhost:8545"
    assert client.pinner_url == "http://127.0.0.1:5000"

def test_pinner_retry(requests_mock):
    """Test that pinner retries on intermittent failures"""
    # Setup client
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=TEST_STAKE_WEI,
        priv_key=TEST_PRIV_KEY,
        recorder_address=TEST_CONTRACT
    )
    
    # Setup a counter to track request attempts
    request_count = 0
    
    def request_callback(request, context):
        nonlocal request_count
        request_count += 1
        # First and second requests fail, third succeeds
        if request_count < 3:
            context.status_code = 500
            return {"error": "Server error"}
        else:
            context.status_code = 200
            return {"cid": "QmExample123456789"}
    
    # Register the mock with the callback
    requests_mock.post("https://pin.example.com/pin", json=request_callback)
    
    # Should succeed after retries
    cid = client.pin_to_ipfs({"test": "data"})
    
    # Verify
    assert cid == "QmExample123456789"
    assert request_count == 3  # Verify it took 3 attempts

def test_content_type_warning(requests_mock):
    """Test handling of unexpected content types"""
    # Setup client
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=TEST_STAKE_WEI,
        priv_key=TEST_PRIV_KEY,
        recorder_address=TEST_CONTRACT
    )
    
    # Setup mock with non-JSON content type but JSON response
    requests_mock.post(
        "https://pin.example.com/pin",
        json={"cid": "QmExample123456789"},
        headers={"Content-Type": "text/plain"},  # Wrong content type
        status_code=200
    )
    
    # Should still work but log a warning (which we can't easily test)
    cid = client.pin_to_ipfs({"test": "data"})
    assert cid == "QmExample123456789"