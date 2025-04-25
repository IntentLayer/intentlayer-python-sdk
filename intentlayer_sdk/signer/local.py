"""
Local ECDSA signer using a private key.
"""
from typing import Dict, Any

from eth_account import Account
from web3 import Web3

from intentlayer_sdk.signer import Signer


class LocalSigner:
    """
    Ethereum transaction signer using a local private key.
    
    This signer uses a private key stored in memory to sign transactions.
    """
    
    def __init__(self, private_key: str):
        """
        Initialize a local key signer.
        
        Args:
            private_key: Ethereum private key (with or without 0x prefix)
        """
        # Normalize the private key format
        if not private_key.startswith("0x"):
            private_key = f"0x{private_key}"
            
        # Create the account
        self.account = Account.from_key(private_key)
    
    @property
    def address(self) -> str:
        """
        Get the Ethereum address associated with this signer.
        
        Returns:
            Ethereum address as a checksummed string
        """
        return Web3.to_checksum_address(self.account.address)
    
    def sign_transaction(self, transaction_dict: Dict[str, Any]) -> "Account._SignedTransaction":
        """
        Sign an Ethereum transaction.
        
        Args:
            transaction_dict: Transaction parameters
            
        Returns:
            Signed transaction object with rawTransaction property
        """
        return self.account.sign_transaction(transaction_dict)