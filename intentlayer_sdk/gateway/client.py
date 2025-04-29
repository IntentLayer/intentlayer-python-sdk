"""
Gateway client implementation for the IntentLayer SDK.

This module provides a gRPC client for interacting with the IntentLayer Gateway service.
"""
import os
import time
import random
import logging
import urllib.parse
import sys # Import sys to access modules if needed
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta

# Import JWT for API key parsing
import jwt

# Conditionally import gRPC dependencies at the module level for type hinting etc.
# The GRPC_AVAILABLE flag controls runtime behavior.
try:
    import grpc
    from google.protobuf import timestamp_pb2
    # Note: The actual proto imports would normally be generated from .proto files
    # Since we don't have access to the compiled protos, we'll use placeholders
    # that will be replaced with actual implementations in a production environment
    GRPC_AVAILABLE = True
except ImportError:
    # Define placeholder types if grpc is not available, for type hinting consistency
    class grpc: # type: ignore
        Channel = type('Channel', (), {})
        RpcError = type('RpcError', (Exception,), {})
        StatusCode = type('StatusCode', (), {
            'DEADLINE_EXCEEDED': 'DEADLINE_EXCEEDED',
            'UNAVAILABLE': 'UNAVAILABLE',
            'RESOURCE_EXHAUSTED': 'RESOURCE_EXHAUSTED',
            'INTERNAL': 'INTERNAL',
            'UNKNOWN': 'UNKNOWN',
        })
        @staticmethod
        def ssl_channel_credentials(**kwargs): pass
        @staticmethod
        def secure_channel(target, creds, options=None): pass
        @staticmethod
        def insecure_channel(target): pass

    GRPC_AVAILABLE = False

from ._deps import ensure_grpc_installed

from .exceptions import (
    GatewayError, GatewayConnectionError, GatewayResponseError,
    GatewayTimeoutError, QuotaExceededError, AlreadyRegisteredError
)

logger = logging.getLogger(__name__)

# Rate limiting for error logs
_error_log_timestamps = {}


from dataclasses import dataclass


@dataclass
class TxReceipt:
    """
    Represents a transaction receipt from the Gateway.

    This is a placeholder that would be replaced with a proper protobuf-generated class.
    """
    hash: str = ""
    gas_used: int = 0
    success: bool = False
    error: str = ""


@dataclass
class DidDocument:
    """
    Represents a DID document for Gateway registration.

    This is a placeholder that would be replaced with a proper protobuf-generated class.
    Field 5 is reserved for parent_did in the upcoming INT-211 proto update.
    """
    did: str
    pub_key: bytes
    org_id: Optional[str] = None
    label: Optional[str] = None
    parent_did: Optional[str] = None  # Field 5 in proto - reserved for future parent_did delegation feature (INT-211)


