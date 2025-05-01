#!/usr/bin/env python3
"""
Auto-DID Gateway Example - IntentLayer SDK

This example demonstrates how to use the IntentLayer SDK with the Auto-DID feature
that automatically creates and registers a DID with the Gateway service
on the first call to send_intent().

Key features demonstrated:
- Creating a client with auto_did enabled (default)
- Automatic DID registration with Gateway on first send_intent call
- Using environment variables for configuration
- Error handling for Gateway-related operations

Note: This example requires the gRPC dependencies to be installed:
    pip install intentlayer-sdk[grpc]
"""
import os
import time
import logging
import hashlib
from typing import Dict, Any

from intentlayer_sdk import IntentClient
from intentlayer_sdk.envelope import CallEnvelope
from intentlayer_sdk.exceptions import (
    PinningError, TransactionError, EnvelopeError, NetworkError,
    AlreadyRegisteredError, InactiveDIDError
)
from intentlayer_sdk.gateway import QuotaExceededError

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("auto-did-gateway-example")

# Network configuration (using testnet)
NETWORK = "zksync-era-sepolia"
RPC_URL = os.environ.get("RPC_URL", "https://sepolia.era.zksync.dev") 
PINNER_URL = os.environ.get("PINNER_URL", "https://pin.intentlayer.net")

# Gateway URL (can also be set via INTENT_GATEWAY_URL env var)
GATEWAY_URL = os.environ.get("INTENT_GATEWAY_URL", "https://gateway.intentlayer.net")


def main():
    """Main example function showing IntentLayer SDK with Auto-DID and Gateway integration."""
    
    # Set Gateway URL environment variable if not already set
    if "INTENT_GATEWAY_URL" not in os.environ:
        os.environ["INTENT_GATEWAY_URL"] = GATEWAY_URL
        logger.info(f"Set INTENT_GATEWAY_URL to {GATEWAY_URL}")
    
    # You can also set API key if you have one
    # os.environ["INTENT_API_KEY"] = "your.jwt.token"  # JWT format with org_id claim
    
    # Schema version 2 is required and used by default
    # os.environ["INTENT_SCHEMA_VERSION"] = "2"  # This is now the default
    
    print("\n=== IntentLayer SDK Auto-DID with Gateway Example ===\n")
    print("This example demonstrates automatic DID creation and registration")
    print("with the Gateway service on first intent\n")
    
    try:
        # Create client with auto_did enabled (default is True)
        # The SDK will automatically create a DID identity if needed
        logger.info("Creating IntentClient with auto-DID (default)")
        client = IntentClient.from_network(
            network=NETWORK,
            pinner_url=PINNER_URL,
            rpc_url=RPC_URL,
            # auto_did=True,  # This is the default now, no need to specify
            logger=logger
        )
        
        print(f"Created client with auto-DID feature")
        print(f"Client address: {client.address}")
        
        # Show the auto-generated DID
        if hasattr(client, "_identity"):
            print(f"Using DID: {client._identity.did}")
            print(f"This DID will be automatically registered with Gateway on first intent")
        
        # Create a test envelope for demonstration
        envelope = create_test_envelope(client)
        print("\nCreated test envelope for intent")
        
        # Ask user if they want to send the intent (which costs real funds on testnet)
        confirm = input("\nSend intent to blockchain? This will spend testnet funds. (y/n): ")
        if confirm.lower() != 'y':
            print("Skipping intent sending. Example complete.")
            return
        
        print("\nSending intent (this will auto-register DID with Gateway if needed)...")
        # Send the intent with retry logic
        receipt = send_intent_with_retry(client, envelope)
        
        # Print transaction details
        tx_hash = receipt.get("transactionHash")
        if isinstance(tx_hash, bytes):
            tx_hash = tx_hash.hex()
        
        print("\n✅ Transaction successful!")
        print(f"Transaction hash: {tx_hash}")
        print(f"View transaction: {client.tx_url(tx_hash)}")
        print("\nThe DID has been automatically registered with the Gateway service")
        print("Future calls will reuse the same DID without requiring registration")
        
    except QuotaExceededError as e:
        print(f"\n❌ Gateway registration quota exceeded: {e}")
        print("Contact support to increase your quota")
    except NetworkError as e:
        print(f"\n❌ Network error: {e}")
    except PinningError as e:
        print(f"\n❌ IPFS pinning error: {e}")
    except TransactionError as e:
        print(f"\n❌ Transaction error: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


def create_test_envelope(client: IntentClient) -> CallEnvelope:
    """Create a simple test envelope for demonstration."""
    
    # For demo purposes, we're creating a basic "hello world" envelope
    timestamp_ms = int(time.time() * 1000)
    
    # Create the envelope (will be automatically signed with the auto-DID's key)
    envelope = CallEnvelope(
        did=client._identity.did,  # Access the auto-generated DID
        model_id="test-model",
        prompt="Hello, world! This is an auto-DID example.",
        tool_id="test-tool",
        timestamp_ms=timestamp_ms,
        stake_wei=client.min_stake_wei
    )
    
    return envelope


def send_intent_with_retry(client: IntentClient, envelope: CallEnvelope, max_retries: int = 3) -> Dict[str, Any]:
    """Send an intent with automatic retries for certain errors."""
    
    attempt = 0
    while attempt < max_retries:
        try:
            logger.info(f"Sending intent (attempt {attempt + 1}/{max_retries})")
            
            # This first call will auto-register the DID with Gateway if needed
            # The registration happens transparently before sending the intent
            receipt = client.send_intent(
                envelope_hash=envelope.hash(),
                payload_dict=envelope.to_dict(),
                wait_for_receipt=True
            )
            return receipt
            
        except AlreadyRegisteredError:
            # This is actually a success case for auto-DID registration
            logger.info("DID already registered, proceeding with intent")
            attempt += 1
            continue
            
        except (PinningError, EnvelopeError) as e:
            # These are non-recoverable errors
            logger.error(f"Non-recoverable error: {e}")
            raise
            
        except TransactionError as e:
            # Some transaction errors may be temporary, so retry
            logger.warning(f"Transaction error (will retry): {e}")
            attempt += 1
            time.sleep(2 ** attempt)  # Exponential backoff
            
    # If we get here, we've exceeded our retry limit
    raise TransactionError(f"Failed to send intent after {max_retries} attempts")


if __name__ == "__main__":
    main()