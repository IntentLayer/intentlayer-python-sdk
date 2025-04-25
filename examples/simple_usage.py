#!/usr/bin/env python3
"""
Simple example of using the IntentLayer SDK.
"""
import os
import json
from intentlayer_sdk import IntentClient

def main():
    """
    Demonstrate basic usage of the IntentClient.
    
    This example shows how to:
    1. Initialize the client
    2. Create a simple call envelope
    3. Send an intent to record it on-chain
    """
    # Read configuration from environment
    RPC_URL = os.environ.get("RPC_URL", "https://sepolia.era.zksync.dev")
    PINNER_URL = os.environ.get("PINNER_URL", "https://pin.example.com")
    CONTRACT_ADDRESS = os.environ.get("INTENT_RECORDER_ADDRESS")
    PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
    
    # Verify configuration
    if not CONTRACT_ADDRESS:
        print("ERROR: INTENT_RECORDER_ADDRESS environment variable is required")
        return
    
    if not PRIVATE_KEY:
        print("ERROR: PRIVATE_KEY environment variable is required")
        return
    
    # Initialize the client
    client = IntentClient(
        rpc_url=RPC_URL,
        pinner_url=PINNER_URL,
        min_stake_wei=10**16,  # 0.01 ETH
        priv_key=PRIVATE_KEY,
        contract_address=CONTRACT_ADDRESS
    )
    
    # Create a sample payload with an envelope
    envelope_hash = "0x7d5a99f603f231d53a4f39d1521f98d2e8bb279cf29bebfd0687dc98458e7f89"
    payload = {
        "prompt": "What is the capital of France?",
        "envelope": {
            "model_id": "gpt-4o@2025-03-12",
            "prompt_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "tool_id": "openai.chat",
            "did": "did:key:z6MkpzExampleDid",
            "timestamp_ms": 1711234567890,
            "stake_wei": "10000000000000000",
            "sig_ed25519": "YXNkZmFzZGZhc2RmYXNkZmFzZGZhc2RmYXNkZmFzZGZhc2RmYXNkZmFzZGZhc2RmYXNkZmFzZGZhc2RmYXNkZmFzZGY="
        },
        "metadata": {
            "user_id": "user123",
            "session_id": "session456"
        }
    }
    
    try:
        # Send the intent
        tx_receipt = client.send_intent(envelope_hash, payload)
        
        # Print transaction details
        print(f"Intent recorded successfully!")
        print(f"Transaction hash: {tx_receipt.tx_hash}")
        print(f"Block number: {tx_receipt.block_number}")
        print(f"Status: {'Success' if tx_receipt.status == 1 else 'Failed'}")
        
    except Exception as e:
        print(f"Error sending intent: {str(e)}")

if __name__ == "__main__":
    main()