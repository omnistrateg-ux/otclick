"""Logging middleware for request/response logging.

Логирование HTTP запросов и ответов.
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request/response logging."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Log request and response.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Skip health check logging
        if request.url.path.startswith("/health"):
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response

        start_time = time.perf_counter()

        # Get client info
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        # Log request
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
                "client_ip": client_ip,
                "user_agent": request.headers.get("User-Agent", ""),
            },
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(
                f"Request failed with exception",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": int(duration * 1000),
                    "error": str(e),
                },
            )
            raise

        duration = time.perf_counter() - start_time

        # Log response
        log_level = logging.INFO if response.status_code < 400 else logging.WARNING

        logger.log(
            log_level,
            f"Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": int(duration * 1000),
            },
        )

        # Add request ID to response
        response.headers["X-Request-ID"] = request_id

        return response
