"""
Signer module for the IntentLayer SDK.

This module provides signing interfaces and implementations for transaction signing.
"""
from typing import Dict, Any, Protocol, runtime_checkable

@runtime_checkable
class Signer(Protocol):
    """
    Protocol for signers that can sign Ethereum transactions.
    
    Implementations must provide:
    - address property: The Ethereum address associated with this signer
    - sign_transaction method: Signs an Ethereum transaction
    """
    @property
    def address(self) -> str:
        """
        Get the Ethereum address associated with this signer.
        
        Returns:
            Ethereum address as a checksummed string
        """
        ...
    
    def sign_transaction(self, transaction_dict: Dict[str, Any]) -> Any:
        """
        Sign an Ethereum transaction.
        
        Args:
            transaction_dict: Transaction parameters
            
        Returns:
            Signed transaction object
        """
        ...