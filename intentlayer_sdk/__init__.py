"""
IntentLayer SDK - Python client for the IntentLayer protocol.
"""
import warnings
from .client import IntentClient
from .models import TxReceipt, CallEnvelope
from .exceptions import IntentLayerError, PinningError, TransactionError, EnvelopeError

# Import version
from .version import __version__

# Backward compatibility layer - will be removed in v1.0.0
class IntentLayerClient(IntentClient):
    """
    Backward compatibility class. Please use IntentClient instead.
    
    This alias will be removed in version 1.0.0.
    """
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "IntentLayerClient is deprecated and will be removed in version 1.0.0. "
            "Please use IntentClient instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        super().__init__(*args, **kwargs)

__all__ = [
    "IntentClient",
    "IntentLayerClient",  # Deprecated
    "TxReceipt", 
    "CallEnvelope",
    "IntentLayerError",
    "PinningError",
    "TransactionError",
    "EnvelopeError",
    "__version__"
]