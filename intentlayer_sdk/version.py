"""
Version information for the IntentLayer SDK.
"""
import importlib.metadata
import pathlib
import tomli

# Default fallback version if metadata and file lookups fail
_DEFAULT_VERSION = "0.5.0"

try:
    # Attempt to read version from installed package metadata
    __version__ = importlib.metadata.version("intentlayer-sdk")
except importlib.metadata.PackageNotFoundError:
    try:
        # Fallback to reading from pyproject.toml for development
        project_root = pathlib.Path(__file__).parent.parent
        pyproject_path = project_root / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            data = tomli.load(f)
        __version__ = data["project"]["version"]
    except (FileNotFoundError, KeyError, tomli.TOMLDecodeError):
        # Any failure reading or parsing falls back to default
        __version__ = _DEFAULT_VERSION
