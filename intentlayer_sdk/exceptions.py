"""
Exceptions used throughout the IntentLayer SDK.
"""

class IntentLayerError(Exception):
    """Base exception for all IntentLayer SDK errors."""
    pass

class PinningError(IntentLayerError):
    """
    Error when pinning to IPFS fails.
    
    This exception is raised when:
    - The IPFS pinner service is unreachable
    - The service returns a non-200 status code
    - The response cannot be parsed as JSON
    - The response is missing the expected CID field
    """
    pass

class TransactionError(IntentLayerError):
    """
    Error when blockchain transaction fails.
    
    This exception is raised when:
    - Transaction signing fails
    - The transaction cannot be sent to the network
    - The transaction is rejected by the network
    - The transaction is reverted by the contract
    """
    pass

class EnvelopeError(IntentLayerError):
    """
    Error with envelope creation or validation.
    
    This exception is raised when:
    - The envelope is missing required fields
    - The envelope hash format is invalid
    - The CID cannot be converted to the correct format
    - The payload is malformed or missing required data
    """
    pass