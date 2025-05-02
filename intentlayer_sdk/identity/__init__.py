"""
Identity module for the IntentLayer SDK.

This module handles key pair generation, storage, and DID derivation
for digital identities used with the IntentLayer protocol.
"""
import os
import time
import logging
import json
import base64
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any, Union, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

from intentlayer_sdk.signer.local import LocalSigner
from intentlayer_sdk.identity.key_store import KeyStore
from intentlayer_sdk.identity.crypto import (
    generate_ed25519_keypair, derive_did_from_pubkey, 
    encrypt_key_data, decrypt_key_data
)
from intentlayer_sdk.identity.ec_constants import SECP256K1_N, SECP256K1_MIN, SECP256K1_MAX
from intentlayer_sdk.identity.types import Identity
from intentlayer_sdk.identity.registration import extract_org_id_from_api_key, IdentityManager

__all__ = [
    'get_or_create_did',
    'create_new_identity',
    'delete_local',
    'list_identities',
    'Identity',
    'extract_org_id_from_api_key',
    'IdentityManager'
]

logger = logging.getLogger(__name__)

# Global KeyStore instance with caching for performance
_key_store = None
_key_store_path_cache = None


def _get_key_store() -> KeyStore:
    """Get or create the global KeyStore instance"""
    global _key_store, _key_store_path_cache
    
    # Get current path from env var
    path = os.environ.get("INTENT_KEY_STORE_PATH")
    
    # If path changed or first call, create/recreate the store
    if _key_store is None or path != _key_store_path_cache:
        _key_store = KeyStore(path)
        _key_store_path_cache = path
        
    return _key_store


def _create_identity_data() -> Tuple[Dict[str, Any], Ed25519PrivateKey, bytes]:
    """
    Create a new identity with keys and DID.
    
    Returns:
        Tuple of (identity_data, private_key, public_key)
    """
    # Generate Ed25519 keypair
    private_key, public_key = generate_ed25519_keypair()
    
    # Derive DID from public key
    did = derive_did_from_pubkey(public_key)
    
    # Serialize private key for storage
    private_key_bytes = private_key.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption()
    )
    
    # Create identity data
    identity_data = {
        "did": did,
        "created_at": datetime.utcnow().isoformat(),
        "private_key": base64.b64encode(private_key_bytes).decode("ascii"),
        "public_key": base64.b64encode(public_key).decode("ascii"),
    }
    
    # Return data and keys
    return identity_data, private_key, public_key


def _derive_eth_key_from_ed25519(ed25519_private_key: bytes) -> str:
    """
    Derive a valid Ethereum private key from an Ed25519 private key.
    
    Args:
        ed25519_private_key: Ed25519 private key bytes
        
    Returns:
        Ethereum private key as hex string with 0x prefix
        
    Notes:
        This function ensures the derived key is within the valid range
        for SECP256K1 curve (between 1 and the curve order - 1)
    """
    # Get a deterministic value from the Ed25519 key
    hash_bytes = hashlib.sha256(ed25519_private_key).digest()
    
    # Convert to integer
    hash_int = int.from_bytes(hash_bytes, byteorder='big')
    
    # Ensure the value is within the valid range for SECP256K1
    valid_private_key = (hash_int % (SECP256K1_N - 1)) + 1
    
    # Convert back to hex
    return "0x" + format(valid_private_key, '064x')


def _identity_data_to_identity(data: Dict[str, Any]) -> Identity:
    """
    Convert stored identity data to Identity object.
    
    Args:
        data: Identity data from key store
        
    Returns:
        Identity object
    """
    # Decode private key
    private_key_bytes = base64.b64decode(data["private_key"])
    
    # Create signer from the private key using proper key derivation
    eth_private_key = _derive_eth_key_from_ed25519(private_key_bytes)
    signer = LocalSigner(eth_private_key)
    
    # Get created_at from either metadata (new format) or direct field (old format)
    if "metadata" in data and "created_at" in data["metadata"]:
        created_at = datetime.fromisoformat(data["metadata"]["created_at"])
    else:
        created_at = datetime.fromisoformat(data["created_at"])
    
    # Create Identity object
    return Identity(
        did=data["did"],
        signer=signer,
        created_at=created_at,
        org_id=data.get("org_id"),
        agent_label=data.get("agent_label")
    )


