"""Optional Redis caching layer.

If REDIS_URL is not configured, all methods are no-ops.
"""
import json
from typing import Optional, Any
from app.config import settings
from app.utils.helpers import logger


class CacheService:
    """Async caching wrapper. No-op if Redis is not configured."""

    def __init__(self):
        self._redis = None
        self._enabled = bool(settings.REDIS_URL)

    async def _ensure_redis(self):
        """Lazy-init Redis connection."""
        if not self._enabled:
            return None
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                )
                # Test connection
                await self._redis.ping()
                logger.info("Redis connected successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed, caching disabled: {e}")
                self._enabled = False
                self._redis = None
        return self._redis

    async def get(self, key: str) -> Optional[dict]:
        """Retrieve cached value by key. Returns None on miss or if disabled."""
        if not self._enabled:
            return None
        r = await self._ensure_redis()
        if r is None:
            return None
        try:
            val = await r.get(key)
            if val:
                logger.debug(f"Cache hit: {key}")
                return json.loads(val)
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
        return None

    async def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Set a cache entry with optional TTL."""
        if not self._enabled:
            return
        r = await self._ensure_redis()
        if r is None:
            return
        if ttl is None:
            ttl = settings.CACHE_TTL_SECONDS
        try:
            await r.setex(key, ttl, json.dumps(value, ensure_ascii=False, default=str))
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
        except Exception as e:
            logger.warning(f"Cache set error: {e}")

    async def delete(self, key: str) -> None:
        """Remove a cache entry."""
        if not self._enabled:
            return
        r = await self._ensure_redis()
        if r is None:
            return
        try:
            await r.delete(key)
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


# Singleton instance
cache_service = CacheService()
