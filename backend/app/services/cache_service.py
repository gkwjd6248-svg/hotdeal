"""Redis caching service for API response caching.

This module provides a singleton Redis cache service with TTL support,
pattern-based invalidation, and health checking.
"""

from typing import Optional
import json
import structlog

from redis.asyncio import Redis, from_url
from redis.exceptions import RedisError

from app.config import settings

logger = structlog.get_logger(__name__)


class CacheService:
    """Async Redis cache service.

    Provides simple key-value caching with TTL, pattern matching,
    and graceful error handling. All methods are async.
    """

    def __init__(self, redis_url: str):
        """Initialize cache service.

        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379/0")
        """
        self.redis_url = redis_url
        self._redis: Optional[Redis] = None
        self.logger = logger.bind(service="cache_service")

    async def _get_redis(self) -> Redis:
        """Get or create Redis connection.

        Returns:
            Redis client instance

        Raises:
            RedisError: If connection fails
        """
        if self._redis is None:
            self._redis = from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self.logger.info("redis_connection_created", url=self.redis_url)

        return self._redis

    async def get(self, key: str) -> Optional[str]:
        """Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value as string, or None if not found or error
        """
        try:
            redis = await self._get_redis()
            value = await redis.get(key)

            if value:
                self.logger.debug("cache_hit", key=key)
            else:
                self.logger.debug("cache_miss", key=key)

            return value

        except RedisError as e:
            self.logger.error(
                "cache_get_failed",
                key=key,
                error=str(e),
                exc_info=True,
            )
            return None

    async def set(self, key: str, value: str, ttl: int = 300) -> bool:
        """Set a value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (string)
            ttl: Time-to-live in seconds (default: 300 = 5 minutes)

        Returns:
            True if successful, False on error
        """
        try:
            redis = await self._get_redis()
            await redis.set(key, value, ex=ttl)

            self.logger.debug(
                "cache_set",
                key=key,
                ttl=ttl,
                value_length=len(value),
            )

            return True

        except RedisError as e:
            self.logger.error(
                "cache_set_failed",
                key=key,
                error=str(e),
                exc_info=True,
            )
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was deleted, False if not found or error
        """
        try:
            redis = await self._get_redis()
            result = await redis.delete(key)

            self.logger.debug("cache_delete", key=key, deleted=bool(result))

            return bool(result)

        except RedisError as e:
            self.logger.error(
                "cache_delete_failed",
                key=key,
                error=str(e),
                exc_info=True,
            )
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.

        Args:
            pattern: Redis pattern (e.g., "deals:*", "user:123:*")

        Returns:
            Number of keys deleted, 0 on error
        """
        try:
            redis = await self._get_redis()

            # Get all keys matching pattern
            keys = []
            async for key in redis.scan_iter(match=pattern, count=100):
                keys.append(key)

            # Delete all matching keys
            if keys:
                deleted = await redis.delete(*keys)
            else:
                deleted = 0

            self.logger.info(
                "cache_pattern_delete",
                pattern=pattern,
                keys_deleted=deleted,
            )

            return deleted

        except RedisError as e:
            self.logger.error(
                "cache_pattern_delete_failed",
                pattern=pattern,
                error=str(e),
                exc_info=True,
            )
            return 0

    async def health_check(self) -> bool:
        """Check Redis connectivity.

        Returns:
            True if Redis is healthy, False otherwise
        """
        try:
            redis = await self._get_redis()
            await redis.ping()
            self.logger.debug("redis_health_check_ok")
            return True

        except Exception as e:
            self.logger.error(
                "redis_health_check_failed",
                error=str(e),
                exc_info=True,
            )
            return False

    async def close(self) -> None:
        """Close Redis connection.

        This should be called on application shutdown.
        """
        if self._redis:
            await self._redis.close()
            self._redis = None
            self.logger.info("redis_connection_closed")


# Global cache instance
_cache_instance: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get or create the global cache service instance.

    This is a singleton factory - the same instance is reused
    across the application.

    Returns:
        CacheService instance
    """
    global _cache_instance

    if _cache_instance is None:
        _cache_instance = CacheService(settings.REDIS_URL)
        logger.info("cache_service_initialized", redis_url=settings.REDIS_URL)

    return _cache_instance


async def get_cache() -> CacheService:
    """FastAPI dependency for cache service.

    Usage:
        @router.get("/endpoint")
        async def endpoint(cache: CacheService = Depends(get_cache)):
            ...

    Returns:
        CacheService instance
    """
    return get_cache_service()


async def invalidate_deals_cache() -> int:
    """Invalidate all deals-related cache entries.

    This should be called when deals are created or updated.

    Returns:
        Number of cache keys deleted
    """
    cache = get_cache_service()

    # Delete all deals-related cache keys
    patterns = [
        "deals:*",
        "deals_top:*",
        "trending:*",
    ]

    total_deleted = 0
    for pattern in patterns:
        deleted = await cache.delete_pattern(pattern)
        total_deleted += deleted

    logger.info("deals_cache_invalidated", keys_deleted=total_deleted)

    return total_deleted


def cache_key_for_deals(
    page: int = 1,
    limit: int = 20,
    category_slug: Optional[str] = None,
    shop_slug: Optional[str] = None,
    sort_by: str = "newest",
    min_discount: Optional[float] = None,
    deal_type: Optional[str] = None,
) -> str:
    """Generate cache key for deals endpoint.

    Args:
        page: Page number
        limit: Results per page
        category_slug: Category filter
        shop_slug: Shop filter
        sort_by: Sort method
        min_discount: Minimum discount filter
        deal_type: Deal type filter

    Returns:
        Cache key string
    """
    parts = [
        "deals",
        f"p{page}",
        f"l{limit}",
        f"s{sort_by}",
    ]

    if category_slug:
        parts.append(f"c{category_slug}")

    if shop_slug:
        parts.append(f"sh{shop_slug}")

    if min_discount is not None:
        parts.append(f"d{min_discount}")

    if deal_type:
        parts.append(f"t{deal_type}")

    return ":".join(parts)


def cache_key_for_top_deals(
    limit: int = 20,
    category_slug: Optional[str] = None,
) -> str:
    """Generate cache key for top deals endpoint.

    Args:
        limit: Number of deals
        category_slug: Optional category filter

    Returns:
        Cache key string
    """
    parts = ["deals_top", f"l{limit}"]

    if category_slug:
        parts.append(f"c{category_slug}")

    return ":".join(parts)
