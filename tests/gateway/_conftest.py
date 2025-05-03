"""
Pytest fixtures for Gateway integration tests.

These fixtures provide test components for gateway client testing.
"""
import pytest
import logging
from typing import Optional
from unittest.mock import patch, MagicMock

# If proto stubs are available, import classes for the fixtures
try:
    import grpc
    # Ensure grpc.__version__ exists for gateway_pb2_grpc import
    if not hasattr(grpc, '__version__'):
        grpc.__version__ = "1.71.0"  # Use the version from pyproject.toml
    
    from intentlayer_sdk.gateway.proto import (
        PROTO_AVAILABLE,
        RegisterError as ProtoRegisterError,
        DidDocument as ProtoDidDocument,
        TxReceipt as ProtoTxReceipt,
        RegisterDidRequest,
        RegisterDidResponse,
        GatewayServiceStub
    )
    
    # Only attempt imports if proto modules are available
    if PROTO_AVAILABLE:
        from intentlayer_sdk.gateway.client import GatewayClient, DidDocument
        from intentlayer_sdk.gateway.proto_transport import ProtoTransport
    else:
        GatewayClient = None
        ProtoTransport = None
except ImportError:
    PROTO_AVAILABLE = False
    GatewayClient = None
    ProtoTransport = None

# Configure logger
logger = logging.getLogger(__name__)

@pytest.fixture
def mock_gateway_stub():
    """Create a mock gateway stub for testing."""
    if not PROTO_AVAILABLE:
        pytest.skip("Proto stubs not available")
        
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
    if not PROTO_AVAILABLE or GatewayClient is None:
        pytest.skip("GatewayClient not available")
        
    # Create the client with a dummy URL
    client = GatewayClient("https://test.example.com")
    
    # Replace the stub with our mock
    client.stub = mock_gateway_stub
    
    return client


@pytest.fixture
def gateway_test_transport(mock_gateway_stub):
    """
    Create a gateway transport with a mock stub.
    
    Args:
        mock_gateway_stub: The mock stub to use
        
    Returns:
        ProtoTransport with mock stub
    """
    if not PROTO_AVAILABLE or ProtoTransport is None:
        pytest.skip("ProtoTransport not available")
        
    # Create the transport
    transport = ProtoTransport()
    
    # Initialize with dummy URL
    transport.initialize("https://test.example.com")
    
    # Replace the stub with our mock
    transport.stub = mock_gateway_stub
    
    return transport