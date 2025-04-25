"""
Property-based tests for IntentLayer SDK.

These tests verify that properties hold true across many random inputs.
"""
import pytest
import re
from hypothesis import given, strategies as st, settings
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from intentlayer_sdk.utils import sha256_hex, create_envelope, create_envelope_hash
from intentlayer_sdk.models import CallEnvelope
from conftest import TEST_STAKE_WEI

# Define reasonable strategies for our inputs
prompt_strategy = st.text(min_size=1, max_size=1000)
model_id_strategy = st.text(min_size=1, max_size=100, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd'),  # Letters and numbers
    whitelist_characters='-_@.'  # Additional allowed characters
))
tool_id_strategy = st.from_regex(r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/[a-zA-Z0-9._~:/?#[\]@!$&\'()*+,;=%-]*)?', fullmatch=True)
did_strategy = st.from_regex(r'did:([a-z]+):([a-zA-Z0-9.%-]+)(:.+)?', fullmatch=True)
stake_wei_strategy = st.integers(min_value=10**15, max_value=10**18).map(str)
metadata_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'))),
    values=st.one_of(
        st.text(max_size=100),
        st.integers(-1000, 1000),
        st.booleans()
    ),
    max_size=5
)

@settings(max_examples=50)  # Limit number of test cases to keep runtime reasonable
@given(
    prompt=prompt_strategy,
    model_id=model_id_strategy,
    tool_id=tool_id_strategy,
    did=did_strategy,
    metadata=metadata_strategy
)
def test_envelope_creation_properties(prompt, model_id, tool_id, did, metadata):
    """
    Verify that envelope creation produces valid, consistent results
    across a wide range of inputs.
    """
    # Generate a new key for each test
    private_key = Ed25519PrivateKey.generate()
    
    # Create envelope
    envelope = create_envelope(
        prompt=prompt,
        model_id=model_id,
        tool_id=tool_id,
        did=did,
        private_key=private_key,
        stake_wei=TEST_STAKE_WEI,
        metadata=metadata
    )
    
    # Property 1: Envelope should have all required fields
    assert envelope.did == did
    assert envelope.model_id == model_id
    assert envelope.tool_id == tool_id
    assert envelope.stake_wei == str(TEST_STAKE_WEI)
    assert envelope.prompt_sha256 is not None
    assert envelope.timestamp_ms is not None
    assert envelope.sig_ed25519 is not None
    assert envelope.metadata == metadata
    
    # Property 2: Prompt SHA256 should match the expected hash
    assert envelope.prompt_sha256 == sha256_hex(prompt)
    
    # Property 3: Ed25519 signature should have correct format (base64url)
    assert isinstance(envelope.sig_ed25519, str)
    assert len(envelope.sig_ed25519) > 50  # Ed25519 signatures are ~86 chars in base64url
    # Check for base64url format (alphanumeric plus '-' and '_')
    assert re.match(r'^[A-Za-z0-9_-]+$', envelope.sig_ed25519)
    
    # Property 4: Creating hash should work deterministically
    envelope_dict = envelope.model_dump()
    hash1 = create_envelope_hash(envelope_dict)
    hash2 = create_envelope_hash(envelope_dict)
    assert hash1 == hash2
    assert len(hash1) == 32  # 32 bytes = 256 bits
    
    # Property 5: Model serialization should be reversible
    envelope_dict = envelope.model_dump()
    envelope2 = CallEnvelope(**envelope_dict)
    assert envelope.did == envelope2.did
    assert envelope.model_id == envelope2.model_id
    assert envelope.tool_id == envelope2.tool_id
    assert envelope.stake_wei == envelope2.stake_wei
    assert envelope.prompt_sha256 == envelope2.prompt_sha256
    assert envelope.timestamp_ms == envelope2.timestamp_ms
    assert envelope.sig_ed25519 == envelope2.sig_ed25519


@settings(max_examples=50)
@given(
    did=did_strategy,
    model_id=model_id_strategy,
    tool_id=tool_id_strategy,
    prompt_sha256=st.text(min_size=64, max_size=64, alphabet='0123456789abcdef'),
    timestamp_ms=st.integers(min_value=1600000000000, max_value=2000000000000),
    stake_wei=stake_wei_strategy,
    signature=st.text(min_size=60, max_size=100)
)
def test_envelope_hash_determinism(did, model_id, tool_id, prompt_sha256, timestamp_ms, stake_wei, signature):
    """
    Verify that envelope hashing is deterministic and order-independent.
    """
    # Create base envelope data
    envelope_data = {
        "did": did,
        "model_id": model_id,
        "tool_id": tool_id,
        "prompt_sha256": prompt_sha256,
        "timestamp_ms": timestamp_ms,
        "stake_wei": stake_wei,
        "sig_ed25519": signature
    }
    
    # Create shuffled versions of the same data
    import random
    
    # Helper to shuffle dict items (create new dict with different key order)
    def shuffle_dict(d):
        items = list(d.items())
        random.shuffle(items)
        return dict(items)
    
    shuffled1 = shuffle_dict(envelope_data)
    shuffled2 = shuffle_dict(envelope_data)
    
    # Property: Hash should be the same regardless of key order
    hash_original = create_envelope_hash(envelope_data)
    hash_shuffled1 = create_envelope_hash(shuffled1)
    hash_shuffled2 = create_envelope_hash(shuffled2)
    
    assert hash_original == hash_shuffled1 == hash_shuffled2
    
    # Important property: The hash depends on all fields in a deterministic way
    # Changing any field should change the hash
    envelope_with_extra = envelope_data.copy()
    envelope_with_extra["extra_field"] = "Adding this should change the hash"
    hash_with_extra = create_envelope_hash(envelope_with_extra)
    
    # Hash should be different with extra fields
    assert hash_original != hash_with_extra
    
    # But always the same for the same input
    assert hash_with_extra == create_envelope_hash(envelope_with_extra)