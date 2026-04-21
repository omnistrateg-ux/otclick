"""Pipeline recovery for failed runs.

Позволяет перезапускать failed/skipped шаги без повторения успешных.
"""

import logging
from dataclasses import dataclass
from typing import Any

from app.observability.pipeline_trace import (
    PipelineTrace,
    StepStatus,
    get_pipeline_trace,
    record_step_start,
)

logger = logging.getLogger(__name__)


# Pipeline step definitions with dependencies
PIPELINE_STEPS = {
    "enrich": {
        "task": "workers.discovery_tasks.enrich_lead",
        "depends_on": [],
        "required_status": "LEAD_FOUND",
    },
    "score": {
        "task": "workers.discovery_tasks.score_lead",
        "depends_on": ["enrich"],
        "required_status": "ENRICHED",
    },
    "qualify": {
        "task": "workers.discovery_tasks.qualify_lead",
        "depends_on": ["score"],
        "required_status": "SCORED",
    },
    "outreach": {
        "task": "workers.outreach_tasks.start_outreach",
        "depends_on": ["qualify"],
        "required_status": "EMAIL_READY",
    },
    "followup_1": {
        "task": "workers.outreach_tasks.send_followup",
        "depends_on": ["outreach"],
        "required_status": "OUTREACH_SENT",
        "extra_args": {"sequence_number": 1},
    },
    "followup_2": {
        "task": "workers.outreach_tasks.send_followup",
        "depends_on": ["followup_1"],
        "required_status": "IN_SEQUENCE",
        "extra_args": {"sequence_number": 2},
    },
    "followup_3": {
        "task": "workers.outreach_tasks.send_followup",
        "depends_on": ["followup_2"],
        "required_status": "IN_SEQUENCE",
        "extra_args": {"sequence_number": 3},
    },
    "analyze_reply": {
        "task": "workers.analysis_tasks.analyze_reply",
        "depends_on": [],
        "required_status": "REPLY_RECEIVED",
    },
    "handle_qualification": {
        "task": "workers.outreach_tasks.handle_qualification_result",
        "depends_on": ["analyze_reply"],
        "required_status": "REPLY_RECEIVED",
    },
    "handoff": {
        "task": "workers.outreach_tasks.create_handoff",
        "depends_on": ["handle_qualification"],
        "required_status": "INTEREST_DETECTED",
    },
}


@dataclass
class RecoveryPlan:
    """Plan for recovering a failed pipeline run."""

    lead_id: str
    run_id: str
    new_run_id: str
    steps_to_retry: list[str]
    steps_skipped: list[str]
    steps_success: list[str]
    can_recover: bool
    reason: str | None = None


async def analyze_failed_run(
    lead_id: str,
    run_id: str,
) -> RecoveryPlan:
    """Analyze a failed pipeline run and create recovery plan.

    Args:
        lead_id: Lead ID
        run_id: Failed pipeline run ID

    Returns:
        RecoveryPlan with steps to retry
    """
    from app.orchestrator.engine import generate_pipeline_run_id

    trace = await get_pipeline_trace(lead_id, run_id)

    if not trace:
        return RecoveryPlan(
            lead_id=lead_id,
            run_id=run_id,
            new_run_id="",
            steps_to_retry=[],
            steps_skipped=[],
            steps_success=[],
            can_recover=False,
            reason="Trace not found",
        )

    # Categorize steps
    steps_success = []
    steps_failed = []
    steps_skipped = []

    for step in trace.steps:
        status = step.status if isinstance(step.status, StepStatus) else StepStatus(step.status)

        if status == StepStatus.SUCCESS:
            steps_success.append(step.step_name)
        elif status == StepStatus.ERROR:
            steps_failed.append(step.step_name)
        elif status == StepStatus.SKIPPED:
            # Only retry skipped if it was due to lock or transient issue
            skip_reason = step.metadata.get("skip_reason", "")
            if skip_reason in ["lock_not_acquired", "retry"]:
                steps_failed.append(step.step_name)
            else:
                steps_skipped.append(step.step_name)

    # Determine steps to retry - failed steps and their dependents
    steps_to_retry = []
    for step_name in steps_failed:
        if step_name not in steps_to_retry:
            steps_to_retry.append(step_name)

        # Also add steps that depend on failed steps
        for name, config in PIPELINE_STEPS.items():
            if step_name in config.get("depends_on", []):
                if name not in steps_to_retry and name not in steps_success:
                    steps_to_retry.append(name)

    # Check if recovery is possible
    can_recover = len(steps_to_retry) > 0

    new_run_id = generate_pipeline_run_id() if can_recover else ""

    logger.info(
        f"[RECOVERY] Analyzed run | lead_id={lead_id} | run_id={run_id} | "
        f"success={len(steps_success)} | failed={len(steps_failed)} | "
        f"to_retry={len(steps_to_retry)} | can_recover={can_recover}"
    )

    return RecoveryPlan(
        lead_id=lead_id,
        run_id=run_id,
        new_run_id=new_run_id,
        steps_to_retry=steps_to_retry,
        steps_skipped=steps_skipped,
        steps_success=steps_success,
        can_recover=can_recover,
        reason=None if can_recover else "No failed steps to retry",
    )


