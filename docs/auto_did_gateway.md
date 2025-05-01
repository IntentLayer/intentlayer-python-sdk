# Auto-DID with Gateway Registration

This document explains how to use the IntentLayer SDK's automatic DID (Decentralized Identifier) feature with Gateway integration, which was introduced in version 0.4.0 and enhanced in version 0.4.1.

## What is Auto-DID?

Auto-DID is a feature that:

1. Automatically creates a DID for you when initializing an `IntentClient`
2. Registers that DID with the IntentLayer Gateway service on your first call to `send_intent()`
3. Handles all the complexity of DID management transparently
4. Provides robust locking mechanisms to prevent concurrent registrations
5. Supports distributed deployments with Redis-based locking (added in v0.4.1)
6. Includes comprehensive error handling and retry logic

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

### JWT Verification

The SDK implements a tiered approach to JWT validation:

1. **Production Environment** (`INTENT_ENV_TIER=production`):
   - Requires HS256 algorithm
   - Enforces signature verification (requires `INTENT_JWT_SECRET`)
   - Validates token expiration
   - Most secure option for production use

2. **Test Environment** (`INTENT_ENV_TIER=test`):
   - Accepts any algorithm except unsafe ones ('none')
   - Validates format and expiration
   - Verifies signature if HMAC algorithm and secret are provided
   - Good balance for testing environments

3. **Development Environment** (`INTENT_ENV_TIER=development`):
   - Minimal validation for ease of development
   - Rejects only unsafe algorithms
   - Most flexible option

Configure the environment tier and JWT secret:

```
INTENT_ENV_TIER=production
INTENT_JWT_SECRET=your_secret_key
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
| `INTENT_SCHEMA_VERSION` | Schema version to use for DID registration | None |
| `INTENT_GW_TIMEOUT` | Gateway request timeout in seconds | `5` |
| `INTENT_LOCK_STRATEGY` | Locking strategy: "file" or "redis" | `file` |
| `INTENT_REDIS_URL` | Redis URL for distributed locking | None |
| `INTENT_ENV_TIER` | Environment tier: "production", "test", or "development" | `production` |
| `INTENT_JWT_SECRET` | Secret key for JWT signature verification | None |

### Advanced Configuration

#### Schema Version

You can specify a schema version for DID registration:

```python
client = IntentClient.from_network(
    network="zksync-era-sepolia",
    pinner_url="https://pin.intentlayer.net",
    gateway_url="https://gateway.intentlayer.net"
)

# Later, when sending an intent:
os.environ["INTENT_SCHEMA_VERSION"] = "2"  # Set schema version
```

#### Distributed Locking with Redis

For multi-process deployments, you can use Redis-based distributed locking:

```
# Set environment variables
INTENT_LOCK_STRATEGY=redis
INTENT_REDIS_URL=redis://localhost:6379/0
```

This requires the `redis` package:

```bash
pip install intentlayer-sdk[redis]
# or
pip install redis
```

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

## Technical Details for Gateway Team

The following section provides detailed technical specifications for the Gateway service team to properly implement support for the auto-DID feature.

### gRPC Service Interface (V2 Protocol)

The Gateway service must implement the following gRPC interface for V2 protocol:

```protobuf
syntax = "proto3";

service GatewayService {
  rpc RegisterDid(DidDocument) returns (TxReceipt);
}

message DidDocument {
  string did = 1;
  bytes pub_key = 2;
  optional string org_id = 3;
  optional string label = 4;
  optional int32 schema_version = 5;  // Added in v0.4.1
  optional string doc_cid = 6;        // Added in v0.4.1
  optional string payload_cid = 7;    // Added in v0.4.1
}

message TxReceipt {
  string hash = 1;
  int32 gas_used = 2;
  bool success = 3;
  string error = 4;
  RegisterError error_code = 5;  // Added in v0.4.1
}

