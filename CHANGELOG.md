# Changelog

All notable changes to the IntentLayer Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2025-05-01

### Added
- Transport layer abstraction for Gateway client to improve modularity
- Created GatewayTransport base class with Protocol Buffers implementation
- Thread-safe rate-limited logging with proper locking mechanisms
- Standardized JWT handling across different environments
- Windows compatibility for proto generation with platform-independent commands
- Redis-based distributed locking for multi-node deployments
- Improved error handling and retry logic for Gateway operations

### Changed
- **BREAKING:** Gateway now requires schema version 2 for all DID registrations
- **BREAKING:** V1 Protocol support has been removed
- **BREAKING:** Now requires gRPC dependencies for Gateway integration (via pip install intentlayer-sdk[grpc])
- Updated documentation and examples for V2-only protocol support
- Enhanced cross-platform compatibility for development workflows
- Improved thread safety across the codebase

### Fixed
- Enhanced thread safety in _rate_limited_log with proper locking
- Made JWT unsafe algorithm handling consistent across environment tiers
- Adjusted TTLCache test to avoid time.sleep() dependencies
- Added Windows compatibility for proto generation
- Fixed Makefile for cross-platform compatibility
- Removed runtime pip install calls from build process
- Improved CI/CD pipeline for better verification across platforms


## [0.4.0] - 2025-04-28

### Added
- Identity module for DID and key management
- Automatic DID generation with did:key method
- Secure key storage with encryption using OS keyring
- New API methods: `get_or_create_did()`, `create_new_identity()`, `delete_local()`
- Support for auto_did in IntentClient.from_network
- New example showcasing the automatic DID feature

### Fixed
- Proper multicodec encoding in did:key generation
- Improved Ethereum key derivation from Ed25519 keys using proper modular arithmetic
- Secure encryption with nacl.SecretBox storing full encrypted payload
- Metadata storage outside of encrypted content for better identity sorting
- Added documentation about Windows permission limitations
- Fixed import of Ed25519PrivateKey for type annotations
- Improved file locking with non-blocking locks and exponential backoff
- Enhanced test fixtures with proper encryption for better CI experience

## [0.3.0] - 2025-04-27

### Added
- CLI: `intent-cli verify` command to verify IntentEnvelopes on-chain against IPFS
- CLI: Distribution via pipx with console script entry point

## [0.2.1] - 2025-04-25

### Fixed
- URLlib3 compatibility issues with URLlib3 2.x by using signature inspection instead of attribute checking
- Fixed test failures caused by method_whitelist parameter in Retry constructor

## [0.2.0] - 2025-04-25

### Added
- Network configuration system with networks.json
- Factory method for network-based client initialization (from_network)
- DID registry interaction for registration and resolution
- Modular signer system with Protocol interface
- Property caching with time-based expiration
- Chain ID validation for transaction safety
- CID length validation with automatic truncation for Solidity contracts

### Fixed
- Exception handling for InactiveDIDError and AlreadyRegisteredError
- IPFS CID conversion with proper fallback options
- Package data configuration to include networks.json in distribution
- Missing validation for address property when signer is missing
- URLlib3 compatibility issues with better attribute detection
- Stake slippage by re-querying min_stake_wei on gas estimation failures
- Manually set min_stake_wei values now won't auto-refresh

### Changed
- Consolidated models and removed duplication
- Improved error handling architecture 
- Enhanced test coverage to 80%+
- Updated client constructor to use signer and recorder_address
- Better dependency specifications in pyproject.toml
- Added py.typed marker file for improved typing support
- Improved poetry packaging configuration

### Removed
- Backward compatibility layer (IntentLayerClient class)
- Deprecated aliases and parameter handling
- Legacy contract_address parameter in favor of recorder_address
- Legacy priv_key parameter in favor of signer object
- Unused imports and dependencies

## [0.1.3] - 2025-04-24

### Fixed
- python >=3.9 in pyproject.toml 

## [0.1.2] - 2025-04-24

### Fixed
- Packaging configuration to include data files

## [0.1.1] - 2025-04-24

### Added
- Comprehensive test suite reaching 90%+ test coverage
- Additional error handling tests for edge cases
- Better retry logic for HTTP requests

### Fixed
- IPFS pinning retry mechanism now properly handles server errors
- URL validation for localhost with port numbers
- Network error handling during transaction submission

### Changed
- Updated HTTP retry configuration for better reliability
- Improved logging for error conditions


## [0.1.0] - 2025-04-15

### Added
- Initial release
- `IntentClient` class for interacting with the IntentLayer protocol
- IPFS pinning functionality
- Blockchain intent recording
- Custom signer support
- Comprehensive error handling
- Utility functions for envelope creation and CID conversion