"""Prometheus metrics endpoint.

Эндпоинт для сбора метрик Prometheus.
"""

from fastapi import APIRouter, Response

from app.config import settings

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns:
        Prometheus metrics in text format
    """
    if not settings.prometheus_enabled:
        return Response(
            content="Prometheus metrics disabled",
            status_code=503,
        )

    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        metrics_output = generate_latest()

        return Response(
            content=metrics_output,
            media_type=CONTENT_TYPE_LATEST,
        )
    except ImportError:
        return Response(
            content="prometheus_client not installed",
            status_code=503,
        )
