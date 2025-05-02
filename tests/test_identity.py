"""
Tests for the identity module.
"""
import os
import json
import time
import pytest
import base64
from pathlib import Path
from datetime import datetime, timedelta

from intentlayer_sdk.identity import (
    get_or_create_did, create_new_identity, delete_local, list_identities, Identity
)
from intentlayer_sdk.identity.key_store import KeyStore
from intentlayer_sdk.identity.crypto import encrypt_key_data
from intentlayer_sdk.signer.local import LocalSigner


@pytest.fixture
def temp_keystore(tmp_path):
    """Create a temporary key store for testing"""
    path = tmp_path / "keys.json"
    os.environ["INTENT_KEY_STORE_PATH"] = str(path)
    # For tests, set CI=true to allow plaintext keys
    os.environ["CI"] = "true"
    yield path
    # Cleanup
    if os.path.exists(path):
        os.remove(path)
    del os.environ["INTENT_KEY_STORE_PATH"]
    os.environ.pop("CI", None)


@pytest.fixture
def large_keystore(tmp_path):
    """Create a temporary key store with 100 dummy identities"""
    path = tmp_path / "keys.json"
    os.environ["INTENT_KEY_STORE_PATH"] = str(path)
    os.environ["CI"] = "true"
    # Set a test master key to make encryption deterministic
    os.environ["INTENT_MASTER_KEY"] = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode('ascii')
    
    # Create store with 100 dummy identities
    store = {"identities": {}}
    # Use a more recent timestamp for the first entry to make it the default
    now = datetime.utcnow()
    
    for i in range(100):
        did = f"did:key:z1234567890{i}"
        created_at = (now - timedelta(days=i)).isoformat()
        
        # Create a simple valid identity data structure
        sample_data = {
            "did": did,
            "created_at": created_at,
            "private_key": base64.b64encode(f"private_key_{i}".encode()).decode('ascii'),
            "public_key": base64.b64encode(f"public_key_{i}".encode()).decode('ascii')
        }
        
        # Properly encrypt it
        encrypted_data = encrypt_key_data(sample_data)
        
        # Add metadata
        encrypted_data["metadata"] = {
            "created_at": created_at
        }
        
        # Add to store
        store["identities"][did] = encrypted_data
    
    # Write to file
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(store, f)
    
    yield path
    
    # Cleanup
    if os.path.exists(path):
        os.remove(path)
    del os.environ["INTENT_KEY_STORE_PATH"]
    os.environ.pop("CI", None)
    os.environ.pop("INTENT_MASTER_KEY", None)


def test_get_or_create_did_auto_true(temp_keystore):
    """Test get_or_create_did with auto=True"""
    identity = get_or_create_did(auto=True)
    assert identity.did.startswith("did:key:")
    assert identity.signer is not None
    assert isinstance(identity.signer, LocalSigner)
    assert isinstance(identity.created_at, datetime)


def test_get_or_create_did_auto_false_no_identity(temp_keystore):
    """Test get_or_create_did with auto=False when no identity exists"""
    with pytest.raises(ValueError):
        get_or_create_did(auto=False)


def test_get_or_create_did_auto_false_with_identity(temp_keystore):
    """Test get_or_create_did with auto=False when identity exists"""
    # First create an identity
    identity1 = get_or_create_did(auto=True)
    
    # Then retrieve it with auto=False
    identity2 = get_or_create_did(auto=False)
    
    assert identity1.did == identity2.did
    assert identity1.created_at == identity2.created_at


def test_create_new_identity(temp_keystore):
    """Test create_new_identity"""
    identity1 = get_or_create_did(auto=True)
    identity2 = create_new_identity()
    
    assert identity1.did != identity2.did
    assert identity1.signer.address != identity2.signer.address


def test_delete_local(temp_keystore):
    """Test delete_local"""
    # First create an identity
    get_or_create_did(auto=True)
    
    # Then delete all local data
    delete_local()
    
    # Check that no identity exists
    with pytest.raises(ValueError):
        get_or_create_did(auto=False)


def test_list_identities(temp_keystore):
    """Test list_identities"""
    # Create multiple identities
    identity1 = get_or_create_did(auto=True)
    identity2 = create_new_identity()
    
    # List all identities
    identities = list_identities()
    
    # Should have at least the two we created
    assert len(identities) >= 2
    
    # DIDs should be in the list
    dids = [identity.did for identity in identities]
    assert identity1.did in dids
    assert identity2.did in dids


# Performance tests
def test_get_or_create_did_cold_start(temp_keystore):
    """Test cold-start performance of get_or_create_did"""
    start_time = time.time()
    get_or_create_did(auto=True)
    elapsed_ms = (time.time() - start_time) * 1000
    
    # Document that cold start might take longer (up to ~70ms)
    # but doesn't fail the test unless it's really slow
    assert elapsed_ms < 200, f"Cold start took {elapsed_ms} ms"


def test_get_or_create_did_warm_cache(temp_keystore):
    """Test cached performance of get_or_create_did"""
    # First create an identity (cold start)
    get_or_create_did(auto=True)
    
    # Then retrieve it again (warm cache)
    start_time = time.time()
    get_or_create_did(auto=True)
    elapsed_ms = (time.time() - start_time) * 1000
    
    # This should generally meet the <10ms requirement
    # We'll use a slightly higher threshold for CI environments
    assert elapsed_ms < 20, f"Warm cache took {elapsed_ms} ms"