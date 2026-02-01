"""
TTL Cache utilities for MCP tools.

Provides caching decorators with time-based expiration for:
- Web page visit results
- Memory retrieval results
- Search results
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, ParamSpec

from backend.core.logging import get_logger

_log = get_logger("cache")

P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class TTLCache:
    """
    Thread-safe TTL cache with LRU eviction.

    Features:
    - Time-based expiration
    - Maximum size limit with LRU eviction
    - Statistics tracking
    """

    def __init__(
        self,
        maxsize: int = 100,
        ttl_seconds: int = 300,
        name: str = "default"
    ):
        self.maxsize = maxsize
        self.ttl = ttl_seconds
        self.name = name
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = asyncio.Lock()
        self.stats = CacheStats()

    async def get(self, key: str) -> tuple[bool, Optional[Any]]:
        """
        Get value from cache.

        Returns:
            Tuple of (hit: bool, value: Optional[Any])
        """
        async with self._lock:
            if key not in self._cache:
                self.stats.misses += 1
                return False, None

            value, timestamp = self._cache[key]

            # Check TTL
            if time.time() - timestamp >= self.ttl:
                del self._cache[key]
                self.stats.misses += 1
                self.stats.evictions += 1
                return False, None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self.stats.hits += 1
            return True, value

    async def set(self, key: str, value: Any) -> None:
        """Store value in cache."""
        async with self._lock:
            # Evict oldest if at capacity
            while len(self._cache) >= self.maxsize:
                self._cache.popitem(last=False)
                self.stats.evictions += 1

            self._cache[key] = (value, time.time())

    async def invalidate(self, key: str) -> bool:
        """Remove specific key from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> int:
        """Clear all cache entries. Returns count of cleared items."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "name": self.name,
            "size": len(self._cache),
            "maxsize": self.maxsize,
            "ttl_seconds": self.ttl,
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "evictions": self.stats.evictions,
            "hit_rate": f"{self.stats.hit_rate:.1%}",
        }


# Global cache registry
_caches: dict[str, TTLCache] = {}


def get_cache(name: str, maxsize: int = 100, ttl_seconds: int = 300) -> TTLCache:
    """Get or create a named cache instance."""
    if name not in _caches:
        _caches[name] = TTLCache(maxsize=maxsize, ttl_seconds=ttl_seconds, name=name)
    return _caches[name]


def get_all_cache_stats() -> dict[str, dict]:
    """Get statistics for all caches."""
    return {name: cache.get_stats() for name, cache in _caches.items()}


def cached(
    cache_name: str,
    ttl: int = 300,
    maxsize: int = 100,
    key_builder: Optional[Callable[..., str]] = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Caching decorator for async functions.

    Args:
        cache_name: Name of the cache (for grouping and stats)
        ttl: Time-to-live in seconds (default: 300 = 5 minutes)
        maxsize: Maximum cache size (default: 100)
        key_builder: Optional function to build cache key from args/kwargs

    Example:
        @cached("webpage", ttl=3600)
        async def visit_webpage(url: str) -> str:
            ...

        @cached("memory", ttl=300, key_builder=lambda q, **kw: f"query:{q}")
        async def retrieve_context(query: str, max_results: int = 10) -> str:
            ...
    """
    cache = get_cache(cache_name, maxsize=maxsize, ttl_seconds=ttl)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Build cache key
            if key_builder:
                try:
                    cache_key = key_builder(*args, **kwargs)
                except Exception:
                    cache_key = _default_key_builder(args, kwargs)
            else:
                cache_key = _default_key_builder(args, kwargs)

            # Check cache
            hit, cached_value = await cache.get(cache_key)
            if hit:
                _log.debug("cache hit", cache=cache_name, key=cache_key[:50])
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Store result
            await cache.set(cache_key, result)
            _log.debug("cache miss", cache=cache_name, key=cache_key[:50])

            return result

        # Attach cache reference for manual operations
        wrapper._cache = cache
        wrapper._cache_name = cache_name

        return wrapper

    return decorator


def _default_key_builder(args: tuple, kwargs: dict) -> str:
    """Build cache key from function arguments."""
    key_data = str((args, sorted(kwargs.items())))
    return hashlib.md5(key_data.encode()).hexdigest()


# Convenience function for manual cache operations
async def invalidate_cache(cache_name: str, key: Optional[str] = None) -> bool:
    """
    Invalidate cache entries.

    Args:
        cache_name: Name of the cache
        key: Specific key to invalidate (if None, clears entire cache)

    Returns:
        True if any entries were invalidated
    """
    if cache_name not in _caches:
        return False

    cache = _caches[cache_name]
    if key:
        return await cache.invalidate(key)
    else:
        count = await cache.clear()
        return count > 0
