"""
Tests for the assert_chain_id method in IntentClient.
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from intentlayer_sdk import IntentClient
from intentlayer_sdk.exceptions import NetworkError
from tests.conftest import TEST_RPC_URL, TEST_PINNER_URL, TEST_CONTRACT, TEST_PRIV_KEY

@pytest.mark.parametrize(
    "expected_chain_id, actual_chain_id, test_id, expected_result", 
    [
        (None, None, "no_expected_id", "warning"),
        (11155111, 11155111, "matching", "pass"),
        (11155111, 1, "mismatch", "error")
    ]
)
def test_assert_chain_id(expected_chain_id, actual_chain_id, test_id, expected_result):
    """Test assert_chain_id with different chain ID scenarios."""
    # Setup
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT,
        expected_chain_id=expected_chain_id
    )
    
    # Create a logger mock to capture warnings if needed
    mock_logger = MagicMock()
    client.logger = mock_logger
    
    # Mock web3 instance if needed
    if actual_chain_id is not None:
        mock_w3 = MagicMock()
        mock_w3.eth.chain_id = actual_chain_id
        client.w3 = mock_w3
    
    # Set network name for error case
    if test_id == "mismatch":
        client._network_name = "test-network"
    
    # Test
    if expected_result == "warning":
        client.assert_chain_id()
        mock_logger.warning.assert_called_once()
        assert "No expected chain ID set" in mock_logger.warning.call_args[0][0]
    elif expected_result == "pass":
        # Should not raise an exception
        client.assert_chain_id()
    elif expected_result == "error":
        with pytest.raises(NetworkError, match="Chain ID mismatch"):
            client.assert_chain_id()

def test_assert_chain_id_w3_error():
    """Test assert_chain_id when web3 call raises an exception."""
    # Setup
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT,
        expected_chain_id=11155111
    )
    
    # Mock web3 instance that raises an exception
    mock_w3 = MagicMock()
    # Ensure the chain_id property actually raises the exception when accessed
    type(mock_w3.eth).chain_id = PropertyMock(side_effect=Exception("RPC error"))
    client.w3 = mock_w3
    
    # Test
    with pytest.raises(NetworkError, match="Failed to validate chain ID"):
        client.assert_chain_id()