"""
Tests for backward compatibility features.
"""
import warnings
import pytest

from intentlayer_sdk import IntentLayerClient, IntentClient

def test_intent_layer_client_alias():
    """Test that IntentLayerClient works as an alias for IntentClient"""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        # Create client with the legacy class name
        client = IntentLayerClient(
            rpc_url="https://rpc.example.com",
            pinner_url="https://pin.example.com",
            min_stake_wei=1000000000000000,
            priv_key="0x" + "1"*64
        )
        
        # Should have raised a deprecation warning
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "IntentLayerClient is deprecated" in str(w[0].message)
        
        # Should be an instance of IntentClient
        assert isinstance(client, IntentClient)
        
        # Should have all the expected attributes
        assert client.rpc_url == "https://rpc.example.com"
        assert client.pinner_url == "https://pin.example.com"
        assert client.min_stake_wei == 1000000000000000