"""
Tests for fallback paths in the version module.
"""
import pytest
import importlib
import io
import tomli
from importlib import metadata
from unittest.mock import patch, MagicMock

def test_version_fallback_to_default(monkeypatch):
    # metadata.version and file open both fail
    monkeypatch.setattr(metadata, "version", lambda name: (_ for _ in ()).throw(metadata.PackageNotFoundError))
    monkeypatch.setattr("pathlib.Path.open", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError))
    import intentlayer_sdk.version as vmod
    importlib.reload(vmod)
    assert vmod.__version__ == "0.1.1"

def test_version_key_error_fallback(monkeypatch):
    # metadata.version fails but file opens, but missing key
    monkeypatch.setattr(metadata, "version", lambda name: (_ for _ in ()).throw(metadata.PackageNotFoundError))
    
    # Mock file handler
    mock_file = MagicMock()
    mock_file.__enter__.return_value = MagicMock()
    monkeypatch.setattr("pathlib.Path.open", lambda *a, **k: mock_file)
    
    # Mock tomli.load to return data without version key
    monkeypatch.setattr(tomli, "load", lambda f: {"project": {"name": "intentlayer-sdk"}})  # No version key
    
    # Force reload
    import intentlayer_sdk.version as vmod
    importlib.reload(vmod)
    assert vmod.__version__ == "0.1.1"  # Default fallback
