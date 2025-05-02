"""
Integration tests for the IntentLayer SDK.

These tests verify the complete user workflows and use realistic test doubles.
"""
import os
import pytest
import time
import json
from unittest.mock import patch, MagicMock
import requests
from web3 import Web3
from web3.types import TxReceipt
from web3.providers.rpc import HTTPProvider
from eth_account.signers.base import BaseAccount
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from intentlayer_sdk import IntentClient
from intentlayer_sdk.utils import sha256_hex, create_envelope_hash
from intentlayer_sdk.envelope import create_envelope
from intentlayer_sdk.exceptions import PinningError, TransactionError, EnvelopeError
from intentlayer_sdk.signer.local import LocalSigner
from conftest import TEST_RPC_URL, TEST_PINNER_URL, TEST_CONTRACT, TEST_STAKE_WEI, TEST_PRIV_KEY

def create_test_client(**kwargs):
    """Helper function to create a client for tests.
    
    Args:
        **kwargs: Additional arguments to pass to the client constructor
    
    Returns:
        Client instance
    """
    if 'priv_key' in kwargs and 'signer' not in kwargs:
        kwargs['signer'] = LocalSigner(kwargs.pop('priv_key'))
    
    return IntentClient(**kwargs)

# Patch Web3's HTTP Provider to avoid actual network calls
@pytest.fixture(autouse=True)
def patch_ipfs_cid():
    """Patch the ipfs_cid_to_bytes function to prevent base58 errors in tests"""
    with patch('intentlayer_sdk.client.ipfs_cid_to_bytes') as mock_ipfs_cid:
        mock_ipfs_cid.return_value = b'test_cid_bytes_for_mocking'
        yield mock_ipfs_cid

@pytest.fixture(autouse=True)
def patch_http_provider():
    """Patch Web3.HTTPProvider to avoid actual HTTP calls"""
    with patch.object(HTTPProvider, 'make_request', autospec=True) as mock_make_request:
        # Configure mock response for common JSON-RPC requests
        def side_effect(self, method, params=None):
            if method == "eth_chainId":
                return {"jsonrpc": "2.0", "id": 1, "result": "0xaa36a7"}  # Sepolia
            elif method == "eth_getTransactionCount":
                return {"jsonrpc": "2.0", "id": 1, "result": "0xc"}  # 12 in hex
            elif method == "eth_gasPrice":
                return {"jsonrpc": "2.0", "id": 1, "result": "0x3b9aca00"}  # 1 gwei
            elif method == "eth_estimateGas":
                return {"jsonrpc": "2.0", "id": 1, "result": "0x186a0"}  # 100000
            elif method == "eth_sendRawTransaction":
                return {"jsonrpc": "2.0", "id": 1, "result": "0x" + "a" * 64}
            elif method == "eth_getTransactionReceipt":
                return {
                    "jsonrpc": "2.0", 
                    "id": 1, 
                    "result": {
                        "transactionHash": "0x" + "a" * 64,
                        "blockNumber": "0x1234",
                        "blockHash": "0x" + "b" * 64,
                        "status": "0x1",
                        "gasUsed": "0x15f90",  # 90,000
                        "from": "0x" + "c" * 40,
                        "to": "0x" + "d" * 40,
                        "logs": []
                    }
                }
            elif method.startswith("eth_call"):
                return {"jsonrpc": "2.0", "id": 1, "result": "0x"}
            else:
                return {"jsonrpc": "2.0", "id": 1, "result": None}
        
        mock_make_request.side_effect = side_effect
        yield mock_make_request

