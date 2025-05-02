"""
Tests for Gateway proto serialization/deserialization roundtrip.

These tests verify that the DidDocument and TxReceipt classes can be properly
serialized to and deserialized from protobuf messages.
"""
import pytest
import os
from unittest.mock import patch, MagicMock

# Skip these tests if grpc or protobuf is not available
try:
    import grpc
    from google.protobuf import wrappers_pb2
    grpc_available = True
except ImportError:
    grpc_available = False

# Skip tests if proto stubs aren't available
try:
    from intentlayer_sdk.gateway.proto import (
        RegisterError as ProtoRegisterError,
        DidDocument as ProtoDidDocument,
        TxReceipt as ProtoTxReceipt,
        RegisterDidRequest,
        RegisterDidResponse,
        PROTO_AVAILABLE
    )
    proto_available = PROTO_AVAILABLE
except ImportError:
    proto_available = False

from intentlayer_sdk.gateway.client import DidDocument, TxReceipt
from intentlayer_sdk.gateway.exceptions import RegisterError

# Skip all tests in this module if proto is not available
pytestmark = pytest.mark.skipif(
    not (grpc_available and proto_available),
    reason="gRPC or proto stubs not available"
)


class TestProtoRoundtrip:
    """Tests for proto serialization/deserialization roundtrip."""

    def test_did_document_roundtrip(self):
        """Test DidDocument serialization/deserialization roundtrip."""
        # Create a DidDocument instance - use schema_version=3 to ensure it gets set in proto
        original_doc = DidDocument(
            did="did:key:test123",
            pub_key=b"test_key",
            org_id="test_org",
            label="test_label",
            schema_version=3,  # Use 3 not 2 to trigger setting it in proto
            doc_cid="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            payload_cid="0xfedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321"
        )

        # Convert to proto
        proto_doc = original_doc.to_proto()

        # Verify the proto object has the right values
        assert proto_doc.did == "did:key:test123"
        assert proto_doc.pub_key == b"test_key"
        assert proto_doc.org_id == "test_org"
        assert proto_doc.label == "test_label"
        assert proto_doc.schema_version.value == 3
        assert proto_doc.doc_cid == "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        assert proto_doc.payload_cid == "0xfedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321"

        # Convert back to DidDocument
        roundtrip_doc = DidDocument.from_proto(proto_doc)

        # Verify values are preserved
        assert roundtrip_doc.did == original_doc.did
        assert roundtrip_doc.pub_key == original_doc.pub_key
        assert roundtrip_doc.org_id == original_doc.org_id
        assert roundtrip_doc.label == original_doc.label
        assert roundtrip_doc.schema_version == original_doc.schema_version
        assert roundtrip_doc.doc_cid == original_doc.doc_cid
        assert roundtrip_doc.payload_cid == original_doc.payload_cid

    def test_did_document_missing_fields(self):
        """Test DidDocument serialization/deserialization with missing fields."""
        # Create a minimal DidDocument
        original_doc = DidDocument(
            did="did:key:test123",
            pub_key=b"test_key"
        )

        # Convert to proto
        proto_doc = original_doc.to_proto()

        # Verify the proto object has the right values
        assert proto_doc.did == "did:key:test123"
        assert proto_doc.pub_key == b"test_key"
        assert proto_doc.org_id == ""
        assert proto_doc.label == ""
        assert not proto_doc.HasField("schema_version") # Should not be set
        assert proto_doc.doc_cid == ""
        assert proto_doc.payload_cid == ""

        # Convert back to DidDocument
        roundtrip_doc = DidDocument.from_proto(proto_doc)

        # Verify values are preserved
        assert roundtrip_doc.did == original_doc.did
        assert roundtrip_doc.pub_key == original_doc.pub_key
        assert roundtrip_doc.org_id is None  # Empty string becomes None
        assert roundtrip_doc.label is None   # Empty string becomes None
        assert roundtrip_doc.schema_version is None
        assert roundtrip_doc.doc_cid is None # Empty string becomes None
        assert roundtrip_doc.payload_cid is None # Empty string becomes None

    def test_tx_receipt_roundtrip(self):
        """Test TxReceipt serialization/deserialization roundtrip."""
        # Create a TxReceipt instance
        original_receipt = TxReceipt(
            hash="0x1234",
            gas_used=21000,
            success=True,
            error="",
            error_code="UNKNOWN_UNSPECIFIED"
        )

        # Convert to proto
        proto_receipt = original_receipt.to_proto()

        # Verify the proto object has the right values
        assert proto_receipt.hash == "0x1234"
        assert proto_receipt.gas_used == 21000
        assert proto_receipt.success is True
        assert proto_receipt.error == ""
        assert proto_receipt.error_code == ProtoRegisterError.UNKNOWN_UNSPECIFIED

        # Convert back to TxReceipt
        roundtrip_receipt = TxReceipt.from_proto(proto_receipt)

        # Verify values are preserved
        assert roundtrip_receipt.hash == original_receipt.hash
        assert roundtrip_receipt.gas_used == original_receipt.gas_used
        assert roundtrip_receipt.success == original_receipt.success
        assert roundtrip_receipt.error == original_receipt.error
        assert roundtrip_receipt.error_code == original_receipt.error_code

    def test_tx_receipt_with_error(self):
        """Test TxReceipt serialization/deserialization with error code."""
        # Create a TxReceipt instance with error
        original_receipt = TxReceipt(
            hash="0x0000",
            gas_used=0,
            success=False,
            error="DID already registered",
            error_code="ALREADY_REGISTERED"
        )

        # Convert to proto
        proto_receipt = original_receipt.to_proto()

        # Verify the proto object has the right values
        assert proto_receipt.hash == "0x0000"
        assert proto_receipt.gas_used == 0
        assert proto_receipt.success is False
        assert proto_receipt.error == "DID already registered"
        assert proto_receipt.error_code == ProtoRegisterError.ALREADY_REGISTERED

        # Convert back to TxReceipt
        roundtrip_receipt = TxReceipt.from_proto(proto_receipt)

        # Verify values are preserved
        assert roundtrip_receipt.hash == original_receipt.hash
        assert roundtrip_receipt.gas_used == original_receipt.gas_used
        assert roundtrip_receipt.success == original_receipt.success
        assert roundtrip_receipt.error == original_receipt.error
        assert roundtrip_receipt.error_code == original_receipt.error_code

    def test_response_to_receipt_conversion(self):
        """Test converting a RegisterDidResponse to TxReceipt."""
        # Create a proto receipt
        proto_receipt = ProtoTxReceipt(
            hash="0x5678",
            gas_used=30000,
            success=True,
            error="",
            error_code=ProtoRegisterError.UNKNOWN_UNSPECIFIED
        )
        
        # Create a proto response with the receipt
        proto_response = RegisterDidResponse(receipt=proto_receipt)
        
        # Convert to TxReceipt
        receipt = TxReceipt.from_proto_response(proto_response)
        
        # Verify values
        assert receipt.hash == "0x5678"
        assert receipt.gas_used == 30000
        assert receipt.success is True
        assert receipt.error == ""
        assert receipt.error_code == "UNKNOWN_UNSPECIFIED"

    def test_cid_validation(self):
        """Test CID validation in DidDocument."""
        # Valid CIDs should pass
        assert DidDocument.validate_cid(None) is True
        assert DidDocument.validate_cid("0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef") is True
        assert DidDocument.validate_cid("1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef") is True
        
        # Invalid CIDs should raise ValueError
        with pytest.raises(ValueError, match="must be a lowercase hex string"):
            DidDocument.validate_cid("0x1234567890ABCDEF1234567890abcdef1234567890abcdef1234567890abcdef")
            
        with pytest.raises(ValueError, match="must be exactly 64 hex characters"):
            DidDocument.validate_cid("0x123456")
            
        with pytest.raises(ValueError, match="must be a lowercase hex string"):
            DidDocument.validate_cid("0x123456789!abcdef1234567890abcdef1234567890abcdef1234567890abcdef")