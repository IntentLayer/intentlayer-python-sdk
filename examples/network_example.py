#!/usr/bin/env python3
"""
Example of using IntentClient with network configuration.
"""
import os
import time
import hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from intentlayer_sdk import (
    IntentClient, 
    create_envelope,
    NetworkConfig,
    LocalSigner
)

def main():
    """
    Demonstrate usage of the IntentClient with network-based configuration.
    
    This example shows how to:
    1. Initialize the client from a network configuration
    2. Create a complete signed envelope
    3. Register a DID
    4. Record an intent
    5. Get a block explorer URL for the transaction
    """
    # Read environment variables
    PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
    PINNER_URL = os.environ.get("PINNER_URL", "https://pin.example.com")
    
    # Verify configuration
    if not PRIVATE_KEY:
        print("ERROR: PRIVATE_KEY environment variable is required")
        return
    
    # Available networks
    print("Available networks:")
    for network_name in NetworkConfig.load_networks().keys():
        print(f"  - {network_name}")
    print()
    
    # Create a signer from private key
    signer = LocalSigner(PRIVATE_KEY)
    print(f"Signer address: {signer.address}")
    
    # Initialize the client using the zksync-era-sepolia network
    network = "zksync-era-sepolia"
    client = IntentClient.from_network(
        network=network,
        pinner_url=PINNER_URL,
        signer=signer
    )
    
    # Verify chain ID
    client.assert_chain_id()
    print(f"Connected to network: {network}")
    
    # Get minimum stake
    min_stake = client.min_stake_wei
    print(f"Minimum stake: {min_stake} wei ({min_stake / 10**18} ETH)")
    
    # Create a signed envelope
    prompt = "What is the capital of France?"
    
    # Generate a test Ed25519 key for envelope signing
    private_key = Ed25519PrivateKey.generate()
    
    # Example DID (would be registered by your application)
    did = "did:key:z6MkpzExampleTestDid123456789abcdefgh"
    
    # Create the envelope
    envelope = create_envelope(
        prompt=prompt,
        model_id="gpt-4o@2025-03-12",
        tool_id="openai.chat",
        did=did,
        private_key=private_key,
        stake_wei=min_stake,
        timestamp_ms=int(time.time() * 1000)
    )
    
    # Get envelope hash
    envelope_hash = envelope.hex_hash()
    print(f"Created envelope with hash: {envelope_hash}")
    
    # Create a payload with the envelope
    payload = {
        "prompt": prompt,
        "envelope": envelope.model_dump(),
        "metadata": {
            "user_id": "user123",
            "session_id": "session456"
        }
    }
    
    try:
        # First, register the DID
        # Note: This is commented out as it might fail if the DID is already registered
        # You would normally check first if the DID is registered
        # print("Registering DID...")
        # did_tx = client.register_did(did)
        # print(f"DID registered: {client.tx_url(did_tx['transactionHash'])}")
        
        # Then, record the intent
        print("Recording intent...")
        tx_receipt = client.record_intent(envelope_hash, payload)
        
        # Print transaction details
        tx_hash = tx_receipt["transactionHash"]
        print(f"Intent recorded successfully!")
        print(f"Transaction hash: {tx_hash}")
        print(f"Block explorer: {client.tx_url(tx_hash)}")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()