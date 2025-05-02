"""
Tests for JWT verification with None algorithm.

These tests specifically verify that the JWT verification rejects tokens
with 'none' algorithm in a case-insensitive manner.
"""
import pytest
from unittest.mock import patch, MagicMock

import jwt
from intentlayer_sdk.identity.jwt_util import (
    verify_jwt_token,
    ENV_TIER_PRODUCTION,
    ENV_TIER_TEST,
    ENV_TIER_DEVELOPMENT
)


class TestJwtNoneAlgorithm:
    """Tests for JWT verification with None algorithm."""
    
    @pytest.mark.parametrize("alg_value", ["none", "None", "NONE", "nOnE"])
    def test_rejects_none_algorithm_case_insensitive(self, alg_value):
        """Test that verify_jwt_token rejects 'none' algorithm regardless of case."""
        # Create a mock token
        mock_token = "mock.jwt.token"
        mock_header = {"alg": alg_value}
        
        # Test with all environment tiers
        for env_tier in [ENV_TIER_PRODUCTION, ENV_TIER_TEST, ENV_TIER_DEVELOPMENT]:
            with patch('jwt.get_unverified_header', return_value=mock_header), \
                 patch('intentlayer_sdk.identity.jwt_util.logger'):
                
                # Call verify_jwt_token
                result = verify_jwt_token(mock_token, env_tier=env_tier)
                
                # Verify that token is rejected
                assert result is None, f"JWT with alg='{alg_value}' should be rejected in {env_tier} environment"
    
    def test_verify_token_checks_header_first(self):
        """Test that verify_jwt_token checks the header before attempting to decode."""
        # Create a mock token with 'none' algorithm
        mock_token = "mock.jwt.token"
        mock_header = {"alg": "none"}
        
        with patch('jwt.get_unverified_header', return_value=mock_header), \
             patch('jwt.decode') as mock_decode, \
             patch('intentlayer_sdk.identity.jwt_util.logger'):
            
            # Call verify_jwt_token with different environment tiers
            for env_tier in [ENV_TIER_PRODUCTION, ENV_TIER_TEST, ENV_TIER_DEVELOPMENT]:
                verify_jwt_token(mock_token, env_tier=env_tier)
                
                # Verify that jwt.decode was never called
                mock_decode.assert_not_called()