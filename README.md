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
from intentlayer_sdk import IntentClient
from intentlayer_sdk.exceptions import PinningError, TransactionError, EnvelopeError

# 1. Configure via environment
RPC_URL       = os.getenv("RPC_URL")
PINNER_URL    = os.getenv("PINNER_URL")
CONTRACT_ADDR = os.getenv("INTENTLAYER_CONTRACT")
PRIVATE_KEY   = os.getenv("INTENTLAYER_PRIVATE_KEY")  # never commit this!

# 2. Initialize client
client = IntentClient(
    rpc_url         = RPC_URL,
    pinner_url      = PINNER_URL,
    min_stake_wei   = 10**16,  # 0.01 ETH
    priv_key        = PRIVATE_KEY,
    contract_address= CONTRACT_ADDR,
)

# 3. Build and send intent
payload = {
    "prompt": "Translate 'hello' to French",
    "envelope": {
        "did":           "did:key:z6MkpzExampleDid",
        "model_id":      "gpt-4o@2025-03-12",
        "prompt_sha256": "e3b0c44298fc1c149af…b7852b855",
        "tool_id":       "openai.chat",
        "timestamp_ms":  1711234567890,
        "stake_wei":     "10000000000000000",
        "sig_ed25519":   "<base64_signature>"
    },
    "metadata": {
        "user_id":    "user123",
        "session_id": "session456"
    }
}

try:
    receipt = client.send_intent(envelope_hash="0x…envelopeHashHex", payload_dict=payload)
    print(f"✔️ TxHash: {receipt.transactionHash}")
    print(f"✔️ Block:  {receipt.blockNumber}")
    print(f"✔️ Status: {'Success' if receipt.status == 1 else 'Failed'}")
except PinningError     as e: print("IPFS error:", e)
except EnvelopeError    as e: print("Envelope error:", e)
except TransactionError as e: print("Tx failed:", e)
```

---

## 🔐 Security Best Practices

- **Never hard-code private keys** in source.  
- **Use environment variables**, hardware wallets, or managed key services (AWS KMS, HashiCorp Vault).  
- The SDK enforces HTTPS for RPC and pinner URLs in production (localhost/127.0.0.1 are exempt).

---

## 📚 High-Level API

### `IntentClient(...)`

| Parameter          | Type                 | Required             | Description                                              |
|--------------------|----------------------|----------------------|----------------------------------------------------------|
| `rpc_url`          | `str`                | Yes                  | EVM RPC endpoint (must be `https://` in prod)           |
| `pinner_url`       | `str`                | Yes                  | IPFS pinner service URL                                  |
| `min_stake_wei`    | `int`                | Yes                  | Minimum collateral for `recordIntent()`                  |
| `priv_key`         | `str`                | _one of_ `priv_key` or `signer` | Hex-encoded Ethereum private key (0x…)         |
| `signer`           | `Signer`             | _one of_ `priv_key` or `signer` | Custom signer implementing `.sign_transaction()` |
| `contract_address` | `str`                | Yes (for on-chain)   | Deployed `IntentRecorder` contract address               |
| `retry_count`      | `int` (default=3)    | No                   | HTTP retry attempts                                      |
| `timeout`          | `int` (default=30)   | No                   | Request timeout in seconds                               |
| `logger`           | `logging.Logger`     | No                   | Custom logger instance                                   |

#### `send_intent(...) → TxReceipt`

- **Pins** JSON to IPFS  
- **Builds** & **signs** a `recordIntent` transaction  
- **Sends** it on-chain and waits for a receipt  

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
