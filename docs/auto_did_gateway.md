# Auto-DID with Gateway Registration

This document explains how to use the IntentLayer SDK's automatic DID (Decentralized Identifier) feature with Gateway integration, which was introduced in version 0.4.0.

## What is Auto-DID?

Auto-DID is a feature that:

1. Automatically creates a DID for you when initializing an `IntentClient`
2. Registers that DID with the IntentLayer Gateway service on your first call to `send_intent()`
3. Handles all the complexity of DID management transparently

This feature significantly reduces the "time-to-first-intent" friction by eliminating manual DID creation and registration steps.

## Getting Started

### Installation

Make sure you have the latest version of the SDK with Gateway support:

```bash
# Basic installation
pip install intentlayer-sdk

# With gRPC support for Gateway integration
pip install intentlayer-sdk[grpc]
```

### Basic Usage

Here's a minimal example of using the auto-DID feature:

```python
from intentlayer_sdk import IntentClient

# Create client with auto_did (enabled by default)
client = IntentClient.from_network(
    network="zksync-era-sepolia",
    pinner_url="https://pin.intentlayer.net",
    # auto_did=True  # This is now the default!
)

# The client now has an automatically created DID
# You can use the client as normal, and the DID will be registered
# automatically on your first call to send_intent()

# Create an envelope and send an intent as usual
envelope = CallEnvelope(...)
receipt = client.send_intent(
    envelope_hash=envelope.hash(),
    payload_dict=envelope.to_dict()
)
```

## Gateway Integration

Auto-DID works seamlessly with the IntentLayer Gateway service to register your DID. Here's how to configure Gateway integration:

### Setting the Gateway URL

You can set the Gateway URL in two ways:

1. Via environment variable (recommended):
   ```
   INTENT_GATEWAY_URL=https://gateway.intentlayer.net
   ```

2. Via client initialization:
   ```python
   client = IntentClient.from_network(
       network="zksync-era-sepolia",
       pinner_url="https://pin.intentlayer.net",
       gateway_url="https://gateway.intentlayer.net"
   )
   ```

### API Keys

If you have an API key for the Gateway service, you can provide it via the `INTENT_API_KEY` environment variable:

```
INTENT_API_KEY=your.jwt.token.here
```

The SDK will automatically extract the `org_id` claim from the JWT and associate it with your DID.

## Security Considerations

### HTTPS Validation

For security reasons, the SDK only accepts HTTPS URLs for Gateway connections by default. If you need to use an insecure URL (e.g., for development), you can override this behavior:

```
INTENT_INSECURE_GW=1
```

### Concurrency Protection

The SDK uses inter-process locking to prevent race conditions when multiple processes attempt to register the same DID simultaneously.

## Configuration Options

### Disabling Auto-DID

You can disable auto-DID if needed:

1. Via environment variable:
   ```
   INTENT_AUTO_DID=false
   ```

2. Via client initialization:
   ```python
   client = IntentClient.from_network(
       network="zksync-era-sepolia",
       pinner_url="https://pin.intentlayer.net",
       auto_did=False,
       # You'll need to provide a signer if auto_did is False:
       signer="0x123...your-private-key"
   )
   ```

### Gateway-Related Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `INTENT_GATEWAY_URL` | URL of the Gateway service | None |
| `INTENT_API_KEY` | JWT token for Gateway authentication | None |
| `INTENT_AUTO_DID` | Enable/disable auto-DID feature | `true` |
| `INTENT_INSECURE_GW` | Allow insecure Gateway URLs | `false` |
| `INTENT_SKIP_CHAIN_CHECK` | Skip chain ID validation | `false` |

## Performance Optimization

The SDK includes several optimizations to enhance performance:

1. **In-process caching**: DIDs are cached in-memory to avoid redundant registrations within the same process
2. **Lock files**: Network-specific lock files prevent multiple processes from attempting registration simultaneously
3. **Module-level Gateway client caching**: Reuses Gateway client connections for better performance

The first call to `send_intent()` with a new DID will have a slight overhead (typically ≤120ms) for Gateway registration. Subsequent calls will have no registration overhead.

## Error Handling

When using auto-DID with Gateway, you may encounter these additional exceptions:

```python
from intentlayer_sdk.gateway import QuotaExceededError

try:
    client.send_intent(...)
except QuotaExceededError:
    # Handle Gateway quota exceeded
    print("DID registration quota exceeded")
except AlreadyRegisteredError:
    # DID is already registered (this is actually good!)
    print("DID is already registered, proceeding...")
except InactiveDIDError:
    # DID exists but is inactive
    print("DID is inactive, please reactivate it")
```

## Complete Example

See the full example in [examples/auto_did_gateway_example.py](../examples/auto_did_gateway_example.py) which demonstrates:

- Automatic DID creation and registration
- Gateway integration
- Error handling
- Transaction submission

## Additional Resources

- [API Reference Documentation](./api_reference.md)
- [Gateway Integration Guide](./gateway_integration.md)
- [Network Configuration](./network_config.md)