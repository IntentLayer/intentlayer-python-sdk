"""
Tests for the tx_url method in IntentClient class.
"""
import pytest
from unittest.mock import patch, MagicMock
from web3 import Web3

from intentlayer_sdk import IntentClient
from tests.conftest import TEST_RPC_URL, TEST_PINNER_URL, TEST_CONTRACT, TEST_PRIV_KEY

def test_tx_url_with_bytes():
    """Test tx_url with bytes input."""
    # Create client with mocked configs
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT
    )
    # Test with bytes input
    tx_hash = bytes.fromhex("1234567890abcdef" * 4)
    url = client.tx_url(tx_hash)
    assert "0x1234567890abcdef" in url
    assert url.startswith("https://")

def test_tx_url_with_hex_without_prefix():
    """Test tx_url with hex string without 0x prefix."""
    # Create client with mocked configs
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT
    )
    # Test with hex string without 0x prefix
    tx_hash = "1234567890abcdef" * 4
    url = client.tx_url(tx_hash)
    assert url.startswith("https://")
    assert "0x1234567890abcdef" in url

def test_tx_url_with_hex_with_prefix():
    """Test tx_url with hex string with 0x prefix."""
    # Create client with mocked configs
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT
    )
    # Test with hex string with 0x prefix
    tx_hash = "0x" + "1234567890abcdef" * 4
    url = client.tx_url(tx_hash)
    assert url.startswith("https://")
    assert tx_hash in url

def test_tx_url_network_specific():
    """Test tx_url with different network names."""
    # Test zksync-era-sepolia network
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT
    )
    client._network_name = "zksync-era-sepolia"
    tx_hash = "0x1234567890abcdef" * 4
    url = client.tx_url(tx_hash)
    assert "sepolia.explorer.zksync.io" in url
    assert tx_hash in url

def test_tx_url_chain_id_specific():
    """Test tx_url with different chain IDs."""
    # Test different chain IDs
    for chain_id, expected_url in [
        (1, "etherscan.io"),
        (11155111, "sepolia.etherscan.io"),
        (300, "sepolia.explorer.zksync.io"),
        (999, "blockscan.com")  # Fallback for unknown chain ID
    ]:
        client = IntentClient(
            rpc_url=TEST_RPC_URL,
            pinner_url=TEST_PINNER_URL,
            signer=MagicMock(),
            recorder_address=TEST_CONTRACT
        )
        client._expected_chain_id = chain_id
        tx_hash = "0x1234567890abcdef" * 4
        url = client.tx_url(tx_hash)
        assert expected_url in url
        assert tx_hash in url

def test_tx_url_fallback_to_web3_chain_id():
    """Test tx_url fallback to web3 chain ID when expected_chain_id is None."""
    # Setup
    client = IntentClient(
        rpc_url=TEST_RPC_URL,
        pinner_url=TEST_PINNER_URL,
        signer=MagicMock(),
        recorder_address=TEST_CONTRACT
    )
    client._expected_chain_id = None
    
    # Mock w3.eth.chain_id
    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 1  # Mainnet
    client.w3 = mock_w3
    
    # Test
    tx_hash = "0x1234567890abcdef" * 4
    url = client.tx_url(tx_hash)
    
    # Verify
    assert "etherscan.io" in url
    assert tx_hash in url