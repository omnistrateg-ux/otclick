"""Pipeline tracing for observability.

Сохраняет и извлекает информацию о выполнении каждого шага pipeline.
Хранение в Redis с TTL для автоматической очистки.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

UTC = timezone.utc

# TTL for trace data (7 days)
TRACE_TTL = 7 * 24 * 60 * 60


class StepStatus(str, Enum):
    """Status of a pipeline step."""

    STARTED = "started"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class PipelineStep:
    """A single step in the pipeline execution."""

    step_name: str
    status: StepStatus
    started_at: str
    finished_at: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    error_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "step_name": self.step_name,
            "status": self.status.value if isinstance(self.status, StepStatus) else self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "error_type": self.error_type,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineStep":
        """Create from dictionary."""
        return cls(
            step_name=data["step_name"],
            status=StepStatus(data["status"]) if data.get("status") else StepStatus.STARTED,
            started_at=data["started_at"],
            finished_at=data.get("finished_at"),
            duration_ms=data.get("duration_ms"),
            error=data.get("error"),
            error_type=data.get("error_type"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PipelineTrace:
    """Complete trace of a pipeline execution."""

    lead_id: str
    run_id: str
    started_at: str
    finished_at: str | None = None
    status: str = "running"  # running, completed, failed
    steps: list[PipelineStep] = field(default_factory=list)
    total_duration_ms: int | None = None
    error_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "lead_id": self.lead_id,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "total_duration_ms": self.total_duration_ms,
            "error_count": self.error_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineTrace":
        """Create from dictionary."""
        return cls(
            lead_id=data["lead_id"],
            run_id=data["run_id"],
            started_at=data["started_at"],
            finished_at=data.get("finished_at"),
            status=data.get("status", "running"),
            steps=[PipelineStep.from_dict(s) for s in data.get("steps", [])],
            total_duration_ms=data.get("total_duration_ms"),
            error_count=data.get("error_count", 0),
        )


def _get_trace_key(lead_id: str, run_id: str) -> str:
    """Get Redis key for trace."""
    return f"trace:{lead_id}:{run_id}"


def _get_lead_traces_key(lead_id: str) -> str:
    """Get Redis key for list of run_ids for a lead."""
    return f"trace_runs:{lead_id}"


def _now_iso() -> str:
    """Get current time in ISO format."""
    return datetime.now(UTC).isoformat()


async def record_step_start(
    lead_id: str,
    run_id: str,
    step_name: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record the start of a pipeline step.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID
        step_name: Name of the step (e.g., "enrich", "score", "outreach")
        metadata: Additional metadata to store
    """
    from app.storage.redis import get_redis

    redis = await get_redis()
    trace_key = _get_trace_key(lead_id, run_id)

    # Get or create trace
    trace_data = await redis.get(trace_key)

    if trace_data:
        trace = PipelineTrace.from_dict(json.loads(trace_data))
    else:
        trace = PipelineTrace(
            lead_id=lead_id,
            run_id=run_id,
            started_at=_now_iso(),
        )
        # Add run_id to lead's list of runs
        await redis.lpush(_get_lead_traces_key(lead_id), run_id)
        await redis.expire(_get_lead_traces_key(lead_id), TRACE_TTL)

    # Add step
    step = PipelineStep(
        step_name=step_name,
        status=StepStatus.STARTED,
        started_at=_now_iso(),
        metadata=metadata or {},
    )
    trace.steps.append(step)

    # Save trace
    await redis.set(trace_key, json.dumps(trace.to_dict()), ex=TRACE_TTL)

    logger.info(
        f"[TRACE] Step started | lead_id={lead_id} | run_id={run_id} | step={step_name}"
    )


