"""
Exceptions for the Gateway module.
"""
from enum import Enum
from typing import Optional


class RegisterError(str, Enum):
    """
    Error codes for DID registration with the Gateway service.
    
    These match the protobuf-generated RegisterError enum values.
    """
    UNKNOWN_UNSPECIFIED = "UNKNOWN_UNSPECIFIED"
    DOC_CID_EMPTY = "DOC_CID_EMPTY"
    ALREADY_REGISTERED = "ALREADY_REGISTERED"
    INVALID_DID = "INVALID_DID"
    SCHEMA_VERSION_MISMATCH = "SCHEMA_VERSION_MISMATCH"
    INVALID_OPERATOR = "INVALID_OPERATOR"
    
    # Legacy/deprecated values not in V2 proto but kept for backward compatibility
    DID_QUOTA_EXCEEDED = "DID_QUOTA_EXCEEDED"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"


class GatewayError(Exception):
    """Base exception for Gateway-related errors."""
    pass


class GatewayConnectionError(GatewayError):
    """Raised when connection to the Gateway service fails."""
    pass


class GatewayResponseError(GatewayError):
    """Raised when the Gateway service returns an error response."""
    
    def __init__(self, message: str, error_code: Optional[str] = None):
        self.error_code = error_code
        super().__init__(message)


class GatewayTimeoutError(GatewayError):
    """Raised when a Gateway operation times out."""
    pass


class QuotaExceededError(GatewayError):
    """Raised when DID registration quota is exceeded."""
    pass


class AlreadyRegisteredError(GatewayError):
    """Raised when attempting to register an already registered DID."""
    pass