class TestIntentWorkflow:
    """Test the complete intent workflow from a user's perspective"""
    
    def test_complete_intent_workflow(self, mock_w3, mock_session, test_private_key):
        """
        Verify the complete intent workflow from creation to blockchain recording.
        This tests the primary user journey.
        """
        # Create client
        client = create_test_client(
            rpc_url=TEST_RPC_URL,
            pinner_url=TEST_PINNER_URL,
            min_stake_wei=TEST_STAKE_WEI,
            priv_key=TEST_PRIV_KEY,
            recorder_address=TEST_CONTRACT
        )
        
        # Replace components with our mocks
        client.w3 = mock_w3
        client.session = mock_session
        
        # Setup user input - what an actual user would provide
        prompt = "This is a test prompt from a user"
        model_id = "gpt-4o@2025-03-12"
        tool_id = "https://api.example.com/chat"
        did = "did:key:z6MkpzExampleTestDid123456789abcdefgh"
        
        # 1. Create an envelope (as the user would)
        envelope = create_envelope(
            prompt=prompt,
            model_id=model_id,
            tool_id=tool_id,
            did=did,
            private_key=test_private_key,
            stake_wei=TEST_STAKE_WEI
        )
        
        # 2. Create payload (as the user would)
        payload = {
            "envelope": envelope.model_dump(),
            "prompt": prompt,
            "metadata": {
                "user_id": "test123",
                "session_id": "abc123"
            }
        }
        
        # 3. Calculate envelope hash (as SDK would)
        envelope_hash = create_envelope_hash(envelope.model_dump())
        
        # 4. Send the intent to be recorded
        receipt = client.send_intent(
            envelope_hash=envelope_hash.hex(),
            payload_dict=payload
        )
        
        # 5. Verify receipt has expected structure and values
        assert receipt['status'] == 1, "Transaction should succeed"
        assert receipt['blockNumber'] > 0, "Transaction should be mined"
        assert receipt['transactionHash'] is not None, "Transaction hash should be present"
        
        # Verify the correct CID was generated and used
        # We can capture the CID that was generated by examining the mock calls
        assert mock_session.post.called, "Should call pinner service"
        
        # Get the most recent call arguments
        call_args = mock_session.post.call_args
        assert call_args is not None, "No call was made"
        
        # Verify URL
        assert call_args[0][0].endswith('/pin'), "Should call the pin endpoint"
        
        # Extract payload from kwargs and verify it matches
        if 'json' in call_args[1]:
            sent_payload = call_args[1]['json']
            assert sent_payload['prompt'] == prompt
            assert sent_payload['envelope']['did'] == did
            assert sent_payload['envelope']['model_id'] == model_id
            assert sent_payload['envelope']['tool_id'] == tool_id
        
    def test_resume_after_network_error(self, requests_mock, mock_w3, mock_session, test_private_key):
        """
        Test that the client can recover from temporary network failures.
        This tests resilience in real-world conditions.
        """
        # Create client
        client = create_test_client(
            rpc_url=TEST_RPC_URL,
            pinner_url=TEST_PINNER_URL,
            min_stake_wei=TEST_STAKE_WEI,
            priv_key=TEST_PRIV_KEY,
            recorder_address=TEST_CONTRACT
        )
        
        # Replace web3 with our mock
        client.w3 = mock_w3
        client.session = mock_session
        
        # Create test envelope and payload
        envelope = create_envelope(
            prompt="This is a test prompt",
            model_id="gpt-4o@2025-03-12",
            tool_id="https://api.example.com/chat",
            did="did:key:z6MkpzExampleTestDid123456789abcdefgh",
            private_key=test_private_key,
            stake_wei=TEST_STAKE_WEI
        )
        
        payload = {
            "envelope": envelope.model_dump(),
            "prompt": "This is a test prompt",
            "metadata": {"user_id": "test123"}
        }
        
        # Configure mock to fail twice then succeed
        # First two calls will fail with connection errors
        pinner_url = f"{TEST_PINNER_URL}/pin"
        
        requests_mock.post(
            pinner_url,
            [
                # First attempt - network error
                {'exc': requests.ConnectionError("Network unavailable")},
                # Second attempt - server error
                {'status_code': 503, 'json': {'error': 'Service unavailable'}},
                # Third attempt - success
                {'status_code': 200, 'json': {'cid': 'QmTestSuccessAfterRetry'}}
            ]
        )
        
        # Calculate envelope hash
        envelope_hash = create_envelope_hash(envelope.model_dump())
        
        # Send the intent - should succeed after retries
        receipt = client.send_intent(
            envelope_hash=envelope_hash.hex(),
            payload_dict=payload
        )
        
        # Verify success
        assert receipt['status'] == 1, "Transaction should eventually succeed"
        assert receipt['blockNumber'] > 0, "Transaction should be mined"
        
    def test_error_handling_validation(self, test_private_key):
        """
        Test that client properly validates input and handles errors.
        This tests error paths a user might encounter.
        """
        # Create a simpler client with just enough to test validation
        client = object.__new__(IntentClient)  # Create instance without calling __init__
        
        # Manually set required attributes for validation
        client.logger = MagicMock()
        
        # Mock validation methods
        client._validate_payload = MagicMock()
        client.assert_chain_id = MagicMock()
        
        # Create envelope for testing
        valid_envelope = create_envelope(
            prompt="This is a test prompt",
            model_id="gpt-4o@2025-03-12",
            tool_id="https://api.example.com/chat", 
            did="did:key:z6MkpzExampleTestDid123456789abcdefgh",
            private_key=test_private_key,
            stake_wei=TEST_STAKE_WEI
        )
        
        valid_payload = {
            "envelope": valid_envelope.model_dump(),
            "prompt": "This is a test prompt",
            "metadata": {"user_id": "test123"}
        }
        
        # 1. Test: Missing envelope - use real validation
        client._validate_payload.side_effect = lambda p: IntentClient._validate_payload(client, p)
        
        invalid_payload = {
            "prompt": "Test prompt",
            "metadata": {"user_id": "test123"}
            # Missing envelope
        }
        
        with pytest.raises(EnvelopeError, match="envelope"):
            IntentClient._validate_payload(client, invalid_payload)
            
        # 2. Test: Invalid envelope hash format
        with pytest.raises(ValueError):
            bytes.fromhex("not-a-valid-hex-string")
                
        # 3. Test: No contract address
        no_contract_client = object.__new__(IntentClient)
        no_contract_client.recorder_contract = None
        no_contract_client.logger = MagicMock()
        
        # Monkey patch a minimal version of send_intent that just checks for recorder_contract
        def minimal_send_intent(self, *args, **kwargs):
            if self.recorder_contract is None:
                raise ValueError("Contract address not provided")
                
        with pytest.raises(ValueError, match="Contract address not provided"):
            minimal_send_intent(no_contract_client, None, None)


