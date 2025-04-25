# Import from the actual package, providing our new unified API
import warnings
import os
import sys

# Add the directory with the new package to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from intentlayer_sdk package
from intentlayer_sdk import IntentClient, TxReceipt, CallEnvelope, IntentLayerError, PinningError, TransactionError, EnvelopeError
from intentlayer_sdk import __version__

# For backwards compatibility, expose the original client with a deprecation warning
class AgentLayerClient:
    """
    DEPRECATED: This class is deprecated and will be removed in a future version.
    Use IntentClient instead.
    """
    def __new__(cls, *args, **kwargs):
        warnings.warn(
            "AgentLayerClient is deprecated and will be removed in a future version. "
            "Use IntentClient instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return IntentClient(*args, **kwargs)

# Use the IntentClient directly for backwards compatibility
CallEnvelope = CallEnvelope

# Re-export all names
__all__ = [
    "IntentClient", 
    "TxReceipt", 
    "CallEnvelope", 
    "IntentLayerError", 
    "PinningError", 
    "TransactionError", 
    "EnvelopeError",
    "__version__",
    "AgentLayerClient",
    "OldCallEnvelope"
]