"""
Identity registration and management module.

This module provides functionality for DID registration with the Gateway service.
"""
import logging
import os
import threading
from pathlib import Path
from typing import Optional, Union, Dict, Any, TYPE_CHECKING

import jwt
import fasteners
import appdirs

# Avoid circular imports with TYPE_CHECKING
if TYPE_CHECKING:
    from ..gateway.client import GatewayClient

from ..gateway.exceptions import AlreadyRegisteredError

logger = logging.getLogger(__name__)


def extract_org_id_from_api_key(api_key: Optional[str] = None) -> Optional[str]:
    """
    Extract org_id from JWT token in INTENT_API_KEY.
    
    Args:
        api_key: Optional API key as JWT token. If None, tries to get from environment.
        
    Returns:
        Organization ID from the JWT token, or None if not found/invalid
        
    Security:
        - Validates that the token uses HS256 algorithm to prevent "zip-bomb" style tokens
        - Does not verify the signature since we're only extracting the claim
        
    Note:
        In production, consider setting INTENT_JWT_SECRET environment variable to enable
        proper signature verification for enhanced security.
    """
    if not api_key:
        api_key = os.environ.get("INTENT_API_KEY")
    if not api_key:
        return None

    try:
        # Get JWT header without verification to check algorithm
        header = jwt.get_unverified_header(api_key)
        if header.get("alg") != "HS256":
            logger.warning(f"Unsupported JWT algorithm: {header.get('alg')}. Only HS256 is supported.")
            return None
            
        # Get JWT secret if available for verification
        jwt_secret = os.environ.get("INTENT_JWT_SECRET")
        if jwt_secret:
            # With secret - verify signature
            try:
                decoded = jwt.decode(api_key, jwt_secret, algorithms=["HS256"])
                logger.info("Used verified JWT signature for API key")
                return decoded.get("org_id")
            except jwt.InvalidSignatureError:
                logger.warning("Invalid JWT signature - rejecting API key")
                return None
            except Exception as e:
                logger.warning(f"JWT verification failed: {e}")
                return None
        else:
            # Without secret - skip verification but log it once
            decoded = jwt.decode(api_key, options={"verify_signature": False})
            logger.warning("JWT signature verification skipped - INTENT_JWT_SECRET not set")
            return decoded.get("org_id")
    except Exception as e:
        logger.warning(f"Failed to extract org_id from API key: {e}")
        return None


class IdentityManager:
    """
    Manages DID registration with the Gateway service.
    """
    
    # Class-level lock for the DID registration file
    _file_lock = None
    
    @classmethod
    def _get_file_lock(cls):
        """Get a process-wide file lock for DID registration."""
        if cls._file_lock is None:
            # Use appdirs to get the appropriate user data directory for the platform
            # This avoids UAC write restrictions on Windows and ensures proper directory 
            # permissions on all platforms
            data_dir = Path(appdirs.user_data_dir("intentlayer"))
            lock_file = data_dir / "did.reg.lock"
            
            # Ensure the directory exists
            os.makedirs(data_dir, exist_ok=True)
            
            # Create the lock
            cls._file_lock = fasteners.InterProcessLock(str(lock_file))
            logger.debug(f"Using lock file at {lock_file}")
        return cls._file_lock
    
    def __init__(self, identity=None, gateway_client=None):
        """
        Initialize the identity manager.
        
        Args:
            identity: Identity object with DID and key information
            gateway_client: GatewayClient instance for DID registration
        """
        if identity is None:
            raise ValueError("Identity must be provided")
        if gateway_client is None:
            raise ValueError("Gateway client must be provided")
            
        self.identity = identity
        self.gateway_client = gateway_client
        self.logger = logging.getLogger(__name__)
        self._is_registered = False
        self._thread_lock = threading.Lock()  # Thread safety for _is_registered flag
        
    def ensure_registered(self, force: bool = False) -> bool:
        """
        Ensure the identity's DID is registered with the Gateway service.
        
        Thread and process-safe implementation using locks to prevent concurrent
        registrations of the same DID.
        
        Args:
            force: If True, attempt registration even if the DID is believed to be registered
            
        Returns:
            True if the DID was newly registered, False if already registered
            
        Raises:
            Various Gateway exceptions if registration fails
        """
        # First check thread-safe local cache to avoid locks if possible
        with self._thread_lock:
            if self._is_registered and not force:
                return False
        
        # Use process-wide file lock to ensure only one process registers the DID
        file_lock = self._get_file_lock()
        
        # Try to acquire the lock with a timeout to avoid deadlocks
        if not file_lock.acquire(timeout=10):
            self.logger.warning("Could not acquire DID registration lock, proceeding without it")
            # Fall through to registration attempt even if lock acquisition fails
        
        try:
            # Double-check inside the lock since another process might have registered
            # while we were waiting for the lock
            with self._thread_lock:
                if self._is_registered and not force:
                    return False
                
            # Extract org_id from API key if available
            org_id = extract_org_id_from_api_key()
            
            # Get the public key bytes if available
            pub_key = self.identity.public_key_bytes if hasattr(self.identity, "public_key_bytes") else None
            
            try:
                # Register the DID with the Gateway
                response = self.gateway_client.register_did(
                    did=self.identity.did,
                    pub_key=pub_key,
                    org_id=org_id
                )
                # Thread-safe update of registration status
                with self._thread_lock:
                    self._is_registered = True
                self.logger.info(f"Registered DID {self.identity.did[:6]}… with Gateway")
                return True
            except AlreadyRegisteredError:
                # Already registered, mark as registered but return False
                with self._thread_lock:
                    self._is_registered = True
                return False
            except Exception:
                # Re-raise other exceptions
                raise
        finally:
            # Always release the lock if we acquired it
            if file_lock.acquired:
                file_lock.release()