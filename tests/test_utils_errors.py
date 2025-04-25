"""
Tests for error paths in the utils module.
"""
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from intentlayer_sdk.utils import create_envelope_hash, create_envelope, ipfs_cid_to_bytes
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
        model_id="m",
        tool_id="t",
        did="d",
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
            prompt="hi", model_id="m", tool_id="t", did="d",
            private_key=key, stake_wei=1, timestamp_ms=1,
            metadata="not a dict"
        )

def test_ipfs_cid_to_bytes_non_str():
    with pytest.raises(EnvelopeError):
        ipfs_cid_to_bytes(1234)  # must be string

def test_ipfs_cid_to_bytes_bad_hex():
    with pytest.raises(EnvelopeError):
        ipfs_cid_to_bytes("0xzznothex")
