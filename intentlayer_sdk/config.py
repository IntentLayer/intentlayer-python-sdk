"""
Network configuration utilities for the IntentLayer SDK.
"""
import json
import os
import importlib.resources
from typing import Dict, Any, Optional

class NetworkConfig:
    """Network configuration manager for the IntentLayer SDK."""
    
    # In-memory cache for network configurations
    _networks_cache: Optional[Dict[str, Dict[str, Any]]] = None
    
    @classmethod
    def load_networks(cls) -> Dict[str, Dict[str, Any]]:
        """
        Load network configurations from the networks.json file.
        
        Returns:
            Dictionary of network configurations indexed by network name
        """
        # Return from cache if available
        if cls._networks_cache is not None:
            return cls._networks_cache
            
        try:
            with importlib.resources.files("intentlayer_sdk").joinpath("networks.json").open() as f:
                cls._networks_cache = json.load(f)
                return cls._networks_cache
        except Exception as e:
            raise ValueError(f"Failed to load network configurations: {e}")
    
    @classmethod
    def get_network(cls, network_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific network.
        
        Args:
            network_name: Name of the network to retrieve
            
        Returns:
            Network configuration dictionary
            
        Raises:
            ValueError: If the network name is not found
        """
        networks = cls.load_networks()
        if network_name not in networks:
            available = ", ".join(networks.keys())
            raise ValueError(
                f"Network '{network_name}' not found. Available networks: {available}"
            )
        return networks[network_name]
    
    @classmethod
    def get_rpc_url(cls, network_name: str, override: Optional[str] = None) -> str:
        """
        Get RPC URL for a network, with optional override.
        
        Args:
            network_name: Name of the network
            override: Optional RPC URL to use instead of the configured one
            
        Returns:
            RPC URL to use for the network
        """
        if override:
            return override
            
        # Check environment variable
        env_var = f"{network_name.upper().replace('-', '_')}_RPC_URL"
        if env_var in os.environ:
            return os.environ[env_var]
            
        # Fall back to configuration
        return cls.get_network(network_name)["rpc"]
    
    @classmethod
    def get_chain_id(cls, network_name: str) -> int:
        """
        Get chain ID for a network.
        
        Args:
            network_name: Name of the network
            
        Returns:
            Chain ID for the network
        """
        return int(cls.get_network(network_name)["chainId"])
    
    @classmethod
    def get_recorder_address(cls, network_name: str) -> str:
        """
        Get IntentRecorder contract address for a network.
        
        Args:
            network_name: Name of the network
            
        Returns:
            IntentRecorder contract address
        """
        return cls.get_network(network_name)["intentRecorder"]
    
    @classmethod
    def get_did_registry_address(cls, network_name: str) -> str:
        """
        Get DIDRegistry contract address for a network.
        
        Args:
            network_name: Name of the network
            
        Returns:
            DIDRegistry contract address
        """
        return cls.get_network(network_name)["didRegistry"]

# Export NETWORKS map for direct access
NETWORKS = NetworkConfig.load_networks()