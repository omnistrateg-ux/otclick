"""Redis async client for caching, rate limits, and locks."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

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


@asynccontextmanager
async def distributed_lock(
    key: str,
    timeout: int = 300,
    retry_interval: float = 0.1,
    max_retries: int = 50,
) -> AsyncGenerator[bool, None]:
    """Acquire distributed lock using Redis.

    Usage:
        async with distributed_lock(f"lead:{lead_id}") as acquired:
            if acquired:
                # do work
            else:
                # lock not acquired

    Args:
        key: Lock key
        timeout: Lock expiration in seconds
        retry_interval: Seconds between retries
        max_retries: Max retry attempts

    Yields:
        True if lock acquired, False otherwise
    """
    redis = await get_redis()
    lock_key = f"lock:{key}"
    lock_value = f"{asyncio.current_task().get_name()}:{id(asyncio.current_task())}"

    acquired = False
    for _ in range(max_retries):
        # Try to acquire lock with NX (set if not exists) and EX (expiration)
        acquired = await redis.set(lock_key, lock_value, nx=True, ex=timeout)
        if acquired:
            break
        await asyncio.sleep(retry_interval)

    try:
        yield acquired
    finally:
        if acquired:
            # Only release if we still own the lock
            current_value = await redis.get(lock_key)
            if current_value == lock_value:
                await redis.delete(lock_key)


async def check_idempotency(
    operation: str,
    key: str,
    ttl: int = 3600,
) -> bool:
    """Check if operation was already processed (idempotency check).

    Args:
        operation: Operation name (e.g., "enrich_lead")
        key: Unique key for the operation (e.g., lead_id)
        ttl: Time to live in seconds

    Returns:
        True if this is a duplicate (already processed), False if new
    """
    redis = await get_redis()
    idempotency_key = f"idem:{operation}:{key}"

    # Try to set with NX - returns None if already exists
    result = await redis.set(idempotency_key, "1", nx=True, ex=ttl)
    return result is None  # True = duplicate, False = new


async def mark_processed(
    operation: str,
    key: str,
    ttl: int = 3600,
) -> None:
    """Mark operation as processed for idempotency.

    Args:
        operation: Operation name
        key: Unique key
        ttl: Time to live in seconds
    """
    redis = await get_redis()
    idempotency_key = f"idem:{operation}:{key}"
    await redis.set(idempotency_key, "1", ex=ttl)


async def check_pipeline_step(
    lead_id: str,
    step: str,
    run_id: str,
    ttl: int = 86400,
) -> bool:
    """Check if pipeline step was already executed for this run.

    Protects against duplicate processing within same pipeline run.

    Args:
        lead_id: Lead ID
        step: Pipeline step name (e.g., "enrich", "score", "outreach")
        run_id: Unique pipeline run identifier
        ttl: TTL in seconds (default 24h)

    Returns:
        True if already processed (duplicate), False if new
    """
    redis = await get_redis()
    key = f"pipeline:{lead_id}:{step}:{run_id}"

    # Try to set with NX - returns None if already exists
    result = await redis.set(key, "1", nx=True, ex=ttl)
    return result is None  # True = duplicate


async def mark_pipeline_step(
    lead_id: str,
    step: str,
    run_id: str,
    ttl: int = 86400,
) -> None:
    """Mark pipeline step as completed.

    Args:
        lead_id: Lead ID
        step: Pipeline step name
        run_id: Pipeline run ID
        ttl: TTL in seconds
    """
    redis = await get_redis()
    key = f"pipeline:{lead_id}:{step}:{run_id}"
    await redis.set(key, "1", ex=ttl)


async def get_pipeline_run_status(
    lead_id: str,
    run_id: str,
) -> dict[str, bool]:
    """Get status of all steps in a pipeline run.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID

    Returns:
        Dict of step_name -> completed
    """
    redis = await get_redis()
    pattern = f"pipeline:{lead_id}:*:{run_id}"

    steps = {}
    async for key in redis.scan_iter(pattern):
        # Extract step name from key
        parts = key.split(":")
        if len(parts) >= 4:
            step = parts[2]
            steps[step] = True

    return steps


async def invalidate_pipeline_run(
    lead_id: str,
    run_id: str,
) -> int:
    """Invalidate all steps of a pipeline run (for retry).

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID

    Returns:
        Number of keys deleted
    """
    redis = await get_redis()
    pattern = f"pipeline:{lead_id}:*:{run_id}"

    deleted = 0
    async for key in redis.scan_iter(pattern):
        await redis.delete(key)
        deleted += 1

    return deleted
