[![PyPI version](https://img.shields.io/pypi/v/intentlayer-sdk.svg)](https://pypi.org/project/intentlayer-sdk/)  
[![Test Coverage](https://img.shields.io/codecov/c/github/IntentLayer/intentlayer-python-sdk.svg?branch=main)](https://app.codecov.io/gh/IntentLayer/intentlayer-python-sdk)  
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

# IntentLayer SDK for Python

A batteries-included client for the IntentLayer protocol: pin JSON payloads to IPFS, generate cryptographically-signed envelopes, and record intents on any EVM-compatible chain in a single call.

---

## 🚀 Key Benefits

- **Verifiable Audit Trail**  
  Tie every action to a Decentralized Identifier (DID) and immutably log a hash on-chain.

- **Built-in Incentives**  
  Stake-and-slash model ensures compliance: honest actors earn yield; misbehavior burns stake.

- **Zero Boilerplate**  
  One `send_intent()` call handles IPFS pinning, envelope creation, signing, gas estimation, and transaction submission.

- **Chain-Agnostic**  
  Compatible with any HTTPS RPC endpoint and EVM-compatible network (Ethereum, zkSync, Polygon, etc.).

- **Extensible Signing**  
  Use raw private keys, hardware wallets, KMS, or your own signer implementation via a simple `Signer` protocol.

---

## 🔧 Installation

Install from PyPI:

```bash
pip install intentlayer-sdk
```

For development or latest changes:

```bash
git clone https://github.com/intentlayer/intentlayer-sdk.git
cd intentlayer-sdk
pip install -e .
```

---

## 🎯 Quickstart

```python
import os
import time
from intentlayer_sdk import (
    IntentClient, create_envelope,
    PinningError, EnvelopeError, TransactionError, NetworkError
)

# 1. Environment
PINNER_URL = os.getenv("PINNER_URL", "https://pin.example.com")
GATEWAY_URL = os.getenv("INTENT_GATEWAY_URL", "https://gateway.example.com")
# Optional: INTENT_API_KEY with org_id claim for DID registration

# 2. Initialize client using network configuration with auto-DID
client = IntentClient.from_network(
    network="zksync-era-sepolia",  # Network from networks.json
    pinner_url=PINNER_URL,
    gateway_url=GATEWAY_URL,
    # No signer needed - auto-generated with auto_did=True (default)
)

# Verify connected to the right chain
client.assert_chain_id()

# Query minimum stake from contract
min_stake = client.min_stake_wei
print(f"Minimum stake: {min_stake / 10**18} ETH")

# 3. Create a signed envelope
prompt = "Translate 'hello' to French"

# Access the auto-generated DID
did = client._identity.did
print(f"Using DID: {did[:10]}...")

# Create full envelope with signature using the client's generated identity
envelope = create_envelope(
    prompt=prompt,
    model_id="gpt-4o@2025-03-12",
    tool_id="openai.chat",
    did=did,
    private_key=None,  # Auto-create a signing key for the envelope
    stake_wei=min_stake,
    timestamp_ms=int(time.time() * 1000)
)

# Get envelope hash for on-chain recording
envelope_hash = envelope.hex_hash()

# 4. Create payload with envelope
payload = {
    "prompt": prompt,
    "envelope": envelope.model_dump(),
    "metadata": {
        "user_id": "user123",
        "session_id": "session456"
    }
}

# 5. Send intent - DID will be automatically registered with Gateway if needed
try:
    receipt = client.send_intent(envelope_hash=envelope_hash, payload_dict=payload)
    tx_hash = receipt["transactionHash"]
    print(f"✔️ TxHash: {tx_hash}")
    print(f"✔️ Explorer: {client.tx_url(tx_hash)}")
except PinningError as e: print("IPFS error:", e)
except EnvelopeError as e: print("Envelope error:", e)
except NetworkError as e: print("Network error:", e)
except TransactionError as e: print("Tx failed:", e)
```

### Alternative: With Manual DID and Signer

```python
import os
import time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from intentlayer_sdk import IntentClient, create_envelope

# Environment
PINNER_URL = os.getenv("PINNER_URL", "https://pin.example.com")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")  # never commit this!

# Initialize client with manual signer
client = IntentClient.from_network(
    network="zksync-era-sepolia",
    pinner_url=PINNER_URL,
    signer=PRIVATE_KEY,  # Can be a private key string or a Signer instance
    auto_did=False,      # Disable auto-DID features
)

# Register a specific DID
did = "did:key:z6MkpzExampleDid"
client.register_did(did)

# Create and sign envelope
private_key = Ed25519PrivateKey.generate()
envelope = create_envelope(
    prompt="What is the capital of France?",
    model_id="gpt-4o@2025-03-12",
    tool_id="openai.chat",
    did=did,
    private_key=private_key,
    stake_wei=client.min_stake_wei
)

# Send intent with more control
client.send_intent(envelope.hex_hash(), {"prompt": "...", "envelope": envelope.model_dump()})
```

---

## 🔐 Security Best Practices

- **Never hard-code private keys** in source.  
- **Use environment variables**, hardware wallets, or managed key services (AWS KMS, HashiCorp Vault).
- **Store API keys securely** using process-specific env-files or secret managers to avoid shell history exposure.
- The SDK enforces HTTPS for RPC, pinner, and Gateway URLs in production (localhost/127.0.0.1 are exempt).
- **Be aware that your DID and Ethereum address are deterministically linked** for transparency and verification.

## 🔧 Environment Variables

| Variable              | Description                                        | Default               |
|-----------------------|----------------------------------------------------|------------------------|
| `INTENT_GATEWAY_URL`  | URL for the Gateway service                        | None                  |
| `INTENT_API_KEY`      | JWT token for Gateway authentication (HS256)       | None                  |
| `INTENT_AUTO_DID`     | Enable/disable auto-DID provisioning               | true                  |
| `INTENT_INSECURE_GW`  | Allow HTTP Gateway URLs (development only)         | false                 |
| `INTENT_GW_TIMEOUT`   | Gateway request timeout in seconds                 | 5                     |
| `INTENT_KEY_STORE_PATH` | Path to the identity key store                   | ~/.intentlayer/keys.json |
| `INTENT_GATEWAY_CA`   | Path to custom CA certificate for Gateway TLS      | None                  |

---

## 📚 High-Level API

### `IntentClient.from_network(...)`

| Parameter          | Type                 | Required             | Description                                              |
|--------------------|----------------------|----------------------|----------------------------------------------------------|
| `network`          | `str`                | Yes                  | Network name from networks.json (e.g., "zksync-era-sepolia") |
| `pinner_url`       | `str`                | Yes                  | IPFS pinner service URL                                  |
| `signer`           | `Union[str, Signer]` | No                   | Private key string or Signer instance (optional with auto_did=True) |
| `rpc_url`          | `str`                | No                   | Override RPC URL from networks.json                      |
| `retry_count`      | `int` (default=3)    | No                   | HTTP retry attempts                                      |
| `timeout`          | `int` (default=30)   | No                   | Request timeout in seconds                               |
| `logger`           | `logging.Logger`     | No                   | Custom logger instance                                   |
| `auto_did`         | `bool` (default=True)| No                   | Whether to automatically create and use DID identity     |
| `gateway_url`      | `str`                | No                   | URL of the Gateway service for DID registration          |

### `IntentClient(...)` (Legacy constructor)

| Parameter          | Type                 | Required             | Description                                              |
|--------------------|----------------------|----------------------|----------------------------------------------------------|
| `rpc_url`          | `str`                | Yes                  | EVM RPC endpoint (must be `https://` in prod)           |
| `pinner_url`       | `str`                | Yes                  | IPFS pinner service URL                                  |
| `signer`           | `Signer`             | Yes                  | Signer implementing `.sign_transaction()`               |
| `recorder_address` | `str`                | Yes                  | Deployed `IntentRecorder` contract address               |
| `did_registry_address` | `str`            | No                   | DIDRegistry contract address (for DID operations)        |
| `retry_count`      | `int` (default=3)    | No                   | HTTP retry attempts                                      |
| `timeout`          | `int` (default=30)   | No                   | Request timeout in seconds                               |
| `logger`           | `logging.Logger`     | No                   | Custom logger instance                                   |

### Key Methods

#### `create_envelope(...) → CallEnvelope`

Creates a complete signed envelope for recording an intent.

```python
from intentlayer_sdk import create_envelope
envelope = create_envelope(
    prompt="What is the capital of France?",
    model_id="gpt-4o@2025-03-12",
    tool_id="openai.chat",
    did="did:key:z6MkpzExampleDid",
    private_key=private_key,  # Ed25519PrivateKey instance
    stake_wei=client.min_stake_wei
)
```

#### `send_intent(...) → Dict[str, Any]`

- **Pins** JSON to IPFS  
- **Builds** & **signs** a `recordIntent` transaction  
- **Sends** it on-chain and waits for a receipt  

#### `register_did(did, ...) → Dict[str, Any]`

Registers a DID with the DIDRegistry contract.

#### `resolve_did(did) → Tuple[str, bool]`

Resolves a DID to an address and active flag.

#### `assert_chain_id()`

Verifies the connected chain matches the expected chain ID.

#### `tx_url(tx_hash) → str`

Gets a block explorer URL for a transaction hash.

---

## ⚙️ Advanced Usage

### Custom Signer

```python
from web3 import Account

class VaultSigner:
    def __init__(self, address, vault_client):
        self.address = address
        self.vault   = vault_client

    def sign_transaction(self, tx):
        # fetch key from vault and sign
        return self.vault.sign(tx)

client = IntentClient(
    rpc_url         = "…",
    pinner_url      = "…",
    min_stake_wei   = 10**16,
    signer          = VaultSigner("0xYourAddr", my_vault),
    contract_address= "0x…"
)
```

---

## 🧪 Testing & Coverage

```bash
pytest --cov=intentlayer_sdk --cov-fail-under=80
```

We maintain ≥ 80% coverage to guarantee stability.

---

## 🤝 Contributing

1. Fork the repo  
2. Create a feature branch (`git checkout -b feature/...`)  
3. Commit your changes  
4. Open a pull request  

Please follow our [Code of Conduct](CODE_OF_CONDUCT.md) and [Contribution Guidelines](CONTRIBUTING.md).

---

## 📝 License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.
