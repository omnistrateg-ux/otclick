"""Observability API endpoints for pipeline tracing."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.observability import (
    PipelineTrace,
    analyze_failed_run,
    get_lead_traces,
    get_pipeline_errors,
    get_pipeline_trace,
    get_recoverable_runs,
    retry_pipeline_run,
    retry_step,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/observability", tags=["observability"])


class RetryRequest(BaseModel):
    """Request to retry a pipeline run."""

    force_steps: list[str] | None = None


class RetryStepRequest(BaseModel):
    """Request to retry a single step."""

    step_name: str


@router.get("/traces/{lead_id}/{run_id}")
async def get_trace(
    lead_id: str,
    run_id: str,
) -> dict[str, Any]:
    """Get complete pipeline trace for a lead and run.

    Returns timeline of all steps with status, duration, and errors.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID

    Returns:
        Pipeline trace with all steps
    """
    trace = await get_pipeline_trace(lead_id, run_id)

    if not trace:
        raise HTTPException(
            status_code=404,
            detail=f"Trace not found for lead={lead_id} run={run_id}",
        )

    logger.info(f"[API] Get trace | lead_id={lead_id} | run_id={run_id}")
    return trace.to_dict()


@router.get("/traces/{lead_id}")
async def get_lead_trace_history(
    lead_id: str,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    """Get all pipeline traces for a lead.

    Returns recent pipeline runs with their status and step summary.

    Args:
        lead_id: Lead ID
        limit: Maximum number of traces to return

    Returns:
        List of pipeline traces
    """
    traces = await get_lead_traces(lead_id, limit=limit)

    logger.info(f"[API] Get lead traces | lead_id={lead_id} | count={len(traces)}")
    return {
        "lead_id": lead_id,
        "total": len(traces),
        "traces": [t.to_dict() for t in traces],
    }


@router.get("/traces/{lead_id}/{run_id}/errors")
async def get_trace_errors(
    lead_id: str,
    run_id: str,
) -> dict[str, Any]:
    """Get all errors from a pipeline run.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID

    Returns:
        List of errors with step and timestamp
    """
    errors = await get_pipeline_errors(lead_id, run_id)

    logger.info(
        f"[API] Get trace errors | lead_id={lead_id} | run_id={run_id} | "
        f"errors={len(errors)}"
    )
    return {
        "lead_id": lead_id,
        "run_id": run_id,
        "error_count": len(errors),
        "errors": errors,
    }


@router.get("/traces/{lead_id}/{run_id}/timeline")
async def get_trace_timeline(
    lead_id: str,
    run_id: str,
) -> dict[str, Any]:
    """Get visual timeline of pipeline execution.

    Returns steps in chronological order with duration bars.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID

    Returns:
        Timeline visualization data
    """
    trace = await get_pipeline_trace(lead_id, run_id)

    if not trace:
        raise HTTPException(
            status_code=404,
            detail=f"Trace not found for lead={lead_id} run={run_id}",
        )

    # Build timeline
    timeline = []
    for step in trace.steps:
        timeline.append({
            "step": step.step_name,
            "status": step.status.value if hasattr(step.status, "value") else step.status,
            "started_at": step.started_at,
            "finished_at": step.finished_at,
            "duration_ms": step.duration_ms,
            "has_error": step.error is not None,
            "error_preview": step.error[:100] if step.error else None,
        })

    return {
        "lead_id": lead_id,
        "run_id": run_id,
        "pipeline_status": trace.status,
        "total_duration_ms": trace.total_duration_ms,
        "started_at": trace.started_at,
        "finished_at": trace.finished_at,
        "step_count": len(timeline),
        "error_count": trace.error_count,
        "timeline": timeline,
    }


# ============================================================================
# Recovery endpoints
# ============================================================================


@router.get("/recovery/{lead_id}")
async def get_recoverable_pipeline_runs(
    lead_id: str,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    """Get list of failed pipeline runs that can be recovered.

    Args:
        lead_id: Lead ID
        limit: Maximum runs to check

    Returns:
        List of recoverable runs with recovery plans
    """
    runs = await get_recoverable_runs(lead_id, limit=limit)

    logger.info(
        f"[API] Get recoverable runs | lead_id={lead_id} | "
        f"recoverable={len(runs)}"
    )

    return {
        "lead_id": lead_id,
        "recoverable_count": len(runs),
        "runs": runs,
    }


@router.get("/recovery/{lead_id}/{run_id}/analyze")
async def analyze_pipeline_run(
    lead_id: str,
    run_id: str,
) -> dict[str, Any]:
    """Analyze a failed pipeline run and get recovery plan.

    Returns which steps succeeded, failed, and need to be retried.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID

    Returns:
        Recovery plan with step analysis
    """
    plan = await analyze_failed_run(lead_id, run_id)

    logger.info(
        f"[API] Analyze run | lead_id={lead_id} | run_id={run_id} | "
        f"can_recover={plan.can_recover} | to_retry={plan.steps_to_retry}"
    )

    return {
        "lead_id": plan.lead_id,
        "run_id": plan.run_id,
        "new_run_id": plan.new_run_id,
        "can_recover": plan.can_recover,
        "reason": plan.reason,
        "steps_success": plan.steps_success,
        "steps_to_retry": plan.steps_to_retry,
        "steps_skipped": plan.steps_skipped,
    }


@router.post("/recovery/{lead_id}/{run_id}/retry")
async def retry_failed_pipeline_run(
    lead_id: str,
    run_id: str,
    request: RetryRequest | None = None,
) -> dict[str, Any]:
    """Retry a failed pipeline run.

    Only retries failed steps - successful steps are not repeated.

    Args:
        lead_id: Lead ID
        run_id: Failed pipeline run ID
        request: Optional request with force_steps

    Returns:
        Result with new run_id and steps being retried
    """
    force_steps = request.force_steps if request else None

    result = await retry_pipeline_run(lead_id, run_id, force_steps=force_steps)

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("reason", "Cannot retry this run"),
        )

    logger.info(
        f"[API] Retry run | lead_id={lead_id} | old_run_id={run_id} | "
        f"new_run_id={result.get('new_run_id')} | "
        f"steps={result.get('steps_retried')}"
    )

    return result


@router.post("/recovery/{lead_id}/retry-step")
async def retry_single_step(
    lead_id: str,
    request: RetryStepRequest,
) -> dict[str, Any]:
    """Retry a single pipeline step.

    Creates a new pipeline run with just this step.

    Args:
        lead_id: Lead ID
        request: Request with step_name

    Returns:
        Result with new run_id
    """
    result = await retry_step(
        lead_id=lead_id,
        run_id="",  # Will generate new
        step_name=request.step_name,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Cannot retry this step"),
        )

    logger.info(
        f"[API] Retry step | lead_id={lead_id} | step={request.step_name} | "
        f"new_run_id={result.get('new_run_id')}"
    )

    return result
