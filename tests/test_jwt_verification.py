"""
Tests for the tiered JWT verification approach.

These tests verify the different validation behaviors based on environment tier.
"""
import os
import pytest
import jwt
from unittest.mock import patch

from intentlayer_sdk.identity.registration import extract_org_id_from_api_key
from intentlayer_sdk.gateway.client import GatewayClient


def create_test_jwt(payload, algorithm="HS256", secret="test_secret"):
    """Helper to create test JWT tokens."""
    return jwt.encode(payload, secret, algorithm=algorithm)


class TestJwtVerification:
    """Tests for JWT verification in different environment tiers."""

    def test_extract_org_id_production_mode(self):
        """Test JWT verification in production mode."""
        # Create a token with HS256 algorithm and valid org_id
        test_token = create_test_jwt({"org_id": "org123"}, algorithm="HS256", secret="test_secret")
        
        # Set up environment for production mode with matching secret
        with patch.dict(os.environ, {
            "INTENT_ENV_TIER": "production",
            "INTENT_JWT_SECRET": "test_secret"
        }):
            # Should succeed with valid signature
            org_id = extract_org_id_from_api_key(test_token)
            assert org_id == "org123"
            
            # Should fail with wrong secret
            with patch.dict(os.environ, {"INTENT_JWT_SECRET": "wrong_secret"}):
                org_id = extract_org_id_from_api_key(test_token)
                assert org_id is None
                
            # Should fail with missing secret
            with patch.dict(os.environ, {}, clear=True):
                with patch.dict(os.environ, {"INTENT_ENV_TIER": "production"}):
                    org_id = extract_org_id_from_api_key(test_token)
                    assert org_id is None
                    
        # Test with non-HS256 algorithm in production mode
        test_token_rs256 = create_test_jwt({"org_id": "org123"}, algorithm="RS256", secret="not_used")
        with patch.dict(os.environ, {"INTENT_ENV_TIER": "production", "INTENT_JWT_SECRET": "test_secret"}):
            org_id = extract_org_id_from_api_key(test_token_rs256)
            assert org_id is None

    def test_extract_org_id_test_mode(self):
        """Test JWT verification in test mode."""
        # Create tokens with different algorithms
        test_token_hs256 = create_test_jwt({"org_id": "org123"}, algorithm="HS256", secret="test_secret")
        test_token_rs256 = create_test_jwt({"org_id": "org123"}, algorithm="RS256", secret="not_used")
        
        # Set up environment for test mode
        with patch.dict(os.environ, {"INTENT_ENV_TIER": "test"}):
            # Should accept HS256 without verifying (no secret provided)
            org_id = extract_org_id_from_api_key(test_token_hs256)
            assert org_id == "org123"
            
            # Should also accept RS256 without verifying
            org_id = extract_org_id_from_api_key(test_token_rs256)
            assert org_id == "org123"
            
            # Should still verify signature if secret is provided for HS256
            with patch.dict(os.environ, {"INTENT_JWT_SECRET": "test_secret"}):
                org_id = extract_org_id_from_api_key(test_token_hs256)
                assert org_id == "org123"
                
                # But should still accept with wrong secret (test mode)
                with patch.dict(os.environ, {"INTENT_JWT_SECRET": "wrong_secret"}):
                    org_id = extract_org_id_from_api_key(test_token_hs256)
                    assert org_id == "org123"

    def test_extract_org_id_dev_mode(self):
        """Test JWT verification in development mode."""
        # Create token with minimal validation
        test_token = create_test_jwt({"org_id": "org123"}, algorithm="HS256", secret="test_secret")
        test_token_rs256 = create_test_jwt({"org_id": "org123"}, algorithm="RS256", secret="not_used")
        
        # Set up environment for dev mode
        with patch.dict(os.environ, {"INTENT_ENV_TIER": "development"}):
            # Should accept both tokens without verification
            org_id = extract_org_id_from_api_key(test_token)
            assert org_id == "org123"
            
            org_id = extract_org_id_from_api_key(test_token_rs256)
            assert org_id == "org123"

    def test_reject_unsafe_algorithms(self):
        """Test that unsafe algorithms are rejected in all modes."""
        # Create a token with 'none' algorithm (potentially unsafe)
        header = {"alg": "none", "typ": "JWT"}
        payload = {"org_id": "bad_org"}
        unsafe_token = jwt.encode(payload, "", algorithm="none")
        
        # Should be rejected in all environments
        for env in ["production", "test", "development"]:
            with patch.dict(os.environ, {"INTENT_ENV_TIER": env}):
                org_id = extract_org_id_from_api_key(unsafe_token)
                assert org_id is None
                
    def test_gateway_client_metadata_validation(self):
        """Test JWT validation in GatewayClient._create_metadata."""
        test_token = create_test_jwt({"org_id": "org123"}, algorithm="HS256", secret="test_secret")
        
        # Production environment
        with patch.dict(os.environ, {
            "INTENT_ENV_TIER": "production",
            "INTENT_JWT_SECRET": "test_secret"
        }):
            client = GatewayClient("https://example.com", api_key=test_token)
            metadata = client._create_metadata()
            
            # Should include the token in metadata
            assert metadata is not None
            assert len(metadata) == 1
            assert metadata[0][0] == "authorization"
            assert metadata[0][1] == f"Bearer {test_token}"
            
        # Test with invalid token in production
        with patch.dict(os.environ, {
            "INTENT_ENV_TIER": "production",
            "INTENT_JWT_SECRET": "wrong_secret"
        }):
            client = GatewayClient("https://example.com", api_key=test_token)
            # Should still include token in metadata even if validation fails
            metadata = client._create_metadata()
            assert metadata is not None
            assert len(metadata) == 1
            
        # Test environment
        with patch.dict(os.environ, {"INTENT_ENV_TIER": "test"}):
            client = GatewayClient("https://example.com", api_key=test_token)
            metadata = client._create_metadata()
            assert metadata is not None
            assert len(metadata) == 1