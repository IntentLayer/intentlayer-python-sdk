"""
Protocol buffer definitions for the IntentLayer Gateway service.

This module provides access to the generated protocol buffer classes
and gRPC service stubs for interacting with the Gateway service.
"""
try:
    from .gateway_pb2 import (
        RegisterError,
        DidDocument,
        TxReceipt,
        RegisterDidRequest,
        RegisterDidResponse,
    )
    from .gateway_pb2_grpc import GatewayServiceStub
    PROTO_AVAILABLE = True
except ImportError:
    PROTO_AVAILABLE = False

__all__ = [
    'RegisterError',
    'DidDocument',
    'TxReceipt',
    'RegisterDidRequest',
    'RegisterDidResponse',
    'GatewayServiceStub',
    'PROTO_AVAILABLE',
]