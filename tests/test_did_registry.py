"""
Test DID registry interactions.
"""
import pytest
from unittest.mock import MagicMock
from web3.exceptions import ContractLogicError
from web3 import Web3

from intentlayer_sdk.client import IntentClient
from intentlayer_sdk.exceptions import AlreadyRegisteredError, InactiveDIDError, TransactionError

class TestDIDRegistry:
    """Test DIDRegistry interactions."""
    
    def test_resolve_did_returns_tuple(self, mock_w3, mock_account):
        """Test resolve_did returns a tuple of (owner, active)."""
        # Setup
        mock_contract = MagicMock()
        mock_function = MagicMock()
        mock_function.call.return_value = ("0x1234567890123456789012345678901234567890", True)
        mock_contract.functions.resolve.return_value = mock_function
        
        client = IntentClient(
            rpc_url="https://example.com",
            pinner_url="https://pin.example.com",
            signer=mock_account,
            recorder_address="0x1234567890123456789012345678901234567890",
            did_registry_address="0x1234567890123456789012345678901234567890"
        )
        client.did_registry_contract = mock_contract
        
        # Execute
        result = client.resolve_did("did:example:123")
        
        # Verify
        assert isinstance(result, tuple)
        assert len(result) == 2
        owner, active = result
        assert owner == "0x1234567890123456789012345678901234567890"
        assert active is True
    
    def test_register_did_already_active(self, mock_w3, mock_account):
        """Test register_did raises AlreadyRegisteredError if already active."""
        # Setup
        mock_contract = MagicMock()
        mock_function = MagicMock()
        mock_function.call.return_value = ("0x1234567890123456789012345678901234567890", True)
        mock_contract.functions.resolve.return_value = mock_function
        
        client = IntentClient(
            rpc_url="https://example.com",
            pinner_url="https://pin.example.com",
            signer=mock_account,
            recorder_address="0x1234567890123456789012345678901234567890",
            did_registry_address="0x1234567890123456789012345678901234567890"
        )
        client.did_registry_contract = mock_contract
        
        # Execute/Verify
        with pytest.raises(AlreadyRegisteredError) as exc_info:
            client.register_did("did:example:123")
        
        # Verify error contains owner info
        assert "0x1234567890123456789012345678901234567890" in str(exc_info.value)
    
    def test_register_did_inactive(self, mock_w3, mock_account):
        """Test register_did raises InactiveDIDError if inactive."""
        # Setup
        mock_contract = MagicMock()
        mock_function = MagicMock()
        mock_function.call.return_value = ("0x1234567890123456789012345678901234567890", False)
        mock_contract.functions.resolve.return_value = mock_function
        
        client = IntentClient(
            rpc_url="https://example.com",
            pinner_url="https://pin.example.com",
            signer=mock_account,
            recorder_address="0x1234567890123456789012345678901234567890",
            did_registry_address="0x1234567890123456789012345678901234567890"
        )
        client.did_registry_contract = mock_contract
        
        # Execute/Verify
        with pytest.raises(InactiveDIDError) as exc_info:
            client.register_did("did:example:123")
            
        # Verify error contains owner info
        assert "0x1234567890123456789012345678901234567890" in str(exc_info.value)
        
    def test_register_did_force_reactivation(self, mock_w3, mock_account):
        """Test register_did with force=True for inactive DIDs."""
        # Setup
        mock_contract = MagicMock()
        mock_resolve_function = MagicMock()
        mock_resolve_function.call.return_value = ("0x1234567890123456789012345678901234567890", False)
        mock_contract.functions.resolve.return_value = mock_resolve_function
        
        mock_register_function = MagicMock()
        mock_register_function.estimate_gas.return_value = 100000
        mock_register_function.build_transaction.return_value = {
            "from": "0x1234567890123456789012345678901234567890",
            "nonce": 1,
            "gas": 100000,
            "gasPrice": 20000000000,
            "to": "0x1234567890123456789012345678901234567890",
            "data": "0x123"
        }
        mock_contract.functions.register.return_value = mock_register_function
        
        # Create client with mocked Web3 instance
        client = IntentClient(
            rpc_url="https://example.com",
            pinner_url="https://pin.example.com",
            signer=mock_account,
            recorder_address="0x1234567890123456789012345678901234567890",
            did_registry_address="0x1234567890123456789012345678901234567890"
        )
        client.did_registry_contract = mock_contract
        client.w3 = mock_w3
        
        # Mock transaction count and send_raw_transaction
        mock_w3.eth.get_transaction_count.return_value = 1
        tx_hash = b'0x1234'
        mock_w3.eth.send_raw_transaction.return_value = tx_hash
        
        # Mock signer
        mock_signed_tx = MagicMock()
        mock_signed_tx.rawTransaction = b'0xsigned'
        mock_account.sign_transaction = MagicMock(return_value=mock_signed_tx)
        
        # Execute
        result = client.register_did("did:example:123", force=True, wait_for_receipt=False)
        
        # Verify function was called (would have raised exception if force wasn't working)
        assert "transactionHash" in result
        # The register function is called multiple times (for estimation and transaction building)
        assert mock_contract.functions.register.called
        assert mock_contract.functions.register.call_args_list[0][0][0] == "did:example:123"
        
    def test_send_intent_with_inactive_did(self, mock_w3, mock_account):
        """Test send_intent raises InactiveDIDError for inactive DIDs."""
        # Setup
        mock_recorder_contract = MagicMock()
        mock_did_contract = MagicMock()
        mock_resolve_function = MagicMock()
        mock_resolve_function.call.return_value = ("0x1234567890123456789012345678901234567890", False)
        mock_did_contract.functions.resolve.return_value = mock_resolve_function
        
        client = IntentClient(
            rpc_url="https://example.com",
            pinner_url="https://pin.example.com",
            signer=mock_account,
            recorder_address="0x1234567890123456789012345678901234567890",
            did_registry_address="0x1234567890123456789012345678901234567890"
        )
        client.recorder_contract = mock_recorder_contract
        client.did_registry_contract = mock_did_contract
        client.w3 = mock_w3
        
        # No need to mock transaction signing or sending since 
        # the test will raise InactiveDIDError before getting there
        
        # Create mock payload with DID
        payload = {
            "envelope": {
                "did": "did:example:123",
                "model_id": "gpt-4",
                "prompt_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "tool_id": "test",
                "timestamp_ms": 1234567890,
                "stake_wei": "1000000000000000",
                "sig_ed25519": "abc123"
            }
        }
        
        # Execute/Verify
        # The InactiveDIDError now gets directly re-raised
        with pytest.raises(InactiveDIDError) as exc_info:
            client.send_intent("0x1234", payload)
            
        # Verify error contains the DID and inactive status
        assert "did:example:123" in str(exc_info.value)
        assert "inactive" in str(exc_info.value)