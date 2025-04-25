"""
IntentLayer SDK - Python client for the IntentLayer protocol.
"""
import warnings
from .client import IntentClient
from .models import TxReceipt
from .envelope import CallEnvelope, create_envelope
from .exceptions import (
    IntentLayerError, PinningError, TransactionError, 
    EnvelopeError, NetworkError, AlreadyRegisteredError, InactiveDIDError
)
from .config import NetworkConfig, NETWORKS
from .signer import Signer
from .signer.local import LocalSigner

# Import version
from .version import __version__

# No backward compatibility layer - using clean API from the start

__all__ = [
    # Main client
    "IntentClient",
    
    # Models
    "TxReceipt", 
    "CallEnvelope",
    
    # Envelope utilities
    "create_envelope",
    
    # Network configuration
    "NetworkConfig",
    "NETWORKS",
    
    # Signers
    "Signer",
    "LocalSigner",
    
    # Exceptions
    "IntentLayerError",
    "PinningError",
    "TransactionError",
    "EnvelopeError",
    "NetworkError",
    "AlreadyRegisteredError",
    "InactiveDIDError",
    
    # Version
    "__version__"
]