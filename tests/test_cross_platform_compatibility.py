"""
Tests for cross-platform compatibility.
These tests verify that the SDK works consistently across
Linux, macOS, and Windows environments.
"""
import os
import sys
import time
import platform
import pytest
import tempfile
from pathlib import Path
import json
import shutil

from intentlayer_sdk.client import IntentClient
from intentlayer_sdk.config import NetworkConfig
from intentlayer_sdk.identity.key_store import KeyStore


def test_path_handling():
    """Test that path handling works correctly on all platforms."""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Convert to Path object for cross-platform path handling
        temp_path = Path(temp_dir)
        
        # Create a test file
        test_file = temp_path / "test_file.txt"
        test_file.write_text("test content")
        
        # Verify the file exists and can be read
        assert test_file.exists()
        assert test_file.read_text() == "test content"
        
        # Create a subdirectory
        subdir = temp_path / "subdir"
        subdir.mkdir()
        
        # Create a file in the subdirectory
        subdir_file = subdir / "subdir_file.txt"
        subdir_file.write_text("subdir content")
        
        # Verify path composition works
        assert subdir_file.exists()
        assert subdir_file.read_text() == "subdir content"


def test_keystore_cross_platform():
    """Test that KeyStore works correctly on all platforms."""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Set the keystore path to the temporary directory
        keystore_path = Path(temp_dir) / "keystore.json"
        
        # Create a keystore
        keystore = KeyStore(str(keystore_path))
        
        # Create a test DID and identity data
        test_did = "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH"
        identity_data = {
            "created_at": int(time.time()),
            "key_type": "ed25519",
            "private_key": "base64_encoded_private_key_placeholder"
        }
        
        # Add the identity to the keystore
        keystore.add_identity(test_did, identity_data, {"label": "test_key"})
        
        # Verify the keystore file was created
        assert keystore_path.exists()
        
        # Load the keystore file and check its structure
        with open(keystore_path, "r") as f:
            keystore_data = json.load(f)
        
        # Verify the keystore structure is as expected
        assert "identities" in keystore_data
        assert test_did in keystore_data["identities"]
        assert "metadata" in keystore_data["identities"][test_did]
        assert keystore_data["identities"][test_did]["metadata"]["label"] == "test_key"


def test_networks_config_loading():
    """Test that network configuration loading works on all platforms."""
    # Load networks configuration
    networks = NetworkConfig.load_networks()
    
    # Verify that the networks configuration was loaded
    assert networks is not None
    assert isinstance(networks, dict)
    assert len(networks) > 0
    
    # Access the network via get_network method instead
    zksync_network = NetworkConfig.get_network("zksync-era-sepolia")
    assert zksync_network is not None
    
    # Check that network entries have required fields
    assert "chainId" in zksync_network
    assert "rpc" in zksync_network
    assert "didRegistry" in zksync_network
    
    # Test chain ID access
    chain_id = NetworkConfig.get_chain_id("zksync-era-sepolia")
    assert isinstance(chain_id, int)
    assert chain_id > 0


@pytest.mark.skipif(
    sys.platform != "win32", 
    reason="Windows-specific test"
)
def test_windows_specific_path_handling():
    """Test Windows-specific path handling."""
    if sys.platform != "win32":
        pytest.skip("This test is only relevant on Windows")
    
    # Create paths with different separators
    path1 = "C:\\Users\\test\\file.txt"
    path2 = "C:/Users/test/file.txt"
    
    # Convert to Path objects
    path_obj1 = Path(path1)
    path_obj2 = Path(path2)
    
    # Verify they are equivalent
    assert str(path_obj1) == str(path_obj2)
    
    # Test UNC paths if on Windows
    unc_path = "\\\\server\\share\\file.txt"
    unc_path_obj = Path(unc_path)
    assert unc_path_obj.as_posix().startswith("//server")


def test_platform_detection():
    """Test that platform detection works correctly."""
    # Get the current platform
    current_platform = sys.platform
    
    # Check that platform is one of the expected values
    assert current_platform in {"linux", "darwin", "win32"}
    
    # Verify platform.system() matches sys.platform
    if current_platform == "linux":
        assert platform.system() == "Linux"
    elif current_platform == "darwin":
        assert platform.system() == "Darwin"
    elif current_platform == "win32":
        assert platform.system() == "Windows"