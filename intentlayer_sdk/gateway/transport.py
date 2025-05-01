"""
Transport layer for the Gateway service.

This module provides an abstraction layer for the transport protocols
used to communicate with the IntentLayer Gateway service, including
both proto-based (gRPC) and stub-based implementations.
"""
import os
import logging
import random
import time
from typing import Optional, Dict, Any, List, Tuple, Protocol, Union, cast

# Import for type checking
from abc import ABC, abstractmethod
from dataclasses import dataclass

# Local imports
from .exceptions import (
    GatewayError, GatewayConnectionError, GatewayResponseError,
    GatewayTimeoutError, QuotaExceededError, AlreadyRegisteredError,
    RegisterError
)

# Configure logger
logger = logging.getLogger(__name__)


class GatewayTransport(ABC):
    """
    Abstract base class for Gateway transport implementations.
    
    This class defines the interface that all transport implementations must follow,
    providing a unified API regardless of the underlying protocol (gRPC, REST, etc.).
    """
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this transport is available for use.
        
        Returns:
            True if transport is available, False otherwise
        """
        pass
    
    @abstractmethod
    def initialize(self, gateway_url: str, verify_ssl: bool = True) -> None:
        """
        Initialize the transport with the given gateway URL.
        
        Args:
            gateway_url: URL of the gateway service
            verify_ssl: Whether to verify SSL certificates
            
        Raises:
            GatewayConnectionError: If connection initialization fails
        """
        pass
    
    @abstractmethod
    def register_did(
        self,
        did: str,
        pub_key: Optional[bytes] = None,
        org_id: Optional[str] = None,
        label: Optional[str] = None,
        schema_version: Optional[int] = None,
        doc_cid: Optional[str] = None,
        payload_cid: Optional[str] = None,
        timeout: Optional[int] = None,
        metadata: Optional[List[Tuple[str, str]]] = None
    ) -> 'TxReceipt':
        """
        Register a DID with the Gateway service.
        
        Args:
            did: The decentralized identifier to register
            pub_key: Public key associated with the DID (optional if already in DID)
            org_id: Organization ID (optional)
            label: Human-readable label for the DID (optional)
            schema_version: Schema version number (optional)
            doc_cid: Document CID (optional)
            payload_cid: Payload CID (optional)
            timeout: Request timeout in seconds
            metadata: Request metadata key-value pairs
            
        Returns:
            Transaction receipt
            
        Raises:
            QuotaExceededError: If DID registration quota is exceeded
            GatewayError: For other Gateway-related errors
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close any open connections or resources."""
        pass


@dataclass
class TxReceipt:
    """
    Represents a transaction receipt from the Gateway.
    
    This class is shared across transport implementations to provide
    a consistent interface regardless of the underlying protocol.
    """
    hash: str = ""
    gas_used: int = 0
    success: bool = False
    error: str = ""
    error_code: str = "UNKNOWN_UNSPECIFIED"  # RegisterError enum as string
    
    @classmethod
    def validate(cls, receipt: 'TxReceipt') -> bool:
        """
        Validate that a TxReceipt has consistent success and error_code values.
        
        Args:
            receipt: The receipt to validate
            
        Returns:
            True if valid, raises ValueError otherwise
        """
        if receipt.success and receipt.error_code != "UNKNOWN_UNSPECIFIED":
            raise ValueError(f"Invalid receipt: success=True with non-zero error code {receipt.error_code}")
        return True


# Transport provider functions
def get_proto_transport() -> Optional[GatewayTransport]:
    """
    Get a proto-based transport implementation if available.
    
    Returns:
        Proto-based transport implementation, or None if not available
    """
    try:
        from .proto_transport import ProtoTransport
        transport = ProtoTransport()
        if transport.is_available():
            return transport
        return None
    except ImportError:
        logger.debug("Proto transport not available")
        return None


def get_stub_transport() -> GatewayTransport:
    """
    Get a stub-based transport implementation.
    
    This always returns a valid transport since the stub implementation
    has no external dependencies.
    
    Returns:
        Stub-based transport implementation
    """
    from .stub_transport import StubTransport
    return StubTransport()


def get_transport(prefer_proto: bool = True) -> GatewayTransport:
    """
    Get the best available transport implementation.
    
    Args:
        prefer_proto: Whether to prefer proto-based transport if available
        
    Returns:
        Transport implementation
        
    Raises:
        GatewayError: If no transport is available
    """
    if prefer_proto:
        proto_transport = get_proto_transport()
        if proto_transport:
            logger.info("Using proto-based transport for Gateway")
            return proto_transport
            
    # Fall back to stub transport
    logger.info("Using stub-based transport for Gateway")
    return get_stub_transport()