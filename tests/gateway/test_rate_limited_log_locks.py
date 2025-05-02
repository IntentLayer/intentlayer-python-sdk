"""
Tests for lock handling in rate-limited logging.

These tests verify that locks are properly acquired and released
in the rate-limited logging implementation.
"""
import pytest
import logging
from unittest.mock import patch, MagicMock

from intentlayer_sdk.gateway._rate_limited_log import rate_limited_log

# Check if the cachetools library is available
try:
    from cachetools import TTLCache
    cachetools_available = True
except ImportError:
    cachetools_available = False


class TestRateLimitedLogLocks:
    """Tests for lock handling in rate-limited logging."""
    
    def test_ttlcache_lock_release_on_success(self):
        """Test lock is released after successful execution with TTLCache."""
        # Skip if cachetools is not available
        if not cachetools_available:
            pytest.skip("cachetools not available")
        
        # Mock the cache, lock, and logger
        mock_cache = {}
        mock_lock = MagicMock()
        mock_logger = MagicMock()
        
        # Test lock release with successful execution
        with patch('intentlayer_sdk.gateway._rate_limited_log._error_log_cache', mock_cache), \
             patch('intentlayer_sdk.gateway._rate_limited_log._error_log_cache_lock', mock_lock), \
             patch('intentlayer_sdk.gateway._rate_limited_log.TTLCACHE_AVAILABLE', True):
            
            # Call the function
            rate_limited_log("Test message", "info", 60, mock_logger)
            
            # Verify lock was acquired and released
            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()
    
    def test_ttlcache_lock_release_on_exception(self):
        """Test lock is released even when an exception occurs."""
        # Skip if cachetools is not available
        if not cachetools_available:
            pytest.skip("cachetools not available")
        
        # Mock the cache, lock, and logger
        mock_cache = {}
        mock_lock = MagicMock()
        mock_logger = MagicMock()
        
        # Make logger.info raise an exception
        mock_logger.info.side_effect = RuntimeError("Test exception")
        
        # Test lock release with exception
        with patch('intentlayer_sdk.gateway._rate_limited_log._error_log_cache', mock_cache), \
             patch('intentlayer_sdk.gateway._rate_limited_log._error_log_cache_lock', mock_lock), \
             patch('intentlayer_sdk.gateway._rate_limited_log.TTLCACHE_AVAILABLE', True):
            
            # Call the function, expecting an exception
            with pytest.raises(RuntimeError):
                rate_limited_log("Test message", "info", 60, mock_logger)
            
            # Verify lock was acquired and released
            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()
    
    def test_fallback_lock_release_on_success(self):
        """Test lock is released after successful execution with fallback implementation."""
        # Mock the timestamps dict, lock, and logger
        mock_timestamps = {}
        mock_lock = MagicMock()
        mock_logger = MagicMock()
        
        # Test lock release with successful execution
        with patch('intentlayer_sdk.gateway._rate_limited_log._error_log_timestamps', mock_timestamps), \
             patch('intentlayer_sdk.gateway._rate_limited_log._error_log_timestamps_lock', mock_lock), \
             patch('intentlayer_sdk.gateway._rate_limited_log.TTLCACHE_AVAILABLE', False):
            
            # Call the function
            rate_limited_log("Test message", "info", 60, mock_logger)
            
            # Verify lock was acquired and released
            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()
    
    def test_fallback_lock_release_on_exception(self):
        """Test lock is released even when an exception occurs with fallback implementation."""
        # Mock the timestamps dict, lock, and logger
        mock_timestamps = {}
        mock_lock = MagicMock()
        mock_logger = MagicMock()
        
        # Make logger.info raise an exception
        mock_logger.info.side_effect = RuntimeError("Test exception")
        
        # Test lock release with exception
        with patch('intentlayer_sdk.gateway._rate_limited_log._error_log_timestamps', mock_timestamps), \
             patch('intentlayer_sdk.gateway._rate_limited_log._error_log_timestamps_lock', mock_lock), \
             patch('intentlayer_sdk.gateway._rate_limited_log.TTLCACHE_AVAILABLE', False):
            
            # Call the function, expecting an exception
            with pytest.raises(RuntimeError):
                rate_limited_log("Test message", "info", 60, mock_logger)
            
            # Verify lock was acquired and released
            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()