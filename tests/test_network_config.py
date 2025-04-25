"""
Tests for the NetworkConfig module.
"""
import pytest
import os
from unittest.mock import patch, mock_open

from intentlayer_sdk.config import NetworkConfig

# Sample network configuration
MOCK_NETWORKS = {
    "test-network": {
        "chainId": 123,
        "rpc": "https://test.example.com",
        "intentRecorder": "0x1234567890123456789012345678901234567890",
        "didRegistry": "0x0987654321098765432109876543210987654321"
    }
}

class TestNetworkConfig:
    """Test NetworkConfig class."""
    
    def test_load_networks_cached(self):
        """Test that networks are cached after first load."""
        # Set the cache directly for testing
        NetworkConfig._networks_cache = MOCK_NETWORKS
        
        # This should return from cache without opening the file
        with patch("importlib.resources.files") as mock_files:
            result = NetworkConfig.load_networks()
            
            # Verify the file was never opened
            mock_files.assert_not_called()
            
        # Verify result
        assert result == MOCK_NETWORKS
        
        # Reset cache for other tests
        NetworkConfig._networks_cache = None
    
    def test_get_network(self):
        """Test getting a specific network configuration."""
        # Set the cache directly for testing
        NetworkConfig._networks_cache = MOCK_NETWORKS
        
        # Get the test network
        result = NetworkConfig.get_network("test-network")
        
        # Verify result
        assert result == MOCK_NETWORKS["test-network"]
        assert result["chainId"] == 123
        assert result["rpc"] == "https://test.example.com"
        
        # Reset cache for other tests
        NetworkConfig._networks_cache = None
    
    def test_get_network_not_found(self):
        """Test getting a non-existent network."""
        # Set the cache directly for testing
        NetworkConfig._networks_cache = MOCK_NETWORKS
        
        # Try to get a non-existent network
        with pytest.raises(ValueError) as exc_info:
            NetworkConfig.get_network("non-existent-network")
        
        # Verify error message includes available networks
        assert "test-network" in str(exc_info.value)
        
        # Reset cache for other tests
        NetworkConfig._networks_cache = None
    
    def test_get_rpc_url_default(self):
        """Test getting RPC URL from network config."""
        # Set the cache directly for testing
        NetworkConfig._networks_cache = MOCK_NETWORKS
        
        # Get RPC URL
        result = NetworkConfig.get_rpc_url("test-network")
        
        # Verify result
        assert result == "https://test.example.com"
        
        # Reset cache for other tests
        NetworkConfig._networks_cache = None
    
    def test_get_rpc_url_override(self):
        """Test RPC URL override parameter."""
        # Set the cache directly for testing
        NetworkConfig._networks_cache = MOCK_NETWORKS
        
        # Get RPC URL with override
        result = NetworkConfig.get_rpc_url("test-network", override="https://override.example.com")
        
        # Verify result
        assert result == "https://override.example.com"
        
        # Reset cache for other tests
        NetworkConfig._networks_cache = None
    
    def test_get_rpc_url_env_var(self):
        """Test RPC URL from environment variable."""
        # Set the cache directly for testing
        NetworkConfig._networks_cache = MOCK_NETWORKS
        
        # Set environment variable
        with patch.dict(os.environ, {"TEST_NETWORK_RPC_URL": "https://env.example.com"}):
            # Get RPC URL
            result = NetworkConfig.get_rpc_url("test-network")
            
            # Verify result
            assert result == "https://env.example.com"
        
        # Reset cache for other tests
        NetworkConfig._networks_cache = None
    
    def test_get_chain_id(self):
        """Test getting chain ID from network config."""
        # Set the cache directly for testing
        NetworkConfig._networks_cache = MOCK_NETWORKS
        
        # Get chain ID
        result = NetworkConfig.get_chain_id("test-network")
        
        # Verify result
        assert result == 123
        
        # Reset cache for other tests
        NetworkConfig._networks_cache = None
    
    def test_get_recorder_address(self):
        """Test getting IntentRecorder address from network config."""
        # Set the cache directly for testing
        NetworkConfig._networks_cache = MOCK_NETWORKS
        
        # Get IntentRecorder address
        result = NetworkConfig.get_recorder_address("test-network")
        
        # Verify result
        assert result == "0x1234567890123456789012345678901234567890"
        
        # Reset cache for other tests
        NetworkConfig._networks_cache = None
    
    def test_get_did_registry_address(self):
        """Test getting DIDRegistry address from network config."""
        # Set the cache directly for testing
        NetworkConfig._networks_cache = MOCK_NETWORKS
        
        # Get DIDRegistry address
        result = NetworkConfig.get_did_registry_address("test-network")
        
        # Verify result
        assert result == "0x0987654321098765432109876543210987654321"
        
        # Reset cache for other tests
        NetworkConfig._networks_cache = None