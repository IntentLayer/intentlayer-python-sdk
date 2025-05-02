"""
Tests for in-process gRPC server for integration testing.

This module provides a lightweight implementation of the GatewayService
for in-process testing of gRPC clients without requiring network connections.
"""
import logging
import pytest
import time
from typing import Dict, Any, Optional, Callable, List, Tuple
from unittest.mock import MagicMock, patch

# Skip tests if grpc-testing or protobuf is not available
try:
    import grpc
    import grpc_testing
    from google.protobuf import wrappers_pb2
    from grpc_testing import server_from_dictionary
    grpc_testing_available = True
except ImportError:
    grpc_testing_available = False

# Skip tests if proto stubs aren't available
try:
    from intentlayer_sdk.gateway.proto import (
        RegisterError as ProtoRegisterError,
        DidDocument as ProtoDidDocument,
        TxReceipt as ProtoTxReceipt,
        RegisterDidRequest,
        RegisterDidResponse,
        GatewayServiceStub,
        PROTO_AVAILABLE
    )
    from intentlayer_sdk.gateway.proto.gateway_pb2_grpc import GatewayServiceServicer
    proto_available = PROTO_AVAILABLE
except ImportError:
    proto_available = False

# Mark to skip if dependencies aren't available
requires_grpc_testing = pytest.mark.skipif(
    not (grpc_testing_available and proto_available),
    reason="grpc_testing or proto stubs not available"
)

# Configure logger
logger = logging.getLogger(__name__)


class TestGatewayServicer(GatewayServiceServicer):
    """
    Test implementation of the GatewayService servicer.
    
    This class implements the Gateway service methods with configurable
    behavior for testing client interactions.
    """
    
    def __init__(self):
        """Initialize the test servicer with default behaviors."""
        self.registered_dids = set()
        self.call_count = {
            "RegisterDid": 0,
            "SendIntent": 0,
            "StreamIntents": 0,
            "StreamDids": 0
        }
        self.metadata_received = {}
        self.requests_received = {}
        
        # Configurable handlers that can be overridden by tests
        self.register_did_handler = None
        self.send_intent_handler = None
        
        # Default delay to simulate network latency (in seconds)
        self.default_delay = 0.0
        
        # Default behavior handlers
        self._setup_default_handlers()
    
    def _setup_default_handlers(self):
        """Set up default behavior handlers for all RPC methods."""
        # Default RegisterDid handler
        def default_register_did(request, context):
            # Basic validation
            if not request.document.did:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("DID is required")
                return None
                
            # Check if DID is already registered
            if request.document.did in self.registered_dids:
                receipt = ProtoTxReceipt(
                    hash="0x0000000000000000000000000000000000000000000000000000000000000000",
                    gas_used=0,
                    success=False,
                    error="DID already registered",
                    error_code=ProtoRegisterError.ALREADY_REGISTERED
                )
                return RegisterDidResponse(receipt=receipt)
            
            # Special DIDs for testing specific behaviors
            if request.document.did == "did:key:timeout":
                # Simulate timeout
                time.sleep(10.0)  # This will typically exceed client timeout
                
            if request.document.did == "did:key:quota_exceeded":
                receipt = ProtoTxReceipt(
                    hash="0x0000000000000000000000000000000000000000000000000000000000000000",
                    gas_used=0,
                    success=False,
                    error="DID registration quota exceeded",
                    error_code=ProtoRegisterError.DID_QUOTA_EXCEEDED
                )
                return RegisterDidResponse(receipt=receipt)
                
            if request.document.did == "did:key:invalid_did":
                receipt = ProtoTxReceipt(
                    hash="0x0000000000000000000000000000000000000000000000000000000000000000",
                    gas_used=0,
                    success=False,
                    error="Invalid DID format",
                    error_code=ProtoRegisterError.INVALID_DID
                )
                return RegisterDidResponse(receipt=receipt)
                
            if request.document.did == "did:key:unavailable":
                context.set_code(grpc.StatusCode.UNAVAILABLE)
                context.set_details("Service temporarily unavailable")
                return None
                
            if request.document.did == "did:key:resource_exhausted":
                context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                context.set_details("Resource quota exceeded")
                return None
            
            # Standard success path
            self.registered_dids.add(request.document.did)
            receipt = ProtoTxReceipt(
                hash="0x" + "1" * 64,  # dummy transaction hash
                gas_used=21000,
                success=True,
                error="",
                error_code=ProtoRegisterError.UNKNOWN_UNSPECIFIED
            )
            return RegisterDidResponse(receipt=receipt)
            
        # Set the default handlers
        self.register_did_handler = default_register_did
    
    def RegisterDid(self, request, context):
        """
        Handle RegisterDid RPC calls.
        
        Args:
            request: The RegisterDidRequest proto message
            context: RPC context
            
        Returns:
            RegisterDidResponse proto message
        """
        self.call_count["RegisterDid"] += 1
        self.requests_received["RegisterDid"] = request
        
        # Store metadata if available
        if context and hasattr(context, "invocation_metadata"):
            self.metadata_received["RegisterDid"] = dict(context.invocation_metadata())
        
        # Simulate network delay
        if self.default_delay > 0:
            time.sleep(self.default_delay)
            
        # Use custom handler if provided, otherwise use default
        if self.register_did_handler:
            return self.register_did_handler(request, context)
            
        # Fallback if handler somehow not set
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not properly implemented")
        return None
    
    def SendIntent(self, request, context):
        """
        Handle SendIntent RPC calls (not fully implemented).
        
        This method is included for completeness but not used in current tests.
        """
        self.call_count["SendIntent"] += 1
        self.requests_received["SendIntent"] = request
        
        # Default implementation
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        return None
    
    def StreamIntents(self, request_iterator, context):
        """
        Handle StreamIntents RPC calls (not fully implemented).
        
        This method is included for completeness but not used in current tests.
        """
        self.call_count["StreamIntents"] += 1
        
        # Default implementation
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        return None
    
    def StreamDids(self, request_iterator, context):
        """
        Handle StreamDids RPC calls (not fully implemented).
        
        This method is included for completeness but not used in current tests.
        """
        self.call_count["StreamDids"] += 1
        
        # Default implementation
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        return None


