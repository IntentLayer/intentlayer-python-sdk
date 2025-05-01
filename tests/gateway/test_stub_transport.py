"""
Tests for the StubTransport implementation.

These tests verify that the StubTransport behaves correctly in various scenarios,
including error cases.
"""
import pytest
from unittest.mock import patch

from intentlayer_sdk.gateway.stub_transport import StubTransport
from intentlayer_sdk.gateway.exceptions import (
    GatewayConnectionError, QuotaExceededError, RegisterError
)


class TestStubTransport:
    """Tests for the StubTransport implementation."""
    
    def test_is_available(self):
        """Test that StubTransport is always available."""
        transport = StubTransport()
        assert transport.is_available() is True
    
    def test_initialization(self):
        """Test StubTransport initialization."""
        transport = StubTransport()
        assert transport.initialized is False
        
        # Initialize the transport
        transport.initialize("https://example.com")
        assert transport.initialized is True
        assert transport.gateway_url == "https://example.com"
    
    def test_register_did_without_initialization(self):
        """Test that register_did raises GatewayConnectionError if not initialized."""
        transport = StubTransport()
        
        with pytest.raises(GatewayConnectionError):
            transport.register_did("did:key:test")
    
    def test_register_did_invalid_did(self):
        """Test register_did with invalid DID."""
        transport = StubTransport()
        transport.initialize("https://example.com")
        
        # Test with a very short DID
        receipt = transport.register_did("did:key:x")
        
        assert receipt.success is False
        assert receipt.error_code == RegisterError.INVALID_DID
        assert "DID is too short or invalid" in receipt.error
    
    def test_register_did_already_registered(self):
        """Test register_did with an already registered DID."""
        transport = StubTransport()
        transport.initialize("https://example.com")
        
        # Test with the special "already registered" DID
        receipt = transport.register_did("did:key:already_registered")
        
        assert receipt.success is False
        assert receipt.error_code == RegisterError.ALREADY_REGISTERED
        assert "already been registered" in receipt.error
    
    def test_register_did_quota_exceeded(self):
        """Test register_did with quota exceeded."""
        transport = StubTransport()
        transport.initialize("https://example.com")
        
        # Test with the special "quota_exceeded" org_id
        with pytest.raises(QuotaExceededError) as excinfo:
            transport.register_did("did:key:valid_did", org_id="quota_exceeded")
        
        assert "quota exceeded" in str(excinfo.value).lower()
    
    def test_register_did_success(self):
        """Test successful DID registration."""
        transport = StubTransport()
        transport.initialize("https://example.com")
        
        # Use a sample valid DID that doesn't trigger errors
        with patch('time.sleep'):  # Skip the sleep for faster tests
            receipt = transport.register_did("did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH")
        
        assert receipt.success is True
        assert receipt.error == ""
        assert receipt.error_code == RegisterError.UNKNOWN_UNSPECIFIED
        assert receipt.gas_used == 21000
        assert receipt.hash.startswith("0x")
    
    def test_close(self):
        """Test that close doesn't raise exceptions."""
        transport = StubTransport()
        # Should not raise any exceptions
        transport.close()