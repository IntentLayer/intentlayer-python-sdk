"""
Tests for the auto DID feature in IntentClient.
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from intentlayer_sdk import IntentClient
from intentlayer_sdk.identity import Identity, get_or_create_did
from intentlayer_sdk.signer import Signer


# Sample identity for mocking
@pytest.fixture
def mock_identity():
    """Mock Identity object"""
    # Create mock signer first
    mock_signer = MagicMock()
    mock_signer.address = "0x1234567890123456789012345678901234567890"
    
    # Create identity with proper attributes
    identity = MagicMock()
    identity.did = "did:key:z6MkpzExampleDid"
    identity.created_at = "2025-04-28T12:00:00"
    identity.signer = mock_signer
    
    return identity


def test_client_with_auto_did(mock_identity):
    """Test creating IntentClient with auto_did=True"""
    
    # Mock network config and URLs
    mock_network_config = {
        "intentRecorder": "0x1111111111111111111111111111111111111111",
        "didRegistry": "0x2222222222222222222222222222222222222222",
        "chainId": "1"
    }
    
    # Setup mocks properly
    with patch("intentlayer_sdk.identity.get_or_create_did", return_value=mock_identity):
        # Mock NetworkConfig.get_network - critical part!
        with patch("intentlayer_sdk.config.NetworkConfig.get_network", return_value=mock_network_config):
            # Mock NetworkConfig.get_rpc_url
            with patch("intentlayer_sdk.config.NetworkConfig.get_rpc_url", return_value="https://example.com/rpc"):
                # Mock Web3 to avoid actual RPC calls
                with patch("intentlayer_sdk.client.Web3") as DummyWeb3:
                    DummyWeb3.HTTPProvider = MagicMock()
                    # Create client with auto_did
                    client = IntentClient.from_network(
                        network="test-network",
                        pinner_url="https://example.com/pin",
                        signer=None,  # No signer provided, should use auto DID
                        auto_did=True
                    )
                    
                    # Verify identity was stored in client
                    assert hasattr(client, "_identity")
                    assert client._identity is mock_identity
                    
                    # Verify signer was set from identity
                    assert client.signer is mock_identity.signer


def test_client_both_signer_and_auto_did(mock_identity):
    """Test creating IntentClient with both explicit signer and auto_did=True"""
    
    # Mock signer
    mock_signer = MagicMock()
    mock_signer.address = "0xABCDEF1234567890ABCDEF1234567890ABCDEF12"
    
    # Mock network config and URLs
    mock_network_config = {
        "intentRecorder": "0x1111111111111111111111111111111111111111",
        "didRegistry": "0x2222222222222222222222222222222222222222",
        "chainId": "1"
    }
    
    # Setup mocks properly
    with patch("intentlayer_sdk.identity.get_or_create_did", return_value=mock_identity):
        # Mock NetworkConfig.get_network - critical part!
        with patch("intentlayer_sdk.config.NetworkConfig.get_network", return_value=mock_network_config):
            # Mock NetworkConfig.get_rpc_url
            with patch("intentlayer_sdk.config.NetworkConfig.get_rpc_url", return_value="https://example.com/rpc"):
                # Stub the exact alias that IntentClient uses
                with patch("intentlayer_sdk.client.Web3") as DummyWeb3:
                    DummyWeb3.HTTPProvider = MagicMock()  # IntentClient expects it
                    # Create client with both signer and auto_did
                    client = IntentClient.from_network(
                        network="test-network",
                        pinner_url="https://example.com/pin",
                        signer=mock_signer,  # Provide explicit signer
                        auto_did=True  # Also enable auto_did
                    )
                    
                    # Verify identity was stored in client
                    assert hasattr(client, "_identity")
                    assert client._identity is mock_identity
                    
                    # Verify signer is the explicitly provided one, not from identity
                    assert client.signer is mock_signer
                    assert client.signer is not mock_identity.signer