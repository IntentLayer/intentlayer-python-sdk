"""
Tests for the gateway transport layer.

These tests verify that the transport layer abstraction works correctly
and selects the appropriate implementation based on available dependencies.
"""
import pytest
from unittest.mock import patch, MagicMock

from intentlayer_sdk.gateway.transport import TxReceipt
from intentlayer_sdk.gateway.exceptions import GatewayError


class TestTransport:
    """Tests for the gateway transport layer."""
    
    def test_tx_receipt_validation(self):
        """Test TxReceipt validation."""
        # Valid receipt with success=True
        valid_receipt = TxReceipt(
            hash="0x1234",
            gas_used=21000,
            success=True,
            error="",
            error_code="UNKNOWN_UNSPECIFIED"
        )
        assert TxReceipt.validate(valid_receipt) is True
        
        # Valid receipt with success=False
        valid_failure = TxReceipt(
            hash="0x1234",
            gas_used=0,
            success=False,
            error="Test error",
            error_code="INVALID_DID"
        )
        assert TxReceipt.validate(valid_failure) is True
        
        # Invalid receipt (success=True with error_code)
        invalid_receipt = TxReceipt(
            hash="0x1234",
            gas_used=21000,
            success=True,
            error="",
            error_code="INVALID_DID"  # This is invalid with success=True
        )
        with pytest.raises(ValueError):
            TxReceipt.validate(invalid_receipt)
    
