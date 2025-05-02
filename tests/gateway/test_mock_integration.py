"""
Integration tests for Gateway client with mock stubs.

These tests verify that the Gateway client can properly communicate with stub
implementations of gRPC services without requiring network connections.
"""
import pytest
import logging
import os
import grpc
from unittest.mock import patch, MagicMock

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

# Only import when proto is available
if proto_available:
    from intentlayer_sdk.gateway.client import GatewayClient, DidDocument
    from intentlayer_sdk.gateway.exceptions import (
        GatewayError, GatewayConnectionError, GatewayTimeoutError,
        QuotaExceededError, GatewayResponseError
    )

# Configure logger
logger = logging.getLogger(__name__)

# Skip all tests in this module if dependencies aren't available
pytestmark = pytest.mark.skipif(
    not proto_available,
    reason="proto stubs not available"
)


@pytest.fixture
def mock_gateway_stub():
    """Create a mock gateway stub for testing."""
    stub = MagicMock()
    
    # Configure RegisterDid to return success by default
    success_receipt = ProtoTxReceipt(
        hash="0x" + "1" * 64,
        gas_used=21000,
        success=True,
        error="",
        error_code=ProtoRegisterError.UNKNOWN_UNSPECIFIED
    )
    success_response = RegisterDidResponse(receipt=success_receipt)
    stub.RegisterDid.return_value = success_response
    
    return stub


@pytest.fixture
def gateway_test_client(mock_gateway_stub):
    """
    Create a gateway client with a mock stub.
    
    Args:
        mock_gateway_stub: The mock stub to use
        
    Returns:
        GatewayClient with mock stub
    """
    # Create the client with a dummy URL
    client = GatewayClient("https://test.example.com")
    
    # Replace the stub with our mock
    client.stub = mock_gateway_stub
    
    return client


class TestGatewayClientIntegration:
    """Integration tests for Gateway client with mock stubs."""
    
    def test_register_did_success(self, gateway_test_client, mock_gateway_stub):
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
        assert response.hash == "0x" + "1" * 64
        assert response.gas_used == 21000
        assert response.error == ""
        assert response.error_code == "UNKNOWN_UNSPECIFIED"
        
        # Verify stub was called with correct parameters
        assert mock_gateway_stub.RegisterDid.called
        request = mock_gateway_stub.RegisterDid.call_args[0][0]
        assert request.document.did == did
        assert request.document.pub_key == pub_key
        assert request.document.org_id == "test_org"
        assert request.document.label == "test_integration"
    
    def test_register_did_already_registered(self, gateway_test_client, mock_gateway_stub):
        """Test registration of an already registered DID."""
        # Configure stub to return already registered error
        already_reg_receipt = ProtoTxReceipt(
            hash="0x0000000000000000000000000000000000000000000000000000000000000000",
            gas_used=0,
            success=False,
            error="DID already registered",
            error_code=ProtoRegisterError.ALREADY_REGISTERED
        )
        already_reg_response = RegisterDidResponse(receipt=already_reg_receipt)
        mock_gateway_stub.RegisterDid.return_value = already_reg_response
        
        # Register the DID
        response = gateway_test_client.register_did(
            did="did:key:already_registered",
            pub_key=b"test_key"
        )
        
        # Verify response
        assert response.success is False
        assert response.error_code == "ALREADY_REGISTERED"
        assert "DID already registered" in response.error
        
        # Verify stub was called
        assert mock_gateway_stub.RegisterDid.called
    
    def test_register_did_error_response(self, gateway_test_client, mock_gateway_stub):
        """Test DID registration with an error response."""
        # Configure stub to return error
        error_receipt = ProtoTxReceipt(
            hash="0x0000000000000000000000000000000000000000000000000000000000000000",
            gas_used=0,
            success=False,
            error="General error from Gateway",
            error_code=ProtoRegisterError.INVALID_DID
        )
        error_response = RegisterDidResponse(receipt=error_receipt)
        mock_gateway_stub.RegisterDid.return_value = error_response
        
        # Attempt to register DID
        with pytest.raises(GatewayError, match="Failed to register DID"):
            gateway_test_client.register_did(
                did="did:key:error_test",
                pub_key=b"test_key",
                max_retries=0
            )
        
        # Verify stub was called
        assert mock_gateway_stub.RegisterDid.called
    
    def test_register_did_multiple_calls(self, gateway_test_client, mock_gateway_stub):
        """Test multiple registration calls."""
        # Create first response (success)
        first_response = RegisterDidResponse(
            receipt=ProtoTxReceipt(
                hash="0x" + "1" * 64,
                gas_used=21000,
                success=True,
                error="",
                error_code=ProtoRegisterError.UNKNOWN_UNSPECIFIED
            )
        )
        
        # Create second response (also success but different hash)
        second_response = RegisterDidResponse(
            receipt=ProtoTxReceipt(
                hash="0x" + "2" * 64,
                gas_used=21000,
                success=True,
                error="",
                error_code=ProtoRegisterError.UNKNOWN_UNSPECIFIED
            )
        )
        
        # Configure stub to return different responses for each call
        mock_gateway_stub.RegisterDid.side_effect = [first_response, second_response]
        
        # First call
        response1 = gateway_test_client.register_did(
            did="did:key:first_test",
            pub_key=b"test_key1"
        )
            
        # Second call
        response2 = gateway_test_client.register_did(
            did="did:key:second_test", 
            pub_key=b"test_key2"
        )
                
        # Verify responses
        assert response1.success is True
        assert response1.hash == "0x" + "1" * 64
        
        assert response2.success is True
        assert response2.hash == "0x" + "2" * 64
        
        # Verify stub was called twice
        assert mock_gateway_stub.RegisterDid.call_count == 2
    
    def test_register_did_with_metadata(self, gateway_test_client, mock_gateway_stub):
        """Test sending metadata with request."""
        # Set API key
        test_api_key = "test_api_key_123"
        gateway_test_client.api_key = test_api_key
        
        # Register DID
        gateway_test_client.register_did(
            did="did:key:metadata_test",
            pub_key=b"test_key"
        )
        
        # Verify metadata was passed
        _, kwargs = mock_gateway_stub.RegisterDid.call_args
        assert "metadata" in kwargs
        assert len(kwargs["metadata"]) > 0
        
        # Check that metadata contains authorization
        auth_found = False
        for key, value in kwargs["metadata"]:
            if key == "authorization":
                auth_found = True
                assert value == f"Bearer {test_api_key}"
                break
        
        assert auth_found, "Authorization metadata not found"