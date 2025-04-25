"""
Tests for fallback paths in the version module.
"""
import pytest
import importlib
from importlib import metadata
from unittest.mock import patch

def test_version_fallback_to_default(monkeypatch):
    # metadata.version and file open both fail
    monkeypatch.setattr(metadata, "version", lambda name: (_ for _ in ()).throw(metadata.PackageNotFoundError))
    monkeypatch.setattr("pathlib.Path.open", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError))
    import intentlayer_sdk.version as vmod
    importlib.reload(vmod)
    assert vmod.__version__ == "0.1.1"
