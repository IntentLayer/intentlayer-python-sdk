"""
Tests for IPFS pinning error paths in IntentClient.
"""
import pytest
import requests
from unittest.mock import patch, MagicMock, mock_open

from intentlayer_sdk import IntentClient
from intentlayer_sdk.exceptions import PinningError
from tests.conftest import TEST_RPC_URL, TEST_PINNER_URL, TEST_CONTRACT, TEST_PRIV_KEY

def test_pin_to_ipfs_retry_on_500():
    """Test IPFS pinning retries on 500 error."""
    # Setup
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT
    )
    
    # Create mock response objects
    error_response = MagicMock(spec=requests.Response)
    error_response.status_code = 500
    
    success_response = MagicMock(spec=requests.Response)
    success_response.status_code = 200
    success_response.headers = {"Content-Type": "application/json"}
    success_response.json.return_value = {"cid": "QmTestCID"}
    success_response.raise_for_status = MagicMock(return_value=None)
    
    # Mock session.post to return error first, then success
    client.session.post = MagicMock(side_effect=[error_response, success_response])
    
    # Test
    result = client.pin_to_ipfs({"test": "data"})
    
    # Verify
    assert result == "QmTestCID"
    assert client.session.post.call_count == 2

def test_pin_to_ipfs_non_json_response():
    """Test handling of non-JSON response from IPFS pinning service."""
    # Setup
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT
    )
    
    # Create mock response
    response = MagicMock(spec=requests.Response)
    response.status_code = 200
    response.headers = {"Content-Type": "text/plain"}
    response.json.side_effect = ValueError("Invalid JSON")
    response.raise_for_status = MagicMock(return_value=None)
    
    # Mock session.post
    client.session.post = MagicMock(return_value=response)
    
    # Test
    with pytest.raises(PinningError, match="Invalid JSON from pinner"):
        client.pin_to_ipfs({"test": "data"})

def test_pin_to_ipfs_max_retries_exceeded():
    """Test behavior when maximum retries for IPFS pinning are exceeded."""
    # Setup
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT
    )
    
    # Create mock response
    error_response = MagicMock(spec=requests.Response)
    error_response.status_code = 500
    
    # Mock session.post to always return error
    client.session.post = MagicMock(return_value=error_response)
    
    # Set lower values for testing
    max_retries = 3
    
    # Test - our patched version wraps HTTPError in PinningError
    with pytest.raises(PinningError, match="IPFS pinning failed"):
        client.pin_to_ipfs({"test": "data"})
    
    # Verify called the expected number of times
    assert client.session.post.call_count == max_retries

def test_pin_to_ipfs_http_error():
    """Test handling of HTTP errors in IPFS pinning."""
    # Setup
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT
    )
    
    # Create mock response that raises HTTPError
    response = MagicMock(spec=requests.Response)
    response.status_code = 404
    http_error = requests.HTTPError("Not Found", response=response)
    response.raise_for_status = MagicMock(side_effect=http_error)
    
    # Mock session.post
    client.session.post = MagicMock(return_value=response)
    
    # Test
    with pytest.raises(PinningError, match="IPFS pinning failed"):
        client.pin_to_ipfs({"test": "data"})

def test_pin_to_ipfs_connection_error():
    """Test handling of connection errors in IPFS pinning."""
    # Setup
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT
    )
    
    # Mock session.post to raise ConnectionError
    client.session.post = MagicMock(side_effect=requests.ConnectionError("Connection refused"))
    
    # Test
    with pytest.raises(PinningError, match="IPFS pinning failed"):
        client.pin_to_ipfs({"test": "data"})

def test_pin_to_ipfs_unexpected_content_type():
    """Test handling of unexpected content type in IPFS pinning response."""
    # Setup
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT
    )
    
    # Create a logger mock to capture warnings
    mock_logger = MagicMock()
    client.logger = mock_logger
    
    # Create mock response with unexpected content type
    response = MagicMock(spec=requests.Response)
    response.status_code = 200
    response.headers = {"Content-Type": "text/plain"}
    response.json.return_value = {"cid": "QmTestCID"}
    response.raise_for_status = MagicMock(return_value=None)
    
    # Mock session.post
    client.session.post = MagicMock(return_value=response)
    
    # Test
    result = client.pin_to_ipfs({"test": "data"})
    
    # Verify
    assert result == "QmTestCID"
    mock_logger.warning.assert_called_once()
    assert "Unexpected Content-Type" in mock_logger.warning.call_args[0][0]