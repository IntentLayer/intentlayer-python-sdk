"""
Dependency management for gateway module.

This standalone module helps break circular import dependencies.
"""
import logging

logger = logging.getLogger(__name__)


def ensure_grpc_installed():
    """
    Check if grpc and related packages are installed.
    Raises ImportError with installation instructions if not found.
    """
    # Check for grpc package using direct import attempt rather than find_spec
    # because the package is sometimes installed under different names
    try:
        import grpc
        import google.protobuf
        return True
    except ImportError:
        raise ImportError(
            "Gateway integration requires additional dependencies: grpcio, protobuf. "
            "Please install with: pip install intentlayer-sdk[grpc]"
        )