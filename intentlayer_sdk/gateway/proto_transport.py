"""
Proto-based transport implementation for the Gateway service.

This module provides a gRPC-based transport implementation using
the protocol buffer definitions generated from gateway.proto.
"""
import os
import sys
import urllib.parse
import logging
import time
import random
from typing import Optional, Dict, Any, List, Tuple, Union

# Import TTLCache for rate limiting if available
try:
    from cachetools import TTLCache
    TTLCACHE_AVAILABLE = True
except ImportError:
    TTLCACHE_AVAILABLE = False

# Conditionally import gRPC dependencies
try:
    import grpc
    from google.protobuf import timestamp_pb2
    from google.protobuf import wrappers_pb2
    
    # Try to import the generated proto classes
    try:
        from .proto import (
            RegisterError as ProtoRegisterError,
            DidDocument as ProtoDidDocument,
            TxReceipt as ProtoTxReceipt,
            RegisterDidRequest,
            RegisterDidResponse,
            GatewayServiceStub,
            PROTO_AVAILABLE
        )
        # If we get here, all proto imports succeeded
        GRPC_AVAILABLE = True
    except ImportError:
        # Proto imports failed
        PROTO_AVAILABLE = False
        GRPC_AVAILABLE = False
except ImportError:
    # gRPC not available
    GRPC_AVAILABLE = False
    PROTO_AVAILABLE = False

# Local imports
from .transport import GatewayTransport, TxReceipt
from .exceptions import (
    GatewayError, GatewayConnectionError, GatewayResponseError,
    GatewayTimeoutError, QuotaExceededError, AlreadyRegisteredError,
    RegisterError
)
from ._deps import ensure_grpc_installed

# Configure logger
logger = logging.getLogger(__name__)


