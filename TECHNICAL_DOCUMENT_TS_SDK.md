# Technical Documentation: IntentLayer TypeScript SDK Implementation

## Overview

This document provides a comprehensive guide for the TypeScript SDK team on how to implement an equivalent IntentLayer SDK in TypeScript, based on our Python implementation. The TypeScript SDK should maintain feature parity while embracing TypeScript and JavaScript ecosystem best practices.

## Core Architecture

The Python SDK is structured around the following key components:

1. **IntentClient**: Primary entry point for interacting with the IntentLayer protocol
2. **Envelope**: Models and utilities for creating signed envelopes
3. **Signer**: Interface for transaction signing
4. **NetworkConfig**: Network configuration management
5. **Utils**: Shared utilities

## Client Implementation Details

### IntentClient

The `IntentClient` class is the core of the SDK, providing methods for:

- Initializing connections to the blockchain and IPFS
- Recording intents on-chain
- Managing DIDs (Decentralized Identifiers)
- Pinning data to IPFS

#### Key Initialization Patterns

```python
# Network-based initialization (recommended)
client = IntentClient.from_network(
    network="zksync-era-sepolia",  # Network from networks.json
    pinner_url="https://pin.example.com",
    signer=private_key_or_signer_instance,
    # Optional: override RPC URL, retry count, timeout, logger
)

# Direct initialization (more flexibility, more parameters required)
client = IntentClient(
    rpc_url="https://rpc.example.com",
    pinner_url="https://pin.example.com",
    signer=signer_instance,
    recorder_address="0x...",
    did_registry_address="0x...",  # Optional
    min_stake_wei=1000000000000000,  # Optional
    # Optional: expected_chain_id, retry_count, timeout, logger
)
```

#### Signer Management

The Python SDK supports passing either:
- A raw private key string (converted to a `LocalSigner` internally)
- A custom `Signer` instance that implements the required interface

This flexible approach should be maintained in the TypeScript SDK.

### Core Contract Interactions

The SDK interacts with two main contracts:

1. **IntentRecorder**: Records intent hashes and IPFS CIDs on-chain
2. **DIDRegistry**: Manages DID registration and resolution

#### IntentRecorder ABI

```typescript
const INTENT_RECORDER_ABI = [
  {
    "inputs": [
      {"internalType": "bytes32", "name": "envelopeHash", "type": "bytes32"},
      {"internalType": "bytes", "name": "cid", "type": "bytes"},
    ],
    "name": "recordIntent",
    "outputs": [],
    "stateMutability": "payable",
    "type": "function",
  },
  {
    "inputs": [],
    "name": "MIN_STAKE_WEI",
    "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
    "stateMutability": "view",
    "type": "function",
  },
];
```

#### DIDRegistry ABI

```typescript
const DID_REGISTRY_ABI = [
  {
    "inputs": [
      {"internalType": "string", "name": "did", "type": "string"}
    ],
    "name": "register",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function",
  },
  {
    "inputs": [
      {"internalType": "string", "name": "did", "type": "string"}
    ],
    "name": "resolve",
    "outputs": [
      {"internalType": "address", "name": "owner", "type": "address"},
      {"internalType": "bool", "name": "active", "type": "bool"}
    ],
    "stateMutability": "view",
    "type": "function",
  }
];
```

### Network Configuration

The Python SDK loads network configurations from a JSON file embedded in the package:

```json
{
  "zksync-era-sepolia": {
    "chainId": 300,
    "rpc": "https://sepolia.era.zksync.dev",
    "intentRecorder": "0x21622b5b79C37F2eC6a1705472b584041165b5E9",
    "didRegistry": "0x20846c77DeCbc7342716D39Dc6F9bBC08E3560b7",
    "deployer": "0x841B4ab8B8fec2737e3860B49664add0724311bd",
    "blockDeployed": 5062168
  },
  "local": {
    "chainId": 9999,
    "rpc": "http://localhost:8545",
    "intentRecorder": "0x0000000000000000000000000000000000000000",
    "didRegistry": "0x0000000000000000000000000000000000000000",
    "deployer": "0x0000000000000000000000000000000000000000",
    "blockDeployed": 0
  }
}
```

### Envelope Structure and Signing

The `CallEnvelope` model defines the structure of an intent envelope:

```typescript
interface CallEnvelope {
  did: string;             // Decentralized Identifier
  model_id: string;        // AI model identifier
  prompt_sha256: string;   // SHA-256 hash of the prompt
  tool_id: string;         // Tool/API identifier
  timestamp_ms: number;    // Timestamp in milliseconds
  stake_wei: string;       // Amount staked (in wei)
  sig_ed25519: string;     // Ed25519 signature (URL-safe base64)
  metadata?: Record<string, any>; // Optional metadata
}
```

The `create_envelope` function constructs a signed envelope:

1. Validates input parameters
2. Hashes the prompt
3. Creates envelope data
4. Signs the canonical JSON representation using Ed25519
5. Encodes the signature and attaches it to the envelope

### Error Handling

The SDK defines several custom error types:

1. `PinningError`: IPFS pinning failures
2. `TransactionError`: Blockchain transaction failures
3. `EnvelopeError`: Envelope validation or creation errors
4. `NetworkError`: Chain ID mismatches or network configuration issues
5. `AlreadyRegisteredError`: When a DID is already registered and active
6. `InactiveDIDError`: When a DID exists but is inactive

