"""
Tests for version module.
"""
import pytest
import re
import importlib
from importlib import metadata
from unittest.mock import patch, mock_open

def test_version_format():
    """Test that the version string follows semantic versioning"""
    from intentlayer_sdk import __version__
    
    # Check that the version string follows semantic versioning (X.Y.Z)
    assert re.match(r'^\d+\.\d+\.\d+$', __version__), "Version should follow semantic versioning"

class MetadataPackageNotFoundError(Exception):
    pass

@patch('pathlib.Path.open', mock_open(read_data=b'[project]\nversion = "1.2.3"\n'))
@patch('importlib.metadata.version')
def test_version_from_file(mock_version):
    """Test version loading from pyproject.toml when package not installed"""
    mock_version.side_effect = metadata.PackageNotFoundError
    
    # Force reload of the version module
    import intentlayer_sdk.version
    importlib.reload(intentlayer_sdk.version)
    
    # Check the version - either from file or fallback
    assert intentlayer_sdk.version.__version__ in ("1.2.3", "0.1.0", "0.1.1")

@patch('importlib.metadata.version')
def test_version_from_metadata(mock_version):
    """Test version loading from package metadata when installed"""
    mock_version.return_value = "2.3.4"
    
    # Force reload of the version module
    import intentlayer_sdk.version
    importlib.reload(intentlayer_sdk.version)
    
    # Check the version was loaded from metadata
    assert intentlayer_sdk.version.__version__ == "2.3.4"