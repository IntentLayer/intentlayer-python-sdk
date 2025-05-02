#!/usr/bin/env python3
"""
Example demonstrating auto DID generation in the IntentLayer SDK.
"""
import os
import json
import logging

from intentlayer_sdk import IntentClient
from intentlayer_sdk.identity import get_or_create_did, create_new_identity, list_identities

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """
    Demonstrate using the identity module and auto DID feature.
    
    This example shows how to:
    1. Use the identity module directly
    2. Initialize a client with auto_did=True
    3. Use the client with an automatically generated DID
    """
    # Read configuration from environment
    RPC_URL = os.environ.get("RPC_URL", "https://sepolia.era.zksync.dev")
    PINNER_URL = os.environ.get("PINNER_URL", "https://pin.example.com")
    NETWORK = os.environ.get("NETWORK", "zksync-era-sepolia")
    
    # Display the example title
    print("\n=== IntentLayer SDK Auto DID Example ===\n")
    
    # Example 1: Using the identity module directly
    print("1. Using the identity module directly:")
    
    # Create or retrieve a DID
    identity = get_or_create_did(auto=True)
    print(f"Retrieved identity: {identity.did}")
    print(f"Ethereum address: {identity.signer.address}")
    print(f"Created at: {identity.created_at}")
    
    # Create a new identity
    new_identity = create_new_identity()
    print(f"\nCreated new identity: {new_identity.did}")
    print(f"Ethereum address: {new_identity.signer.address}")
    
    # List all identities
    identities = list_identities()
    print(f"\nFound {len(identities)} identities stored locally")
    
    # Example 2: Using auto_did with the client
    print("\n2. Using auto_did with IntentClient:")
    
    # Initialize a client with auto_did
    try:
        client = IntentClient.from_network(
            network=NETWORK,
            pinner_url=PINNER_URL,
            # Note: No signer provided, will use auto-generated DID
            signer=None,
            auto_did=True,
            logger=logger
        )
        print(f"Created client with auto DID")
        print(f"Client address: {client.address}")
        
        # Access the identity from the client (if needed)
        if hasattr(client, "_identity"):
            print(f"Using DID: {client._identity.did}")
        
    except Exception as e:
        print(f"Error creating client: {str(e)}")


if __name__ == "__main__":
    main()