"""
Tests for using a custom signer with IntentClient.
"""
import pytest
from unittest.mock import MagicMock, patch
import requests_mock

from eth_account import Account
from intentlayer_sdk import IntentClient
from intentlayer_sdk.exceptions import TransactionError

class CustomSigner:
    """Custom signer implementation for testing"""
    def __init__(self, account):
        self.account = account
        self.address = account.address
        
    def sign_transaction(self, transaction_dict):
        """Sign transaction with the account"""
        return self.account.sign_transaction(transaction_dict)

class FailingSigner:
    """Custom signer that fails to sign"""
    def __init__(self):
        self.address = "0x1234567890123456789012345678901234567890"
        
    def sign_transaction(self, transaction_dict):
        """Always fails to sign"""
        raise ValueError("Signing failed deliberately")

@patch('intentlayer_sdk.client.Web3', autospec=True)
def test_custom_signer(MockWeb3, mock_w3, mock_account, test_payload, requests_mock):
    """Test successful use of a custom signer"""
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
    
    # Create custom signer
    signer = CustomSigner(mock_account)
    
    # Create client with mocked web3 and custom signer
    client = IntentClient(
        rpc_url="https://rpc.example.com",
        pinner_url="https://pin.example.com",
        min_stake_wei=1000000000000000,
        signer=signer,  # Use custom signer
        contract_address="0x1234567890123456789012345678901234567890"
    )
    
    # Directly set the mocked web3 instance
    client.w3 = mock_w3
    
    # Override signer.sign_transaction to return what we expect
    signer.sign_transaction = MagicMock(return_value=MagicMock(
        rawTransaction=b'signed_transaction'
    ))
    
    # Test send_intent
    envelope_hash = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    receipt = client.send_intent(envelope_hash, test_payload)
    
    # Verify
    assert receipt.tx_hash == "0x123456789abcdef"
    assert receipt.block_number == 12345
    assert receipt.status == 1
    assert requests_mock.called
    assert mock_w3.eth.send_raw_transaction.called
    assert signer.sign_transaction.called
    mock_w3.eth.send_raw_transaction.assert_called_with(b'signed_transaction')
    
    # Verify address property uses signer
    assert client.address == signer.address

@patch('intentlayer_sdk.client.Web3', autospec=True)
def test_failing_signer(MockWeb3, mock_w3, test_payload, requests_mock):
    """Test handling of a signer that fails to sign"""
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
    
    # Create failing signer
    signer = FailingSigner()
    
    # Create client with mocked web3 and failing signer
    client = IntentClient(
        rpc_url="https://rpc.example.com",
        pinner_url="https://pin.example.com",
        min_stake_wei=1000000000000000,
        signer=signer,
        contract_address="0x1234567890123456789012345678901234567890"
    )
    
    # Directly set the mocked web3 instance
    client.w3 = mock_w3
    
    # Test send_intent with failing signer should raise TransactionError
    envelope_hash = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    with pytest.raises(TransactionError, match="Failed to sign transaction"):
        client.send_intent(envelope_hash, test_payload)