"""
Tests for IPFS utility functions.
"""
import pytest
import base58
from intentlayer_sdk.utils import ipfs_cid_to_bytes
from intentlayer_sdk.exceptions import EnvelopeError

class TestIpfsCidToBytes:
    """Test ipfs_cid_to_bytes utility function."""
    
    def test_hex_cid(self):
        """Test conversion of hex CID."""
        cid = "0x1234567890abcdef"
        result = ipfs_cid_to_bytes(cid)
        assert result == bytes.fromhex("1234567890abcdef")
    
    def test_base58_cid(self):
        """Test conversion of base58 CID."""
        # Create a sample base58 value
        original_bytes = b"test_ipfs_cid"
        base58_cid = base58.b58encode(original_bytes).decode()
        
        # Convert back to bytes
        result = ipfs_cid_to_bytes(base58_cid)
        assert result == original_bytes
    
    def test_invalid_hex_cid(self):
        """Test invalid hex CID raises error."""
        cid = "0xGGGG"  # Invalid hex
        with pytest.raises(EnvelopeError) as exc_info:
            ipfs_cid_to_bytes(cid)
        assert "Invalid hex CID format" in str(exc_info.value)
    
    def test_invalid_base58_no_fallback(self):
        """Test invalid base58 CID raises error with fallback disabled."""
        cid = "$$$$"  # Invalid base58
        with pytest.raises(EnvelopeError) as exc_info:
            ipfs_cid_to_bytes(cid)
        assert "Failed to decode CID" in str(exc_info.value)
        assert "allow_utf8_fallback=True" in str(exc_info.value)
    
    def test_invalid_base58_with_fallback(self):
        """Test invalid base58 CID with fallback enabled."""
        cid = "$$$$"  # Invalid base58
        result = ipfs_cid_to_bytes(cid, allow_utf8_fallback=True)
        assert result == b"$$$$"
    
    def test_non_string_cid(self):
        """Test non-string CID raises error."""
        cid = 12345  # Not a string
        with pytest.raises(EnvelopeError) as exc_info:
            ipfs_cid_to_bytes(cid)
        assert "CID must be a string" in str(exc_info.value)