async def retry_pipeline_run(
    lead_id: str,
    run_id: str,
    force_steps: list[str] | None = None,
) -> dict[str, Any]:
    """Retry a failed pipeline run.

    Only retries failed/skipped steps, not successful ones.

    Args:
        lead_id: Lead ID
        run_id: Failed pipeline run ID
        force_steps: Optional list of specific steps to retry

    Returns:
        Dict with new run_id and tasks started
    """
    from app.storage.redis import invalidate_pipeline_run

    # Analyze the failed run
    plan = await analyze_failed_run(lead_id, run_id)

    if not plan.can_recover and not force_steps:
        logger.warning(
            f"[RECOVERY] Cannot recover run | lead_id={lead_id} | "
            f"run_id={run_id} | reason={plan.reason}"
        )
        return {
            "success": False,
            "lead_id": lead_id,
            "run_id": run_id,
            "reason": plan.reason,
        }

    # Use forced steps or plan steps
    steps_to_run = force_steps if force_steps else plan.steps_to_retry

    if not steps_to_run:
        return {
            "success": False,
            "lead_id": lead_id,
            "run_id": run_id,
            "reason": "No steps to retry",
        }

    new_run_id = plan.new_run_id

    # Invalidate old idempotency keys for steps we're retrying
    for step in steps_to_run:
        await invalidate_pipeline_run(lead_id, run_id)

    # Start the first step that needs retry
    tasks_started = []

    for step_name in steps_to_run:
        step_config = PIPELINE_STEPS.get(step_name)
        if not step_config:
            logger.warning(f"[RECOVERY] Unknown step: {step_name}")
            continue

        # Check if dependencies are satisfied
        deps = step_config.get("depends_on", [])
        deps_satisfied = all(
            dep in plan.steps_success or dep in tasks_started
            for dep in deps
        )

        if not deps_satisfied:
            logger.info(
                f"[RECOVERY] Step {step_name} waiting for dependencies: {deps}"
            )
            continue

        # Start the task
        task_result = await _start_recovery_task(
            lead_id=lead_id,
            run_id=new_run_id,
            step_name=step_name,
            step_config=step_config,
        )

        if task_result:
            tasks_started.append(step_name)

    logger.info(
        f"[RECOVERY] Started recovery | lead_id={lead_id} | "
        f"old_run_id={run_id} | new_run_id={new_run_id} | "
        f"tasks_started={tasks_started}"
    )

    return {
        "success": True,
        "lead_id": lead_id,
        "old_run_id": run_id,
        "new_run_id": new_run_id,
        "steps_retried": tasks_started,
        "steps_skipped": plan.steps_success,
    }


async def _start_recovery_task(
    lead_id: str,
    run_id: str,
    step_name: str,
    step_config: dict[str, Any],
) -> bool:
    """Start a recovery task for a specific step.

    Args:
        lead_id: Lead ID
        run_id: New pipeline run ID
        step_name: Step name to start
        step_config: Step configuration

    Returns:
        True if task was started
    """
    from celery import current_app

    task_name = step_config["task"]
    extra_args = step_config.get("extra_args", {})

    try:
        # Get the task
        task = current_app.tasks.get(task_name)
        if not task:
            logger.error(f"[RECOVERY] Task not found: {task_name}")
            return False

        # Build kwargs
        kwargs = {
            "lead_id": lead_id,
            "pipeline_run_id": run_id,
            **extra_args,
        }

        # Start task
        task.delay(**kwargs)

        logger.info(
            f"[RECOVERY] Started task | step={step_name} | "
            f"task={task_name} | lead_id={lead_id} | run_id={run_id}"
        )

        return True

    except Exception as e:
        logger.error(
            f"[RECOVERY] Failed to start task | step={step_name} | "
            f"task={task_name} | error={e}"
        )
        return False


async def retry_step(
    lead_id: str,
    run_id: str,
    step_name: str,
) -> dict[str, Any]:
    """Retry a single step.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID (will create new one)
        step_name: Step to retry

    Returns:
        Result dict
    """
    from app.orchestrator.engine import generate_pipeline_run_id

    step_config = PIPELINE_STEPS.get(step_name)
    if not step_config:
        return {
            "success": False,
            "error": f"Unknown step: {step_name}",
        }

    new_run_id = generate_pipeline_run_id()

    success = await _start_recovery_task(
        lead_id=lead_id,
        run_id=new_run_id,
        step_name=step_name,
        step_config=step_config,
    )

    return {
        "success": success,
        "lead_id": lead_id,
        "new_run_id": new_run_id,
        "step": step_name,
    }


async def get_recoverable_runs(
    lead_id: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Get list of failed runs that can be recovered.

    Args:
        lead_id: Lead ID
        limit: Max runs to check

    Returns:
        List of recoverable runs with recovery plans
    """
    from app.observability.pipeline_trace import get_lead_traces

    traces = await get_lead_traces(lead_id, limit=limit)

    recoverable = []
    for trace in traces:
        if trace.status == "failed" or trace.error_count > 0:
            plan = await analyze_failed_run(lead_id, trace.run_id)
            if plan.can_recover:
                recoverable.append({
                    "run_id": trace.run_id,
                    "started_at": trace.started_at,
                    "error_count": trace.error_count,
                    "steps_to_retry": plan.steps_to_retry,
                    "steps_success": plan.steps_success,
                })

    return recoverable
