"""
FABI+ Framework Caching System
High-performance caching for faster API responses
"""

import hashlib
import json
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional, Union

from ..conf.settings import settings


class CacheBackend:
    """Base cache backend interface"""

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        raise NotImplementedError

    def clear(self) -> bool:
        """Clear all cache"""
        raise NotImplementedError

    def keys(self) -> List[str]:
        """Get all cache keys"""
        raise NotImplementedError

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        raise NotImplementedError


class MemoryCache(CacheBackend):
    """In-memory cache backend"""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "clears": 0}

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key in self._cache:
            entry = self._cache[key]

            # Check if expired
            if entry["expires_at"] and datetime.now() > entry["expires_at"]:
                del self._cache[key]
                self._stats["misses"] += 1
                return None

            self._stats["hits"] += 1
            return entry["value"]

        self._stats["misses"] += 1
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        expires_at = None
        if ttl:
            expires_at = datetime.now() + timedelta(seconds=ttl)
        elif settings.CACHE_TTL:
            expires_at = datetime.now() + timedelta(seconds=settings.CACHE_TTL)

        self._cache[key] = {
            "value": value,
            "created_at": datetime.now(),
            "expires_at": expires_at,
        }

        self._stats["sets"] += 1
        return True

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        if key in self._cache:
            del self._cache[key]
            self._stats["deletes"] += 1
            return True
        return False

    def clear(self) -> bool:
        """Clear all cache"""
        self._cache.clear()
        self._stats["clears"] += 1
        return True

    def keys(self) -> List[str]:
        """Get all cache keys"""
        return list(self._cache.keys())

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            **self._stats,
            "total_keys": len(self._cache),
            "memory_usage": sum(len(str(entry)) for entry in self._cache.values()),
        }


class RedisCache(CacheBackend):
    """Redis cache backend"""

    def __init__(self):
        try:
            import redis

            self.redis = redis.from_url(
                settings.REDIS_URL or "redis://localhost:6379/0"
            )
            self.redis.ping()  # Test connection
        except ImportError:
            raise ImportError("Redis not installed. Install with: pip install redis")
        except Exception as e:
            raise ConnectionError(f"Could not connect to Redis: {e}")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = self.redis.get(f"fabiplus:{key}")
            if value:
                return json.loads(value)
            return None
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        try:
            ttl = ttl or settings.CACHE_TTL
            serialized = json.dumps(value, default=str)
            return self.redis.setex(f"fabiplus:{key}", ttl, serialized)
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            return bool(self.redis.delete(f"fabiplus:{key}"))
        except Exception:
            return False

    def clear(self) -> bool:
        """Clear all cache"""
        try:
            keys = self.redis.keys("fabiplus:*")
            if keys:
                return bool(self.redis.delete(*keys))
            return True
        except Exception:
            return False

    def keys(self) -> List[str]:
        """Get all cache keys"""
        try:
            keys = self.redis.keys("fabiplus:*")
            return [key.decode().replace("fabiplus:", "") for key in keys]
        except Exception:
            return []

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            info = self.redis.info()
            return {
                "total_keys": len(self.keys()),
                "memory_usage": info.get("used_memory", 0),
                "connected_clients": info.get("connected_clients", 0),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
            }
        except Exception:
            return {}


class CacheManager:
    """Cache manager with multiple backends"""

    def __init__(self):
        self._backend = None
        self._initialize_backend()

    def _initialize_backend(self):
        """Initialize cache backend based on settings"""
        backend_type = settings.CACHE_BACKEND.lower()

        if backend_type == "redis":
            try:
                self._backend = RedisCache()
            except (ImportError, ConnectionError):
                print("Warning: Redis cache failed, falling back to memory cache")
                self._backend = MemoryCache()
        else:
            self._backend = MemoryCache()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        return self._backend.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        return self._backend.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        return self._backend.delete(key)

    def clear(self) -> bool:
        """Clear all cache"""
        return self._backend.clear()

    def keys(self) -> List[str]:
        """Get all cache keys"""
        return self._backend.keys()

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self._backend.stats()


# Global cache instance
cache = CacheManager()


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments"""
    key_data = f"{args}:{sorted(kwargs.items())}"
    return hashlib.md5(key_data.encode()).hexdigest()


def cached(ttl: Optional[int] = None, key_prefix: str = ""):
    """Cache decorator for functions"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{key_prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"

            # Try to get from cache
            cached_result = cache.get(key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{key_prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"

            # Try to get from cache
            cached_result = cache.get(key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def cache_model_query(model_name: str, query_hash: str, ttl: Optional[int] = None):
    """Cache model query results"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"model:{model_name}:{query_hash}"

            cached_result = cache.get(key)
            if cached_result is not None:
                return cached_result

            result = func(*args, **kwargs)
            cache.set(key, result, ttl or 300)  # 5 minutes default
            return result

        return wrapper

    return decorator
