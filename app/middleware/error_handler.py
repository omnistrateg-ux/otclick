"""Error handler middleware.

Централизованная обработка ошибок с интеграцией Sentry.
"""

import logging
import traceback
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for centralized error handling."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Handle errors during request processing.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        try:
            return await call_next(request)

        except Exception as e:
            return await self._handle_exception(request, e)

    async def _handle_exception(
        self,
        request: Request,
        exc: Exception,
    ) -> Response:
        """Handle exception and return appropriate response.

        Args:
            request: HTTP request
            exc: Exception that occurred

        Returns:
            JSON error response
        """
        # Get request ID if available
        request_id = getattr(request.state, "request_id", "unknown")

        # Log error
        logger.exception(
            f"Unhandled exception",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )

        # Send to Sentry
        try:
            from app.monitoring.sentry import capture_exception

            capture_exception(
                exc,
                request_id=request_id,
                method=request.method,
                path=request.url.path,
            )
        except Exception:
            pass

        # Record error metric
        try:
            from app.monitoring.metrics import get_metrics

            metrics = get_metrics()
            if metrics:
                metrics.record_error(type(exc).__name__, "http")
        except Exception:
            pass

        # Determine status code
        status_code = 500

        # Build error response
        error_response = {
            "error": "Internal server error",
            "request_id": request_id,
        }

        # Add details in development
        if settings.debug or settings.is_development:
            error_response["detail"] = str(exc)
            error_response["traceback"] = traceback.format_exc()
            error_response["error_type"] = type(exc).__name__

        return JSONResponse(
            status_code=status_code,
            content=error_response,
        )
