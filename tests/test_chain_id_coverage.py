"""
Tests for the assert_chain_id method in IntentClient.
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from intentlayer_sdk import IntentClient
from intentlayer_sdk.exceptions import NetworkError
from tests.conftest import TEST_RPC_URL, TEST_PINNER_URL, TEST_CONTRACT, TEST_PRIV_KEY

def test_assert_chain_id_no_expected_id():
    """Test assert_chain_id when no expected chain ID is set."""
    # Setup
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT,
        expected_chain_id=None  # Explicitly set to None
    )
    
    # Create a logger mock to capture warnings
    mock_logger = MagicMock()
    client.logger = mock_logger
    
    # Test
    client.assert_chain_id()
    
    # Verify
    mock_logger.warning.assert_called_once()
    assert "No expected chain ID set" in mock_logger.warning.call_args[0][0]

def test_assert_chain_id_matching():
    """Test assert_chain_id when chain IDs match."""
    # Setup
    expected_chain_id = 11155111  # Sepolia testnet
    
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT,
        expected_chain_id=expected_chain_id
    )
    
    # Mock web3 instance
    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = expected_chain_id
    client.w3 = mock_w3
    
    # Test - should not raise an exception
    client.assert_chain_id()

def test_assert_chain_id_mismatch():
    """Test assert_chain_id when chain IDs do not match."""
    # Setup
    expected_chain_id = 11155111  # Sepolia testnet
    actual_chain_id = 1  # Mainnet
    
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT,
        expected_chain_id=expected_chain_id
    )
    
    # Mock web3 instance
    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = actual_chain_id
    client.w3 = mock_w3
    
    # Set network name
    client._network_name = "test-network"
    
    # Test
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