"""
Secure key storage for the identity module.
"""
import os
import json
import stat
import logging
import ctypes
from pathlib import Path
from typing import Dict, Any, Optional, List

# Import portalocker for file locking
try:
    import portalocker
except ImportError:
    raise ImportError(
        "portalocker package is required for identity module. "
        "Install with: pip install portalocker"
    )

logger = logging.getLogger(__name__)


class KeyStore:
    """Thread-safe and process-safe key store"""
    
    def __init__(self, store_path: Optional[str] = None):
        """
        Initialize the key store.
        
        Args:
            store_path: Optional custom path for key store
        """
        # Use INTENT_KEY_STORE_PATH env var or default to ~/.intentlayer/keys.json
        if store_path:
            self.store_path = Path(store_path)
        else:
            default_path = os.environ.get(
                "INTENT_KEY_STORE_PATH", 
                os.path.expanduser("~/.intentlayer/keys.json")
            )
            self.store_path = Path(default_path)
            
        # Ensure directory exists with proper permissions
        self._ensure_dir()
        
    def _ensure_dir(self):
        """Ensure key store directory exists with proper permissions"""
        directory = self.store_path.parent
        
        # Create directory if it doesn't exist
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            
        # Set secure permissions on directory
        if os.name == 'posix':  # Unix/Linux/Mac
            os.chmod(directory, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)  # 0700
            
        # Ensure the store file exists with proper permissions
        if not self.store_path.exists():
            with open(self.store_path, 'w') as f:
                json.dump({"identities": {}}, f)
                
        # Set secure permissions on file
        if os.name == 'posix':  # Unix/Linux/Mac
            os.chmod(self.store_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        elif os.name == 'nt':  # Windows
            # Make file hidden and system on Windows
            try:
                ctypes.windll.kernel32.SetFileAttributesW(str(self.store_path), 0x80)
            except Exception as e:
                logger.warning(f"Could not set Windows file attributes: {e}")
    
    def _get_lock_path(self) -> str:
        """Get path for the lock file"""
        return str(self.store_path) + '.lock'
    
    def read(self) -> Dict[str, Any]:
        """
        Read the key store with proper locking.
        
        Returns:
            Dictionary with store contents
        """
        with portalocker.Lock(self._get_lock_path(), timeout=10):
            try:
                with open(self.store_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                # Return empty store if file is empty or not found
                return {"identities": {}}
    
    def write(self, data: Dict[str, Any]):
        """
        Write to the key store with proper locking.
        
        Args:
            data: Dictionary to write to store
        """
        with portalocker.Lock(self._get_lock_path(), timeout=10):
            with open(self.store_path, 'w') as f:
                json.dump(data, f, indent=2)
    
    def add_identity(self, did: str, identity_data: Dict[str, Any]):
        """
        Add a new identity to the store.
        
        Args:
            did: DID of the identity
            identity_data: Identity data to store
        """
        store = self.read()
        store["identities"][did] = identity_data
        self.write(store)
    
    def get_identity(self, did: str) -> Optional[Dict[str, Any]]:
        """
        Get an identity by DID.
        
        Args:
            did: DID to retrieve
            
        Returns:
            Identity data or None if not found
        """
        store = self.read()
        return store["identities"].get(did)
    
    def list_identities(self) -> List[Dict[str, Any]]:
        """
        List all identities in the store.
        
        Returns:
            List of identity data dictionaries
        """
        store = self.read()
        return list(store["identities"].values())
    
    def delete_identity(self, did: str):
        """
        Delete an identity from the store.
        
        Args:
            did: DID to delete
        """
        store = self.read()
        if did in store["identities"]:
            del store["identities"][did]
            self.write(store)
    
    def clear(self):
        """Clear all identities (for testing)"""
        self.write({"identities": {}})