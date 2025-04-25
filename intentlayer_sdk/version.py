"""
Version information for the IntentLayer SDK.
"""
import importlib.metadata
import pathlib
import json
import tomli

# Try to get version from installed package metadata
try:
    __version__ = importlib.metadata.version("intentlayer-sdk")
except importlib.metadata.PackageNotFoundError:
    # Fall back to reading from pyproject.toml for development
    try:
        path = pathlib.Path(__file__).parent.parent / "pyproject.toml"
        with open(path, "rb") as f:
            data = tomli.load(f)
        __version__ = data["project"]["version"]
    except (FileNotFoundError, KeyError, ImportError):
        __version__ = "0.1.1"  # Default fallback version