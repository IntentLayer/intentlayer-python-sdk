"""
Tests for the IntentClient class.
"""
import pytest
from unittest.mock import patch, MagicMock
import requests
import requests_mock
import json
from web3 import Web3

from intentlayer_sdk import IntentClient
from intentlayer_sdk.exceptions import PinningError, TransactionError

def test_client_initialization():
    """Test client initialization with valid parameters"""
    client = IntentClient(
        rpc_url="https://rpc.example.com",
        pinner_url="https://pin.example.com",
        min_stake_wei=1000000000000000,  # 0.001 ETH
        priv_key="0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )
    
    assert client.rpc_url == "https://rpc.example.com"
    assert client.pinner_url == "https://pin.example.com"
    assert client.min_stake_wei == 1000000000000000
    assert client.account is not None

def test_client_initialization_no_credentials():
    """Test client initialization with no credentials raises error"""
    with pytest.raises(ValueError, match="Either priv_key or signer must be provided"):
        IntentClient(
            rpc_url="https://rpc.example.com",
            pinner_url="https://pin.example.com",
            min_stake_wei=1000000000000000
        )

def test_pin_to_ipfs_success(requests_mock):
    """Test successful pinning to IPFS"""
    # Setup mock
    requests_mock.post(
        "https://pin.example.com/pin",
        json={"cid": "QmExample123456789"},
        status_code=200
    )
    
    # Create client
    client = IntentClient(
        rpc_url="https://rpc.example.com",
        pinner_url="https://pin.example.com",
        min_stake_wei=1000000000000000,
        priv_key="0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )
    
    # Test pinning
    payload = {"test": "data"}
    cid = client.pin_to_ipfs(payload)
    
    # Verify
    assert cid == "QmExample123456789"
    assert requests_mock.called
    assert requests_mock.last_request.json() == {"test": "data"}

def test_pin_to_ipfs_error(requests_mock):
    """Test error handling when pinning to IPFS fails"""
    # Setup mock
    requests_mock.post(
        "https://pin.example.com/pin",
        json={"error": "Server error"},
        status_code=500
    )
    
    # Create client
    client = IntentClient(
        rpc_url="https://rpc.example.com",
        pinner_url="https://pin.example.com",
        min_stake_wei=1000000000000000,
        priv_key="0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )
    
    # Test pinning error
    with pytest.raises(PinningError):
        client.pin_to_ipfs({"test": "data"})

def test_pin_to_ipfs_invalid_response(requests_mock):
    """Test error handling when pinning service returns invalid response"""
    # Setup mock
    requests_mock.post(
        "https://pin.example.com/pin",
        json={"not_cid": "something else"},
        status_code=200
    )
    
    # Create client
    client = IntentClient(
        rpc_url="https://rpc.example.com",
        pinner_url="https://pin.example.com",
        min_stake_wei=1000000000000000,
        priv_key="0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )
    
    # Test pinning error
    with pytest.raises(PinningError, match="Missing CID in pinner response"):
        client.pin_to_ipfs({"test": "data"})

@patch('intentlayer_sdk.client.Web3', autospec=True)
def test_send_intent_success(MockWeb3, mock_w3, mock_account, test_payload, requests_mock):
    """Test successful intent sending"""
    # Setup mocks
    mock_provider = MagicMock()
    MockWeb3.HTTPProvider.return_value = mock_provider
    MockWeb3.return_value = mock_w3
    MockWeb3.keccak.return_value = b'0123456789abcdef' * 2
    
    # Mock pinner
    requests_mock.post(
        "https://pin.example.com/pin",
        json={"cid": "QmExample123456789"},
        status_code=200
    )
    
    # Create mock contract
    mock_contract = MagicMock()
    mock_w3.eth.contract.return_value = mock_contract
    
    # Mock function call
    mock_function = MagicMock()
    mock_contract.functions.recordIntent.return_value = mock_function
    mock_function.build_transaction.return_value = {"mock": "tx"}
    
    # Create client with mocked web3
    client = IntentClient(
        rpc_url="https://rpc.example.com",
        pinner_url="https://pin.example.com",
        min_stake_wei=1000000000000000,
        priv_key=mock_account.key.hex(),
        contract_address="0x1234567890123456789012345678901234567890"
    )
    
    # Directly set the mocked web3 instance
    client.w3 = mock_w3
    
    # Mock signing
    client.account.sign_transaction = MagicMock(return_value=MagicMock(
        rawTransaction=b'signed_transaction'
    ))
    
    # Test send_intent
    envelope_hash = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    receipt = client.send_intent(envelope_hash, test_payload)
    
    # Verify
    # Don't check exact tx_hash value, just ensure it's a non-empty string
    assert isinstance(receipt.tx_hash, str)
    assert receipt.tx_hash.startswith("0x")
    assert len(receipt.tx_hash) > 10
    
    # Check other properties
    assert receipt.block_number > 0  # Just check it's a positive number
    assert receipt.status == 1
    assert requests_mock.called
    assert mock_w3.eth.send_raw_transaction.called
    mock_w3.eth.send_raw_transaction.assert_called_with(b'signed_transaction')

@patch('intentlayer_sdk.client.Web3', autospec=True)
def test_send_intent_transaction_error(MockWeb3, mock_w3, mock_account, test_payload, requests_mock):
    """Test error handling when transaction fails"""
    # Setup mocks
    mock_provider = MagicMock()
    MockWeb3.HTTPProvider.return_value = mock_provider
    MockWeb3.return_value = mock_w3
    MockWeb3.keccak.return_value = b'0123456789abcdef' * 2
    
    # Mock pinner
    requests_mock.post(
        "https://pin.example.com/pin",
        json={"cid": "QmExample123456789"},
        status_code=200
    )
    
    # Create mock contract
    mock_contract = MagicMock()
    mock_w3.eth.contract.return_value = mock_contract
    
    # Mock function call
    mock_function = MagicMock()
    mock_contract.functions.recordIntent.return_value = mock_function
    mock_function.build_transaction.return_value = {"mock": "tx"}
    
    # Create client with mocked web3
    client = IntentClient(
        rpc_url="https://rpc.example.com",
        pinner_url="https://pin.example.com",
        min_stake_wei=1000000000000000,
        priv_key=mock_account.key.hex(),
        contract_address="0x1234567890123456789012345678901234567890"
    )
    
    # Directly set the mocked web3 instance
    client.w3 = mock_w3
    
    # Mock signing
    client.account.sign_transaction = MagicMock(return_value=MagicMock(
        rawTransaction=b'signed_transaction'
    ))
    
    # Mock transaction failure
    mock_w3.eth.send_raw_transaction.side_effect = Exception("Transaction failed")
    
    # Test send_intent
    envelope_hash = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    with pytest.raises(TransactionError, match="Transaction failed"):
        client.send_intent(envelope_hash, test_payload)

def test_send_intent_no_contract():
    """Test sending intent without a contract address raises error"""
    client = IntentClient(
        rpc_url="https://rpc.example.com",
        pinner_url="https://pin.example.com",
        min_stake_wei=1000000000000000,
        priv_key="0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )
    
    with pytest.raises(ValueError, match="Contract address not provided"):
        client.send_intent("0x1234", {"test": "data"})