async def record_step_success(
    lead_id: str,
    run_id: str,
    step_name: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record successful completion of a pipeline step.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID
        step_name: Name of the step
        metadata: Additional metadata to store
    """
    from app.storage.redis import get_redis

    redis = await get_redis()
    trace_key = _get_trace_key(lead_id, run_id)

    trace_data = await redis.get(trace_key)
    if not trace_data:
        logger.warning(f"[TRACE] No trace found for lead={lead_id} run={run_id}")
        return

    trace = PipelineTrace.from_dict(json.loads(trace_data))

    # Find and update the step
    now = _now_iso()
    for step in reversed(trace.steps):
        if step.step_name == step_name and step.status == StepStatus.STARTED:
            step.status = StepStatus.SUCCESS
            step.finished_at = now
            # Calculate duration
            started = datetime.fromisoformat(step.started_at)
            finished = datetime.fromisoformat(now)
            step.duration_ms = int((finished - started).total_seconds() * 1000)
            if metadata:
                step.metadata.update(metadata)
            break

    # Save trace
    await redis.set(trace_key, json.dumps(trace.to_dict()), ex=TRACE_TTL)

    logger.info(
        f"[TRACE] Step completed | lead_id={lead_id} | run_id={run_id} | "
        f"step={step_name} | status=success"
    )


async def record_step_error(
    lead_id: str,
    run_id: str,
    step_name: str,
    error: Exception | str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record error in a pipeline step.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID
        step_name: Name of the step
        error: Exception or error message
        metadata: Additional metadata to store
    """
    from app.storage.redis import get_redis

    redis = await get_redis()
    trace_key = _get_trace_key(lead_id, run_id)

    trace_data = await redis.get(trace_key)

    if trace_data:
        trace = PipelineTrace.from_dict(json.loads(trace_data))
    else:
        # Create trace if doesn't exist (error before start was recorded)
        trace = PipelineTrace(
            lead_id=lead_id,
            run_id=run_id,
            started_at=_now_iso(),
        )

    # Error details
    if isinstance(error, Exception):
        error_msg = str(error)
        error_type = type(error).__name__
    else:
        error_msg = error
        error_type = "Error"

    now = _now_iso()

    # Find and update the step or create new error step
    step_found = False
    for step in reversed(trace.steps):
        if step.step_name == step_name and step.status == StepStatus.STARTED:
            step.status = StepStatus.ERROR
            step.finished_at = now
            step.error = error_msg
            step.error_type = error_type
            started = datetime.fromisoformat(step.started_at)
            finished = datetime.fromisoformat(now)
            step.duration_ms = int((finished - started).total_seconds() * 1000)
            if metadata:
                step.metadata.update(metadata)
            step_found = True
            break

    if not step_found:
        # Create error step
        trace.steps.append(
            PipelineStep(
                step_name=step_name,
                status=StepStatus.ERROR,
                started_at=now,
                finished_at=now,
                duration_ms=0,
                error=error_msg,
                error_type=error_type,
                metadata=metadata or {},
            )
        )

    trace.error_count += 1
    trace.status = "failed"

    # Save trace
    await redis.set(trace_key, json.dumps(trace.to_dict()), ex=TRACE_TTL)

    # Also save to a separate errors index for quick lookup
    error_key = f"trace_errors:{lead_id}:{run_id}:{step_name}"
    error_data = {
        "lead_id": lead_id,
        "run_id": run_id,
        "step_name": step_name,
        "error": error_msg,
        "error_type": error_type,
        "timestamp": now,
    }
    await redis.set(error_key, json.dumps(error_data), ex=TRACE_TTL)

    logger.error(
        f"[TRACE] Step failed | lead_id={lead_id} | run_id={run_id} | "
        f"step={step_name} | error_type={error_type} | error={error_msg[:200]}"
    )


async def record_step_skipped(
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
    from app.storage.redis import get_redis

    redis = await get_redis()
    trace_key = _get_trace_key(lead_id, run_id)

    trace_data = await redis.get(trace_key)

    if trace_data:
        trace = PipelineTrace.from_dict(json.loads(trace_data))
    else:
        trace = PipelineTrace(
            lead_id=lead_id,
            run_id=run_id,
            started_at=_now_iso(),
        )

    now = _now_iso()
    trace.steps.append(
        PipelineStep(
            step_name=step_name,
            status=StepStatus.SKIPPED,
            started_at=now,
            finished_at=now,
            duration_ms=0,
            metadata={"skip_reason": reason},
        )
    )

    await redis.set(trace_key, json.dumps(trace.to_dict()), ex=TRACE_TTL)

    logger.info(
        f"[TRACE] Step skipped | lead_id={lead_id} | run_id={run_id} | "
        f"step={step_name} | reason={reason}"
    )


async def complete_pipeline_trace(
    lead_id: str,
    run_id: str,
    status: str = "completed",
) -> None:
    """Mark pipeline trace as completed.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID
        status: Final status (completed, failed)
    """
    from app.storage.redis import get_redis

    redis = await get_redis()
    trace_key = _get_trace_key(lead_id, run_id)

    trace_data = await redis.get(trace_key)
    if not trace_data:
        return

    trace = PipelineTrace.from_dict(json.loads(trace_data))
    trace.status = status
    trace.finished_at = _now_iso()

    # Calculate total duration
    started = datetime.fromisoformat(trace.started_at)
    finished = datetime.fromisoformat(trace.finished_at)
    trace.total_duration_ms = int((finished - started).total_seconds() * 1000)

    await redis.set(trace_key, json.dumps(trace.to_dict()), ex=TRACE_TTL)

    logger.info(
        f"[TRACE] Pipeline completed | lead_id={lead_id} | run_id={run_id} | "
        f"status={status} | duration_ms={trace.total_duration_ms} | errors={trace.error_count}"
    )


async def get_pipeline_trace(
    lead_id: str,
    run_id: str,
) -> PipelineTrace | None:
    """Get complete pipeline trace.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID

    Returns:
        PipelineTrace or None if not found
    """
    from app.storage.redis import get_redis

    redis = await get_redis()
    trace_key = _get_trace_key(lead_id, run_id)

    trace_data = await redis.get(trace_key)
    if not trace_data:
        return None

    return PipelineTrace.from_dict(json.loads(trace_data))


async def get_lead_traces(
    lead_id: str,
    limit: int = 10,
) -> list[PipelineTrace]:
    """Get all pipeline traces for a lead.

    Args:
        lead_id: Lead ID
        limit: Maximum number of traces to return

    Returns:
        List of PipelineTrace objects
    """
    from app.storage.redis import get_redis

    redis = await get_redis()

    # Get run IDs for this lead
    run_ids = await redis.lrange(_get_lead_traces_key(lead_id), 0, limit - 1)

    traces = []
    for run_id in run_ids:
        trace = await get_pipeline_trace(lead_id, run_id)
        if trace:
            traces.append(trace)

    return traces


async def get_pipeline_errors(
    lead_id: str,
    run_id: str,
) -> list[dict[str, Any]]:
    """Get all errors from a pipeline run.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID

    Returns:
        List of error dictionaries
    """
    from app.storage.redis import get_redis

    redis = await get_redis()

    errors = []
    pattern = f"trace_errors:{lead_id}:{run_id}:*"

    async for key in redis.scan_iter(pattern):
        error_data = await redis.get(key)
        if error_data:
            errors.append(json.loads(error_data))

    return sorted(errors, key=lambda e: e.get("timestamp", ""))
