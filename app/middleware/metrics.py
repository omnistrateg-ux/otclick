"""Metrics middleware for HTTP request tracking.

Сбор метрик HTTP запросов для Prometheus.
"""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request and record metrics.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        start_time = time.perf_counter()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.perf_counter() - start_time

        # Get simplified endpoint for grouping
        endpoint = self._get_endpoint(request)

        # Record metrics
        try:
            from app.monitoring.metrics import get_metrics

            metrics = get_metrics()
            if metrics:
                metrics.record_http_request(
                    method=request.method,
                    endpoint=endpoint,
                    status=response.status_code,
                    duration=duration,
                )
        except Exception as e:
            logger.warning(f"Failed to record HTTP metrics: {e}")

        # Add timing header
        response.headers["X-Response-Time"] = f"{duration:.3f}s"

        return response

    def _get_endpoint(self, request: Request) -> str:
        """Get simplified endpoint for metrics grouping.

        Args:
            request: HTTP request

        Returns:
            Simplified endpoint path
        """
        path = request.url.path

        # Group parametrized paths
        parts = path.split("/")
        simplified = []

        for part in parts:
            # Replace UUIDs with placeholder
            if len(part) == 36 and part.count("-") == 4:
                simplified.append("{id}")
            # Replace numeric IDs
            elif part.isdigit():
                simplified.append("{id}")
            else:
                simplified.append(part)

        return "/".join(simplified)
