# Security Considerations

This document outlines security considerations for the IntentLayer Python SDK, particularly around the identity module.

## Key Derivation and Correlation

The identity module in the IntentLayer SDK currently derives Ethereum private keys from Ed25519 keys using a deterministic algorithm. This has important security implications:

- The Ethereum address derived from a DID is linkable to that DID
- An observer who sees both the DID and the Ethereum address can correlate them
- This correlation is by design to simplify the current implementation

This approach is considered acceptable as an interim solution until the release of the KMS integration (ticket INT-213) which will provide native Secp256k1 key support.

## Key Storage

Keys are stored locally in `~/.intentlayer/keys.json` with the following security measures:

- On UNIX-like systems (Linux, macOS), the file has 0600 permissions (readable/writable only by the owner)
- On Windows, file permissions cannot be restricted with the same granularity
- Keys in the file are encrypted using libsodium's SecretBox with a master key stored in the OS keyring

### Windows Security

On Windows, we currently cannot enforce the same level of file protection as on Unix systems. Users on Windows should be aware of this limitation and consider:

- Using the SDK in environments with properly configured access controls
- Looking forward to the KMS integration (INT-213) which will provide better key management
- For production environments, using a secure key management solution

### Master Key Handling

The master encryption key used to protect the keys.json file is stored in the operating system's keyring:

- This relies on the security of the OS keyring (Keychain on macOS, Credential Manager on Windows)
- In CI environments, a plaintext environment variable `INTENT_MASTER_KEY` can be used as fallback
- No encryption key rotation is currently implemented (planned for INT-213-B)

## Future Improvements

The following security improvements are planned:

1. **KMS Integration (INT-213)** - Native Secp256k1 key support and external key management
2. **Master Key Rotation (INT-213-B)** - Allow rotating the master encryption key
3. **Windows ACL Hardening (INT-212-C)** - Better file protection on Windows

## CLI Helper for Keyring Setup

If you encounter issues with the keyring on your system, a helper CLI command will be provided in an upcoming release:

```bash
intent-cli init-keyring
```

This will assist with setting up the keyring properly on your system.