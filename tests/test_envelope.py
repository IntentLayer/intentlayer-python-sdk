"""
Tests for the envelope module.
"""
import pytest
import time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from intentlayer_sdk.envelope import CallEnvelope, create_envelope

class TestCallEnvelope:
    """Test CallEnvelope model and validation."""
    
    def test_valid_envelope(self):
        """Test creating valid envelope."""
        env = CallEnvelope(
            did="did:key:123",
            model_id="gpt-4",
            prompt_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            tool_id="test",
            timestamp_ms=1234567890,
            stake_wei="1000000000000000",
            sig_ed25519="abc123"
        )
        assert env.did == "did:key:123"
        assert env.model_id == "gpt-4"
    
    def test_invalid_did(self):
        """Test did validation."""
        with pytest.raises(ValidationError) as exc_info:
            CallEnvelope(
                did="invalid",  # Missing did: prefix
                model_id="gpt-4",
                prompt_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                tool_id="test",
                timestamp_ms=1234567890,
                stake_wei="1000000000000000",
                sig_ed25519="abc123"
            )
        assert "DID must start with 'did:'" in str(exc_info.value)
    
    def test_invalid_prompt_hash_length(self):
        """Test prompt_sha256 length validation."""
        with pytest.raises(ValidationError) as exc_info:
            CallEnvelope(
                did="did:key:123",
                model_id="gpt-4",
                prompt_sha256="abc123",  # Too short
                tool_id="test",
                timestamp_ms=1234567890,
                stake_wei="1000000000000000",
                sig_ed25519="abc123"
            )
        assert "prompt_sha256 must be a 64-character hex string" in str(exc_info.value)
    
    def test_invalid_prompt_hash_chars(self):
        """Test prompt_sha256 character validation."""
        with pytest.raises(ValidationError) as exc_info:
            CallEnvelope(
                did="did:key:123",
                model_id="gpt-4",
                prompt_sha256="X" * 64,  # Not hex
                tool_id="test",
                timestamp_ms=1234567890,
                stake_wei="1000000000000000",
                sig_ed25519="abc123"
            )
        assert "prompt_sha256 must be a hex string" in str(exc_info.value)
    
    def test_hash_method(self):
        """Test envelope hash method."""
        env = CallEnvelope(
            did="did:key:123",
            model_id="gpt-4",
            prompt_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            tool_id="test",
            timestamp_ms=1234567890,
            stake_wei="1000000000000000",
            sig_ed25519="abc123"
        )
        
        hash_bytes = env.hash()
        assert isinstance(hash_bytes, bytes)
        assert len(hash_bytes) == 32  # keccak256 hash is 32 bytes
        
        hex_hash = env.hex_hash()
        assert isinstance(hex_hash, str)
        assert hex_hash.startswith("0x")
        assert len(hex_hash) == 66  # 0x + 64 chars

class TestCreateEnvelope:
    """Test create_envelope utility function."""
    
    def test_create_envelope(self):
        """Test creating a complete envelope."""
        private_key = Ed25519PrivateKey.generate()
        prompt = "Test prompt"
        timestamp = int(time.time() * 1000)
        
        env = create_envelope(
            prompt=prompt,
            model_id="gpt-4",
            tool_id="test_tool",
            did="did:key:test123",
            private_key=private_key,
            stake_wei=1000000000000000,
            timestamp_ms=timestamp
        )
        
        # Verify fields
        assert env.did == "did:key:test123"
        assert env.model_id == "gpt-4"
        assert env.tool_id == "test_tool"
        assert env.timestamp_ms == timestamp
        assert env.stake_wei == "1000000000000000"
        assert env.sig_ed25519  # Should have a signature
        
        # Verify prompt hash
        import hashlib
        expected_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        assert env.prompt_sha256 == expected_hash
    
    def test_create_envelope_with_metadata(self):
        """Test creating envelope with metadata."""
        private_key = Ed25519PrivateKey.generate()
        metadata = {"user_id": "test123", "session_id": "abc456"}
        
        env = create_envelope(
            prompt="Test prompt",
            model_id="gpt-4",
            tool_id="test_tool",
            did="did:key:test123",
            private_key=private_key,
            stake_wei=1000000000000000,
            metadata=metadata
        )
        
        assert env.metadata == metadata