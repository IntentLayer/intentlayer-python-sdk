"""
Pytest fixtures for Gateway integration tests.

These fixtures provide test components including:
- In-process gRPC test server
- Gateway client connected to the test server
"""
import pytest
import logging
from typing import Optional
from unittest.mock import patch

# Skip fixtures if dependencies aren't available
try:
    import grpc
    import grpc_testing
    grpc_testing_available = True
except ImportError:
    grpc_testing_available = False

# Skip fixtures if proto stubs aren't available
try:
    from intentlayer_sdk.gateway.proto import (
        PROTO_AVAILABLE,
        GatewayServiceStub
    )
    proto_available = PROTO_AVAILABLE
except ImportError:
    proto_available = False

# Only define fixtures if dependencies are available
if grpc_testing_available and proto_available:
    from .test_grpc_server import GrpcTestServer
    from intentlayer_sdk.gateway.client import GatewayClient
    from intentlayer_sdk.gateway.proto_transport import ProtoTransport

    # Configure logger
    logger = logging.getLogger(__name__)

    @pytest.fixture
    def grpc_test_server():
        """
        Fixture providing an in-process gRPC test server.
        
        This fixture creates a fresh test server instance for each test,
        avoiding any state sharing between tests.
        
        Returns:
            GrpcTestServer instance
        """
        server = GrpcTestServer()
        yield server

    @pytest.fixture
    def grpc_test_channel(grpc_test_server):
        """
        Fixture providing a gRPC channel connected to the test server.
        
        This fixture creates a channel that can be used by gRPC clients
        to communicate with the test server without network connections.
        
        Args:
            grpc_test_server: The test server instance (injected by pytest)
            
        Returns:
            grpc_testing test channel
        """
        return grpc_test_server.get_test_channel()

    @pytest.fixture
    def gateway_test_client(grpc_test_server, monkeypatch):
        """
        Fixture providing a GatewayClient connected to the test server.
        
        This fixture creates a client configured to use the test server's
        channel, bypassing actual network connections.
        
        Args:
            grpc_test_server: The test server instance (injected by pytest)
            monkeypatch: Pytest's monkeypatch fixture
            
        Returns:
            GatewayClient instance connected to the test server
        """
        # Create test stub connected to the test server
        test_stub = grpc_test_server.get_stub()
        
        # Create the client with a dummy URL (will be patched)
        client = GatewayClient("https://test.example.com")
        
        # Replace the real stub with our test stub
        client.stub = test_stub
        
        # Mark that we're using real proto implementation
        monkeypatch.setattr("intentlayer_sdk.gateway.client.PROTO_AVAILABLE", True)
        
        return client

    @pytest.fixture
    def gateway_test_transport(grpc_test_server, monkeypatch):
        """
        Fixture providing a ProtoTransport connected to the test server.
        
        This fixture creates a transport configured to use the test server's
        channel, bypassing actual network connections.
        
        Args:
            grpc_test_server: The test server instance (injected by pytest)
            monkeypatch: Pytest's monkeypatch fixture
            
        Returns:
            ProtoTransport instance connected to the test server
        """
        # Create test stub connected to the test server
        test_stub = grpc_test_server.get_stub()
        
        # Create the transport
        transport = ProtoTransport()
        
        # Initialize with dummy URL
        transport.initialize("https://test.example.com")
        
        # Replace the real stub with our test stub
        transport.stub = test_stub
        
        return transport