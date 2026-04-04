"""Redis async client for caching, rate limits, and locks."""

from redis.asyncio import Redis

from app.config import settings

# Redis client instance
_redis: Redis | None = None


async def init_redis() -> Redis:
    """Initialize Redis connection.

    Call on application startup.
    """
    global _redis
    _redis = Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    # Test connection
    await _redis.ping()
    return _redis


async def get_redis() -> Redis:
    """Get Redis client instance.

    Use as FastAPI dependency:
        async def endpoint(redis: Redis = Depends(get_redis)):
            ...
    """
    if _redis is None:
        return await init_redis()
    return _redis


async def close_redis() -> None:
    """Close Redis connection.

    Call on application shutdown.
    """
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
