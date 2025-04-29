"""
Exceptions for the Gateway module.
"""


class GatewayError(Exception):
    """Base exception for Gateway-related errors."""
    pass


class GatewayConnectionError(GatewayError):
    """Raised when connection to the Gateway service fails."""
    pass


class GatewayResponseError(GatewayError):
    """Raised when the Gateway service returns an error response."""
    pass


class GatewayTimeoutError(GatewayError):
    """Raised when a Gateway operation times out."""
    pass


class QuotaExceededError(GatewayError):
    """Raised when DID registration quota is exceeded."""
    pass


class AlreadyRegisteredError(GatewayError):
    """Raised when attempting to register an already registered DID."""
    pass