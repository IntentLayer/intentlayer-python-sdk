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

class NetworkError(IntentLayerError):
    """
    Error related to network configuration or connection.
    
    This exception is raised when:
    - Network configuration is invalid or cannot be loaded
    - Chain ID validation fails
    - RPC endpoint is unreachable
    - Network-specific parameters are incorrect
    """
    pass

class AlreadyRegisteredError(IntentLayerError):
    """
    Error when trying to register a DID that is already registered.
    
    This exception is raised when:
    - A DID is already registered and active in the DIDRegistry
    
    Attributes:
        did: The DID that was attempted to be registered
        owner: The address that already owns the DID
    """
    def __init__(self, did: str, owner: str):
        self.did = did
        self.owner = owner
        super().__init__(f"DID '{did}' is already registered to {owner}")
        
class InactiveDIDError(IntentLayerError):
    """
    Error when trying to use an inactive DID.
    
    This exception is raised when:
    - A DID exists but has been marked as inactive
    
    Attributes:
        did: The inactive DID
        owner: The address that owns the DID (optional)
    """
    def __init__(self, did: str, owner: str = None):
        self.did = did
        self.owner = owner
        if owner:
            message = f"DID '{did}' exists but is inactive (owner: {owner})"
        else:
            message = f"DID '{did}' is not active"
        super().__init__(message)