"""
Simple in-memory cache to reduce database queries
"""
import time
from typing import Any, Optional
from functools import lru_cache

# Simple dict-based cache with TTL
_cache = {}
_cache_ttl = {}

def get_cached(key: str, ttl: int = 300) -> Optional[Any]:
    """Get cached value if not expired"""
    if key not in _cache:
        return None
    if key in _cache_ttl:
        if time.time() > _cache_ttl[key]:
            # Expired
            del _cache[key]
            del _cache_ttl[key]
            return None
    return _cache[key]

def set_cached(key: str, value: Any, ttl: int = 300):
    """Set cached value with TTL in seconds"""
    _cache[key] = value
    _cache_ttl[key] = time.time() + ttl

def invalidate_cache(key: str):
    """Invalidate a specific cache key"""
    if key in _cache:
        del _cache[key]
    if key in _cache_ttl:
        del _cache_ttl[key]

def clear_cache():
    """Clear all cache"""
    _cache.clear()
    _cache_ttl.clear()

# Cache for frequently accessed settings
@lru_cache(maxsize=128)
def get_bot_active_status() -> str:
    """Cached bot active status - invalidate on change"""
    from .db import query_db
    cur = query_db("SELECT value FROM settings WHERE key='bot_active'", one=True)
    return (cur or {}).get('value') or '1'

def invalidate_bot_active_cache():
    """Call this when bot_active setting changes"""
    get_bot_active_status.cache_clear()