### Key Methods

#### `send_intent(envelope_hash, payload_dict, ...)`

This method:
1. Validates the chain ID
2. Validates the payload format
3. Verifies DID is active (if DID registry is available)
4. Pins the payload to IPFS
5. Converts IPFS CID to bytes for on-chain storage
6. Estimates gas (with fallback values)
7. Builds, signs, and sends the transaction
8. Optionally waits for receipt

#### `register_did(did, ...)`

This method:
1. Verifies chain ID
2. Checks if the DID already exists
3. Sends a transaction to register the DID
4. Optionally waits for receipt

#### `resolve_did(did)`

Queries the DID registry to resolve a DID to its owner address and active status.

#### `pin_to_ipfs(payload)`

Pins data to IPFS via a pinning service, with retry logic.

#### `tx_url(tx_hash)`

Generates a block explorer URL for a transaction hash based on the network.

## TypeScript/JavaScript Adaptations

### Promises vs. Synchronous Calls

The Python SDK uses synchronous calls. The TypeScript SDK should use Promises for all async operations:

```typescript
// Python (synchronous)
receipt = client.send_intent(envelope_hash, payload)

// TypeScript (Promise-based)
const receipt = await client.sendIntent(envelope_hash, payload)
```

### HTTP Client

The Python SDK uses the `requests` library. The TypeScript SDK should use the native `fetch` API or a minimal wrapper:

```typescript
// Python (requests)
resp = self.session.post(f"{self.pinner_url}/pin", json=payload, timeout=self.timeout)

// TypeScript (fetch)
const resp = await fetch(`${this.pinnerUrl}/pin`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
  signal: AbortSignal.timeout(this.timeout)
})
```

### Web3 Interactions

We use `web3.py` in Python. For TypeScript, consider:
- `ethers.js`: Full-featured library with excellent TypeScript support
- `viem`: Modern, lightweight alternative focused on TypeScript

### Error Handling

Adapt the error hierarchy for JavaScript/TypeScript, using inheritance:

```typescript
class IntentLayerError extends Error {
  constructor(message: string) {
    super(message);
    this.name = this.constructor.name;
  }
}

class PinningError extends IntentLayerError { /* ... */ }
class TransactionError extends IntentLayerError { /* ... */ }
// etc.
```

### Type Definitions

Leverage TypeScript's type system for better developer experience:

```typescript
interface NetworkConfig {
  chainId: number;
  rpc: string;
  intentRecorder: string;
  didRegistry: string;
  deployer: string;
  blockDeployed: number;
}

interface TxReceipt {
  transactionHash: string;
  blockNumber: number;
  blockHash: string;
  status: number;
  gasUsed: number;
  logs: any[];
  from: string;
  to: string;
}

type Signer = {
  readonly address: string;
  signTransaction(tx: Record<string, any>): Promise<SignedTransaction>;
};
```

## Implementation Recommendations

### Project Structure

```
packages/sdk-ts/
├── src/
│   ├── index.ts              # Main exports
│   ├── client.ts             # IntentClient implementation
│   ├── envelope.ts           # Envelope models and creation
│   ├── signer/
│   │   ├── index.ts          # Signer interface
│   │   └── local.ts          # LocalSigner implementation
│   ├── config.ts             # Network configuration
│   ├── utils.ts              # Utility functions
│   ├── networks.json         # Network configurations
│   ├── errors.ts             # Custom error types
│   └── types.ts              # TypeScript type definitions
├── tests/                    # Unit and integration tests
├── examples/                 # Usage examples
├── package.json
└── tsconfig.json
```

### Build Configuration

Use `tsup` for a zero-config TypeScript build:

```json
{
  "scripts": {
    "build": "tsup src/index.ts --format esm,cjs --dts",
    "test": "vitest run",
    "coverage": "vitest run --coverage"
  }
}
```

### Additional Features for TypeScript SDK

Consider adding these TypeScript-specific enhancements:

1. **Runtime Type Validation**: Use Zod or a similar library for runtime validation
2. **Better Error Details**: Leverage TypeScript union types for more specific error information
3. **Browser Compatibility**: Ensure the SDK works in both Node.js and modern browsers
4. **Tree-Shakable Exports**: Allow users to import only what they need

## Testing Strategy

The Python SDK uses pytest with:
- Mock HTTP responses
- Mock Web3 provider
- Unit tests for all components
- Integration tests for end-to-end flows

For TypeScript, use Vitest with:
- MSW (Mock Service Worker) for HTTP mocking
- Mock implementations of Ethereum providers
- Type testing to verify interfaces

## Documentation

1. **JSDoc Comments**: Add comprehensive TSDoc comments for all exports
2. **Type Declarations**: Generate and include .d.ts files
3. **README**: Clear examples for common use patterns
4. **Inline Examples**: Add usage examples in comments

## Security Considerations

1. **HTTPS Enforcement**: Like the Python SDK, enforce HTTPS for RPC and pinner URLs
2. **Private Key Handling**: Never store private keys, use environment variables
3. **Input Validation**: Validate all inputs, especially those going to contracts
4. **Strict Content Security**: Ensure all IPFS-bound data is properly validated

## Conclusion

This technical guide outlines how to implement the TypeScript SDK with feature parity to our Python SDK. By following these patterns and recommendations, we can deliver a consistent developer experience while leveraging TypeScript's type system and the JavaScript ecosystem's strengths.