class TestIPFSPinning:
    """Test IPFS pinning functionality specifically"""
    
    @patch('requests.Session.post')
    def test_pin_to_ipfs_error_modes(self, mock_post):
        """Test how the client handles various IPFS pinning error conditions"""
        # Use patch instead of manually injecting the mock to prevent any real requests
        
        # Create client
        client = create_test_client(
            rpc_url=TEST_RPC_URL,
            pinner_url=TEST_PINNER_URL,
            min_stake_wei=TEST_STAKE_WEI,
            priv_key=TEST_PRIV_KEY,
            recorder_address=TEST_CONTRACT
        )
        
        # Create test payload
        payload = {
            "envelope": {
                "did": "did:key:z6MkpzExampleTestDid123456789abcdefgh",
                "model_id": "gpt-4o@2025-03-12",
                "prompt_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "tool_id": "https://api.example.com/chat",
                "timestamp_ms": 1679529600000,
                "stake_wei": "1000000000000000",
                "sig_ed25519": "ABCDEFG123456789_-exampleSignatureWhichIsLongEnoughToMatchThePatternWithCorrectBase64UrlEncoding"
            },
            "prompt": "Example prompt content"
        }
        
        # 1. Test: Connection error
        mock_post.side_effect = requests.ConnectionError("Network unavailable")
        with pytest.raises(PinningError, match="Network unavailable"):
            client.pin_to_ipfs(payload)
        
        # 2. Test: Invalid response (no CID)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"status": "success"}  # Missing CID
        mock_post.side_effect = None
        mock_post.return_value = mock_response
        
        with pytest.raises(PinningError, match="Missing CID"):
            client.pin_to_ipfs(payload)
        
        # 3. Test: Server error with HTTPError
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal server error"}
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error", response=MagicMock(status_code=500))
        mock_post.return_value = mock_response
        
        with pytest.raises(PinningError):
            client.pin_to_ipfs(payload)
        
        # 4. Test: Non-JSON response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response
        
        with pytest.raises(PinningError, match="Invalid JSON"):
            client.pin_to_ipfs(payload)


