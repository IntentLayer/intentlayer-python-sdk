# intent-cli verify

The `verify` command checks that an IntentEnvelope recorded on-chain matches the JSON envelope stored on IPFS.

## Usage

```bash
intent-cli verify <TX_HASH> [OPTIONS]
```

## Description

This command provides a single-step way to prove that an IntentEnvelope recorded on-chain exactly matches the JSON envelope stored on IPFS.

The verification process:

1. Fetches the transaction receipt for the given hash
2. Extracts the IPFS CID from the IntentRecorded event log
3. Downloads the JSON payload from IPFS
4. Compares the on-chain envelope hash with the envelope in the JSON payload
5. Reports a PASS/FAIL result with appropriate exit code

## Arguments

- `TX_HASH` (required): The transaction hash to verify

## Options

- `--gateway TEXT`: IPFS gateway URL (default: https://w3s.link/ipfs/)
- `--gateway-token TEXT`: Authentication token for private IPFS gateways
- `--network TEXT`: Specific network to use (default: auto-detect)
- `--no-color`: Disable colored output
- `--debug`: Enable debug output
- `--help`: Show this message and exit

## Exit Codes

The command returns one of the following exit codes:

- `0`: Hashes match (PASS)
- `1`: Mismatch (FAIL)
- `2`: Network/RPC error or gateway unreachable
- `3`: Unexpected error
- `4`: Invalid command arguments

## Examples

### Basic Usage

```bash
intent-cli verify 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
```

### With Custom IPFS Gateway

```bash
intent-cli verify 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef --gateway https://ipfs.io/ipfs/
```

### Using a Private IPFS Gateway with Authentication

```bash
intent-cli verify 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef --gateway https://my-private-gateway.com/ipfs/ --gateway-token my-auth-token
```

### Specify Network Explicitly

```bash
intent-cli verify 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef --network zksync-era-sepolia
```

### Disable Colored Output

```bash
intent-cli verify 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef --no-color
```

### Debug Mode

```bash
intent-cli verify 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef --debug
```

## Installation

The command is part of the IntentLayer SDK and can be installed via pipx:

```bash
pipx install intentlayer-sdk
```

## Notes

- The command automatically detects the network from the transaction receipt's chain ID
- It works with any network defined in the SDK's networks.json file
- The verification ignores non-critical fields like metadata and JSON key order