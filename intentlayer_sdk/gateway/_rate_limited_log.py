"""
Thread-safe rate-limited logging utilities.

This module provides thread-safe rate-limited logging functionality to prevent
log spam while still maintaining visibility into important events.
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable

# Import TTLCache for rate limiting if available
try:
    from cachetools import TTLCache
    TTLCACHE_AVAILABLE = True
except ImportError:
    TTLCACHE_AVAILABLE = False

# Configure logger
logger = logging.getLogger(__name__)

# Global rate limiting cache with thread safety
if TTLCACHE_AVAILABLE:
    # Use TTLCache with a maximum of 100 entries and 1 hour TTL
    _error_log_cache = TTLCache(maxsize=100, ttl=3600)
    _error_log_cache_lock = threading.RLock()  # Thread safety for the cache
else:
    # Fallback to simple dict if TTLCache is not available
    logger.info("cachetools.TTLCache not available, using simple dict for rate limiting")
    _error_log_timestamps: Dict[str, datetime] = {}
    _error_log_timestamps_lock = threading.RLock()  # Thread safety for the dict


def rate_limited_log(
    message: str,
    level: str = "warning",
    interval: int = 60,
    logger_instance: Optional[logging.Logger] = None
) -> None:
    """
    Log a message with rate limiting, in a thread-safe manner.
    
    Args:
        message: Message to log
        level: Log level (debug, info, warning, error, critical)
        interval: Minimum interval between logs in seconds
        logger_instance: Logger to use (defaults to module logger)
    """
    # Use the provided logger or default to module logger
    log_instance = logger_instance or logger
    
    # Get the appropriate log method
    log_method = getattr(log_instance, level.lower(), log_instance.warning)
    
    # Create a key based on the message and level
    key = f"{level}:{message}"
    
    if TTLCACHE_AVAILABLE:
        # Thread-safe check and update with TTLCache
        with _error_log_cache_lock:
            # If the key is in the cache, we've logged it recently
            if key in _error_log_cache:
                return  # Skip logging
            
            # Log the message and update the cache
            log_method(message)
            _error_log_cache[key] = True  # Value doesn't matter, TTL handles expiry
    else:
        # Thread-safe check and update with timestamp dict
        with _error_log_timestamps_lock:
            now = datetime.now()
            
            # Check if we've logged this recently
            last_time = _error_log_timestamps.get(key)
            if last_time and (now - last_time < timedelta(seconds=interval)):
                return  # Skip logging
            
            # Log the message and update timestamp
            log_method(message)
            _error_log_timestamps[key] = now
            
            # Clean up old entries (simple TTL cleanup)
            expired_cutoff = now - timedelta(seconds=3600)  # 1 hour TTL
            expired_keys = [k for k, v in _error_log_timestamps.items() if v < expired_cutoff]
            for k in expired_keys:
                _error_log_timestamps.pop(k, None)