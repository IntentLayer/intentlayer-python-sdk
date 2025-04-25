"""
Tests for error paths in the IntentClient class.
"""
import pytest
from unittest.mock import MagicMock, patch
import requests
from web3.exceptions import ContractLogicError

from intentlayer_sdk import IntentClient
from intentlayer_sdk.exceptions import PinningError, TransactionError
from tests.test_helpers import create_test_client, TEST_RPC_URL, TEST_PINNER_URL, TEST_STAKE_WEI, TEST_PRIV_KEY, TEST_CONTRACT

def test_address_property_no_credentials():
    """Accessing .address with no signer should ValueError."""
    # Bypass __init__ key check by injecting attributes manually
    client = IntentClient.__new__(IntentClient)
    # Initialize logger to avoid AttributeError
    client.logger = MagicMock()
    # Set signer to None
    client.signer = None

    with pytest.raises(ValueError, match="No signer available"):
        _ = client.address

def test_pin_to_ipfs_network_fail(requests_mock):
    """Simulate a ConnectionError so retries exhaust and raise PinningError."""
    # Force a network-level exception
    requests_mock.post("https://pin.example.com/pin", exc=requests.ConnectionError("down"))

    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=1,  # Use a small value for this specific test
        priv_key=TEST_PRIV_KEY
    )

    with pytest.raises(PinningError, match="IPFS pinning failed"):
        client.pin_to_ipfs({"foo": "bar"})

@patch("intentlayer_sdk.client.Web3", autospec=True)
@patch('intentlayer_sdk.client.ipfs_cid_to_bytes')
def test_gas_estimation_uses_default_on_error(mock_ipfs_cid_to_bytes, MockWeb3, test_payload, requests_mock, caplog):
    """Test that gas estimation failure falls back to default gas limit"""
    # Setup mocks
    mock_w3 = MagicMock()
    MockWeb3.return_value = mock_w3
    
    # Mock CID conversion
    mock_ipfs_cid_to_bytes.return_value = b'mocked_cid_bytes'
    
    # Mock IPFS pinning
    requests_mock.post("https://pin.example.com/pin", json={"cid": "QmExample123456789"}, status_code=200)
    
    # Mock contract and estimation failure
    mock_contract = MagicMock()
    mock_w3.eth.contract.return_value = mock_contract
    mock_fn = mock_contract.functions.recordIntent.return_value
    mock_fn.estimate_gas.side_effect = Exception("Gas estimation failed")
    mock_fn.build_transaction.return_value = {
        "nonce": 1,
        "gasPrice": 2000000000,
        "gas": 300000,
        "to": "0x1234567890abcdef",
        "data": "0x1234",
        "value": 1000000000000000
    }
    
    # Mock transaction sending
    mock_w3.eth.send_raw_transaction.return_value = b"0xtx_hash"
    
    # Mock receipt
    mock_receipt = {
        'transactionHash': b'0xtx_hash',
        'blockNumber': 12345,
        'blockHash': '0xabcdef1234567890',
        'status': 1,
        'gasUsed': 100000,
        'from': '0x1234567890123456789012345678901234567890',
        'to': '0x0987654321098765432109876543210987654321',
        'logs': []
    }
    mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt
    
    # Create a custom IntentClient class that bypasses signer creation
    class TestIntentClient(IntentClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Replace the signer with a mock
            self.signer = MagicMock()
            self.signer.address = "0x1234567890123456789012345678901234567890"
            
            # Mock the sign_transaction method
            mock_signed = MagicMock()
            mock_signed.rawTransaction = b"0xsigned_raw_tx"
            self.signer.sign_transaction.return_value = mock_signed
    
    # Create client with our test class
    client = TestIntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=TEST_STAKE_WEI,
        signer=MagicMock(),  # This will be replaced in __init__
        recorder_address=TEST_CONTRACT
    )
    
    # Execute with logging captured
    caplog.set_level("WARNING")
    receipt = client.send_intent("0x" + "0"*64, test_payload)
    
    # Verify gas estimation failure was logged and default gas was used
    assert any("Gas estimation failed" in msg for msg in caplog.messages)
    assert isinstance(receipt, dict)
    assert "blockNumber" in receipt

class BadSigner:
    address = "0x0"
    def sign_transaction(self, _): 
        raise RuntimeError("nope")

@patch("intentlayer_sdk.client.Web3", autospec=True)
def test_signing_failure_raises_transaction_error(MockWeb3, mock_w3, test_payload, requests_mock):
    MockWeb3.return_value = mock_w3
    requests_mock.post("https://pin.example.com/pin", json={"cid":"QmC"}, status_code=200)
    mock_w3.eth.contract.return_value.functions.recordIntent.return_value.build_transaction.return_value = {}
    client = create_test_client(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        min_stake_wei=1,  # Use small stake for this test
        signer=BadSigner(),
        recorder_address=TEST_CONTRACT
    )
    client.w3 = mock_w3

    with pytest.raises(TransactionError, match="Failed to sign transaction"):
        client.send_intent("0x"+"0"*64, test_payload)