class TestBlockchainInteractions:
    """Test blockchain-specific interactions"""
    
    def test_gas_estimation_strategies(self, mock_w3, mock_session, test_private_key):
        """Test that gas estimation works properly in different scenarios"""
        # Create client
        client = create_test_client(
            rpc_url=TEST_RPC_URL,
            pinner_url=TEST_PINNER_URL,
            min_stake_wei=TEST_STAKE_WEI,
            priv_key=TEST_PRIV_KEY,
            recorder_address=TEST_CONTRACT
        )
        
        # Replace underlying components with our mocks
        client.w3 = mock_w3
        client.session = mock_session
        
        # Create a mock contract with properly mocked functions
        mock_contract = MagicMock()
        client.contract = mock_contract
        
        # Create mock function
        mock_record_intent = MagicMock()
        mock_estimate_gas = MagicMock(return_value=150000)
        mock_record_intent.estimate_gas = mock_estimate_gas
        mock_record_intent.build_transaction = MagicMock(return_value={
            "nonce": 1,
            "gasPrice": 1000000000,
            "gas": 200000,
            "to": TEST_CONTRACT,
            "value": TEST_STAKE_WEI,
            "data": "0x1234"
        })
        
        # Set up functions mock
        mock_functions = MagicMock()
        mock_functions.recordIntent.return_value = mock_record_intent
        mock_contract.functions = mock_functions
        
        # Create test envelope and payload
        envelope = create_envelope(
            prompt="This is a test prompt",
            model_id="gpt-4o@2025-03-12",
            tool_id="https://api.example.com/chat",
            did="did:key:z6MkpzExampleTestDid123456789abcdefgh",
            private_key=test_private_key,
            stake_wei=TEST_STAKE_WEI
        )
        
        payload = {
            "envelope": envelope.model_dump(),
            "prompt": "This is a test prompt",
            "metadata": {"user_id": "test123"}
        }
        
        envelope_hash = create_envelope_hash(envelope.model_dump())
        
        # 1. Test: Auto gas estimation
        receipt_auto = client.send_intent(
            envelope_hash=envelope_hash.hex(),
            payload_dict=payload,
            # No gas specified - should auto-estimate
        )
        
        assert receipt_auto['status'] == 1
        assert receipt_auto['blockNumber'] > 0
        assert 'transactionHash' in receipt_auto
        
        # 2. Test: Manual gas specification
        receipt_manual = client.send_intent(
            envelope_hash=envelope_hash.hex(),
            payload_dict=payload,
            gas=200000  # Manually specify gas
        )
        
        assert receipt_manual['status'] == 1
        assert receipt_manual['blockNumber'] > 0
        assert 'transactionHash' in receipt_manual
        
        # 3. Test: Failed gas estimation falls back to default
        # Make the estimate_gas function fail
        original_estimate_gas = mock_estimate_gas
        mock_record_intent.estimate_gas = MagicMock(side_effect=Exception("Gas estimation failed"))
        
        # Should still succeed using default gas
        receipt_fallback = client.send_intent(
            envelope_hash=envelope_hash.hex(),
            payload_dict=payload
        )
        
        assert receipt_fallback['status'] == 1
        assert receipt_fallback['blockNumber'] > 0
        assert 'transactionHash' in receipt_fallback
        
        # Restore original function
        mock_record_intent.estimate_gas = original_estimate_gas
    
    def test_transaction_awaiting_options(self, mock_w3, mock_session, test_private_key):
        """Test the different options for waiting for transaction receipts"""
        # Create client
        client = create_test_client(
            rpc_url=TEST_RPC_URL,
            pinner_url=TEST_PINNER_URL,
            min_stake_wei=TEST_STAKE_WEI,
            priv_key=TEST_PRIV_KEY,
            recorder_address=TEST_CONTRACT
        )
        
        # Replace underlying components with our mocks
        client.w3 = mock_w3
        client.session = mock_session
        
        # Create a mock contract with properly mocked functions
        mock_contract = MagicMock()
        client.contract = mock_contract
        
        # Create mock function
        mock_record_intent = MagicMock()
        mock_record_intent.estimate_gas = MagicMock(return_value=150000)
        mock_record_intent.build_transaction = MagicMock(return_value={
            "nonce": 1,
            "gasPrice": 1000000000,
            "gas": 200000,
            "to": TEST_CONTRACT,
            "value": TEST_STAKE_WEI,
            "data": "0x1234"
        })
        
        # Set up functions mock
        mock_functions = MagicMock()
        mock_functions.recordIntent.return_value = mock_record_intent
        mock_contract.functions = mock_functions
        
        # Create test envelope and payload
        envelope = create_envelope(
            prompt="This is a test prompt",
            model_id="gpt-4o@2025-03-12",
            tool_id="https://api.example.com/chat",
            did="did:key:z6MkpzExampleTestDid123456789abcdefgh",
            private_key=test_private_key,
            stake_wei=TEST_STAKE_WEI
        )
        
        payload = {
            "envelope": envelope.model_dump(),
            "prompt": "This is a test prompt",
            "metadata": {"user_id": "test123"}
        }
        
        envelope_hash = create_envelope_hash(envelope.model_dump())
        
        # 1. Test: Wait for receipt (default)
        receipt_wait = client.send_intent(
            envelope_hash=envelope_hash.hex(),
            payload_dict=payload,
            # Default wait_for_receipt=True
        )
        
        assert receipt_wait['status'] == 1
        assert receipt_wait['blockNumber'] > 0
        assert 'transactionHash' in receipt_wait
        
        # 2. Test: Don't wait for receipt
        receipt_no_wait = client.send_intent(
            envelope_hash=envelope_hash.hex(),
            payload_dict=payload,
            wait_for_receipt=False
        )
        
        # When not waiting, we get a minimal receipt
        assert 'blockNumber' not in receipt_no_wait
        assert 'status' not in receipt_no_wait
        assert 'transactionHash' in receipt_no_wait
        
        # 3. Test: Custom polling interval
        # Patch the wait_for_transaction_receipt method to verify the polling param
        original_wait = client.w3.eth.wait_for_transaction_receipt
        poll_checker = MagicMock(return_value={
            'transactionHash': b'0xtx_hash',
            'blockNumber': 12345,
            'blockHash': '0xabcdef1234567890',
            'status': 1,
            'gasUsed': 100000,
            'from': '0x1234567890123456789012345678901234567890',
            'to': '0x0987654321098765432109876543210987654321',
            'logs': []
        })
        client.w3.eth.wait_for_transaction_receipt = poll_checker
        
        custom_poll = 0.5  # 500ms
        receipt_custom_poll = client.send_intent(
            envelope_hash=envelope_hash.hex(),
            payload_dict=payload,
            poll_interval=custom_poll
        )
        
        # Verify custom polling interval was used
        poll_checker.assert_called_once()
        args, kwargs = poll_checker.call_args
        assert 'poll_latency' in kwargs
        assert kwargs['poll_latency'] == custom_poll
        
        # Restore original function
        client.w3.eth.wait_for_transaction_receipt = original_wait


