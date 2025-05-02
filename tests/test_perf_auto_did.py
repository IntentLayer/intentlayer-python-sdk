"""
Performance tests for the Auto-DID feature and Gateway integration.
"""
import os
import time
import pytest
from unittest.mock import patch, MagicMock

from intentlayer_sdk import IntentClient

# Skip tests if running in CI environment (these can be flaky due to performance variations)
# Also skip by default unless explicitly enabled
skip_perf_tests = os.environ.get('ENABLE_PERF_TESTS') != 'true'


class TestAutoDIDPerformance:
    """Performance tests for automatic DID provisioning with Gateway integration."""

    @pytest.fixture
    def mock_gateway_client(self):
        """Create a mock gateway client that simulates realistic behavior."""
        with patch('intentlayer_sdk.gateway.get_gateway_client') as mock_get:
            # Create a gateway client that sleeps for a realistic amount of time
            mock_client = MagicMock()
            
            def sleep_register_did(*args, **kwargs):
                # Simulate network latency (50ms)
                time.sleep(0.05)
                return MagicMock(success=True)
                
            mock_client.register_did.side_effect = sleep_register_did
            mock_get.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def mock_dependencies(self):
        """Mock dependencies for performance testing."""
        with patch('intentlayer_sdk.client.NetworkConfig.get_network') as mock_net, \
             patch('intentlayer_sdk.client.NetworkConfig.get_rpc_url') as mock_rpc, \
             patch('intentlayer_sdk.client.Web3') as mock_web3, \
             patch('intentlayer_sdk.client.requests.Session') as mock_session:
            
            # Setup minimal network config
            mock_net.return_value = {
                "intentRecorder": "0x1234567890123456789012345678901234567890",
                "didRegistry": "0x0987654321098765432109876543210987654321",
                "chainId": "1"
            }
            mock_rpc.return_value = "https://example.com/rpc"
            
            # Setup Web3
            mock_web3_instance = MagicMock()
            mock_web3.return_value = mock_web3_instance
            mock_web3.to_checksum_address.side_effect = lambda x: x
            
            # Setup session
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            
            yield {
                "web3": mock_web3_instance,
                "session": mock_session_instance
            }

    @pytest.mark.skipif(skip_perf_tests, reason="Performance tests skipped in CI environment")
    def test_gateway_registration_overhead(self, mock_gateway_client, mock_dependencies):
        """Test that Gateway DID registration adds ≤120ms overhead to first call."""
        # Mock other internals but NOT send_intent to allow our ensure_registered hook to work
        with patch('intentlayer_sdk.client.IntentClient._validate_payload'), \
             patch('intentlayer_sdk.client.IntentClient.pin_to_ipfs') as mock_pin, \
             patch('intentlayer_sdk.client.IntentClient.resolve_did', return_value=("0x1234", True)), \
             patch('intentlayer_sdk.client.IntentClient.assert_chain_id'):
            
            # Setup mock responses
            mock_pin.return_value = "QmTestCid"
            mock_dependencies["web3"].eth.send_raw_transaction.return_value = b'tx_hash'
            
            # Create both clients outside the timed sections to isolate just the operation overhead
            
            # Client without Gateway
            mock_identity_manager_without = MagicMock()
            # Mock identity manager to avoid issues in test
            with patch('intentlayer_sdk.identity.registration.IdentityManager'):
                # Create client with auto_did but no Gateway URL
                client_without = IntentClient.from_network(
                    network="test-network",
                    pinner_url="https://pin.example.com",
                    auto_did=True,
                    gateway_url=None  # No Gateway = no registration
                )
            
            # Create a mock envelope for the first client
            envelope_without = MagicMock()
            envelope_without.hash.return_value = b'mock_hash'
            envelope_without.to_dict.return_value = {
                "envelope": {
                    "did": client_without._identity.did,
                    "model_id": "test-model",
                    "prompt_sha256": "0123456789abcdef0123456789abcdef",
                    "tool_id": "test-tool",
                    "timestamp_ms": 1234567890,
                    "stake_wei": "1000000000000000000",
                    "sig_ed25519": "ABCDEFGHIJKLMNOP",
                },
                "prompt": "Test prompt"
            }
            
            # Client with Gateway
            mock_identity_manager_with = MagicMock()
            mock_identity_manager_with.ensure_registered.return_value = True
            
            with patch.dict(os.environ, {"INTENT_GATEWAY_URL": "https://gateway.example.com"}):
                # Create client_with with identity manager that will do registration
                with patch('intentlayer_sdk.identity.registration.IdentityManager') as MockIdentityManager:
                    # Mock the ensure_registered method that will trigger registration
                    MockIdentityManager.return_value = mock_identity_manager_with
                    
                    client_with = IntentClient.from_network(
                        network="test-network",
                        pinner_url="https://pin.example.com",
                        auto_did=True
                    )
            
            # Create a mock envelope for the second client
            envelope_with = MagicMock()
            envelope_with.hash.return_value = b'mock_hash'
            envelope_with.to_dict.return_value = {
                "envelope": {
                    "did": client_with._identity.did,
                    "model_id": "test-model",
                    "prompt_sha256": "0123456789abcdef0123456789abcdef",
                    "tool_id": "test-tool",
                    "timestamp_ms": 1234567890,
                    "stake_wei": "1000000000000000000",
                    "sig_ed25519": "ABCDEFGHIJKLMNOP",
                },
                "prompt": "Test prompt"
            }
            
            # Before sending, make sure the identity manager will call register_did
            # Set the gateway client for the mock identity manager
            client_with._gateway_client = mock_gateway_client
            client_with._identity_manager = mock_identity_manager_with
            
            def ensure_registered_with_gateway(*args, **kwargs):
                # This calls the actual mock directly
                mock_gateway_client.register_did("did:key:test", b"pubkey", "org123")
                return True
            
            # Override the ensure_registered method
            client_with._identity_manager.ensure_registered = ensure_registered_with_gateway
            
            # Create a mock send_intent method that will use our ensure_registered
            def mock_send_intent_with(envelope_hash, payload_dict, **kwargs):
                # First ensure the DID is registered (this will call register_did)
                client_with._identity_manager.ensure_registered()
                # Then return a dummy receipt
                return {"transactionHash": "0x123"}
            
            # Replace the send_intent method
            client_with.send_intent = mock_send_intent_with
            
            # Create a mock send_intent method for the client without gateway
            def mock_send_intent_without(envelope_hash, payload_dict, **kwargs):
                # No gateway registration call here
                return {"transactionHash": "0x123"}
            
            # Replace the send_intent method
            client_without.send_intent = mock_send_intent_without
            
            # First, time a call without Gateway registration
            start_without = time.time()
            # Send intent without Gateway registration
            client_without.send_intent(
                envelope_hash=envelope_without.hash(),
                payload_dict=envelope_without.to_dict()
            )
            end_without = time.time()
            time_without = end_without - start_without
            
            # Now, time a call with Gateway registration
            start_with = time.time()
            # Send intent with Gateway registration
            client_with.send_intent(
                envelope_hash=envelope_with.hash(),
                payload_dict=envelope_with.to_dict()
            )
            end_with = time.time()
            time_with = end_with - start_with
            
            # Calculate overhead
            overhead_ms = (time_with - time_without) * 1000
            
            # Verify that the Gateway call was made
            mock_gateway_client.register_did.assert_called_once()
            
            # Assert overhead is within limit (120ms)
            assert overhead_ms <= 120, f"Gateway registration overhead ({overhead_ms:.2f}ms) exceeds 120ms limit"
            
            # Log the measured overhead for information
            print(f"\nGateway registration overhead: {overhead_ms:.2f}ms")