def get_or_create_did(auto: bool = True) -> Identity:
    """
    Get existing identity or create a new one if none exists.
    
    Args:
        auto: If True, automatically create an identity if none exists
        
    Returns:
        Identity object with DID and signer
        
    Raises:
        ValueError: If no identity exists and auto=False
    """
    start_time = time.time()
    
    # Get key store
    store = _get_key_store()
    
    # List existing identities
    identities = store.list_identities()
    
    if identities:
        # Use the most recently created identity
        # Check for metadata-based created_at first, then fall back to direct value
        sorted_identities = sorted(
            identities,
            key=lambda i: (
                i.get("metadata", {}).get("created_at", "") 
                if "metadata" in i 
                else i.get("created_at", "")
            ),
            reverse=True
        )
        
        # Decrypt if needed
        identity_data = sorted_identities[0]
        if "encrypted" in identity_data:
            identity_data = decrypt_key_data(identity_data)
        
        # Convert to Identity object
        identity = _identity_data_to_identity(identity_data)
        
        # Log performance (truncate DID for privacy)
        elapsed_ms = (time.time() - start_time) * 1000
        logger.debug("Retrieved DID %s… in %.2f ms", identity.did[:6], elapsed_ms)
        
        return identity
    
    if not auto:
        raise ValueError("No identity exists and auto=False")
    
    # Create new identity
    identity_data, _, _ = _create_identity_data()
    
    # Extract metadata for storage outside encryption
    created_at = identity_data["created_at"]
    metadata = {
        "created_at": created_at
    }
    
    # Encrypt sensitive data
    encrypted_data = encrypt_key_data(identity_data)
    
    # Store in key store with unencrypted metadata
    store.add_identity(identity_data["did"], encrypted_data, metadata)
    
    # Convert to Identity object
    identity = _identity_data_to_identity(identity_data)
    
    # Log performance (truncate DID for privacy)
    elapsed_ms = (time.time() - start_time) * 1000
    logger.debug("Created new DID %s… in %.2f ms", identity.did[:6], elapsed_ms)
    
    return identity


def create_new_identity() -> Identity:
    """
    Create a new identity with a new DID.
    
    Note: This creates a completely new identity, not a key rotation.
          The did:key method does not support key rotation.
    
    Returns:
        New Identity object
    """
    start_time = time.time()
    
    # Create new identity data
    identity_data, _, _ = _create_identity_data()
    
    # Extract metadata for storage outside encryption
    created_at = identity_data["created_at"]
    metadata = {
        "created_at": created_at
    }
    
    # Encrypt sensitive data
    encrypted_data = encrypt_key_data(identity_data)
    
    # Store in key store with unencrypted metadata
    store = _get_key_store()
    store.add_identity(identity_data["did"], encrypted_data, metadata)
    
    # Convert to Identity object
    identity = _identity_data_to_identity(identity_data)
    
    # Log performance (truncate DID for privacy)
    elapsed_ms = (time.time() - start_time) * 1000
    logger.debug("Created new DID %s… in %.2f ms", identity.did[:6], elapsed_ms)
    
    return identity


def delete_local() -> None:
    """
    Delete all local identity data (for GDPR compliance).
    
    Warning: This will permanently delete all local keys.
             DIDs registered on-chain will remain but become inaccessible.
    """
    store = _get_key_store()
    store.clear()
    logger.info("Deleted all local identity data")


def list_identities() -> List[Identity]:
    """
    List all locally stored identities.
    
    Returns:
        List of Identity objects
    """
    store = _get_key_store()
    stored_identities = store.list_identities()
    
    # Convert to Identity objects
    identities = []
    for data in stored_identities:
        # Decrypt if needed
        if "encrypted" in data:
            try:
                # Decrypt the sensitive data
                decrypted_data = decrypt_key_data(data)
                
                # Add metadata from the store entry if available
                if "metadata" in data:
                    for key, value in data["metadata"].items():
                        decrypted_data[key] = value
                        
                # Convert to Identity object
                identities.append(_identity_data_to_identity(decrypted_data))
            except Exception as e:
                logger.error(f"Failed to decrypt identity: {e}")
    
    return identities