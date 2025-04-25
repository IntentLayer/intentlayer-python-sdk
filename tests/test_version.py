"""
Tests for the version module of the IntentLayer SDK.
"""
import pytest
import re
import importlib
from importlib import metadata as importlib_metadata
from unittest.mock import patch, mock_open
import tomli

from intentlayer_sdk import __version__


def test_version_format():
    """Test that the version string follows semantic versioning"""
    assert re.match(r'^\d+\.\d+\.\d+$', __version__), "Version should follow semantic versioning"


@patch('importlib.metadata.version')
@patch('pathlib.Path.open', new_callable=mock_open, read_data=b'[project]\nversion = "1.2.3"\n')
def test_version_from_file(mock_open_file, mock_metadata_version):
    """When metadata lookup fails, pyproject.toml is read"""
    mock_metadata_version.side_effect = importlib_metadata.PackageNotFoundError
    import intentlayer_sdk.version as vmod
    importlib.reload(vmod)
    # Should pick up 1.2.3 from the file
    assert vmod.__version__ == "1.2.3"


@patch('importlib.metadata.version')
def test_version_from_metadata(mock_metadata_version):
    """When metadata lookup succeeds, version comes from metadata"""
    mock_metadata_version.return_value = "2.3.4"
    import intentlayer_sdk.version as vmod
    importlib.reload(vmod)
    assert vmod.__version__ == "2.3.4"


def test_version_file_not_found(monkeypatch):
    """If pyproject.toml is missing, fallback to default"""
    # Simulate metadata not found
    monkeypatch.setattr(importlib_metadata, 'version', lambda name: (_ for _ in ()).throw(importlib_metadata.PackageNotFoundError()))
    # Simulate file missing
    monkeypatch.setattr('pathlib.Path.open', lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    import intentlayer_sdk.version as vmod
    importlib.reload(vmod)
    assert vmod.__version__ == "0.1.1"


def test_version_key_error(monkeypatch):
    """If TOML exists but missing version key, fallback to default"""
    monkeypatch.setattr(importlib_metadata, 'version', lambda name: (_ for _ in ()).throw(importlib_metadata.PackageNotFoundError()))
    # Provide TOML without version key
    m = mock_open(read_data=b'[project]\nname = "intentlayer-sdk"\n')
    monkeypatch.setattr('pathlib.Path.open', m)
    import intentlayer_sdk.version as vmod
    importlib.reload(vmod)
    assert vmod.__version__ == "0.1.1"


def test_version_toml_decode_error(monkeypatch):
    """If TOML parse fails, fallback to default"""
    monkeypatch.setattr(importlib_metadata, 'version', lambda name: (_ for _ in ()).throw(importlib_metadata.PackageNotFoundError()))
    # File opens
    m = mock_open(read_data=b'invalid toml content')
    monkeypatch.setattr('pathlib.Path.open', m)
    # tomli.load raises decode error
    monkeypatch.setattr(tomli, 'load', lambda f: (_ for _ in ()).throw(tomli.TOMLDecodeError("fail", b"", 0)))
    import intentlayer_sdk.version as vmod
    importlib.reload(vmod)
    assert vmod.__version__ == "0.1.1"