enum RegisterError {
  UNKNOWN_UNSPECIFIED = 0;
  ALREADY_REGISTERED = 1;
  INVALID_DID = 2;
  INVALID_DOC_CID = 3;
  DID_QUOTA_EXCEEDED = 4;
  PROCESSING_ERROR = 5;
  UNAUTHORIZED = 6;
  INVALID_PAYLOAD = 7;
}
```

### Error Response Schema

The Gateway should use consistent error codes in the `error_code` field of `TxReceipt`:

| Error Condition | Error Code | Client Behavior |
|-----------------|------------|----------------|
| DID Already Registered | `ALREADY_REGISTERED` | Returns receipt with error, no exception |
| Registration Quota Exceeded | `DID_QUOTA_EXCEEDED` | Raises `QuotaExceededError` |
| Invalid DID | `INVALID_DID` | Raises `GatewayResponseError` |
| Invalid Document CID | `INVALID_DOC_CID` | Raises `GatewayResponseError` |
| Unauthorized | `UNAUTHORIZED` | Raises `GatewayResponseError` |
| Invalid Payload | `INVALID_PAYLOAD` | Raises `GatewayResponseError` |
| Processing Error | `PROCESSING_ERROR` | Retries with backoff, then raises `GatewayError` |
| Unknown Error | `UNKNOWN_UNSPECIFIED` | Retries with backoff, then raises `GatewayError` |

### Authentication Flow

1. SDK sends the JWT token via `authorization: Bearer <token>` in the gRPC metadata
2. Gateway validates the token and extracts the `org_id` 
3. Gateway associates the registered DID with the organization
4. Only HS256 algorithm is supported for JWT tokens to prevent JOSE/JWT exploits

### Concurrency Support

The SDK provides two locking strategies to prevent multiple processes from registering the same DID:

1. **File-based locking** (default): Works for single-machine deployments
   - Uses `fasteners.InterProcessLock` for process-wide locking
   - Fallbacks gracefully if lock cannot be acquired

2. **Redis-based locking** (optional): Works for distributed deployments
   - Requires the `redis` package to be installed
   - Configured via environment variables:
     ```
     INTENT_LOCK_STRATEGY=redis
     INTENT_REDIS_URL=redis://localhost:6379/0
     ```

The Gateway must handle concurrent registration attempts from multiple clients and return ALREADY_REGISTERED for duplicates.

### Timeout and Performance

- SDK default timeout is 5 seconds per request (configurable via `INTENT_GW_TIMEOUT`)
- SDK implements automatic retry with exponential backoff (plus jitter) for transient errors
- SDK recognizes various gRPC error codes for smart retry decisions:
  - `DEADLINE_EXCEEDED`: Raise immediate timeout error
  - `UNAVAILABLE`: Retry with connection error message
  - `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNKNOWN`: Retry with general error message
  - Other codes: Raise appropriate error without retry

### Configuration Options Reference

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `INTENT_SCHEMA_VERSION` | Schema version to use for registration | None |
| `INTENT_LOCK_STRATEGY` | Locking strategy: "file" or "redis" | "file" |
| `INTENT_REDIS_URL` | Redis URL for distributed locking | None |
| `INTENT_GW_TIMEOUT` | Timeout for Gateway requests (seconds) | 5 |
| `INTENT_AUTO_DID` | Enable/disable auto-DID feature | true |
| `INTENT_API_KEY` | JWT token for Gateway authentication | None |
| `INTENT_GATEWAY_URL` | URL of the Gateway service | None |
| `INTENT_ENV_TIER` | Environment tier for JWT validation | "production" |
| `INTENT_JWT_SECRET` | Secret key for JWT signature verification | None |
| `INTENT_INSECURE_GW` | Allow insecure Gateway URLs | false |
| `INTENT_GATEWAY_CA` | Path to custom CA certificate | None |
| `INTENT_GATEWAY_APPEND_CA` | Append custom CA to system roots | false |
| `INTENT_GATEWAY_STRICT_CA` | Require custom CA to load successfully | false |

### Client Retry Implementation

The SDK implements a sophisticated retry mechanism:

```python
# Pseudo-code of the retry mechanism
retry_count = 0
while retry_count <= max_retries:  # default max_retries = 3
    if retry_count > 0:
        # Calculate delay with exponential backoff
        delay = backoff_base * (2 ** (retry_count - 1))  # default backoff_base = 0.5
        # Add jitter to avoid thundering herd
        jitter = delay * 0.1 * random.random()
        time.sleep(delay + jitter)

    try:
        # Use per-retry timeout
        timeout = retry_timeout or self.timeout  # default timeout = 5s
        response = self.stub.RegisterDid(doc, timeout=timeout, metadata=metadata)
        
        # Handle specific error responses
        if not response.success:
            if "ALREADY_REGISTERED" in response.error:
                return response  # Success case for our use
            elif "DID_QUOTA_EXCEEDED" in response.error:
                raise QuotaExceededError()
            else:
                # Retry for other error messages
                continue
                
        return response  # Success case
        
    except grpc.RpcError as e:
        # Handle specific gRPC errors with appropriate retry logic
        # ...
```

### Security Implementation

- SDK enforces HTTPS by default
- JWT tokens are validated for the HS256 algorithm to prevent JOSE/JWT exploits
- SDK supports custom CA certificates for enhanced security
- Process-level locking prevents race conditions in multi-process environments

### Additional Resources

- [API Reference Documentation](./api_reference.md)
- [Gateway Integration Guide](./gateway_integration.md)
- [Network Configuration](./network_config.md)