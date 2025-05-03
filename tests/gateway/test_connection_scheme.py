"""
Tests for URL scheme handling and authentication methods in the GatewayClient.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
import urllib.parse

from intentlayer_sdk.gateway.client import GatewayClient


class TestConnectionScheme:
    """Test URL scheme handling and secure/insecure channel creation."""

    def test_http_scheme_requires_override(self):
        """Test that http:// scheme requires INTENT_SKIP_TLS_VERIFY=true."""
        # Import the module first
        from intentlayer_sdk.gateway import client as client_module

        # Without the environment variable, should raise error
        with pytest.raises(ValueError, match="Gateway URL uses insecure scheme"):
            GatewayClient("http://gateway.example.com")

        # With the environment variable, should work
        with patch.dict(os.environ, {"INTENT_SKIP_TLS_VERIFY": "true"}):
            with patch.object(client_module.grpc, 'insecure_channel') as mock_insecure:
                client = GatewayClient("http://gateway.example.com")
                mock_insecure.assert_called_once()

    def test_grpc_scheme_requires_override(self):
        """Test that grpc:// scheme requires INTENT_SKIP_TLS_VERIFY=true."""
        # Import the module first to ensure proper patching
        from intentlayer_sdk.gateway import client as client_module
        
        # Without the environment variable, should raise error
        with pytest.raises(ValueError, match="Gateway URL uses insecure scheme"):
            GatewayClient("grpc://gateway.example.com")

        # With the environment variable, should work
        with patch.dict(os.environ, {"INTENT_SKIP_TLS_VERIFY": "true"}):
            with patch.object(client_module.grpc, 'insecure_channel') as mock_insecure:
                client = GatewayClient("grpc://gateway.example.com")
                mock_insecure.assert_called_once()

    def test_https_uses_secure_channel(self):
        """Test that https:// scheme uses secure_channel."""
        # Import the module first to ensure proper patching
        from intentlayer_sdk.gateway import client as client_module
        
        with patch.object(client_module.grpc, 'secure_channel') as mock_secure:
            client = GatewayClient("https://gateway.example.com")
            mock_secure.assert_called_once()

    def test_grpcs_uses_secure_channel(self):
        """Test that grpcs:// scheme uses secure_channel."""
        # Import the module first to ensure proper patching
        from intentlayer_sdk.gateway import client as client_module
        
        with patch.object(client_module.grpc, 'secure_channel') as mock_secure:
            client = GatewayClient("grpcs://gateway.example.com")
            mock_secure.assert_called_once()

    def test_localhost_allows_insecure(self):
        """Test that localhost URLs allow insecure schemes without override."""
        # Import the module first to ensure proper patching
        from intentlayer_sdk.gateway import client as client_module
        
        for scheme in ["http", "grpc"]:
            for host in ["localhost", "127.0.0.1", "::1"]:
                with patch.object(client_module.grpc, 'insecure_channel') as mock_insecure:
                    client = GatewayClient(f"{scheme}://{host}")
                    mock_insecure.assert_called_once()

    def test_invalid_scheme_raises_error(self):
        """Test that invalid schemes raise an error."""
        with pytest.raises(ValueError, match="Gateway URL scheme must be one of"):
            GatewayClient("ftp://gateway.example.com")
        
        with pytest.raises(ValueError, match="Gateway URL scheme must be one of"):
            GatewayClient("ws://gateway.example.com")

    def test_skip_tls_verify_uses_secure_with_override(self):
        """Test that INTENT_SKIP_TLS_VERIFY with https creates secure channel with override."""
        # Import the module first to ensure proper patching
        from intentlayer_sdk.gateway import client as client_module
        
        # Mock ssl_channel_credentials and secure_channel to verify they're called properly
        with patch.dict(os.environ, {"INTENT_SKIP_TLS_VERIFY": "true"}):
            with patch.object(client_module.grpc, 'ssl_channel_credentials') as mock_creds:
                with patch.object(client_module.grpc, 'secure_channel') as mock_secure:
                    # Set the return value for channel to track what options were passed
                    mock_channel = MagicMock()
                    mock_secure.return_value = mock_channel
                    
                    # Create the client, which will use our mocked functions
                    client = GatewayClient("https://gateway.example.com")
                    
                    # Verify ssl_channel_credentials was called with root_certificates=None
                    mock_creds.assert_called_once_with(root_certificates=None)
                    
                    # Verify secure_channel was called (instead of insecure_channel)
                    mock_secure.assert_called_once()
                    
                    # Verify ssl_target_name_override was included in options
                    options = mock_secure.call_args[0][2]
                    assert any(opt[0] == "grpc.ssl_target_name_override" for opt in options), \
                        "ssl_target_name_override option not found in channel options"


