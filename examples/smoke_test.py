#!/usr/bin/env python3
"""
Smoke test script for the IntentLayer SDK.

This script verifies that all imports work correctly without making any actual
network connections or blockchain transactions.

Usage:
    python smoke_test.py
"""
import os
import sys
from unittest.mock import MagicMock

# Try importing all the main components of the SDK
try:
    from intentlayer_sdk import IntentClient
    from intentlayer_sdk.exceptions import IntentLayerError, PinningError, TransactionError, EnvelopeError
    from intentlayer_sdk.utils import sha256_hex, create_envelope_hash, ipfs_cid_to_bytes
    from intentlayer_sdk.models import CallEnvelope, TxReceipt
    from intentlayer_sdk.version import __version__
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def run_smoke_test():
    """Run a basic smoke test to verify imports and basic functionality."""
    print(f"🧪 Running IntentLayer SDK smoke test (v{__version__})...")
    
    # Create a mock client (no actual connections)
    try:
        # Create a mock client with dummy values
        client = MagicMock(spec=IntentClient)
        client.address = "0x1234567890123456789012345678901234567890"
        
        # Test hash function
        hash_result = sha256_hex("test data")
        assert len(hash_result) == 64, "SHA256 hash should be 64 hex chars"
        
        # Test envelope hash creation
        envelope_data = {"test": "data"}
        envelope_hash = create_envelope_hash(envelope_data)
        assert isinstance(envelope_hash, bytes), "Envelope hash should be bytes"
        assert len(envelope_hash) == 32, "Envelope hash should be 32 bytes"
        
        # Convert bytes to hex representation if needed
        envelope_hash_hex = '0x' + envelope_hash.hex()
        assert len(envelope_hash_hex) == 66, "Hex representation should be 66 chars (with 0x prefix)"
        
        print(f"✅ Smoke test passed! IntentLayer SDK version {__version__} is working correctly.")
        return True
    except Exception as e:
        print(f"❌ Smoke test failed: {e}")
        return False

if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)