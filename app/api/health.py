"""Health check endpoints."""

from datetime import datetime, timezone

UTC = timezone.utc

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.storage.database import async_session_factory
from app.storage.redis import get_redis

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: datetime
    database: str
    redis: str
    version: str = "0.1.0"


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    ready: bool
    checks: dict[str, bool]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness and basic health check.

    Returns health status of the application and its dependencies.
    """
    # Check database
    db_status = "ok"
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    # Check Redis
    redis_status = "ok"
    try:
        redis = await get_redis()
        await redis.ping()
    except Exception:
        redis_status = "error"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        timestamp=datetime.now(UTC),
        database=db_status,
        redis=redis_status,
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    """Readiness check for load balancers.

    Returns detailed status of all dependencies.
    """
    checks: dict[str, bool] = {}

    # Check database
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # Check Redis
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    return ReadinessResponse(
        ready=all(checks.values()),
        checks=checks,
    )


@router.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """Simple liveness check.

    Just returns OK - used by orchestrators to check if process is alive.
    """
    return {"status": "ok"}
