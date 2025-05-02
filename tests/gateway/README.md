# Gateway Integration Tests

This directory contains integration tests for the IntentLayer Gateway client. These tests verify that the client can properly communicate with a gRPC server using real proto messages.

## Overview

The integration tests use an in-process gRPC test server to simulate Gateway service responses without requiring network connections. This approach allows for testing the real client code with various server responses, including error conditions.

## Components

### Test Server

The `test_grpc_server.py` file provides:

- `TestGatewayServicer`: A test implementation of the Gateway service
- `GrpcTestServer`: A lightweight in-process gRPC server for testing

The test server can be configured to respond with various success and error cases to test client handling.

### Fixtures

The `conftest.py` file provides pytest fixtures for integration testing:

- `grpc_test_server`: Creates a fresh test server instance
- `grpc_test_channel`: Provides a gRPC channel connected to the test server
- `gateway_test_client`: Provides a configured `GatewayClient` that uses the test server
- `gateway_test_transport`: Provides a `ProtoTransport` that uses the test server

### Integration Tests

The `test_grpc_integration.py` file contains tests that verify:

- Successful DID registration
- Error handling (already registered, quota exceeded, etc.)
- Retries and timeouts
- Metadata/API key handling
- Transport layer integration

## Running the Tests

To run the integration tests, you need to have the gRPC dependencies installed:

```bash
# Install dependencies with Poetry
poetry install --extras grpc
poetry add grpcio-testing --group dev

# Run the tests
poetry run pytest tests/gateway/test_grpc_integration.py -v
```

## Extending the Tests

To add new test cases:

1. Add test methods to the `TestGatewayClientIntegration` or `TestTransportIntegration` classes
2. For testing custom server behaviors, add handling in `TestGatewayServicer` or use the custom handler mechanism

## CI Integration

The integration tests are run automatically in the CI pipeline using the `integration-tests.yml` GitHub Actions workflow. This workflow verifies that all Gateway integration tests pass on each pull request and push to the main branch.

## Notes

- The tests are skipped if gRPC or protobuf dependencies are not available
- For comprehensive coverage, ensure both success and error paths are tested
- Use the fixtures to create test clients instead of creating them directly