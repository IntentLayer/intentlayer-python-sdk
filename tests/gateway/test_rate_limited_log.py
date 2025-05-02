"""
Tests for the shared rate-limited logging implementation.

These tests verify that the rate limiting functionality works correctly
in both TTLCache and fallback modes.
"""
import pytest
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Check if the cachetools library is available
try:
    from cachetools import TTLCache
    cachetools_available = True
except ImportError:
    cachetools_available = False

from intentlayer_sdk.gateway._rate_limited_log import rate_limited_log


class TestRateLimitedLog:
    """Tests for the rate-limited logging implementation."""
    
    def test_rate_limited_log_with_ttlcache(self):
        """Test rate limiting with TTLCache."""
        # Skip if cachetools is not available
        if not cachetools_available:
            pytest.skip("cachetools not available")
        
        # Mock the cache, lock, and logger
        mock_cache = {}
        mock_lock = MagicMock()
        mock_logger = MagicMock()
        
        # Test with our mocked environment
        with patch('intentlayer_sdk.gateway._rate_limited_log._error_log_cache', mock_cache), \
             patch('intentlayer_sdk.gateway._rate_limited_log._error_log_cache_lock', mock_lock), \
             patch('intentlayer_sdk.gateway._rate_limited_log.TTLCACHE_AVAILABLE', True):
             
            # First log should go through
            rate_limited_log("Test message", level="warning", logger_instance=mock_logger)
            mock_logger.warning.assert_called_once_with("Test message")
            mock_lock.__enter__.assert_called()  # Lock should be acquired
            assert "warning:Test message" in mock_cache  # Key should be added to cache
            
            # Reset mock
            mock_logger.reset_mock()
            
            # Second immediate log should be suppressed
            rate_limited_log("Test message", level="warning", logger_instance=mock_logger)
            mock_logger.warning.assert_not_called()  # Log should be suppressed
            
            # Different level should go through
            rate_limited_log("Test message", level="error", logger_instance=mock_logger)
            mock_logger.error.assert_called_once_with("Test message")
            assert "error:Test message" in mock_cache
            
            # Different message should go through
            mock_logger.reset_mock()
            rate_limited_log("Different message", level="warning", logger_instance=mock_logger)
            mock_logger.warning.assert_called_once_with("Different message")
            assert "warning:Different message" in mock_cache
    
    def test_rate_limited_log_fallback(self):
        """Test rate limiting with timestamp fallback."""
        # Mock timestamps, lock, and logger
        mock_timestamps = {}
        mock_lock = MagicMock()
        mock_logger = MagicMock()
        
        # Create timestamp for testing
        now = datetime(2023, 1, 1, 12, 0, 0)
        old_time = now - timedelta(seconds=2)  # 2 seconds old
        future_time = now + timedelta(seconds=60)  # 60 seconds in future
        
        # Test with our mocked environment
        with patch('intentlayer_sdk.gateway._rate_limited_log._error_log_timestamps', mock_timestamps), \
             patch('intentlayer_sdk.gateway._rate_limited_log._error_log_timestamps_lock', mock_lock), \
             patch('intentlayer_sdk.gateway._rate_limited_log.TTLCACHE_AVAILABLE', False), \
             patch('intentlayer_sdk.gateway._rate_limited_log.datetime') as mock_datetime:
            
            # Mock datetime.now() to return specific timestamps
            mock_datetime.now.return_value = now
            
            # First log should go through
            rate_limited_log("Test message", level="warning", interval=1, logger_instance=mock_logger)
            mock_logger.warning.assert_called_once_with("Test message")
            assert "warning:Test message" in mock_timestamps
            
            # Reset mock
            mock_logger.reset_mock()
            
            # Second immediate log should be suppressed (same timestamp)
            rate_limited_log("Test message", level="warning", interval=1, logger_instance=mock_logger)
            mock_logger.warning.assert_not_called()  # Log should be suppressed
            
            # Advance time past the interval
            mock_datetime.now.return_value = now + timedelta(seconds=1.5)
            
            # Now the log should go through again
            rate_limited_log("Test message", level="warning", interval=1, logger_instance=mock_logger)
            mock_logger.warning.assert_called_once_with("Test message")
            
            # Test with pre-populated timestamps cache
            mock_logger.reset_mock()
            mock_timestamps.clear()
            # Pre-populate with an expired entry
            mock_timestamps["warning:expired"] = old_time
            # Pre-populate with a future entry (shouldn't log)
            mock_timestamps["warning:future"] = future_time
            
            # Try to log the expired entry
            rate_limited_log("expired", level="warning", interval=1, logger_instance=mock_logger)
            mock_logger.warning.assert_called_once_with("expired")
            
            # Try to log the future entry (should be suppressed)
            mock_logger.reset_mock()
            rate_limited_log("future", level="warning", interval=1, logger_instance=mock_logger)
            mock_logger.warning.assert_not_called()
    
    def test_passing_custom_logger(self):
        """Test passing a custom logger instance."""
        # Create mock logger with full method specs
        mock_logger = MagicMock(spec=logging.Logger)
        
        # Use rate_limited_log with custom logger directly
        rate_limited_log("Debug message", level="debug", logger_instance=mock_logger)
        
        # Verify correct logger method was called
        mock_logger.debug.assert_called_once_with("Debug message")