class ProtoTransport(GatewayTransport):
    """
    gRPC-based transport implementation using protocol buffers.
    """
    
    def __init__(self):
        """Initialize the proto transport."""
        self.channel = None
        self.stub = None
        self.gateway_url = None
        
    def is_available(self) -> bool:
        """
        Check if proto transport is available.
        
        Returns:
            True if gRPC and proto dependencies are available, False otherwise
        """
        return GRPC_AVAILABLE and PROTO_AVAILABLE
    
    def _validate_gateway_url(self, url: str) -> None:
        """
        Validate the gateway URL is secure.
        
        Args:
            url: Gateway URL to validate
            
        Raises:
            ValueError: If URL is invalid or uses insecure HTTP
        """
        try:
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname or ""
            # Treat loopback IPv6 address as local as well
            is_local = host in ("localhost", "127.0.0.1", "::1")
            
            # Check for HTTPS unless explicitly allowed insecure or it's a local address
            if parsed.scheme != "https" and not is_local:
                insecure_allowed = os.environ.get("INTENT_INSECURE_GW") == "1"
                if not insecure_allowed:
                    raise ValueError(
                        f"Gateway URL must use HTTPS for security (got: {parsed.scheme}://). "
                        "Set INTENT_INSECURE_GW=1 to allow HTTP for development."
                    )
        except Exception as e:
            # Catch potential parsing errors too
            raise ValueError(f"Invalid gateway URL '{url}': {e}")
            
    def _create_channel(self, url: str, verify_ssl: bool) -> grpc.Channel:
        """
        Create a secure gRPC channel with optional custom CA.
        
        Args:
            url: Gateway URL
            verify_ssl: Whether to verify SSL certificates
            
        Returns:
            gRPC channel
        """
        # Parse URL to extract host and port
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        # Default to port 443 for https, 80 for http if not specified
        default_port = 443 if parsed.scheme == 'https' else 80
        port = parsed.port or default_port
        target = f"{host}:{port}"
        
        # Handle custom CA certificate if provided
        # By default, INTENT_GATEWAY_CA replaces system roots unless INTENT_GATEWAY_APPEND_CA=1
        ca_path = os.environ.get("INTENT_GATEWAY_CA")
        strict_ca = os.environ.get("INTENT_GATEWAY_STRICT_CA") == "1"
        append_ca = os.environ.get("INTENT_GATEWAY_APPEND_CA") == "1"
        
        creds = None  # Initialize creds
        
        if verify_ssl:
            if ca_path:
                try:
                    with open(ca_path, 'rb') as f:
                        ca_data = f.read()
                        
                    if append_ca:
                        # Append custom CA to system roots
                        try:
                            import certifi
                            system_ca_path = certifi.where()
                            with open(system_ca_path, 'rb') as f:
                                system_ca_data = f.read()
                            # Cache the combined CA data to avoid memory issues with repeated calls
                            # Use a class attribute for caching
                            if not hasattr(ProtoTransport, '_combined_ca_cache'):
                                ProtoTransport._combined_ca_cache = {}
                            cache_key = f"{system_ca_path}:{ca_path}"
                            if cache_key not in ProtoTransport._combined_ca_cache:
                                ProtoTransport._combined_ca_cache[cache_key] = system_ca_data + b'\n' + ca_data
                            combined_ca = ProtoTransport._combined_ca_cache[cache_key]
                            creds = grpc.ssl_channel_credentials(root_certificates=combined_ca)
                            logger.info(f"Using custom CA certificate from {ca_path} appended to system roots")
                        except ImportError:
                            logger.warning("certifi not installed, cannot append custom CA to system roots. Using only custom CA.")
                            creds = grpc.ssl_channel_credentials(root_certificates=ca_data)
                        except Exception as e_append:
                            logger.warning(f"Failed to load or append system CA: {e_append}. Using only custom CA.")
                            creds = grpc.ssl_channel_credentials(root_certificates=ca_data)
                    else:
                        # Use only the provided CA cert, replacing system roots (default, more secure)
                        creds = grpc.ssl_channel_credentials(root_certificates=ca_data)
                        logger.info(f"Using custom CA certificate from {ca_path} (replacing system roots)")
                except Exception as e_load:
                    logger.warning(f"Failed to load custom CA certificate from {ca_path}: {e_load}")
                    if strict_ca:
                        raise ValueError(f"Failed to load custom CA certificate from {ca_path}: {e_load}")
                    # Fallback to default credentials if not strict
                    creds = grpc.ssl_channel_credentials()
            else:
                # Standard SSL credentials with system roots if no custom CA path
                creds = grpc.ssl_channel_credentials()
                
            # Create secure channel with proper options for performance
            options = [
                # Keepalive settings
                ('grpc.keepalive_time_ms', 30000),  # 30 seconds
                ('grpc.keepalive_timeout_ms', 10000),  # 10 seconds
                ('grpc.http2.max_pings_without_data', 0),  # Allow pings even without data
                ('grpc.http2.min_time_between_pings_ms', 10000),  # Minimum 10s between pings
                
                # Message size limits (10 MB for future batched envelopes)
                ('grpc.max_send_message_length', 10 * 1024 * 1024),  # 10 MB
                ('grpc.max_receive_message_length', 10 * 1024 * 1024),  # 10 MB
            ]
            return grpc.secure_channel(target, creds, options=options)
            
        else:
            # Insecure channel (for development only)
            logger.warning(f"Creating insecure gRPC channel to {target} (not recommended for production)")
            return grpc.insecure_channel(target)
    
    def initialize(self, gateway_url: str, verify_ssl: bool = True) -> None:
        """
        Initialize the proto transport with the given gateway URL.
        
        Args:
            gateway_url: URL of the gateway service
            verify_ssl: Whether to verify SSL certificates
            
        Raises:
            GatewayConnectionError: If connection initialization fails
            ImportError: If gRPC dependencies are not installed
        """
        # Ensure gRPC is installed
        ensure_grpc_installed()
        
        # Validate URL
        self._validate_gateway_url(gateway_url)
        self.gateway_url = gateway_url
        
        # Create gRPC channel
        try:
            self.channel = self._create_channel(gateway_url, verify_ssl)
            # Create stub for gRPC communication
            self.stub = GatewayServiceStub(self.channel)
            logger.debug(f"Initialized proto transport for {gateway_url}")
        except Exception as e:
            raise GatewayConnectionError(f"Failed to initialize proto transport: {e}")
    
    def _create_did_document(
        self,
        did: str,
        pub_key: Optional[bytes] = None,
        org_id: Optional[str] = None,
        label: Optional[str] = None,
        schema_version: Optional[int] = 2,
        doc_cid: Optional[str] = None,
        payload_cid: Optional[str] = None
    ) -> ProtoDidDocument:
        """
        Create a DidDocument proto message.
        
        Args:
            did: DID to register
            pub_key: Public key bytes
            org_id: Organization ID
            label: Label for the DID
            schema_version: Schema version
            doc_cid: Document CID
            payload_cid: Payload CID
            
        Returns:
            DidDocument proto message
        """
        doc = ProtoDidDocument()
        doc.did = did
        if pub_key:
            doc.pub_key = pub_key
            
        if org_id:
            doc.org_id = org_id
        if label:
            doc.label = label
            
        # Use wrappers for optional schema_version
        if schema_version is not None:
            doc.schema_version.value = schema_version
            
        if doc_cid:
            doc.doc_cid = doc_cid
        if payload_cid:
            doc.payload_cid = payload_cid
            
        return doc
    
    def _tx_receipt_from_proto(self, proto_response: RegisterDidResponse) -> TxReceipt:
        """
        Convert a proto response to a TxReceipt.
        
        Args:
            proto_response: Proto response with receipt
            
        Returns:
            TxReceipt
        """
        if not hasattr(proto_response, "receipt"):
            raise ValueError("Response does not contain a receipt")
            
        proto_receipt = proto_response.receipt
        
        # Convert proto enum to string for our enum
        error_code_str = ProtoRegisterError.Name(proto_receipt.error_code)
        
        return TxReceipt(
            hash=proto_receipt.hash,
            gas_used=proto_receipt.gas_used,
            success=proto_receipt.success,
            error=proto_receipt.error,
            error_code=error_code_str
        )
    
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
        Register a DID with the Gateway service.
        
        Args:
            did: The decentralized identifier to register
            pub_key: Public key associated with the DID (optional if already in DID)
            org_id: Organization ID (optional)
            label: Human-readable label for the DID (optional)
            schema_version: Schema version number (optional)
            doc_cid: Document CID (optional)
            payload_cid: Payload CID (optional)
            timeout: Request timeout in seconds (defaults to environment var or 5s)
            metadata: Request metadata key-value pairs
            
        Returns:
            Transaction receipt
            
        Raises:
            QuotaExceededError: If DID registration quota is exceeded
            GatewayError: For other Gateway-related errors
        """
        if not self.stub:
            raise GatewayConnectionError("Proto transport not initialized")
            
        # Check for timeout from environment or parameter (default: 5 seconds)
        if timeout is None:
            timeout = int(os.environ.get("INTENT_GW_TIMEOUT", "5"))
            
        # Create DID document
        proto_doc = self._create_did_document(
            did=did,
            pub_key=pub_key,
            org_id=org_id,
            label=label,
            schema_version=schema_version,
            doc_cid=doc_cid,
            payload_cid=payload_cid
        )
        
        # Create request
        request = RegisterDidRequest(document=proto_doc)
        
        try:
            # Send request
            proto_response = self.stub.RegisterDid(
                request,
                timeout=timeout,
                metadata=metadata
            )
            
            # Convert response to TxReceipt
            response = self._tx_receipt_from_proto(proto_response)
            
            # Check for errors in the response
            if not response.success:
                error = response.error or "Unknown error from Gateway"
                error_code = response.error_code
                
                # Handle specific error cases based on error code
                if error_code == RegisterError.ALREADY_REGISTERED:
                    logger.debug(f"DID {did[:10]}... already registered with Gateway (received error: {error})")
                    # Return the error response rather than raising an exception
                    return response
                    
                elif error_code == RegisterError.DID_QUOTA_EXCEEDED:
                    # Rate limit this error log to avoid spam
                    logger.warning(f"DID quota exceeded for {did[:10]}... (received error: {error})")
                    # Raise specific exception for quota exceeded
                    raise QuotaExceededError(f"DID registration quota exceeded (Gateway error: {error})")
                    
                elif error_code == RegisterError.INVALID_DID:
                    # This is a client-side validation error, should not be retried
                    raise GatewayResponseError(f"Invalid DID format: {error}", error_code)
                    
                elif error_code in (RegisterError.DOC_CID_EMPTY, RegisterError.INVALID_DOC_CID):
                    # CID validation errors
                    raise GatewayResponseError(f"Invalid document CID: {error}", error_code)
                    
                elif error_code == RegisterError.UNAUTHORIZED:
                    # Authorization errors
                    raise GatewayResponseError(f"Unauthorized: {error}", error_code)
                    
                elif error_code == RegisterError.INVALID_PAYLOAD:
                    # Invalid payload errors
                    raise GatewayResponseError(f"Invalid payload: {error}", error_code)
                    
                else:
                    # General error from Gateway
                    raise GatewayResponseError(f"Gateway error: {error}", error_code)
                    
            # Log success (with truncated DID for privacy)
            logger.info(f"Successfully registered DID {did[:10]}... with Gateway")
            return response
            
        except QuotaExceededError:
            # Explicitly re-raise QuotaExceededError to prevent it being caught
            raise
            
        except grpc.RpcError as e:
            # Handle gRPC-specific errors
            if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                raise GatewayTimeoutError(f"DID registration timed out after {timeout}s")
                
            elif e.code() == grpc.StatusCode.UNAVAILABLE:
                raise GatewayConnectionError(f"Gateway service unavailable: {e.details()}")
                
            elif e.code() in (
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                grpc.StatusCode.INTERNAL,
                grpc.StatusCode.UNKNOWN
            ):
                # These are potentially retryable by the caller
                raise GatewayError(f"gRPC error during DID registration: {e.code()} - {e.details()}")
                
            else:
                # Other gRPC errors
                raise GatewayError(f"gRPC error during DID registration: {e.code()} - {e.details()}")
                
        except (GatewayResponseError, GatewayTimeoutError):
            # Re-raise these errors directly
            raise
            
        except Exception as e:
            # Handle any other exceptions
            raise GatewayError(f"Failed to register DID: {e}")
    
    def close(self) -> None:
        """Close any open connections."""
        if hasattr(self, "channel") and self.channel and hasattr(self.channel, "close"):
            try:
                self.channel.close()
                logger.debug("Proto transport closed")
            except Exception as e:
                logger.warning(f"Error closing proto transport: {e}")