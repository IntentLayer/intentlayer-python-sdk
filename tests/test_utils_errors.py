"""
Tests for error paths in the utils module.
"""
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from intentlayer_sdk.utils import create_envelope_hash, ipfs_cid_to_bytes
from intentlayer_sdk.envelope import create_envelope
from intentlayer_sdk.exceptions import EnvelopeError

def test_create_envelope_hash_type_error():
    with pytest.raises(TypeError):
        create_envelope_hash("not a dict")

def test_create_envelope_hash_unserializable():
    # JSON can't serialize a set
    with pytest.raises(ValueError):
        create_envelope_hash({"foo": {1,2,3}})

key = Ed25519PrivateKey.generate()

@pytest.mark.parametrize("arg, val, exc", [
    ("prompt", "", ValueError),
    ("model_id", "", ValueError),
    ("tool_id", "", ValueError),
    ("did", "", ValueError),
])
def test_create_envelope_missing_required(arg, val, exc):
    kwargs = dict(
        prompt="ok",
        model_id="model123",
        tool_id="tool123",
        did="did:key:test123",
        private_key=key,
        stake_wei=1,
        timestamp_ms=1,
    )
    kwargs[arg] = val
    with pytest.raises(exc):
        create_envelope(**kwargs)

def test_create_envelope_metadata_type_error():
    with pytest.raises(TypeError):
        create_envelope(
            prompt="hi", 
            model_id="model123", 
            tool_id="tool123", 
            did="did:key:test123",
            private_key=key, 
            stake_wei=1, 
            timestamp_ms=1,
            metadata="not a dict"
        )

def test_ipfs_cid_to_bytes_non_str():
    with pytest.raises(EnvelopeError):
        ipfs_cid_to_bytes(1234)  # must be string

def test_ipfs_cid_to_bytes_bad_hex():
    with pytest.raises(EnvelopeError):
        ipfs_cid_to_bytes("0xzznothex")

def test_ipfs_cid_to_bytes_invalid_base58_no_fallback():
    with pytest.raises(EnvelopeError):
        ipfs_cid_to_bytes("not-a-valid-base58")
        
def test_ipfs_cid_to_bytes_invalid_base58_with_fallback():
    result = ipfs_cid_to_bytes("not-a-valid-base58", allow_utf8_fallback=True)
    assert result == b"not-a-valid-base58"
