"""
Tests for the JWT utility functions.

These tests verify that the JWT validation logic works correctly
across different environment tiers.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
import jwt

from intentlayer_sdk.identity.jwt_util import (
    get_environment_tier,
    get_jwt_secret,
    is_safe_jwt_algorithm,
    verify_jwt_token,
    extract_claim_from_jwt,
    ENV_TIER_PRODUCTION,
    ENV_TIER_TEST,
    ENV_TIER_DEVELOPMENT,
    UNSAFE_JWT_ALGORITHMS
)


class TestJwtUtil:
    """Tests for the JWT utility functions."""
    
    def test_get_environment_tier(self):
        """Test getting the environment tier from environment variables."""
        # Test with no environment variable (should default to production)
        with patch.dict(os.environ, {}, clear=True):
            assert get_environment_tier() == ENV_TIER_PRODUCTION
            
        # Test with different valid environment tiers
        with patch.dict(os.environ, {"INTENT_ENV_TIER": "production"}):
            assert get_environment_tier() == ENV_TIER_PRODUCTION
            
        with patch.dict(os.environ, {"INTENT_ENV_TIER": "prod"}):
            assert get_environment_tier() == ENV_TIER_PRODUCTION
            
        with patch.dict(os.environ, {"INTENT_ENV_TIER": "test"}):
            assert get_environment_tier() == ENV_TIER_TEST
            
        with patch.dict(os.environ, {"INTENT_ENV_TIER": "qa"}):
            assert get_environment_tier() == ENV_TIER_TEST
            
        with patch.dict(os.environ, {"INTENT_ENV_TIER": "development"}):
            assert get_environment_tier() == ENV_TIER_DEVELOPMENT
            
        with patch.dict(os.environ, {"INTENT_ENV_TIER": "dev"}):
            assert get_environment_tier() == ENV_TIER_DEVELOPMENT
            
        # Test with invalid environment tier (should default to production)
        with patch.dict(os.environ, {"INTENT_ENV_TIER": "invalid"}):
            assert get_environment_tier() == ENV_TIER_PRODUCTION
    
    def test_get_jwt_secret(self):
        """Test getting the JWT secret from environment variables."""
        # Test with no environment variable
        with patch.dict(os.environ, {}, clear=True):
            assert get_jwt_secret() is None
            
        # Test with environment variable
        with patch.dict(os.environ, {"INTENT_JWT_SECRET": "test-secret"}):
            assert get_jwt_secret() == "test-secret"
    
    def test_is_safe_jwt_algorithm(self):
        """Test checking if a JWT algorithm is considered safe."""
        # Test safe algorithms
        assert is_safe_jwt_algorithm("HS256") is True
        assert is_safe_jwt_algorithm("RS256") is True
        assert is_safe_jwt_algorithm("ES256") is True
        
        # Test unsafe algorithms
        for alg in UNSAFE_JWT_ALGORITHMS:
            assert is_safe_jwt_algorithm(alg) is False
            
        # Test case insensitivity
        assert is_safe_jwt_algorithm("NONE") is False
        assert is_safe_jwt_algorithm("None") is False
        assert is_safe_jwt_algorithm("nOnE") is False
    
    def test_verify_jwt_token_production(self):
        """Test JWT token verification in production environment."""
        # Create a mock token and parameters
        mock_token = "mock.jwt.token"
        mock_secret = "mock-secret"
        
        # Mock jwt.get_unverified_header to return a safe algorithm
        mock_header = {"alg": "HS256"}
        mock_decoded = {"sub": "1234", "org_id": "test-org"}
        
        # Test successful verification
        with patch('jwt.get_unverified_header', return_value=mock_header), \
             patch('jwt.decode', return_value=mock_decoded), \
             patch('intentlayer_sdk.identity.jwt_util.logger'):
            
            # Production environment with correct algorithm and secret
            result = verify_jwt_token(mock_token, ENV_TIER_PRODUCTION, mock_secret)
            assert result == mock_decoded
            
            # jwt.decode should be called with correct parameters
            jwt.decode.assert_called_with(
                mock_token,
                mock_secret,
                algorithms=["HS256"],
                options={"verify_signature": True, "verify_exp": True}
            )
            
            # Test with unsafe algorithm
            jwt.get_unverified_header.return_value = {"alg": "none"}
            result = verify_jwt_token(mock_token, ENV_TIER_PRODUCTION, mock_secret)
            assert result is None
            
            # Test with wrong algorithm
            jwt.get_unverified_header.return_value = {"alg": "RS256"}
            result = verify_jwt_token(mock_token, ENV_TIER_PRODUCTION, mock_secret)
            assert result is None
            
            # Test with no secret
            jwt.get_unverified_header.return_value = {"alg": "HS256"}
            result = verify_jwt_token(mock_token, ENV_TIER_PRODUCTION, None)
            assert result is None
    
    def test_verify_jwt_token_test(self):
        """Test JWT token verification in test environment."""
        # Create a mock token and parameters
        mock_token = "mock.jwt.token"
        mock_secret = "mock-secret"
        
        # Mock jwt.get_unverified_header to return a safe algorithm
        mock_header = {"alg": "HS256"}
        mock_decoded = {"sub": "1234", "org_id": "test-org"}
        
        # Test successful verification
        with patch('jwt.get_unverified_header', return_value=mock_header), \
             patch('jwt.decode', return_value=mock_decoded), \
             patch('intentlayer_sdk.identity.jwt_util.logger'):
            
            # Test environment with HS256 algorithm and secret
            jwt.decode.reset_mock()  # Reset mock to clear call history
            result = verify_jwt_token(mock_token, ENV_TIER_TEST, mock_secret)
            assert result == mock_decoded
            
            # jwt.decode should be called with signature verification (HMAC algorithm + secret)
            jwt.decode.assert_called_with(
                mock_token,
                mock_secret,
                algorithms=["HS256"],
                options={"verify_signature": True, "verify_exp": True}
            )
            
            # Test with RS256 algorithm (should skip signature verification)
            jwt.get_unverified_header.return_value = {"alg": "RS256"}
            jwt.decode.reset_mock()
            result = verify_jwt_token(mock_token, ENV_TIER_TEST, mock_secret)
            assert result == mock_decoded
            
            # jwt.decode should be called without signature verification
            jwt.decode.assert_called_with(
                mock_token,
                options={"verify_signature": False, "verify_exp": True}
            )
            
            # Test with unsafe algorithm
            jwt.get_unverified_header.return_value = {"alg": "none"}
            result = verify_jwt_token(mock_token, ENV_TIER_TEST, mock_secret)
            assert result is None
            
            # Mock jwt.decode to simulate signature verification failure
            with patch('jwt.decode') as mock_decode:
                # First call raises InvalidSignatureError, second call returns mock_decoded
                mock_decode.side_effect = [
                    jwt.InvalidSignatureError("invalid signature"),
                    mock_decoded
                ]
                
                # HS256 with invalid signature should fall back to unverified decode
                jwt.get_unverified_header.return_value = {"alg": "HS256"}
                result = verify_jwt_token(mock_token, ENV_TIER_TEST, mock_secret)
                assert result == mock_decoded
                
                # Both decode calls should have happened
                assert mock_decode.call_count == 2
    
    def test_verify_jwt_token_development(self):
        """Test JWT token verification in development environment."""
        # Create a mock token and parameters
        mock_token = "mock.jwt.token"
        
        # Mock jwt.get_unverified_header to return a safe algorithm
        mock_header = {"alg": "HS256"}
        mock_decoded = {"sub": "1234", "org_id": "test-org"}
        
        # Test successful verification
        with patch('jwt.get_unverified_header', return_value=mock_header), \
             patch('jwt.decode', return_value=mock_decoded), \
             patch('intentlayer_sdk.identity.jwt_util.logger'):
            
            # Development environment should skip signature and expiration verification
            jwt.decode.reset_mock()
            result = verify_jwt_token(mock_token, ENV_TIER_DEVELOPMENT)
            assert result == mock_decoded
            
            # jwt.decode should be called without signature or expiration verification
            jwt.decode.assert_called_with(
                mock_token,
                options={"verify_signature": False, "verify_exp": False}
            )
            
            # Test with unsafe algorithm
            jwt.get_unverified_header.return_value = {"alg": "none"}
            result = verify_jwt_token(mock_token, ENV_TIER_DEVELOPMENT)
            assert result is None
    
    def test_extract_claim_from_jwt(self):
        """Test extracting a claim from a JWT token."""
        # Create a mock token and parameters
        mock_token = "mock.jwt.token"
        mock_decoded = {"sub": "1234", "org_id": "test-org"}
        
        # Test successful extraction
        with patch('intentlayer_sdk.identity.jwt_util.verify_jwt_token', return_value=mock_decoded):
            # Extract existing claim
            result = extract_claim_from_jwt(mock_token, "org_id")
            assert result == "test-org"
            
            # Extract non-existent claim
            result = extract_claim_from_jwt(mock_token, "non_existent")
            assert result is None
            
        # Test with invalid token
        with patch('intentlayer_sdk.identity.jwt_util.verify_jwt_token', return_value=None):
            result = extract_claim_from_jwt(mock_token, "org_id")
            assert result is None