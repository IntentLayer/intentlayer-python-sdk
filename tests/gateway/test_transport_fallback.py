"""
Tests for the gateway transport layer fallback behavior.

These tests verify that the transport layer falls back to StubTransport
when gRPC/protocol buffers are not available.
"""
import pytest
from unittest.mock import patch, MagicMock

from intentlayer_sdk.gateway.transport import get_transport


class TestTransportFallback:
    """Tests for the gateway transport layer fallback behavior."""
    
    def test_fallback_to_stub_when_grpc_unavailable(self):
        """Test that get_transport falls back to StubTransport when gRPC is unavailable."""
        # Mock the proto transport to be unavailable
        with patch('intentlayer_sdk.gateway.transport.get_proto_transport', return_value=None), \
             patch('intentlayer_sdk.gateway.transport.get_stub_transport') as mock_get_stub:
            
            # Set up the stub transport mock
            mock_stub_transport = MagicMock()
            mock_get_stub.return_value = mock_stub_transport
            
            # Call get_transport with prefer_proto=True
            transport = get_transport(prefer_proto=True)
            
            # Verify it falls back to stub transport
            assert transport == mock_stub_transport
            mock_get_stub.assert_called_once()
    
    def test_direct_use_of_stub_transport(self):
        """Test that get_transport uses StubTransport when prefer_proto=False."""
        with patch('intentlayer_sdk.gateway.transport.get_proto_transport') as mock_get_proto, \
             patch('intentlayer_sdk.gateway.transport.get_stub_transport') as mock_get_stub:
            
            # Set up the transport mocks
            mock_proto_transport = MagicMock()
            mock_stub_transport = MagicMock()
            mock_get_proto.return_value = mock_proto_transport
            mock_get_stub.return_value = mock_stub_transport
            
            # Call get_transport with prefer_proto=False
            transport = get_transport(prefer_proto=False)
            
            # Verify it uses stub transport directly without trying proto
            assert transport == mock_stub_transport
            mock_get_stub.assert_called_once()
            mock_get_proto.assert_not_called()