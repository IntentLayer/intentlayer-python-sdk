"""
Gateway module for the IntentLayer SDK.

This module provides integration with the IntentLayer Gateway service,
which handles DID registration and intent submission.

Note: This module requires additional dependencies that can be installed with:
    pip install intentlayer-sdk[grpc]
"""
import os
import sys
import importlib.util
import logging
import threading
from typing import Optional, Dict, Any

from .exceptions import QuotaExceededError, AlreadyRegisteredError
from ._deps import ensure_grpc_installed

__all__ = ['GatewayClient', 'ensure_grpc_installed', 'QuotaExceededError', 
           'AlreadyRegisteredError', 'get_gateway_client']

logger = logging.getLogger(__name__)

# Module-level gateway client cache with thread safety
_gateway_client_cache = {}
_cache_lock = threading.RLock()


def get_gateway_client(gateway_url: str, api_key: Optional[str] = None) -> 'GatewayClient':
    """
    Get or create a gateway client from the module-level cache.
    
    Args:
        gateway_url: URL of the gateway service
        api_key: Optional API key for authentication
        
    Returns:
        GatewayClient instance
    """
    cache_key = gateway_url
    with _cache_lock:
        if cache_key not in _gateway_client_cache:
            from .client import GatewayClient
            _gateway_client_cache[cache_key] = GatewayClient(gateway_url, api_key=api_key)
        return _gateway_client_cache[cache_key]