class GrpcTestServer:
    """
    In-process gRPC test server for integration testing.
    
    This class provides a lightweight implementation of a gRPC server
    that runs in-process for testing client code without network connections.
    """
    
    def __init__(self):
        """Initialize the test server with a test servicer."""
        if not (grpc_testing_available and proto_available):
            raise ImportError("grpc_testing and proto stubs must be available")
            
        # Create the test servicer
        self.servicer = TestGatewayServicer()
        
        # Create the in-process test server
        service_descriptors = {
            'intentlayer.v2.GatewayService': GatewayServiceServicer
        }
        
        # Create test server (with both APIs for compatibility)
        self.test_server = server_from_dictionary(
            service_descriptors, grpc_testing.strict_real_time()
        )
    
    def get_test_channel(self):
        """
        Get a test channel for client use.
        
        Returns:
            A grpc_testing test channel connected to this test server
        """
        # Different versions of grpc_testing have different APIs
        if hasattr(self.test_server, 'channel'):
            return self.test_server.channel()
        else:
            # For newer grpc_testing versions
            return self.test_server
    
    def get_stub(self):
        """
        Get a GatewayServiceStub connected to this test server.
        
        Returns:
            GatewayServiceStub connected to the test server
        """
        return GatewayServiceStub(self.get_test_channel())
    
    def set_register_did_handler(self, handler):
        """
        Set a custom handler for RegisterDid RPC.
        
        Args:
            handler: Function with signature (request, context) -> response
        """
        self.servicer.register_did_handler = handler
    
    def set_network_delay(self, delay_seconds):
        """
        Set a simulated network delay for all RPC calls.
        
        Args:
            delay_seconds: Delay in seconds to simulate network latency
        """
        self.servicer.default_delay = delay_seconds