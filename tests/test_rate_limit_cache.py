"""
Tests for the rate limiting cache implementation.

These tests verify that the rate limiting cache works correctly.

NOTE: This test file is deprecated and has been replaced by dedicated tests in
tests/gateway/test_rate_limited_log*.py
"""
import pytest
import logging
import time
from unittest.mock import patch, MagicMock

# Check if the cachetools library is available
try:
    from cachetools import TTLCache
    cachetools_available = True
except ImportError:
    cachetools_available = False

from intentlayer_sdk.gateway.client import GatewayClient
from intentlayer_sdk.gateway._rate_limited_log import rate_limited_log


class TestRateLimitCache:
    """Tests for the rate limiting cache implementation."""

    def test_rate_limited_log_with_ttlcache(self):
        """Test rate limiting with TTLCache."""
        # Skip test - this has been moved to the dedicated test file
        pytest.skip("This test has been moved to tests/gateway/test_rate_limited_log.py")

    def test_rate_limited_log_fallback(self):
        """Test rate limiting with timestamp fallback."""
        # Skip test - this has been moved to the dedicated test file
        pytest.skip("This test has been moved to tests/gateway/test_rate_limited_log.py")