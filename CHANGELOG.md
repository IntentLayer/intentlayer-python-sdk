# Changelog

All notable changes to the IntentLayer Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

### Deprecated
- The backward compatibility layer for `IntentLayerClient` alias will be removed in version 1.0.0. 
  Please use `IntentClient` instead.

## [0.1.0] - 2025-04-15

### Added
- Initial release
- `IntentClient` class for interacting with the IntentLayer protocol
- IPFS pinning functionality
- Blockchain intent recording
- Custom signer support
- Comprehensive error handling
- Utility functions for envelope creation and CID conversion