#!/usr/bin/env python3
"""
Example demonstrating automatic DID registration with Gateway integration.
"""
import os
import time
import logging
import hashlib
from datetime import datetime

from intentlayer_sdk import (
    IntentClient, 
    create_envelope,
    PinningError, 
    EnvelopeError, 
    TransactionError, 
    NetworkError
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """
    Demonstrate automatic DID registration with Gateway.
    
    This example shows:
    1. Zero-config client initialization with auto_did=True
    2. Automatic DID registration with Gateway on first send_intent()
    3. JWT API key handling for organization ID
    """
    # Read configuration from environment
    RPC_URL = os.environ.get("RPC_URL", "https://sepolia.era.zksync.dev")
    PINNER_URL = os.environ.get("PINNER_URL", "https://pin.example.com")
    GATEWAY_URL = os.environ.get("INTENT_GATEWAY_URL", "https://gateway.example.com")
    NETWORK = os.environ.get("NETWORK", "zksync-era-sepolia")
    
    # Optional JWT API key with org_id claim
    # Set to empty string by default to demonstrate that it's optional
    API_KEY = os.environ.get("INTENT_API_KEY", "")
    if API_KEY:
        print("\nUsing API key from environment (truncated for privacy):")
        print(f"  {API_KEY[:10]}...{API_KEY[-5:] if len(API_KEY) > 15 else ''}")
    
    # Print info
    print("\n=== IntentLayer SDK Gateway Integration Example ===\n")
    print(f"Network: {NETWORK}")
    print(f"Gateway: {GATEWAY_URL}")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Timestamp: {timestamp}\n")
    
    # Initialize client with auto_did and Gateway integration
    try:
        client = IntentClient.from_network(
            network=NETWORK,
            pinner_url=PINNER_URL,
            gateway_url=GATEWAY_URL,
            # No signer provided - auto_did=True will create one
            logger=logger
        )
        
        print("Client initialized successfully")
        print(f"Client address: {client.address}")
        print(f"Auto-generated DID: {client._identity.did}")
        
        # Create prompt and get minimum stake
        prompt = "What is the capital of Germany?"
        min_stake = client.min_stake_wei
        print(f"\nMinimum stake: {min_stake / 10**18} ETH")
        
        # Create envelope using client's identity
        did = client._identity.did
        
        # Create signature data
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        timestamp_ms = int(time.time() * 1000)
        
        # Create the envelope
        envelope = create_envelope(
            prompt=prompt,
            model_id="gpt-4o@2025-03-12",
            tool_id="openai.chat",
            did=did,
            # Auto-generate a private key for envelope signing
            private_key=None,
            stake_wei=min_stake,
            timestamp_ms=timestamp_ms
        )
        
        # Get envelope hash for on-chain recording
        envelope_hash = envelope.hex_hash()
        print(f"Created envelope with hash: {envelope_hash}")
        
        # Create intent payload
        payload = {
            "prompt": prompt,
            "envelope": envelope.model_dump(),
            "metadata": {
                "user_id": "example_user",
                "session_id": "example_session",
                "timestamp": timestamp
            }
        }
        
        # Send the intent - DID will be automatically registered with Gateway
        print("\nSending intent (first call triggers DID registration)...")
        
        try:
            receipt = client.send_intent(envelope_hash, payload)
            
            # Print transaction details
            tx_hash = receipt["transactionHash"]
            block = receipt.get("blockNumber", "pending")
            status = "Success" if receipt.get("status") == 1 else "Failed/Pending"
            
            print(f"\n✅ Intent recorded successfully!")
            print(f"Transaction hash: {tx_hash}")
            print(f"Block number: {block}")
            print(f"Status: {status}")
            print(f"Block explorer: {client.tx_url(tx_hash)}")
            
        except PinningError as e:
            print(f"❌ IPFS pinning error: {e}")
        except EnvelopeError as e:
            print(f"❌ Envelope error: {e}")
        except NetworkError as e:
            print(f"❌ Network error: {e}")
        except TransactionError as e:
            print(f"❌ Transaction error: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
    
    except Exception as e:
        print(f"❌ Error initializing client: {e}")


if __name__ == "__main__":
    main()