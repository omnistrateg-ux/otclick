"""Context manager for pipeline step tracing.

Позволяет автоматически отслеживать начало, успех и ошибки шагов.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from app.observability.pipeline_trace import (
    record_step_error,
    record_step_skipped,
    record_step_start,
    record_step_success,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def trace_step(
    lead_id: str,
    run_id: str,
    step_name: str,
    metadata: dict[str, Any] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Context manager for tracing a pipeline step.

    Usage:
        async with trace_step(lead_id, run_id, "enrich") as ctx:
            # do work
            ctx["contacts_found"] = 5  # add metadata

    On success: records step as completed
    On exception: records step as error with exception details

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID
        step_name: Name of the step
        metadata: Initial metadata

    Yields:
        Context dict for adding metadata during execution
    """
    ctx: dict[str, Any] = metadata.copy() if metadata else {}

    await record_step_start(lead_id, run_id, step_name, metadata)

    try:
        yield ctx
        # Success
        await record_step_success(lead_id, run_id, step_name, ctx)
    except Exception as e:
        # Error
        await record_step_error(lead_id, run_id, step_name, e, ctx)
        raise


async def trace_skip(
    lead_id: str,
    run_id: str,
    step_name: str,
    reason: str,
) -> None:
    """Record that a step was skipped.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID
        step_name: Name of the step
        reason: Reason for skipping
    """
    await record_step_skipped(lead_id, run_id, step_name, reason)


class TracedTask:
    """Helper class for tracing Celery task execution.

    Usage in Celery task:
        tracer = TracedTask(lead_id, run_id, "enrich")
        await tracer.start()
        try:
            # do work
            await tracer.success({"contacts_found": 5})
        except Exception as e:
            await tracer.error(e)
            raise
    """

    def __init__(
        self,
        lead_id: str,
        run_id: str,
        step_name: str,
        metadata: dict[str, Any] | None = None,
    ):
        self.lead_id = lead_id
        self.run_id = run_id
        self.step_name = step_name
        self.metadata = metadata or {}

    async def start(self) -> None:
        """Record step start."""
        await record_step_start(
            self.lead_id,
            self.run_id,
            self.step_name,
            self.metadata,
        )

    async def success(self, result_metadata: dict[str, Any] | None = None) -> None:
        """Record step success."""
        metadata = {**self.metadata, **(result_metadata or {})}
        await record_step_success(
            self.lead_id,
            self.run_id,
            self.step_name,
            metadata,
        )

    async def error(
        self,
        exc: Exception | str,
        error_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record step error."""
        metadata = {**self.metadata, **(error_metadata or {})}
        await record_step_error(
            self.lead_id,
            self.run_id,
            self.step_name,
            exc,
            metadata,
        )

    async def skip(self, reason: str) -> None:
        """Record step skip."""
        await record_step_skipped(
            self.lead_id,
            self.run_id,
            self.step_name,
            reason,
        )


def log_with_trace(
    logger: logging.Logger,
    level: int,
    message: str,
    lead_id: str | None = None,
    run_id: str | None = None,
    step: str | None = None,
    **extra: Any,
) -> None:
    """Log message with trace context.

    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        lead_id: Lead ID
        run_id: Pipeline run ID
        step: Step name
        **extra: Additional fields
    """
    parts = [message]

    if lead_id:
        parts.append(f"lead_id={lead_id}")
    if run_id:
        parts.append(f"run_id={run_id}")
    if step:
        parts.append(f"step={step}")

    for key, value in extra.items():
        parts.append(f"{key}={value}")

    logger.log(level, " | ".join(parts))
