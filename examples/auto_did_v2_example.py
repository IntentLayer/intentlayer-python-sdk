#!/usr/bin/env python3
"""
Auto-DID V2 Example - IntentLayer SDK

This example demonstrates how to use the IntentLayer SDK with the Auto-DID feature
that automatically creates and registers a DID with the Gateway service
on the first call to send_intent(), using the V2 protocol.

Key features demonstrated:
- Creating a client with auto_did enabled (default)
- Using V2 schema version and proto-based communication
- Automatic DID registration with Gateway on first send_intent call
- Handling errors for Auto-DID feature
- Using environment variables for configuration
"""
import os
import time
import logging
import argparse
import sys
from typing import Dict, Any, Optional

from intentlayer_sdk import IntentClient
from intentlayer_sdk.envelope import CallEnvelope
from intentlayer_sdk.exceptions import (
    PinningError, TransactionError, EnvelopeError, NetworkError
)
from intentlayer_sdk.gateway import (
    QuotaExceededError, AlreadyRegisteredError
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("auto-did-v2-example")

# Network configuration (using testnet)
NETWORK = "zksync-era-sepolia"
RPC_URL = os.environ.get("RPC_URL", "https://sepolia.era.zksync.dev") 
PINNER_URL = os.environ.get("PINNER_URL", "https://pin.intentlayer.net")

# Gateway URL (can also be set via INTENT_GATEWAY_URL env var)
GATEWAY_URL = os.environ.get("INTENT_GATEWAY_URL", "https://gateway.intentlayer.net")

# Set environment tier for proper JWT validation
# Options: "production", "test", "development"
ENV_TIER = os.environ.get("INTENT_ENV_TIER", "test")

def is_ci_environment() -> bool:
    """Detect if running in a CI environment."""
    # Common CI environment variables
    ci_env_vars = [
        "CI",                  # Generic CI
        "GITHUB_ACTIONS",      # GitHub Actions
        "GITLAB_CI",           # GitLab CI
        "JENKINS_URL",         # Jenkins
        "CIRCLECI",            # CircleCI
        "TRAVIS",              # Travis CI
        "BITBUCKET_COMMIT",    # Bitbucket Pipelines
        "TF_BUILD",            # Azure Pipelines
    ]
    return any(os.environ.get(var) for var in ci_env_vars)

def confirm_action(message: str, default: bool = False, non_interactive: bool = False) -> bool:
    """
    Ask for user confirmation with support for non-interactive mode.
    
    Args:
        message: Message to display
        default: Default action if running in non-interactive mode
        non_interactive: Force non-interactive mode
        
    Returns:
        True if confirmed, False otherwise
    """
    # In non-interactive mode or CI, return the default
    if non_interactive or is_ci_environment():
        logger.info(f"{message} [auto-{default}]")
        return default
    
    # Interactive mode
    prompt = f"{message} (y/n): "
    while True:
        try:
            response = input(prompt).strip().lower()
            if response in ('y', 'yes'):
                return True
            elif response in ('n', 'no'):
                return False
            else:
                print("Please enter 'y' or 'n'")
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled by user")
            return False

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="IntentLayer SDK Auto-DID V2 Example")
    parser.add_argument(
        "--non-interactive", 
        action="store_true",
        help="Run in non-interactive mode (suitable for CI/CD pipelines)"
    )
    parser.add_argument(
        "--send-intent",
        action="store_true",
        help="Automatically send intent without confirmation"
    )
    parser.add_argument(
        "--gateway-url",
        help="Override the gateway URL"
    )
    parser.add_argument(
        "--env-tier",
        choices=["production", "test", "development"],
        help="Set the environment tier (production, test, development)"
    )
    parser.add_argument(
        "--network",
        help="Override the network (default: zksync-era-sepolia)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()

def main():
    """Main example function showing IntentLayer SDK with Auto-DID feature."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Set up logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        # Also set root logger to DEBUG for library logs
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Process command line overrides
    network = args.network or NETWORK
    gateway_url = args.gateway_url or GATEWAY_URL
    env_tier = args.env_tier or ENV_TIER
    non_interactive = args.non_interactive or is_ci_environment()
    
    # Set Gateway URL environment variable if not already set
    if "INTENT_GATEWAY_URL" not in os.environ:
        os.environ["INTENT_GATEWAY_URL"] = gateway_url
        logger.info(f"Set INTENT_GATEWAY_URL to {gateway_url}")
    
    # Set environment tier for JWT validation
    if "INTENT_ENV_TIER" not in os.environ:
        os.environ["INTENT_ENV_TIER"] = env_tier
        logger.info(f"Set INTENT_ENV_TIER to {env_tier}")
    
    # Set schema version to 2 for V2 proto support
    if "INTENT_SCHEMA_VERSION" not in os.environ:
        os.environ["INTENT_SCHEMA_VERSION"] = "2"
        logger.info("Set INTENT_SCHEMA_VERSION to 2 for V2 protocol")
    
    # You can also set API key if you have one
    # os.environ["INTENT_API_KEY"] = "your.jwt.token.here"  # JWT format with org_id claim
    
    if not non_interactive:
        print("\n=== IntentLayer SDK Auto-DID V2 Example ===\n")
        print("This example demonstrates automatic DID creation and registration")
        print("with the Gateway service using protocol V2\n")
    
    try:
        # Create client with auto_did enabled (default is True)
        # The SDK will automatically create a DID identity if needed
        logger.info("Creating IntentClient with auto-DID (default)")
        client = IntentClient.from_network(
            network=network,
            pinner_url=PINNER_URL,
            rpc_url=RPC_URL,
            # auto_did=True,  # This is the default now, no need to specify
            logger=logger
        )
        
        if not non_interactive:
            print(f"Created client with auto-DID feature")
            print(f"Client address: {client.address}")
        
        # Show the auto-generated DID
        if hasattr(client, "_identity"):
            did_info = f"Using DID: {client._identity.did}"
            if non_interactive:
                logger.info(did_info)
            else:
                print(did_info)
                print(f"This DID will be registered automatically on first intent")
                print(f"Schema version: {os.environ.get('INTENT_SCHEMA_VERSION', '2')}")
        
        # Create a test envelope for demonstration
        envelope = create_test_envelope(client)
        logger.info("Created test envelope for intent")
        if not non_interactive:
            print("\nCreated test envelope for intent")
        
        # Ask user if they want to send the intent (which costs real funds on testnet)
        should_send = args.send_intent or confirm_action(
            "\nSend intent to blockchain? This will spend testnet funds.",
            default=False,
            non_interactive=non_interactive
        )
        
        if not should_send:
            logger.info("User chose not to send intent")
            if not non_interactive:
                print("Skipping intent sending. Example complete.")
            return 0
        
        logger.info("Sending intent (this will auto-register DID with Gateway if needed)...")
        if not non_interactive:
            print("\nSending intent (this will auto-register DID with Gateway if needed)...")
            
        # Send the intent with retry logic
        receipt = send_intent_with_retry(client, envelope)
        
        # Print transaction details
        tx_hash = receipt.get("transactionHash")
        if isinstance(tx_hash, bytes):
            tx_hash = tx_hash.hex()
        
        transaction_url = client.tx_url(tx_hash)
        logger.info(f"Transaction successful: {tx_hash}")
        logger.info(f"Transaction URL: {transaction_url}")
        
        if not non_interactive:
            print("\n✅ Transaction successful!")
            print(f"Transaction hash: {tx_hash}")
            print(f"View transaction: {transaction_url}")
            print("\nThe DID has been automatically registered with the Gateway service")
            print("Future calls will reuse the same DID without requiring registration")
        
        return 0
        
    except QuotaExceededError as e:
        error_msg = f"Gateway registration quota exceeded: {e}"
        logger.error(error_msg)
        if not non_interactive:
            print(f"\n❌ {error_msg}")
            print("Contact support to increase your quota")
        return 1
    except AlreadyRegisteredError as e:
        # This is usually not a real error
        logger.warning(f"DID already registered: {e}")
        if not non_interactive:
            print(f"\n❌ DID already registered: {e}")
            print("This is usually not an error - the DID was previously registered")
        return 0
    except NetworkError as e:
        error_msg = f"Network error: {e}"
        logger.error(error_msg)
        if not non_interactive:
            print(f"\n❌ {error_msg}")
        return 1
    except PinningError as e:
        error_msg = f"IPFS pinning error: {e}"
        logger.error(error_msg)
        if not non_interactive:
            print(f"\n❌ {error_msg}")
        return 1
    except TransactionError as e:
        error_msg = f"Transaction error: {e}"
        logger.error(error_msg)
        if not non_interactive:
            print(f"\n❌ {error_msg}")
        return 1
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logger.error(error_msg, exc_info=True)
        if not non_interactive:
            print(f"\n❌ {error_msg}")
        return 1


def create_test_envelope(client: IntentClient) -> CallEnvelope:
    """Create a simple test envelope for demonstration."""
    
    # For demo purposes, we're creating a basic "hello world" envelope
    import hashlib
    
    # Get the prompt
    prompt = "Hello, world! This is an auto-DID V2 example."
    
    # We need the signer's private key, but the Identity class doesn't expose it directly
    # Instead, we'll use a workaround by creating a simple test envelope directly
    
    # Create timestamp
    timestamp_ms = int(time.time() * 1000)
    
    # IMPORTANT HACK FOR EXAMPLE PURPOSES ONLY: 
    # -------------------------------------------------
    # This is not how you would create an envelope in a real application!
    # In production code, you should use the proper signing mechanism with the 
    # correct private key. This example uses a dummy signature only to demonstrate
    # the API workflow without requiring direct access to the internal key material.
    #
    # A real implementation would:
    # 1. Use intentlayer_sdk.envelope.create_envelope() with proper crypto keys
    # 2. Handle key security and signing correctly
    # 3. Never use dummy signatures as they will be rejected in production
    envelope = CallEnvelope(
        did=client._identity.did,
        model_id="test-model",
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        tool_id="test-tool",
        timestamp_ms=timestamp_ms,
        stake_wei=str(client.min_stake_wei),
        # Add a dummy signature for demonstration purposes only
        sig_ed25519="dummySignatureForTestingOnly_ThisWillBeRejectedInProduction_butWorksForExamplePurposes"
    )
    
    # Log that we're using a simplified envelope
    logger.warning("Using test envelope with dummy signature - this is for demo only")
    
    return envelope


def send_intent_with_retry(client: IntentClient, envelope: CallEnvelope, max_retries: int = 3) -> Dict[str, Any]:
    """Send an intent with automatic retries for certain errors."""
    
    attempt = 0
    while attempt < max_retries:
        try:
            logger.info(f"Sending intent (attempt {attempt + 1}/{max_retries})")
            
            # This first call will auto-register the DID with Gateway if needed
            # The registration happens transparently before sending the intent
            # Convert the envelope to a dict using model_dump() instead of to_dict()
            payload_dict = {
                "envelope": envelope.model_dump(),
                "prompt": "Hello, world! This is an auto-DID V2 example."
            }
            
            receipt = client.send_intent(
                envelope_hash=envelope.hash(),
                payload_dict=payload_dict,
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
    sys.exit(main())