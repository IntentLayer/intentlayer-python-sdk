"""
Tests for using a custom signer with IntentClient.
"""
import pytest
from unittest.mock import MagicMock, patch
import requests_mock

from eth_account import Account
from intentlayer_sdk import IntentClient
from intentlayer_sdk.exceptions import TransactionError
from tests.test_helpers import create_test_client, TEST_RPC_URL, TEST_PINNER_URL, TEST_STAKE_WEI, TEST_PRIV_KEY, TEST_CONTRACT

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
@patch('intentlayer_sdk.client.ipfs_cid_to_bytes')
def test_custom_signer(mock_ipfs_cid_to_bytes, MockWeb3, mock_w3, mock_account, test_payload, requests_mock):
    """Test successful use of a custom signer"""
    # Setup mocks
    mock_provider = MagicMock()
    MockWeb3.HTTPProvider.return_value = mock_provider
    MockWeb3.return_value = mock_w3
    MockWeb3.keccak.return_value = b'0123456789abcdef' * 2
    
    # Mock IPFS CID conversion
    mock_ipfs_cid_to_bytes.return_value = b'mocked_cid_bytes'
    
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
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=TEST_STAKE_WEI,
        signer=signer,  # Use custom signer
        recorder_address=TEST_CONTRACT
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
    # The receipt is now a dictionary, not a TxReceipt object
    assert isinstance(receipt, dict)
    assert "transactionHash" in receipt
    
    # Check that our mocks were called correctly
    assert requests_mock.called
    assert mock_w3.eth.send_raw_transaction.called
    assert signer.sign_transaction.called
    mock_w3.eth.send_raw_transaction.assert_called_with(b'signed_transaction')
    
    # Verify address property uses signer
    assert client.address == signer.address

@patch('intentlayer_sdk.client.Web3', autospec=True)
@patch('intentlayer_sdk.client.ipfs_cid_to_bytes')
def test_failing_signer(mock_ipfs_cid_to_bytes, MockWeb3, mock_w3, test_payload, requests_mock):
    """Test handling of a signer that fails to sign"""
    # Setup mocks
    mock_provider = MagicMock()
    MockWeb3.HTTPProvider.return_value = mock_provider
    MockWeb3.return_value = mock_w3
    MockWeb3.keccak.return_value = b'0123456789abcdef' * 2
    
    # Mock IPFS CID conversion
    mock_ipfs_cid_to_bytes.return_value = b'mocked_cid_bytes'
    
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
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=TEST_STAKE_WEI,
        signer=signer,
        recorder_address=TEST_CONTRACT
    )
    
    # Directly set the mocked web3 instance
    client.w3 = mock_w3
    
    # Test send_intent with failing signer should raise TransactionError
    envelope_hash = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    with pytest.raises(TransactionError, match="Failed to sign transaction"):
        client.send_intent(envelope_hash, test_payload)