class GatewayClient:
    """
    Client for interacting with the IntentLayer Gateway service.

    This client handles DID registration and intent submission via gRPC.
    """

    def __init__(
        self,
        gateway_url: str,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        verify_ssl: bool = True
    ):
        """
        Initialize the Gateway client.

        Args:
            gateway_url: URL of the gateway service
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates

        Raises:
            ValueError: If gateway_url is invalid or uses insecure HTTP
            ImportError: If gRPC dependencies are not installed
        """
        # Always call ensure_grpc_installed which will raise a proper error if needed
        ensure_grpc_installed()

        # Validate URL
        self._validate_gateway_url(gateway_url)
        self.gateway_url = gateway_url
        self.api_key = api_key

        # Get timeout from env var or parameter (default: 5 seconds)
        self.timeout = timeout or int(os.environ.get("INTENT_GW_TIMEOUT", "5"))

        # Create gRPC channel and stub
        # Note: _create_channel uses 'import grpc' internally, which works with sys.modules patching
        self.channel = self._create_channel(gateway_url, verify_ssl)
        # Stub would be created from generated proto code
        # self.stub = gateway_pb2_grpc.GatewayServiceStub(self.channel)

        # For the proof of concept, we'll simulate the stub
        self.stub = self._create_stub_placeholder()

        logger.debug(f"Initialized Gateway client for {gateway_url}")

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
        # Ensure grpc is imported (this will pick up the mock from sys.modules in tests)
        import grpc as _grpc_runtime # Use a different alias to avoid confusion
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

        creds = None # Initialize creds

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
                            if not hasattr(GatewayClient, '_combined_ca_cache'):
                                GatewayClient._combined_ca_cache = {}
                            cache_key = f"{system_ca_path}:{ca_path}"
                            if cache_key not in GatewayClient._combined_ca_cache:
                                GatewayClient._combined_ca_cache[cache_key] = system_ca_data + b'\n' + ca_data
                            combined_ca = GatewayClient._combined_ca_cache[cache_key]
                            creds = _grpc_runtime.ssl_channel_credentials(root_certificates=combined_ca)
                            logger.info(f"Using custom CA certificate from {ca_path} appended to system roots")
                        except ImportError:
                            logger.warning("certifi not installed, cannot append custom CA to system roots. Using only custom CA.")
                            creds = _grpc_runtime.ssl_channel_credentials(root_certificates=ca_data)
                        except Exception as e_append:
                            logger.warning(f"Failed to load or append system CA: {e_append}. Using only custom CA.")
                            creds = _grpc_runtime.ssl_channel_credentials(root_certificates=ca_data)
                    else:
                        # Use only the provided CA cert, replacing system roots (default, more secure)
                        creds = _grpc_runtime.ssl_channel_credentials(root_certificates=ca_data)
                        logger.info(f"Using custom CA certificate from {ca_path} (replacing system roots)")
                except Exception as e_load:
                    logger.warning(f"Failed to load custom CA certificate from {ca_path}: {e_load}")
                    if strict_ca:
                        raise ValueError(f"Failed to load custom CA certificate from {ca_path}: {e_load}")
                    # Fallback to default credentials if not strict
                    creds = _grpc_runtime.ssl_channel_credentials()
            else:
                 # Standard SSL credentials with system roots if no custom CA path
                creds = _grpc_runtime.ssl_channel_credentials()

            # Create secure channel with proper options for performance
            options = [
                # Keepalive settings
                ('grpc.keepalive_time_ms', 30000),  # 30 seconds
                ('grpc.keepalive_timeout_ms', 10000),  # 10 seconds
                ('grpc.http2.max_pings_without_data', 0), # Allow pings even without data
                ('grpc.http2.min_time_between_pings_ms', 10000), # Minimum 10s between pings

                # Message size limits (10 MB for future batched envelopes)
                ('grpc.max_send_message_length', 10 * 1024 * 1024),     # 10 MB
                ('grpc.max_receive_message_length', 10 * 1024 * 1024),  # 10 MB
            ]
            return _grpc_runtime.secure_channel(target, creds, options=options)

        else:
            # Insecure channel (for development only)
            logger.warning(f"Creating insecure gRPC channel to {target} (not recommended for production)")
            # No creds needed for insecure channel
            return _grpc_runtime.insecure_channel(target)


    def _create_stub_placeholder(self):
        """
        Create a placeholder for the gRPC stub.

        Note: This is a temporary solution until we have proper proto-generated stubs.

        When the actual stub is wired, the register_did method should include:
        - per-retry timeout parameter to avoid N × global timeout
        - proper error handling for actual gRPC responses
        """
        class StubPlaceholder:
            def RegisterDid(self, request, timeout=None, metadata=None): # Add metadata arg
                # Simulate a successful response
                logger.debug(f"StubPlaceholder.RegisterDid called with request: {request}, timeout: {timeout}, metadata: {metadata}")
                # In a real scenario, you might simulate errors based on input
                return TxReceipt(
                    hash="0x0000000000000000000000000000000000000000000000000000000000000000",
                    gas_used=0,
                    success=True,
                    error=""
                )

        return StubPlaceholder()

    def _rate_limited_log(self, message: str, level: str = "warning", interval: int = 60) -> None:
        """
        Log a message with rate limiting.

        Args:
            message: Message to log
            level: Log level (debug, info, warning, error, critical)
            interval: Minimum interval between logs in seconds
        """
        now = datetime.now()
        key = f"{level}:{message}"

        # Check if we've logged this recently
        last_time = _error_log_timestamps.get(key)
        if last_time and (now - last_time < timedelta(seconds=interval)):
            return  # Skip logging

        # Log the message
        log_method = getattr(logger, level.lower(), logger.warning) # Default to warning if invalid level
        log_method(message)

        # Update timestamp
        _error_log_timestamps[key] = now

    def _create_metadata(self) -> Optional[Tuple[Tuple[str, str], ...]]:
        """
        Create gRPC metadata with authentication.

        Returns:
            Tuple of metadata key-value pairs, or None if no metadata needed.
        """
        metadata = []
        if self.api_key:
            # TODO: Add logic here to potentially validate/decode the API key if needed
            # Example: Check expiry, required claims etc.
            # try:
            #     # Decode without verification just to check structure/expiry
            #     # Replace with actual validation logic if required
            #     decoded = jwt.decode(self.api_key, options={"verify_signature": False, "verify_aud": False})
            #     # Check expiry if present
            #     if 'exp' in decoded and datetime.utcfromtimestamp(decoded['exp']) < datetime.utcnow():
            #         logger.error("API Key has expired.")
            #         # Decide how to handle expired key - raise error? log warning? proceed anyway?
            #         # For now, just log and proceed
            # except jwt.ExpiredSignatureError:
            #      logger.error("API Key has expired (jwt verification).")
            # except jwt.InvalidTokenError as e:
            #      logger.warning(f"Invalid API Key format: {e}")

            metadata.append(('authorization', f'Bearer {self.api_key}'))

        return tuple(metadata) if metadata else None # Return None if empty

    def register_did(
        self,
        did: str,
        pub_key: Optional[bytes] = None,
        org_id: Optional[str] = None,
        label: Optional[str] = None,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        retry_timeout: Optional[int] = None
    ) -> TxReceipt:
        """
        Register a DID with the Gateway service.

        Implements automatic exponential backoff retries for transient errors.

        Args:
            did: The decentralized identifier to register
            pub_key: Public key associated with the DID (optional if already in DID)
            org_id: Organization ID (optional)
            label: Human-readable label for the DID (optional)
            max_retries: Maximum number of retry attempts (default: 3)
            backoff_base: Base delay for exponential backoff in seconds (default: 0.5)
            retry_timeout: Timeout for each retry attempt in seconds (defaults to self.timeout)

        Returns:
            Transaction receipt

        Raises:
            QuotaExceededError: If DID registration quota is exceeded
            AlreadyRegisteredError: If DID is already registered (Note: This is now returned, not raised)
            GatewayError: For other Gateway-related errors
        """
        last_error = None
        retry_count = 0

        # Create DID document once outside the retry loop
        doc = DidDocument(did=did, pub_key=pub_key or b'', org_id=org_id, label=label)

        # Create metadata with authorization
        metadata = self._create_metadata()

        # Implement retry with exponential backoff
        while retry_count <= max_retries:
            # If this is a retry, delay with exponential backoff
            if retry_count > 0:
                delay = backoff_base * (2 ** (retry_count - 1))
                # Add up to 10% jitter to avoid thundering herd
                jitter = delay * random.uniform(0, 0.1)
                actual_delay = delay + jitter
                logger.info(f"Retrying DID registration (attempt {retry_count+1}/{max_retries+1}) in {actual_delay:.2f}s") # Corrected log message
                time.sleep(actual_delay)

            # Use per-retry timeout if specified, otherwise fall back to global timeout
            current_timeout = retry_timeout if retry_timeout is not None else self.timeout

            try:
                # Pass metadata to the stub call
                response = self.stub.RegisterDid(doc, timeout=current_timeout, metadata=metadata)

                # Check for errors in the response
                if not response.success:
                    error = response.error or "Unknown error from Gateway"

                    # Handle specific error cases
                    if "ALREADY_REGISTERED" in error:
                        logger.debug(f"DID {did[:10]}... already registered with Gateway (received error: {error})")
                        # Not raising an exception here, as this is often expected
                        return response # Return the error response from the gateway

                    elif "DID_QUOTA_EXCEEDED" in error:
                        self._rate_limited_log(
                            f"DID quota exceeded for {did[:10]}... (received error: {error})",
                            level="warning",
                            interval=60 # Log only once per minute
                        )
                        # Raise specific exception for quota exceeded
                        raise QuotaExceededError(f"DID registration quota exceeded (Gateway error: {error})")

                    else:
                        # General error from Gateway - might be retryable depending on gateway logic
                        # For now, treat unknown gateway errors as potentially retryable
                        logger.warning(f"Gateway returned failure for DID {did[:10]}...: {error}. Retrying (attempt {retry_count+1}/{max_retries+1})...")
                        last_error = GatewayResponseError(f"Failed to register DID: {error}")
                        retry_count += 1
                        continue # Go to next retry iteration

                # Log success (with truncated DID for privacy)
                logger.info(f"Successfully registered DID {did[:10]}... with Gateway")
                return response # Return successful response

            except QuotaExceededError:
                # Explicitly re-raise QuotaExceededError to prevent it being caught by general Exception
                raise

            # ==================================================================
            # Start of the Exception Handling Block with Corrected Timeout Check
            # ==================================================================
            except Exception as e:
                # 1) IMMEDIATELY turn grpc DEADLINE_EXCEEDED into a timeout and bubble out
                if GRPC_AVAILABLE:
                    _grpc = None # Define _grpc before try block
                    try:
                        import grpc as _grpc
                    except ImportError:
                        # Should not happen if GRPC_AVAILABLE is true, but handle defensively
                        logger.error("GRPC_AVAILABLE is True, but failed to import grpc dynamically in timeout check.")
                        _grpc = None # Ensure _grpc is None if import fails

                    # Check for DEADLINE_EXCEEDED only if _grpc was successfully imported and e has .code()
                    # Place the raise OUTSIDE the inner try/except
                    if (
                        _grpc
                        and hasattr(e, "code") and callable(e.code)
                        # Check code == DEADLINE_EXCEEDED (handle potential AttributeError if e.code fails)
                        # This comparison happens *before* raising, so no inner try/except needed here
                        and getattr(e, 'code', lambda: None)() == _grpc.StatusCode.DEADLINE_EXCEEDED
                    ):
                        # Bypass all other handling and immediately escape
                        raise GatewayTimeoutError(f"DID registration timed out after {current_timeout}s")

                # 2) Now do your existing fallback for UNAVAILABLE, RESOURCE_EXHAUSTED, etc.
                error_details = str(e)
                is_retryable = False
                grpc_error   = False # Assume not a gRPC error initially

                # Check for other gRPC errors using duck typing (has .code() method)
                if GRPC_AVAILABLE:
                    # Reuse _grpc if already imported, otherwise try importing again
                    if _grpc is None: # Check if import failed above
                         try: import grpc as _grpc
                         except ImportError: _grpc = None

                    # Check if 'e' behaves like a gRPC error (has code() and details())
                    # AND ensure it wasn't the DEADLINE_EXCEEDED already handled/raised above
                    if _grpc and hasattr(e, "code") and callable(e.code) and \
                       (not hasattr(_grpc.StatusCode, 'DEADLINE_EXCEEDED') or e.code() != _grpc.StatusCode.DEADLINE_EXCEEDED):
                        grpc_error = True
                        code = None
                        details = error_details # Default details
                        try: code = e.code()
                        except Exception: logger.warning("Caught gRPC-like error without .code() method.")
                        try:
                            # Use details() if available and callable
                            details_method = getattr(e, 'details', None)
                            if callable(details_method):
                                details = details_method() or details
                        except Exception: logger.warning("Error calling .details() on gRPC-like error.")

                        # now branch on code (excluding DEADLINE_EXCEEDED)
                        if code == _grpc.StatusCode.UNAVAILABLE:
                             # Simplified error message for unavailable
                            last_error = GatewayConnectionError(
                                f"Gateway service unavailable: {details}"
                            )
                            is_retryable = True
                        elif code in (
                            _grpc.StatusCode.RESOURCE_EXHAUSTED,
                            _grpc.StatusCode.INTERNAL,
                            _grpc.StatusCode.UNKNOWN,
                        ):
                             # Simplified error message for other retryable codes
                            last_error = GatewayError(
                                f"gRPC error during DID registration: {code} - {details}"
                            )
                            is_retryable = True
                        else:
                             # Simplified error message for non-retryable codes
                            last_error = GatewayError(
                                f"gRPC error during DID registration: {code} - {details}"
                            )
                            is_retryable = False # Don't retry other gRPC errors

                # If it wasn’t identified as a gRPC error (and wasn't DEADLINE_EXCEEDED)
                if not grpc_error:
                    # Check if it's the GatewayTimeoutError we might have raised (shouldn't happen now)
                    if isinstance(e, GatewayTimeoutError):
                         last_error = e
                         is_retryable = False # Should have already been raised
                         logger.error("Caught GatewayTimeoutError unexpectedly in fallback logic - indicates issue.")
                    else:
                        # Handle non-gRPC errors by checking keywords
                        retryable_keywords = ["timeout", "unavailable", "resource", "temporary", "overloaded", "connection refused"]
                        is_retryable = any(tok in error_details.lower() for tok in retryable_keywords)
                        last_error = GatewayError(f"Failed to register DID: {error_details}")

                # Decide whether to retry or raise based on retry logic
                if is_retryable and retry_count < max_retries:
                    # Log the specific error determined above before retrying
                    logger.warning(f"Caught retryable error during DID registration (attempt {retry_count+1}/{max_retries+1}): {last_error or e}. Retrying...")
                    retry_count += 1
                    continue # Continue to the next iteration of the while loop
                else:
                    # Ran out of retries or the error was not retryable
                    # Use the 'last_error' if set, otherwise wrap the original 'e'
                    final_error = last_error or GatewayError(f"Failed to register DID: {error_details}")
                    logger.error(f"Failed to register DID {did[:10]}... after {retry_count+1} attempts. Final error: {final_error}")
                    raise final_error # Raise the specific error we determined
            # ==================================================================
            # End of the Exception Handling Block
            # ==================================================================

        # If the loop finishes without returning or raising (should only happen if max_retries is negative)
        logger.error(f"DID registration loop completed unexpectedly for {did[:10]}... Max retries exceeded.")
        # Raise the last recorded error, or a generic message if none was recorded
        raise last_error or GatewayError("Failed to register DID after multiple attempts")


    def close(self):
        """Close the gRPC channel."""
        # Check if channel exists and has a close method
        channel_to_close = getattr(self, "channel", None)
        if channel_to_close and callable(getattr(channel_to_close, "close", None)):
            try:
                channel_to_close.close()
                logger.debug("gRPC channel closed.")
            except Exception as e:
                # Log warning but don't prevent cleanup
                logger.warning(f"Error closing gRPC channel: {e}", exc_info=True)
        # Ensure self.channel reference is NOT cleared here for testing purposes

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager, ensuring channel closure."""
        self.close()
