"""
Integration tests for Gateway client with in-process gRPC server.

These tests verify that the Gateway client can properly communicate with a
gRPC server using real proto messages without requiring network connections.
"""
import pytest
import logging
import os
from unittest.mock import patch, MagicMock

# Skip tests if grpc-testing or protobuf is not available
try:
    import grpc
    import grpc_testing
    grpc_testing_available = True
except ImportError:
    grpc_testing_available = False

# Skip tests if proto stubs aren't available
try:
    from intentlayer_sdk.gateway.proto import (
        RegisterError as ProtoRegisterError,
        DidDocument as ProtoDidDocument,
        TxReceipt as ProtoTxReceipt,
        RegisterDidRequest,
        RegisterDidResponse,
        PROTO_AVAILABLE
    )
    proto_available = PROTO_AVAILABLE
except ImportError:
    proto_available = False

# Import test server
if grpc_testing_available and proto_available:
    from tests.gateway.test_grpc_server import GrpcTestServer, requires_grpc_testing
    from intentlayer_sdk.gateway.client import GatewayClient, DidDocument
    from intentlayer_sdk.gateway.exceptions import (
        GatewayError, GatewayConnectionError, GatewayTimeoutError,
        QuotaExceededError, GatewayResponseError
    )

# Configure logger
logger = logging.getLogger(__name__)

# Skip all tests in this module if dependencies aren't available
pytestmark = pytest.mark.skipif(
    not (grpc_testing_available and proto_available),
    reason="grpc_testing or proto stubs not available"
)


