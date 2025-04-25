"""
Tests for the refresh_min_stake method and related functionality in IntentClient.
"""
import pytest
import time
from unittest.mock import patch, MagicMock

from intentlayer_sdk import IntentClient
from intentlayer_sdk.exceptions import TransactionError
from tests.conftest import TEST_RPC_URL, TEST_PINNER_URL, TEST_CONTRACT, TEST_PRIV_KEY

def test_refresh_min_stake_success():
    """Test successful refresh of min_stake_wei."""
    # Setup
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT
    )
    
    # Create mock recorder contract
    mock_contract = MagicMock()
    mock_function = MagicMock()
    mock_function.call.return_value = 1000000
    mock_contract.functions.MIN_STAKE_WEI.return_value = mock_function
    client.recorder_contract = mock_contract
    
    # Set initial state
    client._min_stake_wei = None
    client._min_stake_wei_timestamp = None
    
    # Test
    result = client.refresh_min_stake()
    
    # Verify
    assert result == 1000000
    assert client._min_stake_wei == 1000000
    assert client._min_stake_wei_timestamp is not None

def test_refresh_min_stake_error():
    """Test error handling in refresh_min_stake."""
    # Setup
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT
    )
    
    # Create mock recorder contract that raises an exception
    mock_contract = MagicMock()
    mock_function = MagicMock()
    mock_function.call.side_effect = Exception("Contract call failed")
    mock_contract.functions.MIN_STAKE_WEI.return_value = mock_function
    client.recorder_contract = mock_contract
    
    # Set initial state
    initial_stake = 999
    initial_timestamp = time.time() - 1000  # Old timestamp
    client._min_stake_wei = initial_stake
    client._min_stake_wei_timestamp = initial_timestamp
    
    # Test
    with pytest.raises(TransactionError, match="Failed to refresh minimum stake"):
        client.refresh_min_stake()
    
    # Verify state remains unchanged on error
    assert client._min_stake_wei == initial_stake
    assert client._min_stake_wei_timestamp == initial_timestamp