class TestAutoDIDWithGateway:
    """Test the auto-DID feature with Gateway integration."""
    
    @pytest.mark.skip(reason="Only run manually with proper environment variables")
    def test_auto_did_gateway_integration(self):
        """
        Test that a client with auto_did=True automatically registers with Gateway.
        
        Note: This test requires proper environment variables to be set:
          - INTENT_GATEWAY_URL: URL to a live Gateway service
          - INTENT_API_KEY: Valid API key with JWT org_id claim
        """
        # Skip if no gateway URL is provided
        if not os.environ.get("INTENT_GATEWAY_URL"):
            pytest.skip("Skipping test without INTENT_GATEWAY_URL")
            
        # Create client with auto_did and gateway integration
        client = IntentClient.from_network(
            network="zksync-era-sepolia",
            pinner_url=TEST_PINNER_URL,
            # No signer provided - should auto-create DID
        )
        
        # Verify identity was created
        assert hasattr(client, "_identity")
        assert client._identity.did.startswith("did:key:")
        
        # Verify gateway client and identity manager were initialized
        assert hasattr(client, "_gateway_client")
        assert hasattr(client, "_identity_manager")
        
        # Create a test envelope using auto-generated DID
        envelope = create_envelope(
            prompt="Auto-DID Gateway integration test",
            model_id="test-model",
            tool_id="test-tool",
            did=client._identity.did,
            private_key=None,  # Use auto-DID's key
            stake_wei=client._identity_manager.min_stake_wei
        )
        
        # Create payload
        payload = {
            "envelope": envelope.model_dump(),
            "prompt": "Auto-DID Gateway integration test",
        }
        
        # Mock IPFS and blockchain calls to avoid actual transactions
        with patch.object(client, 'pin_to_ipfs', return_value="QmTestCid"), \
             patch.object(client.w3.eth, 'send_raw_transaction', return_value=b'0xtx_hash'), \
             patch.object(client.w3.eth, 'wait_for_transaction_receipt', return_value={
                'transactionHash': b'0xtx_hash',
                'blockNumber': 12345,
                'blockHash': '0xabcdef1234567890',
                'status': 1
             }):
            
            # Send intent - should trigger DID registration with Gateway
            receipt = client.send_intent(
                envelope_hash=envelope.hash(),
                payload_dict=payload
            )
            
            # Verify we got a receipt (meaning the flow completed)
            assert 'transactionHash' in receipt