"""
Tests for the rate limiting cache implementation.

These tests verify that the rate limiting cache works correctly.
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


class TestRateLimitCache:
    """Tests for the rate limiting cache implementation."""

    def test_rate_limited_log_with_ttlcache(self):
        """Test rate limiting with TTLCache."""
        # Skip if cachetools is not available
        if not cachetools_available:
            pytest.skip("cachetools not available")

        # Mock the TTLCache to test its usage
        mock_cache = {}
        mock_lock = MagicMock()
        
        # Create a mock logger that records calls
        mock_logger = MagicMock()
        
        # Create a client with our mocks
        client = GatewayClient("https://example.com")
        
        # Test with our mocked environment
        with patch('intentlayer_sdk.gateway.client._error_log_cache', mock_cache), \
             patch('intentlayer_sdk.gateway.client._error_log_cache_lock', mock_lock), \
             patch('intentlayer_sdk.gateway.client.logger', mock_logger), \
             patch('intentlayer_sdk.gateway.client.TTLCACHE_AVAILABLE', True):
             
            # First log should go through
            client._rate_limited_log("Test message", level="warning")
            mock_logger.warning.assert_called_once_with("Test message")
            mock_lock.__enter__.assert_called()  # Lock should be acquired
            assert "warning:Test message" in mock_cache  # Key should be added to cache
            
            # Reset mock
            mock_logger.reset_mock()
            
            # Second immediate log should be suppressed
            client._rate_limited_log("Test message", level="warning")
            mock_logger.warning.assert_not_called()  # Log should be suppressed
            
            # Different level should go through
            client._rate_limited_log("Test message", level="error")
            mock_logger.error.assert_called_once_with("Test message")
            assert "error:Test message" in mock_cache
            
            # Different message should go through
            mock_logger.reset_mock()
            client._rate_limited_log("Different message", level="warning")
            mock_logger.warning.assert_called_once_with("Different message")
            assert "warning:Different message" in mock_cache

    def test_rate_limited_log_fallback(self):
        """Test rate limiting with timestamp fallback."""
        # Create a mock logger that records calls
        mock_logger = MagicMock()
        mock_timestamps = {}
        
        # Create a client
        client = GatewayClient("https://example.com")
        
        # Create a timestamp in the past for testing expiration
        from datetime import datetime, timedelta
        now = datetime.now()
        old_time = now - timedelta(seconds=2)  # 2 seconds old
        future_time = now + timedelta(seconds=60)  # 60 seconds in future
        
        # Test with our mocked environment
        with patch('intentlayer_sdk.gateway.client._error_log_timestamps', mock_timestamps), \
             patch('intentlayer_sdk.gateway.client.logger', mock_logger), \
             patch('intentlayer_sdk.gateway.client.TTLCACHE_AVAILABLE', False), \
             patch('intentlayer_sdk.gateway.client.datetime') as mock_datetime:
            
            # Mock datetime.now() to return specific timestamps
            mock_datetime.now.return_value = now
            
            # First log should go through
            client._rate_limited_log("Test message", level="warning", interval=1)
            mock_logger.warning.assert_called_once_with("Test message")
            assert "warning:Test message" in mock_timestamps
            
            # Reset mock
            mock_logger.reset_mock()
            
            # Second immediate log should be suppressed (same timestamp)
            client._rate_limited_log("Test message", level="warning", interval=1)
            mock_logger.warning.assert_not_called()  # Log should be suppressed
            
            # Advance time past the interval (mock instead of sleep)
            mock_datetime.now.return_value = now + timedelta(seconds=1.5)
            
            # Now the log should go through again
            client._rate_limited_log("Test message", level="warning", interval=1)
            mock_logger.warning.assert_called_once_with("Test message")
            
            # Test with pre-populated timestamps cache
            mock_logger.reset_mock()
            mock_timestamps.clear()
            # Pre-populate with an expired entry
            mock_timestamps["warning:expired"] = old_time
            # Pre-populate with a future entry (shouldn't log)
            mock_timestamps["warning:future"] = future_time
            
            # Try to log the expired entry
            client._rate_limited_log("expired", level="warning", interval=1)
            mock_logger.warning.assert_called_once_with("expired")
            
            # Try to log the future entry (should be suppressed)
            mock_logger.reset_mock()
            client._rate_limited_log("future", level="warning", interval=1)
            mock_logger.warning.assert_not_called()