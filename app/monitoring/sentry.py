"""Sentry integration for error tracking.

Интеграция с Sentry для отслеживания ошибок и производительности.
"""

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_sentry_initialized = False


def init_sentry() -> bool:
    """Initialize Sentry SDK.

    Returns:
        True if Sentry was initialized successfully
    """
    global _sentry_initialized

    if _sentry_initialized:
        return True

    if not settings.sentry_dsn:
        logger.info("Sentry DSN not configured, skipping initialization")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.httpx import HttpxIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            release=f"{settings.app_name}@{settings.app_version}",
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry_profiles_sample_rate,
            send_default_pii=False,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                CeleryIntegration(),
                SqlalchemyIntegration(),
                RedisIntegration(),
                HttpxIntegration(),
                AsyncioIntegration(),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR,
                ),
            ],
            before_send=_before_send,
        )

        _sentry_initialized = True
        logger.info(f"Sentry initialized for environment: {settings.environment}")
        return True

    except ImportError:
        logger.warning("sentry-sdk not installed, skipping Sentry initialization")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")
        return False


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Filter events before sending to Sentry.

    Args:
        event: Sentry event
        hint: Additional context

    Returns:
        Event to send or None to drop
    """
    # Filter out health check errors
    if "request" in event:
        url = event["request"].get("url", "")
        if "/health" in url:
            return None

    # Don't send PII
    if "user" in event:
        user = event["user"]
        if "email" in user:
            user["email"] = "[REDACTED]"
        if "ip_address" in user:
            user["ip_address"] = "[REDACTED]"

    return event


def capture_exception(error: Exception, **extra: Any) -> str | None:
    """Capture exception to Sentry.

    Args:
        error: Exception to capture
        **extra: Additional context

    Returns:
        Sentry event ID or None
    """
    if not _sentry_initialized:
        logger.exception(f"Error (Sentry not initialized): {error}")
        return None

    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in extra.items():
                scope.set_extra(key, value)
            return sentry_sdk.capture_exception(error)
    except Exception as e:
        logger.error(f"Failed to capture exception to Sentry: {e}")
        return None


def capture_message(message: str, level: str = "info", **extra: Any) -> str | None:
    """Capture message to Sentry.

    Args:
        message: Message to capture
        level: Log level (info, warning, error)
        **extra: Additional context

    Returns:
        Sentry event ID or None
    """
    if not _sentry_initialized:
        logger.log(
            getattr(logging, level.upper(), logging.INFO),
            f"Message (Sentry not initialized): {message}",
        )
        return None

    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in extra.items():
                scope.set_extra(key, value)
            return sentry_sdk.capture_message(message, level=level)
    except Exception as e:
        logger.error(f"Failed to capture message to Sentry: {e}")
        return None


def set_user(user_id: str, **extra: Any) -> None:
    """Set user context for Sentry.

    Args:
        user_id: User identifier
        **extra: Additional user data
    """
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        sentry_sdk.set_user({"id": user_id, **extra})
    except Exception as e:
        logger.error(f"Failed to set Sentry user: {e}")


def set_tag(key: str, value: str) -> None:
    """Set a tag for Sentry events.

    Args:
        key: Tag key
        value: Tag value
    """
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        sentry_sdk.set_tag(key, value)
    except Exception as e:
        logger.error(f"Failed to set Sentry tag: {e}")


def start_transaction(name: str, op: str = "task") -> Any:
    """Start a Sentry transaction for performance monitoring.

    Args:
        name: Transaction name
        op: Operation type

    Returns:
        Transaction context manager or None
    """
    if not _sentry_initialized:
        return None

    try:
        import sentry_sdk

        return sentry_sdk.start_transaction(name=name, op=op)
    except Exception as e:
        logger.error(f"Failed to start Sentry transaction: {e}")
        return None