class TestAuthenticationMethods:
    """Test authentication methods and header creation."""
    
    def test_api_key_uses_key_prefix(self):
        """Test that API key uses 'Key' prefix in Authorization header."""
        api_key = "sk_test_123456"
        # Import the module first
        from intentlayer_sdk.gateway import client as client_module
        
        # Create a client with a patched channel
        with patch.object(client_module.grpc, 'secure_channel'):
            client = GatewayClient("https://gateway.example.com", api_key=api_key)
            metadata = client._create_metadata()
            
            # Verify the header has the correct format
            assert metadata is not None
            assert len(metadata) == 1
            assert metadata[0][0] == client_module.AUTH_HEADER
            assert metadata[0][1] == f"{client_module.KEY_PREFIX}{api_key}"
    
    def test_bearer_token_uses_bearer_prefix(self):
        """Test that bearer token uses 'Bearer' prefix in Authorization header."""
        bearer_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        # Import the module first
        from intentlayer_sdk.gateway import client as client_module
        
        # Create a client with a patched channel
        with patch.object(client_module.grpc, 'secure_channel'):
            client = GatewayClient("https://gateway.example.com", bearer_token=bearer_token)
            metadata = client._create_metadata()
            
            # Verify the header has the correct format
            assert metadata is not None
            assert len(metadata) == 1
            assert metadata[0][0] == client_module.AUTH_HEADER
            assert metadata[0][1] == f"{client_module.BEARER_PREFIX}{bearer_token}"
    
    def test_api_key_from_env(self):
        """Test that API key can be provided via environment variable."""
        api_key = "sk_test_123456"
        # Import the module first
        from intentlayer_sdk.gateway import client as client_module
        
        with patch.dict(os.environ, {"INTENT_API_KEY": api_key}):
            with patch.object(client_module.grpc, 'secure_channel'):
                client = GatewayClient("https://gateway.example.com")
                metadata = client._create_metadata()
                
                # Verify the header has the correct format
                assert metadata is not None
                assert len(metadata) == 1
                assert metadata[0][0] == client_module.AUTH_HEADER
                assert metadata[0][1] == f"{client_module.KEY_PREFIX}{api_key}"
    
    def test_bearer_token_from_env(self):
        """Test that bearer token can be provided via environment variable."""
        bearer_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        # Import the module first
        from intentlayer_sdk.gateway import client as client_module
        
        with patch.dict(os.environ, {"INTENT_BEARER_TOKEN": bearer_token}):
            with patch.object(client_module.grpc, 'secure_channel'):
                client = GatewayClient("https://gateway.example.com")
                metadata = client._create_metadata()
                
                # Verify the header has the correct format
                assert metadata is not None
                assert len(metadata) == 1
                assert metadata[0][0] == client_module.AUTH_HEADER
                assert metadata[0][1] == f"{client_module.BEARER_PREFIX}{bearer_token}"
    
    def test_both_auth_methods_raises_error(self):
        """Test that providing both API key and bearer token raises an error."""
        api_key = "sk_test_123456"
        bearer_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        
        # Import the module first
        from intentlayer_sdk.gateway import client as client_module
        
        # Test with constructor parameters
        with pytest.raises(ValueError, match="Both API key and bearer token provided"):
            # No need to patch since it should fail before channel creation
            client = GatewayClient("https://gateway.example.com", api_key=api_key, bearer_token=bearer_token)
        
        # Test with environment variables
        with patch.dict(os.environ, {"INTENT_API_KEY": api_key, "INTENT_BEARER_TOKEN": bearer_token}):
            with pytest.raises(ValueError, match="Both API key and bearer token provided"):
                # No need to patch since it should fail before channel creation
                client = GatewayClient("https://gateway.example.com")
    
    def test_whitespace_trimming(self):
        """Test that whitespace is trimmed from credentials."""
        # Import the module first
        from intentlayer_sdk.gateway import client as client_module
        
        # Test API key with whitespace
        api_key = "  sk_test_123456  \n"
        with patch.object(client_module.grpc, 'secure_channel'):
            client = GatewayClient("https://gateway.example.com", api_key=api_key)
            metadata = client._create_metadata()
            
            # Verify whitespace was trimmed
            assert metadata is not None
            assert metadata[0][1] == f"{client_module.KEY_PREFIX}sk_test_123456"
        
        # Test bearer token with whitespace
        bearer_token = "  eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0  "
        with patch.object(client_module.grpc, 'secure_channel'):
            client = GatewayClient("https://gateway.example.com", bearer_token=bearer_token)
            metadata = client._create_metadata()
            
            # Verify whitespace was trimmed
            assert metadata is not None
            assert metadata[0][1] == f"{client_module.BEARER_PREFIX}eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"