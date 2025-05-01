"""
Tests for expired entry cleanup in rate-limited logging.

These tests verify that expired entries are properly cleaned up
in the rate-limited logging implementation's fallback mode.
"""
import pytest
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from intentlayer_sdk.gateway._rate_limited_log import rate_limited_log


class TestRateLimitedLogExpiry:
    """Tests for expired entry cleanup in rate-limited logging."""
    
    def test_cleanup_expired_entries(self):
        """Test that expired entries are cleaned up in the fallback implementation."""
        # Mock the timestamps dict, lock, and logger
        mock_timestamps = {}
        mock_logger = MagicMock()
        
        # Create the current time and times for entries
        now = datetime(2023, 1, 1, 12, 0, 0)  # Fixed time for test
        
        # Recent entry (should stay)
        recent_time = now - timedelta(minutes=30)
        # Expired entry (should be removed - older than 1 hour)
        expired_time = now - timedelta(hours=2)
        
        # Populate the mock timestamps with test data
        mock_timestamps["info:recent"] = recent_time
        mock_timestamps["warning:expired"] = expired_time
        
        # Test that expired entries are cleaned up
        with patch('intentlayer_sdk.gateway._rate_limited_log._error_log_timestamps', mock_timestamps), \
             patch('intentlayer_sdk.gateway._rate_limited_log.TTLCACHE_AVAILABLE', False), \
             patch('intentlayer_sdk.gateway._rate_limited_log.datetime') as mock_datetime, \
             patch('intentlayer_sdk.gateway._rate_limited_log._error_log_timestamps_lock', MagicMock()):
            
            # Set the current time for the test
            mock_datetime.now.return_value = now
            
            # Call rate_limited_log with a new message
            rate_limited_log("new_message", "debug", 60, mock_logger)
            
            # Verify the logger was called
            mock_logger.debug.assert_called_once_with("new_message")
            
            # Verify that expired entry was removed and recent entry was kept
            assert "warning:expired" not in mock_timestamps
            assert "info:recent" in mock_timestamps
            # Verify the new entry was added
            assert "debug:new_message" in mock_timestamps
    
    def test_cleanup_with_multiple_expired_entries(self):
        """Test cleanup with multiple expired entries of varying ages."""
        # Mock the timestamps dict, lock, and logger
        mock_timestamps = {}
        mock_logger = MagicMock()
        
        # Create the current time and times for entries
        now = datetime(2023, 1, 1, 12, 0, 0)  # Fixed time for test
        
        # Create multiple entries with different expiration times
        entries = [
            ("info:recent1", now - timedelta(minutes=30)),  # Recent - keep
            ("info:recent2", now - timedelta(minutes=59)),  # Recent - keep
            ("warning:expired1", now - timedelta(hours=1, minutes=1)),  # Expired - remove
            ("warning:expired2", now - timedelta(hours=2)),  # Expired - remove
            ("error:expired3", now - timedelta(days=1))  # Expired - remove
        ]
        
        # Populate the mock timestamps
        mock_timestamps.update(dict(entries))
        
        # Test that expired entries are cleaned up
        with patch('intentlayer_sdk.gateway._rate_limited_log._error_log_timestamps', mock_timestamps), \
             patch('intentlayer_sdk.gateway._rate_limited_log.TTLCACHE_AVAILABLE', False), \
             patch('intentlayer_sdk.gateway._rate_limited_log.datetime') as mock_datetime, \
             patch('intentlayer_sdk.gateway._rate_limited_log._error_log_timestamps_lock', MagicMock()):
            
            # Set the current time for the test
            mock_datetime.now.return_value = now
            
            # Call rate_limited_log with a new message
            rate_limited_log("new_message", "debug", 60, mock_logger)
            
            # Verify the logger was called
            mock_logger.debug.assert_called_once_with("new_message")
            
            # Check which entries remain and which were cleaned up
            for key, timestamp in entries:
                if now - timestamp < timedelta(hours=1):
                    # Recent entries should be kept
                    assert key in mock_timestamps, f"Recent entry {key} should be kept"
                else:
                    # Expired entries should be removed
                    assert key not in mock_timestamps, f"Expired entry {key} should be removed"
            
            # Verify the new entry was added
            assert "debug:new_message" in mock_timestamps