@requires_grpc_testing
class TestGatewayClientIntegration:
    """Integration tests for the Gateway client with in-process server."""
    
    def test_register_did_success(self, gateway_test_client):
        """Test successful DID registration."""
        # Create a test DID document
        did = "did:key:test123"
        pub_key = b"test_key"
        
        # Register the DID
        response = gateway_test_client.register_did(
            did=did,
            pub_key=pub_key,
            org_id="test_org",
            label="test_integration"
        )
        
        # Verify response
        assert response.success is True
        assert response.hash == "0x" + "1" * 64  # Matches test server's success hash
        assert response.gas_used == 21000
        assert response.error == ""
        assert response.error_code == "UNKNOWN_UNSPECIFIED"
    
    def test_register_did_already_registered(self, grpc_test_server, gateway_test_client):
        """Test DID registration when DID is already registered."""
        # Pre-register a DID in the test server
        did = "did:key:already_registered_test"
        grpc_test_server.servicer.registered_dids.add(did)
        
        # Try to register the same DID
        response = gateway_test_client.register_did(
            did=did,
            pub_key=b"test_key"
        )
        
        # Verify response
        assert response.success is False
        assert response.error_code == "ALREADY_REGISTERED"
    
    def test_register_did_quota_exceeded(self, gateway_test_client):
        """Test DID registration with quota exceeded."""
        # Use special DID that triggers quota exceeded in test server
        did = "did:key:quota_exceeded"
        
        # Attempt to register DID that will exceed quota
        with pytest.raises(QuotaExceededError, match="DID registration quota exceeded"):
            gateway_test_client.register_did(
                did=did,
                pub_key=b"test_key"
            )
    
    def test_register_did_invalid_did(self, gateway_test_client):
        """Test DID registration with invalid DID format."""
        # Use special DID that triggers invalid DID error in test server
        did = "did:key:invalid_did"
        
        # Attempt to register invalid DID
        with pytest.raises(GatewayResponseError, match="Invalid DID format"):
            gateway_test_client.register_did(
                did=did,
                pub_key=b"test_key"
            )
    
    def test_register_did_unavailable(self, gateway_test_client):
        """Test DID registration when service is unavailable."""
        # Use special DID that triggers unavailable error in test server
        did = "did:key:unavailable"
        
        # Attempt to register DID when service is unavailable
        with pytest.raises(GatewayConnectionError, match="Gateway service unavailable"):
            gateway_test_client.register_did(
                did=did,
                pub_key=b"test_key",
                max_retries=0  # Disable retries for this test
            )
    
    def test_register_did_resource_exhausted(self, gateway_test_client):
        """Test DID registration when resources are exhausted."""
        # Use special DID that triggers resource exhausted error in test server
        did = "did:key:resource_exhausted"
        
        # Attempt to register DID when resources are exhausted
        with pytest.raises(GatewayError, match="gRPC error during DID registration"):
            gateway_test_client.register_did(
                did=did,
                pub_key=b"test_key",
                max_retries=0  # Disable retries for this test
            )
    
    def test_register_did_retry_success(self, grpc_test_server, gateway_test_client):
        """Test DID registration with retries."""
        # Create a test DID
        did = "did:key:retry_test"
        pub_key = b"test_key"
        
        # Configure a handler that fails initially then succeeds
        attempt_count = [0]  # Use list for mutable state
        
        def retry_handler(request, context):
            attempt_count[0] += 1
            
            # Fail on first attempt
            if attempt_count[0] == 1:
                context.set_code(grpc.StatusCode.UNAVAILABLE)
                context.set_details("Temporary unavailable, please retry")
                return None
                
            # Succeed on second attempt
            receipt = ProtoTxReceipt(
                hash="0x" + "2" * 64,  # Different hash to verify retry response
                gas_used=21000,
                success=True,
                error="",
                error_code=ProtoRegisterError.UNKNOWN_UNSPECIFIED
            )
            return RegisterDidResponse(receipt=receipt)
        
        # Set the custom handler
        grpc_test_server.set_register_did_handler(retry_handler)
        
        # Register DID with retry
        response = gateway_test_client.register_did(
            did=did,
            pub_key=pub_key,
            max_retries=3  # Allow retries
        )
        
        # Verify response from the second attempt
        assert response.success is True
        assert response.hash == "0x" + "2" * 64  # Hash from second attempt
        assert attempt_count[0] == 2  # Verify it took 2 attempts

    def test_register_did_with_custom_timeout(self, gateway_test_client):
        """Test DID registration with custom timeout."""
        # Create a test DID document
        did = "did:key:timeout_test"
        pub_key = b"test_key"
        
        # Register the DID with custom timeout
        response = gateway_test_client.register_did(
            did=did,
            pub_key=pub_key,
            retry_timeout=10  # Custom timeout
        )
        
        # Verify response
        assert response.success is True
        
    def test_register_did_with_metadata(self, grpc_test_server, gateway_test_client):
        """Test DID registration with metadata."""
        # Create a test DID
        did = "did:key:metadata_test"
        pub_key = b"test_key"
        
        # Set API key on client
        test_api_key = "test_api_key_123"
        gateway_test_client.api_key = test_api_key
        
        # Register the DID
        response = gateway_test_client.register_did(
            did=did,
            pub_key=pub_key
        )
        
        # Verify response
        assert response.success is True
        
        # Verify metadata was sent
        assert "RegisterDid" in grpc_test_server.servicer.metadata_received
        metadata_dict = grpc_test_server.servicer.metadata_received["RegisterDid"]
        assert "authorization" in metadata_dict
        assert metadata_dict["authorization"] == f"Bearer {test_api_key}"

    def test_register_did_with_custom_handler(self, grpc_test_server, gateway_test_client):
        """Test DID registration with a custom handler."""
        # Create a test DID document
        did = "did:key:custom_test"
        pub_key = b"test_key"
        
        # Create a custom handler that inspects the request
        def custom_handler(request, context):
            # Verify request contents
            assert request.document.did == did
            assert request.document.pub_key == pub_key
            
            # Return custom response
            receipt = ProtoTxReceipt(
                hash="0x" + "custom" * 10 + "0" * 4,
                gas_used=12345,
                success=True,
                error="",
                error_code=ProtoRegisterError.UNKNOWN_UNSPECIFIED
            )
            return RegisterDidResponse(receipt=receipt)
        
        # Set the custom handler
        grpc_test_server.set_register_did_handler(custom_handler)
        
        # Register the DID
        response = gateway_test_client.register_did(
            did=did,
            pub_key=pub_key
        )
        
        # Verify custom response
        assert response.success is True
        assert response.hash.startswith("0x" + "custom" * 10)
        assert response.gas_used == 12345


@requires_grpc_testing
class TestTransportIntegration:
    """Integration tests for the ProtoTransport with in-process server."""
    
    def test_transport_register_did(self, gateway_test_transport):
        """Test DID registration through the transport layer."""
        # Create test parameters
        did = "did:key:transport_test"
        pub_key = b"transport_key"
        
        # Register DID through transport
        response = gateway_test_transport.register_did(
            did=did,
            pub_key=pub_key,
            org_id="transport_org",
            label="transport_test"
        )
        
        # Verify response
        assert response.success is True
        assert response.hash == "0x" + "1" * 64
        assert response.gas_used == 21000
        assert response.error == ""
        assert response.error_code == "UNKNOWN_UNSPECIFIED"