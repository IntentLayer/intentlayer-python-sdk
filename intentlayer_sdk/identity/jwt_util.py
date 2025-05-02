"""
JWT utility functions for the IntentLayer SDK.

This module provides utility functions for JWT token validation
with consistent behavior across different environments.
"""
import os
import logging
from typing import Optional, Dict, Any, List, Tuple

import jwt

# Configure logger
logger = logging.getLogger(__name__)

# Environment tiers
ENV_TIER_PRODUCTION = "production"
ENV_TIER_TEST = "test"
ENV_TIER_DEVELOPMENT = "development"

# Unsafe algorithms that should always be rejected
UNSAFE_JWT_ALGORITHMS = ["none", ""]


def get_environment_tier() -> str:
    """
    Get the current environment tier from environment variables.
    
    Returns:
        Environment tier string (production, test, or development)
    """
    tier = os.environ.get("INTENT_ENV_TIER", ENV_TIER_PRODUCTION).lower()
    # Normalize environment names
    if tier in ("prod", "production"):
        return ENV_TIER_PRODUCTION
    elif tier in ("test", "testing", "qa"):
        return ENV_TIER_TEST
    elif tier in ("dev", "development", "local"):
        return ENV_TIER_DEVELOPMENT
    else:
        # Default to production for unknown values (safest option)
        logger.warning(f"Unknown environment tier: {tier}, defaulting to production")
        return ENV_TIER_PRODUCTION


def get_jwt_secret() -> Optional[str]:
    """
    Get the JWT secret from environment variables.
    
    Returns:
        JWT secret string, or None if not set
    """
    return os.environ.get("INTENT_JWT_SECRET")


def is_safe_jwt_algorithm(algorithm: str) -> bool:
    """
    Check if a JWT algorithm is considered safe.
    
    Args:
        algorithm: JWT algorithm string
        
    Returns:
        True if the algorithm is considered safe, False otherwise
    """
    return algorithm.lower() not in UNSAFE_JWT_ALGORITHMS


def verify_jwt_token(
    token: str,
    env_tier: Optional[str] = None,
    jwt_secret: Optional[str] = None,
    allowed_algorithms: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Verify a JWT token based on environment tier.
    
    Implements a tiered verification approach:
    - Production: Enforces signature verification & HS256 algorithm
    - Test: Allows token without signature verification but validates format
    - Development: Minimal validation for development ease
    
    Args:
        token: JWT token string
        env_tier: Environment tier (production, test, development)
                 Defaults to INTENT_ENV_TIER environment variable
        jwt_secret: JWT secret for signature verification
                  Defaults to INTENT_JWT_SECRET environment variable
        allowed_algorithms: List of allowed algorithms (defaults based on env_tier)
        
    Returns:
        Decoded JWT token as dictionary, or None if validation fails
    """
    if not token:
        return None
        
    # Get environment tier and JWT secret if not provided
    if env_tier is None:
        env_tier = get_environment_tier()
    if jwt_secret is None:
        jwt_secret = get_jwt_secret()
        
    # Set default allowed algorithms based on environment tier
    if allowed_algorithms is None:
        if env_tier == ENV_TIER_PRODUCTION:
            allowed_algorithms = ["HS256"]
        elif env_tier == ENV_TIER_TEST:
            allowed_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512", "ES256", "ES384", "ES512"]
        else:
            # Development allows all algorithms except unsafe ones
            allowed_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512", "ES256", "ES384", "ES512"]
    
    try:
        # Get JWT header without verification to check algorithm
        try:
            header = jwt.get_unverified_header(token)
        except jwt.DecodeError:
            logger.warning("Invalid JWT format - could not decode header")
            return None
            
        # Always reject unsafe algorithms regardless of environment
        algorithm = header.get("alg", "")
        if not is_safe_jwt_algorithm(algorithm):
            logger.warning(f"Unsafe JWT algorithm: {algorithm}. Rejecting token.")
            return None
            
        # Check if algorithm is allowed for the current environment
        if algorithm not in allowed_algorithms:
            logger.warning(f"JWT algorithm {algorithm} not allowed in {env_tier} environment. Allowed: {allowed_algorithms}")
            return None
            
        # Tiered verification approach
        if env_tier == ENV_TIER_PRODUCTION:
            # Production tier: Strict validation with signature verification
            if not jwt_secret:
                logger.warning("Production environment requires INTENT_JWT_SECRET to be set")
                return None
                
            # Verify with secret and check expiration
            decoded = jwt.decode(
                token,
                jwt_secret,
                algorithms=allowed_algorithms,
                options={"verify_signature": True, "verify_exp": True}
            )
            logger.info("JWT token signature verified successfully (production mode)")
            return decoded
            
        elif env_tier == ENV_TIER_TEST:
            # Test tier: Check if we have a secret for HMAC algorithms
            if algorithm.upper().startswith("HS") and jwt_secret:
                try:
                    # Verify with secret but be more lenient
                    decoded = jwt.decode(
                        token,
                        jwt_secret,
                        algorithms=[algorithm],
                        options={"verify_signature": True, "verify_exp": True}
                    )
                    logger.info(f"JWT signature verified in test environment ({algorithm})")
                    return decoded
                except jwt.InvalidSignatureError:
                    logger.warning(f"Invalid JWT signature in test environment with {algorithm}")
                    # Fall through to unverified decode
                except Exception as e:
                    logger.warning(f"JWT verification error in test environment: {e}")
                    # Fall through to unverified decode
            
            # Skip signature verification for test environment
            decoded = jwt.decode(token, options={"verify_signature": False, "verify_exp": True})
            logger.info(f"JWT token format valid in test environment (algorithm: {algorithm})")
            return decoded
            
        else:
            # Development tier: Minimal validation, skip signature and expiration checks
            decoded = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
            logger.debug(f"JWT token format valid in development environment (algorithm: {algorithm})")
            return decoded
            
    except jwt.ExpiredSignatureError:
        logger.warning(f"JWT token has expired (environment: {env_tier})")
        return None
    except jwt.InvalidSignatureError:
        logger.warning(f"Invalid JWT signature (environment: {env_tier})")
        return None
    except Exception as e:
        logger.warning(f"JWT token validation failed: {e}")
        return None
        
    # Should never reach here
    return None


def extract_claim_from_jwt(
    token: str,
    claim_name: str,
    env_tier: Optional[str] = None,
    jwt_secret: Optional[str] = None
) -> Optional[Any]:
    """
    Extract a specific claim from a JWT token.
    
    Args:
        token: JWT token string
        claim_name: Name of the claim to extract
        env_tier: Environment tier (production, test, development)
        jwt_secret: JWT secret for signature verification
        
    Returns:
        Claim value, or None if the token is invalid or the claim doesn't exist
    """
    decoded = verify_jwt_token(token, env_tier, jwt_secret)
    if decoded:
        return decoded.get(claim_name)
    return None