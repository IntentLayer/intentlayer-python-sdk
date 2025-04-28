# IntentLayer SDK Examples

This directory contains examples showing how to use the IntentLayer SDK.

## Files

- `simple_usage.py`: Basic example with manual initialization
- `network_example.py`: Demonstrates network-based initialization
- `smoke_test.py`: Simple test script
- `verify_example.py`: Shows how to use the `intent-cli verify` command to verify on-chain intents

## Running an Example

1. Make sure you have the required environment variables:

```bash
# Required
export PRIVATE_KEY=0x123...  # Your private key
export PINNER_URL=https://pin.example.com  # IPFS pinning service URL

# Optional (when not using network-based config)
export RPC_URL=https://sepolia.era.zksync.dev  # RPC endpoint
export INTENT_RECORDER_ADDRESS=0x123...  # Contract address
```

2. Run the example:

```bash
python examples/network_example.py
```

## Network-Based Configuration

The recommended way to use the SDK is with the `from_network()` factory method:

```python
from intentlayer_sdk import IntentClient

client = IntentClient.from_network(
    network="zksync-era-sepolia",  # Network from networks.json
    pinner_url="https://pin.example.com",
    signer=PRIVATE_KEY,  # Can be a string private key or a Signer instance
)

# Now you can use the client
client.assert_chain_id()  # Verify connected to the right chain
min_stake = client.min_stake_wei  # Query minimum stake from contract
```

This approach simplifies configuration management by using predefined network settings.