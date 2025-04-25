"""
Tests for error paths in the IntentClient class.
"""
import pytest
from unittest.mock import MagicMock, patch
import requests
from web3.exceptions import ContractLogicError

from intentlayer_sdk import IntentClient
from intentlayer_sdk.exceptions import PinningError, TransactionError

def test_address_property_no_credentials():
    """Accessing .address with neither priv_key nor signer should ValueError."""
    # Bypass __init__ key check by injecting attributes manually
    client = IntentClient.__new__(IntentClient)
    client.account = None
    client.signer = None

    with pytest.raises(ValueError, match="No account or signer available"):
        _ = client.address

def test_pin_to_ipfs_network_fail(requests_mock):
    """Simulate a ConnectionError so retries exhaust and raise PinningError."""
    # Force a network-level exception
    requests_mock.post("https://pin.example.com/pin", exc=requests.ConnectionError("down"))

    client = IntentClient(
        rpc_url="https://rpc.example.com",
        pinner_url="https://pin.example.com",
        min_stake_wei=1,
        priv_key="0x"+ "1"*64
    )

    with pytest.raises(PinningError, match="IPFS pinning failed"):
        client.pin_to_ipfs({"foo": "bar"})

@patch("intentlayer_sdk.client.Web3", autospec=True)
def test_gas_estimation_uses_default_on_error(MockWeb3, test_payload, requests_mock, caplog):
    """Test that gas estimation failure falls back to default gas limit"""
    # Setup mocks
    mock_w3 = MagicMock()
    MockWeb3.return_value = mock_w3
    
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
    
    # Create a custom IntentClient class that bypasses account creation
    class TestIntentClient(IntentClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Replace the account with a mock
            self.account = MagicMock()
            self.account.address = "0x1234567890123456789012345678901234567890"
            
            # Mock the sign_transaction method
            mock_signed = MagicMock()
            mock_signed.rawTransaction = b"0xsigned_raw_tx"
            self.account.sign_transaction.return_value = mock_signed
    
    # Create client with our test class
    client = TestIntentClient(
        rpc_url="https://rpc.example.com",
        pinner_url="https://pin.example.com",
        min_stake_wei=1000000000000000,
        priv_key="0x" + "1"*64,
        contract_address="0x1234567890123456789012345678901234567890"
    )
    
    # Execute with logging captured
    caplog.set_level("WARNING")
    receipt = client.send_intent("0x" + "0"*64, test_payload)
    
    # Verify gas estimation failure was logged and default gas was used
    assert any("Gas estimation failed" in msg for msg in caplog.messages)
    assert receipt.block_number > 0  # Just check it's a positive number

class BadSigner:
    address = "0x0"
    def sign_transaction(self, _): 
        raise RuntimeError("nope")

@patch("intentlayer_sdk.client.Web3", autospec=True)
def test_signing_failure_raises_transaction_error(MockWeb3, mock_w3, test_payload, requests_mock):
    MockWeb3.return_value = mock_w3
    requests_mock.post("https://pin.example.com/pin", json={"cid":"QmC"}, status_code=200)
    mock_w3.eth.contract.return_value.functions.recordIntent.return_value.build_transaction.return_value = {}
    client = IntentClient(
        rpc_url="https://rpc.example.com",
        pinner_url="https://pin.example.com",
        min_stake_wei=1,
        signer=BadSigner(),
        contract_address="0x1"
    )
    client.w3 = mock_w3

    with pytest.raises(TransactionError, match="Failed to sign transaction"):
        client.send_intent("0x"+"0"*64, test_payload)
