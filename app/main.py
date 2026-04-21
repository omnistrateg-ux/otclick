"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.api.metrics import router as metrics_router
from app.config import settings
from app.storage.database import engine
from app.storage.redis import close_redis, init_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Initializes and cleans up resources on startup/shutdown.
    """
    # Initialize logging
    from app.monitoring.logging import setup_logging

    setup_logging()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    # Validate security configuration
    settings.validate_or_raise()

    # Initialize Sentry
    from app.monitoring.sentry import init_sentry

    if settings.sentry_dsn:
        init_sentry()

    # Initialize Prometheus metrics
    from app.monitoring.metrics import init_metrics

    if settings.prometheus_enabled:
        init_metrics()

    # Initialize Redis
    try:
        await init_redis()
        logger.info("Redis connected")
    except Exception as e:
        if settings.is_development:
            logger.warning(f"Redis not available: {e}")
        else:
            raise

    logger.info(f"Application started in {settings.environment} mode")

    yield

    # Shutdown
    logger.info("Shutting down application")
    await close_redis()
    await engine.dispose()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    # Determine OpenAPI URL based on environment
    openapi_url = "/openapi.json" if not settings.is_production else None

    app = FastAPI(
        title="Otclick Employer Acquisition Engine",
        description="AI-система поиска и квалификации работодателей для массового найма",
        version=settings.app_version,
        lifespan=lifespan,
        debug=settings.debug,
        openapi_url=openapi_url,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # Error handler middleware (must be first)
    from app.middleware.error_handler import ErrorHandlerMiddleware

    app.add_middleware(ErrorHandlerMiddleware)

    # Logging middleware
    from app.middleware.logging import LoggingMiddleware

    app.add_middleware(LoggingMiddleware)

    # Metrics middleware
    from app.middleware.metrics import MetricsMiddleware

    app.add_middleware(MetricsMiddleware)

    # Rate limiting middleware
    if settings.rate_limit_enabled:
        from app.middleware.rate_limit import RateLimitMiddleware

        app.add_middleware(RateLimitMiddleware)

    # CORS middleware
    # Fix security issue: can't use credentials with allow_origins=["*"]
    cors_origins = settings.cors_origins_list
    cors_credentials = settings.cors_allow_credentials
    if cors_origins == ["*"] and cors_credentials:
        logger.warning(
            "CORS: Disabling allow_credentials because allow_origins is '*'. "
            "Set specific origins to enable credentials."
        )
        cors_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(router)
    app.include_router(metrics_router)

    return app


# Application instance
app = create_app()
