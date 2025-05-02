"""
Stub-based transport implementation for the Gateway service.

This module provides a fallback implementation when the protocol buffer
definitions and gRPC dependencies are not available. It uses a simple
stub class to simulate a successful response.
"""
import os
import logging
import time
from typing import Optional, Dict, Any, List, Tuple

# Local imports
from .transport import GatewayTransport, TxReceipt
from .exceptions import (
    GatewayError, GatewayConnectionError, GatewayResponseError,
    GatewayTimeoutError, QuotaExceededError, AlreadyRegisteredError,
    RegisterError
)

# Configure logger
logger = logging.getLogger(__name__)


class StubTransport(GatewayTransport):
    """
    A simple stub implementation for the Gateway transport.
    
    This class provides a fallback implementation when the protocol buffer
    definitions are not available. It simulates a successful response
    for testing and development purposes.
    """
    
    def __init__(self):
        """Initialize the stub transport."""
        self.gateway_url = None
        self.initialized = False
    
    def is_available(self) -> bool:
        """
        Check if stub transport is available.
        
        Returns:
            Always True since stub transport has no dependencies
        """
        return True
    
    def initialize(self, gateway_url: str, verify_ssl: bool = True) -> None:
        """
        Initialize the stub transport.
        
        Args:
            gateway_url: URL of the gateway service (ignored)
            verify_ssl: Whether to verify SSL certificates (ignored)
        """
        self.gateway_url = gateway_url
        self.initialized = True
        logger.debug(f"Initialized stub transport for {gateway_url}")
    
    def register_did(
        self,
        did: str,
        pub_key: Optional[bytes] = None,
        org_id: Optional[str] = None,
        label: Optional[str] = None,
        schema_version: Optional[int] = 2,
        doc_cid: Optional[str] = None,
        payload_cid: Optional[str] = None,
        timeout: Optional[int] = None,
        metadata: Optional[List[Tuple[str, str]]] = None
    ) -> TxReceipt:
        """
        Register a DID with the Gateway service (stubbed).
        
        Args:
            did: The decentralized identifier to register
            pub_key: Public key associated with the DID (optional if already in DID)
            org_id: Organization ID (optional)
            label: Human-readable label for the DID (optional)
            schema_version: Schema version number (optional)
            doc_cid: Document CID (optional)
            payload_cid: Payload CID (optional)
            timeout: Request timeout in seconds (ignored)
            metadata: Request metadata key-value pairs (ignored)
            
        Returns:
            Transaction receipt
            
        Raises:
            GatewayConnectionError: If stub transport not initialized
            QuotaExceededError: If org_id is "quota_exceeded" for testing
            GatewayResponseError: For other simulated errors
        """
        if not self.initialized:
            raise GatewayConnectionError("Stub transport not initialized")
            
        logger.debug(f"StubTransport.register_did called with did={did}, org_id={org_id}")
        
        # Basic validation checks to simulate Gateway behavior
        if not did or len(did) < 10:
            return TxReceipt(
                hash="0x0000000000000000000000000000000000000000000000000000000000000000",
                gas_used=0,
                success=False,
                error="DID is too short or invalid",
                error_code=RegisterError.INVALID_DID
            )
        
        # Dummy check for already registered DIDs (just a placeholder)
        if did == "did:key:already_registered":
            return TxReceipt(
                hash="0x0000000000000000000000000000000000000000000000000000000000000000",
                gas_used=0,
                success=False,
                error="DID has already been registered",
                error_code=RegisterError.ALREADY_REGISTERED
            )
        
        # Dummy check for rate limiting
        if org_id == "quota_exceeded":
            error_msg = "DID registration quota exceeded for organization"
            logger.warning(f"Simulating quota exceeded error: {error_msg}")
            raise QuotaExceededError(error_msg)
        
        # Simulate successful response
        dummy_tx_hash = "0x" + "0" * 64  # 0x followed by 64 zeros
        
        # Delay for a short time to simulate network latency
        time.sleep(0.1)
        
        logger.info(f"Simulated successful DID registration for {did[:10]}...")
        
        return TxReceipt(
            hash=dummy_tx_hash,
            gas_used=21000,
            success=True,
            error="",
            error_code=RegisterError.UNKNOWN_UNSPECIFIED
        )
    
    def close(self) -> None:
        """Close the stub transport (no-op)."""
        pass