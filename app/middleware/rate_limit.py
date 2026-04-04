"""Rate limiting middleware.

Ограничение частоты запросов по IP и API ключу.
"""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis.

    Limits requests per minute and per hour based on:
    - IP address (for unauthenticated requests)
    - API key (for authenticated requests)
    """

    def __init__(
        self,
        app: Callable,
        requests_per_minute: int | None = None,
        requests_per_hour: int | None = None,
    ) -> None:
        """Initialize rate limiter.

        Args:
            app: ASGI application
            requests_per_minute: Max requests per minute
            requests_per_hour: Max requests per hour
        """
        super().__init__(app)
        self.requests_per_minute = (
            requests_per_minute or settings.rate_limit_requests_per_minute
        )
        self.requests_per_hour = (
            requests_per_hour or settings.rate_limit_requests_per_hour
        )
        self._redis = None

    async def _get_redis(self):
        """Get Redis client lazily."""
        if self._redis is None:
            from app.storage.redis import get_redis

            self._redis = await get_redis()
        return self._redis

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting.

        Args:
            request: HTTP request

        Returns:
            Client identifier
        """
        # Check for API key
        api_key = request.headers.get(settings.api_key_header)
        if api_key:
            return f"api_key:{api_key[:8]}"

        # Fall back to IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return f"ip:{client_ip}"

    async def _check_rate_limit(
        self,
        client_id: str,
        limit: int,
        window_seconds: int,
        limit_type: str,
    ) -> tuple[bool, int, int]:
        """Check if request is within rate limit.

        Args:
            client_id: Client identifier
            limit: Max requests
            window_seconds: Time window in seconds
            limit_type: Type of limit (minute/hour)

        Returns:
            Tuple of (allowed, remaining, reset_at)
        """
        try:
            redis = await self._get_redis()
            key = f"rate_limit:{limit_type}:{client_id}"

            # Get current count
            current = await redis.get(key)
            current_count = int(current) if current else 0

            if current_count >= limit:
                ttl = await redis.ttl(key)
                return False, 0, int(time.time()) + ttl

            # Increment counter
            pipe = redis.pipeline()
            pipe.incr(key)
            if current_count == 0:
                pipe.expire(key, window_seconds)
            await pipe.execute()

            remaining = limit - current_count - 1
            return True, remaining, int(time.time()) + window_seconds

        except Exception as e:
            logger.warning(f"Rate limit check failed: {e}")
            # Allow request if Redis is unavailable
            return True, limit, int(time.time()) + window_seconds

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request through rate limiter.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        # Skip rate limiting if disabled
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # Skip health checks
        if request.url.path.startswith("/health") or request.url.path.startswith("/api/v1/health"):
            return await call_next(request)

        # Skip metrics endpoint
        if request.url.path == "/metrics":
            return await call_next(request)

        client_id = self._get_client_id(request)

        # Check per-minute limit
        allowed, remaining_minute, reset_minute = await self._check_rate_limit(
            client_id,
            self.requests_per_minute,
            60,
            "minute",
        )

        if not allowed:
            from app.monitoring.metrics import get_metrics

            metrics = get_metrics()
            if metrics:
                metrics.record_rate_limit_hit(request.url.path, "per_minute")

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": "Too many requests per minute",
                    "retry_after": reset_minute - int(time.time()),
                },
                headers={
                    "Retry-After": str(reset_minute - int(time.time())),
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_minute),
                },
            )

        # Check per-hour limit
        allowed, remaining_hour, reset_hour = await self._check_rate_limit(
            client_id,
            self.requests_per_hour,
            3600,
            "hour",
        )

        if not allowed:
            from app.monitoring.metrics import get_metrics

            metrics = get_metrics()
            if metrics:
                metrics.record_rate_limit_hit(request.url.path, "per_hour")

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": "Too many requests per hour",
                    "retry_after": reset_hour - int(time.time()),
                },
                headers={
                    "Retry-After": str(reset_hour - int(time.time())),
                    "X-RateLimit-Limit": str(self.requests_per_hour),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_hour),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(remaining_minute)
        response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(remaining_hour)

        return response
