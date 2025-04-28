"""
Cryptographic operations for the identity module.
"""
import os
import sys
import base64
import json
import hashlib
import logging
from typing import Tuple, Dict, Any, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption
)
import nacl.secret
import nacl.utils

# Import base58 for DID encoding
try:
    import base58
except ImportError:
    raise ImportError(
        "base58 package is required for identity module. "
        "Install with: pip install base58"
    )

# Module-level cache for encryption key to improve performance
_encryption_key_cache = None
logger = logging.getLogger(__name__)


def generate_ed25519_keypair() -> Tuple[Ed25519PrivateKey, bytes]:
    """
    Generate an Ed25519 keypair.
    
    Returns:
        Tuple of (private_key, public_key_bytes)
    """
    private_key = Ed25519PrivateKey.generate()
    public_key_bytes = private_key.public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw
    )
    return private_key, public_key_bytes


def derive_did_from_pubkey(public_key: bytes) -> str:
    """
    Derive a did:key from an Ed25519 public key.
    
    Args:
        public_key: Raw Ed25519 public key bytes
        
    Returns:
        did:key identifier
    """
    # Add the correct multicodec prefix 0xED 0x01 for Ed25519
    multicodec_key = b"\xed\x01" + public_key
    
    # Base58 encode - note that the base58 library already prepends the 'z' prefix
    encoded = base58.b58encode(multicodec_key).decode("ascii")
    did = f"did:key:{encoded}"
    
    # Log truncated DID for privacy
    logger.info("Generated DID %s…", did[:6])
    
    return did


def get_encryption_key() -> bytes:
    """
    Get encryption key from OS keyring or environment.
    
    Returns:
        32-byte encryption key
    
    Note:
        Caches the key after first lookup for better performance
        Falls back to environment variable only in CI environments
    """
    global _encryption_key_cache
    
    # Return cached key if available (saves ~6ms per call)
    if _encryption_key_cache is not None:
        return _encryption_key_cache
    
    key = None
    service_name = "intentlayer-sdk"
    key_name = "master-key"
    
    # Try to get key from OS keyring
    try:
        import keyring
        key = keyring.get_password(service_name, key_name)
        if key:
            key = base64.b64decode(key)
    except Exception as e:
        logger.debug("Keyring access failed: %s", str(e))
    
    # If keyring failed, check for environment variable (only in CI)
    if not key and os.environ.get("CI") == "true":
        env_key = os.environ.get("INTENT_MASTER_KEY")
        if env_key:
            try:
                key = base64.b64decode(env_key)
            except Exception:
                logger.warning("Invalid INTENT_MASTER_KEY format")
    
    # If no key exists yet, generate one and store it
    if not key:
        # Only allow this in CI or if keyring is available
        if os.environ.get("CI") == "true" or "keyring" in sys.modules:
            key = nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE)
            try:
                import keyring
                keyring.set_password(
                    service_name, 
                    key_name,
                    base64.b64encode(key).decode("ascii")
                )
            except Exception as e:
                if os.environ.get("CI") != "true":
                    raise ValueError(
                        "Failed to store encryption key in OS keyring and not in CI environment"
                    ) from e
                else:
                    # In CI, export the key to environment
                    logger.warning("Set INTENT_MASTER_KEY environment variable for CI")
        else:
            raise ValueError(
                "No encryption key available and not in CI environment. "
                "Install keyring or set CI=true for development."
            )
    
    # Cache the key for future calls
    _encryption_key_cache = key
    return key


def encrypt_key_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypt sensitive key data using libsodium secretbox.
    
    Args:
        data: Dictionary with sensitive key data
        
    Returns:
        Dictionary with encrypted data
    """
    # Convert data to JSON bytes
    json_data = json.dumps(data).encode("utf-8")
    
    # Get encryption key
    key = get_encryption_key()
    
    # Create secret box
    box = nacl.secret.SecretBox(key)
    
    # Generate a random nonce and encrypt the data
    # Note: box.encrypt already combines nonce+ciphertext+tag in its output
    encrypted = box.encrypt(json_data)
    
    # Store the full encrypted data (which already includes the nonce)
    return {
        "encrypted": base64.b64encode(encrypted).decode("ascii"),
        "version": 1  # For future format changes
    }


def decrypt_key_data(encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt key data.
    
    Args:
        encrypted_data: Dictionary with encrypted data
        
    Returns:
        Decrypted data as dictionary
        
    Raises:
        ValueError: If decryption fails
    """
    # Get encryption key
    key = get_encryption_key()
    
    # Create secret box
    box = nacl.secret.SecretBox(key)
    
    # Get full encrypted data (includes nonce+ciphertext+tag)
    encrypted = base64.b64decode(encrypted_data["encrypted"])
    
    # Decrypt
    try:
        # box.decrypt automatically handles nonce extraction
        decrypted = box.decrypt(encrypted)
        return json.loads(decrypted.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to decrypt key data: {e}")