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
        - Uses tiered verification approach based on environment:
            - Production: Enforces signature verification & HS256 algorithm
            - Test: Allows token without signature verification but validates format
            - Dev: Minimal validation for development ease
        - Validates that the token uses HS256 algorithm to prevent JOSE/JWT exploits
    """
    if not api_key:
        api_key = os.environ.get("INTENT_API_KEY")
    if not api_key:
        return None

    # Determine environment tier
    env_tier = os.environ.get("INTENT_ENV_TIER", "production").lower()
    jwt_secret = os.environ.get("INTENT_JWT_SECRET")
    
    try:
        # Get JWT header without verification to check algorithm
        try:
            header = jwt.get_unverified_header(api_key)
        except jwt.DecodeError:
            logger.warning("Invalid JWT format - could not decode header")
            return None
        
        # Always check for unsafe algorithms
        algorithm = header.get("alg", "")
        if algorithm.lower() in ("none", ""):
            logger.warning(f"Unsafe JWT algorithm: {algorithm}. Rejecting token.")
            return None
            
        # Tiered verification approach
        if env_tier == "production":
            # Production tier: Strict validation
            if algorithm != "HS256":
                logger.warning(f"Production environment requires HS256 algorithm, got: {algorithm}")
                return None
                
            if not jwt_secret:
                logger.warning("Production environment requires INTENT_JWT_SECRET to be set")
                return None
                
            try:
                decoded = jwt.decode(api_key, jwt_secret, algorithms=["HS256"])
                logger.info("Used verified JWT signature for API key (production mode)")
                return decoded.get("org_id")
            except jwt.InvalidSignatureError:
                logger.warning("Invalid JWT signature in production environment - rejecting API key")
                return None
            except Exception as e:
                logger.warning(f"JWT verification failed in production environment: {e}")
                return None
                
        elif env_tier == "test":
            # Test tier: Allow RSA and other algorithms, but check for unsafe ones
            if algorithm.lower() in ("hs256", "hs384", "hs512") and jwt_secret:
                # If we have a secret and it's HMAC-based, still verify
                try:
                    decoded = jwt.decode(api_key, jwt_secret, algorithms=["HS256", "HS384", "HS512"])
                    logger.info(f"Used verified JWT signature for API key (test mode, {algorithm})")
                    return decoded.get("org_id")
                except jwt.InvalidSignatureError:
                    logger.warning(f"Invalid JWT signature in test environment with {algorithm} - proceeding anyway")
                    # Fall through to unverified decode
                except Exception as e:
                    logger.warning(f"JWT verification failed in test environment: {e}")
                    # Fall through to unverified decode
            
            # Skip verification but log it
            decoded = jwt.decode(api_key, options={"verify_signature": False})
            logger.info(f"JWT signature verification skipped in test environment (algorithm: {algorithm})")
            return decoded.get("org_id")
            
        else:
            # Dev tier: Minimal validation
            decoded = jwt.decode(api_key, options={"verify_signature": False})
            logger.debug(f"JWT signature verification skipped in development environment (algorithm: {algorithm})")
            return decoded.get("org_id")
            
    except Exception as e:
        logger.warning(f"Failed to extract org_id from API key: {e}")
        return None


class IdentityManager:
    """
    Manages DID registration with the Gateway service.
    
    Supports multiple locking strategies for concurrent registration prevention:
    1. File-based locking (default) - works for multi-threaded and multi-process applications on a single machine
    2. Redis-based locking (optional) - works for distributed applications across multiple machines
    """
    
    # Class-level lock for the DID registration file
    _file_lock = None
    
    # Lock strategy constants
    LOCK_STRATEGY_FILE = "file"
    LOCK_STRATEGY_REDIS = "redis"
    
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
    
    @classmethod
    def _get_redis_lock(cls, redis_url: str, lock_name: str, timeout: int = 30):
        """
        Get a distributed lock using Redis.
        
        Args:
            redis_url: Redis connection URL (redis://host:port/db)
            lock_name: Name of the lock
            timeout: Lock timeout in seconds
            
        Returns:
            A Redis lock object
            
        Raises:
            ImportError: If redis package is not installed
            ValueError: If redis_url is invalid
        """
        try:
            import redis
            from redis.exceptions import LockError
        except ImportError:
            raise ImportError(
                "Redis locking requires the 'redis' package. "
                "Install it with 'pip install redis'."
            )
        
        try:
            client = redis.from_url(redis_url)
            lock = client.lock(
                lock_name,
                timeout=timeout,
                blocking_timeout=10  # Max wait time to acquire lock
            )
            return lock
        except Exception as e:
            raise ValueError(f"Failed to create Redis lock: {e}")
    
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
        
    def _get_lock(self, lock_strategy: str = None, redis_url: str = None):
        """
        Get the appropriate lock based on strategy.
        
        Args:
            lock_strategy: Lock strategy to use (file or redis)
            redis_url: Redis connection URL if using redis strategy
            
        Returns:
            Lock object
            
        Raises:
            ValueError: If lock_strategy is invalid or redis_url is missing when needed
        """
        # Get lock strategy from env var if not specified
        if lock_strategy is None:
            lock_strategy = os.environ.get("INTENT_LOCK_STRATEGY", self.LOCK_STRATEGY_FILE).lower()
        
        # Get redis URL from env var if not specified
        if redis_url is None and lock_strategy == self.LOCK_STRATEGY_REDIS:
            redis_url = os.environ.get("INTENT_REDIS_URL")
        
        # Create the appropriate lock
        if lock_strategy == self.LOCK_STRATEGY_REDIS:
            if not redis_url:
                raise ValueError(
                    "Redis URL is required for redis locking strategy. "
                    "Set INTENT_REDIS_URL environment variable or provide redis_url parameter."
                )
            lock_name = f"intent:did:lock:{self.identity.did}"
            return self._get_redis_lock(redis_url, lock_name)
        elif lock_strategy == self.LOCK_STRATEGY_FILE:
            return self._get_file_lock()
        else:
            raise ValueError(
                f"Invalid lock strategy: {lock_strategy}. "
                f"Valid options are: {self.LOCK_STRATEGY_FILE}, {self.LOCK_STRATEGY_REDIS}"
            )
    
    def ensure_registered(
        self,
        force: bool = False,
        lock_strategy: str = None,
        redis_url: str = None,
        schema_version: Optional[int] = None
    ) -> bool:
        """
        Ensure the identity's DID is registered with the Gateway service.
        
        Thread and process-safe implementation using locks to prevent concurrent
        registrations of the same DID.
        
        Args:
            force: If True, attempt registration even if the DID is believed to be registered
            lock_strategy: Locking strategy to use: 'file' (default) or 'redis'
            redis_url: Redis URL for distributed locking (required if lock_strategy='redis')
            schema_version: Schema version number to use for registration (optional)
            
        Returns:
            True if the DID was newly registered, False if already registered
            
        Raises:
            Various Gateway exceptions if registration fails
        """
        # First check thread-safe local cache to avoid locks if possible
        with self._thread_lock:
            if self._is_registered and not force:
                return False
        
        # Get the appropriate lock
        try:
            lock = self._get_lock(lock_strategy, redis_url)
        except (ImportError, ValueError) as e:
            self.logger.warning(f"Failed to create lock: {e}. Proceeding without locking.")
            lock = None
        
        # Try to acquire the lock if we have one
        acquired = False
        if lock:
            try:
                acquired = lock.acquire(timeout=10)
                if not acquired:
                    self.logger.warning(f"Could not acquire DID registration lock, proceeding without it")
            except Exception as e:
                self.logger.warning(f"Error acquiring lock: {e}. Proceeding without locking.")
        
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
                    org_id=org_id,
                    schema_version=schema_version
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
            if lock and acquired:
                try:
                    lock.release()
                except Exception as e:
                    self.logger.warning(f"Error releasing lock: {e}")
                    # Continue even if lock release fails