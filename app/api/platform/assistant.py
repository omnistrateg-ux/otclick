"""Ops assistant API endpoints."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.ops_assistant import (
    OpsAssistantService,
    TriageSeverity,
    TriageCategory,
    RemediationStatus,
    RunbookSafetyLevel,
    EscalationLevel,
    HandoffStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


# Request models
class TriageIncidentRequest(BaseModel):
    """Triage incident request."""

    incident_id: str
    title: str
    description: str
    metadata: dict[str, Any] | None = None


class GeneratePlanRequest(BaseModel):
    """Generate remediation plan request."""

    incident_id: str
    created_by: str = "ops_assistant"


class AdvancePlanRequest(BaseModel):
    """Advance plan step request."""

    actor: str


class ExecuteRunbookRequest(BaseModel):
    """Execute runbook request."""

    executed_by: str
    parameters: dict[str, Any] | None = None
    approval_id: str | None = None


class CreateNoteRequest(BaseModel):
    """Create operator note request."""

    author: str
    content: str
    shift: str = "day"
    incident_ids: list[str] | None = None
    action_items: list[str] | None = None
    tags: list[str] | None = None


class CreateHandoffRequest(BaseModel):
    """Create shift handoff request."""

    from_operator: str
    to_operator: str
    shift_start: str
    shift_end: str


class AcknowledgeHandoffRequest(BaseModel):
    """Acknowledge handoff request."""

    acknowledged_by: str


class RecordFixRequest(BaseModel):
    """Record fix request."""

    incident_id: str
    fix_description: str
    runbook_id: str | None = None
    resolution_minutes: float = 30
    tags: list[str] | None = None


# Triage endpoints
@router.post("/triage")
async def triage_incident(
    request: TriageIncidentRequest,
) -> dict[str, Any]:
    """Auto-triage an incident.

    Analyzes incident title and description to determine:
    - Severity (P0-P4)
    - Category (availability, performance, etc.)
    - Affected services
    - Escalation requirements
    - Similar past incidents
    """
    service = OpsAssistantService()
    triage = await service.auto_triage(
        incident_id=request.incident_id,
        title=request.title,
        description=request.description,
        metadata=request.metadata,
    )
    return triage.to_dict()


@router.get("/triage/{incident_id}")
async def get_triage(incident_id: str) -> dict[str, Any]:
    """Get triage result for an incident."""
    service = OpsAssistantService()
    triage = await service.get_triage(incident_id)
    if not triage:
        raise HTTPException(404, "Triage not found")
    return triage.to_dict()


# Remediation plan endpoints
@router.post("/plans")
async def generate_remediation_plan(
    request: GeneratePlanRequest,
) -> dict[str, Any]:
    """Generate a remediation plan for an incident.

    Creates step-by-step plan based on incident triage:
    - Diagnostic steps
    - Automated runbook actions
    - Manual interventions
    - Verification steps
    """
    service = OpsAssistantService()
    plan = await service.generate_remediation_plan(
        incident_id=request.incident_id,
        created_by=request.created_by,
    )
    if not plan:
        raise HTTPException(404, "Incident triage not found")
    return plan.to_dict()


@router.get("/plans/{plan_id}")
async def get_remediation_plan(plan_id: str) -> dict[str, Any]:
    """Get a remediation plan."""
    service = OpsAssistantService()
    plan = await service.get_remediation_plan(plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    return plan.to_dict()


@router.post("/plans/{plan_id}/advance")
async def advance_plan(
    plan_id: str,
    request: AdvancePlanRequest,
) -> dict[str, Any]:
    """Advance plan to next step.

    Marks current step as complete and moves to next.
    """
    service = OpsAssistantService()
    plan = await service.advance_plan(plan_id, request.actor)
    if not plan:
        raise HTTPException(404, "Plan not found")
    return plan.to_dict()


# Runbook endpoints
@router.post("/runbooks/initialize")
async def initialize_runbooks() -> dict[str, Any]:
    """Initialize default runbooks.

    Creates safe, pre-defined runbooks for common operations.
    """
    service = OpsAssistantService()
    created = await service.initialize_runbooks()
    return {"created": created, "message": f"Created {created} runbooks"}


@router.get("/runbooks")
async def list_runbooks(
    category: str = Query(default=None),
    safety_level: str = Query(default=None),
) -> list[dict[str, Any]]:
    """List available runbooks.

    Args:
        category: Filter by category
        safety_level: Filter by safety level (safe, caution, dangerous, critical)
    """
    service = OpsAssistantService()

    cat = None
    if category:
        try:
            cat = TriageCategory(category)
        except ValueError:
            valid = [c.value for c in TriageCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    level = None
    if safety_level:
        try:
            level = RunbookSafetyLevel(safety_level)
        except ValueError:
            valid = [lv.value for lv in RunbookSafetyLevel]
            raise HTTPException(400, f"Invalid safety_level. Valid: {valid}")

    runbooks = await service.list_runbooks(category=cat, safety_level=level)
    return [r.to_dict() for r in runbooks]


@router.get("/runbooks/{runbook_id}")
async def get_runbook(runbook_id: str) -> dict[str, Any]:
    """Get runbook details."""
    service = OpsAssistantService()
    runbook = await service.get_runbook(runbook_id)
    if not runbook:
        raise HTTPException(404, "Runbook not found")
    return runbook.to_dict()


@router.post("/runbooks/{runbook_id}/execute")
async def execute_runbook(
    runbook_id: str,
    request: ExecuteRunbookRequest,
) -> dict[str, Any]:
    """Execute a runbook.

    Runs pre-checks, executes commands, runs post-checks.
    Requires approval for dangerous/critical runbooks.
    """
    service = OpsAssistantService()
    try:
        execution = await service.execute_runbook(
            runbook_id=runbook_id,
            executed_by=request.executed_by,
            parameters=request.parameters,
            approval_id=request.approval_id,
        )
        return execution.to_dict()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/executions")
async def get_execution_history(
    runbook_id: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get runbook execution history."""
    service = OpsAssistantService()
    executions = await service.get_execution_history(runbook_id=runbook_id, limit=limit)
    return [e.to_dict() for e in executions]


# Escalation endpoints
@router.post("/escalation/initialize")
async def initialize_escalation_rules() -> dict[str, Any]:
    """Initialize default escalation rules."""
    service = OpsAssistantService()
    created = await service.initialize_escalation_rules()
    return {"created": created, "message": f"Created {created} escalation rules"}


@router.get("/escalation/rules")
async def list_escalation_rules() -> list[dict[str, Any]]:
    """List escalation rules."""
    service = OpsAssistantService()
    rules = await service.list_escalation_rules()
    return [r.to_dict() for r in rules]


# Notes and handoffs endpoints
@router.post("/notes")
async def create_note(request: CreateNoteRequest) -> dict[str, Any]:
    """Create an operator note.

    For documenting observations, actions, and handoff information.
    """
    service = OpsAssistantService()
    note = await service.create_note(
        author=request.author,
        content=request.content,
        shift=request.shift,
        incident_ids=request.incident_ids,
        action_items=request.action_items,
        tags=request.tags,
    )
    return note.to_dict()


@router.get("/notes")
async def get_recent_notes(
    hours: int = Query(default=24, ge=1, le=168),
    author: str = Query(default=None),
    shift: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get recent operator notes."""
    service = OpsAssistantService()
    notes = await service.get_recent_notes(hours=hours, author=author, shift=shift)
    return [n.to_dict() for n in notes]


@router.post("/handoffs")
async def create_handoff(request: CreateHandoffRequest) -> dict[str, Any]:
    """Create a shift handoff.

    Gathers notes, active incidents, and pending actions.
    """
    service = OpsAssistantService()
    handoff = await service.create_handoff(
        from_operator=request.from_operator,
        to_operator=request.to_operator,
        shift_start=datetime.fromisoformat(request.shift_start),
        shift_end=datetime.fromisoformat(request.shift_end),
    )
    return handoff.to_dict()


@router.get("/handoffs/{handoff_id}")
async def get_handoff(handoff_id: str) -> dict[str, Any]:
    """Get handoff details."""
    service = OpsAssistantService()
    handoff = await service.get_handoff(handoff_id)
    if not handoff:
        raise HTTPException(404, "Handoff not found")
    return handoff.to_dict()


@router.post("/handoffs/{handoff_id}/acknowledge")
async def acknowledge_handoff(
    handoff_id: str,
    request: AcknowledgeHandoffRequest,
) -> dict[str, Any]:
    """Acknowledge a shift handoff."""
    service = OpsAssistantService()
    handoff = await service.acknowledge_handoff(handoff_id, request.acknowledged_by)
    if not handoff:
        raise HTTPException(404, "Handoff not found")
    return handoff.to_dict()


# Historical fixes endpoints
@router.post("/fixes")
async def record_fix(request: RecordFixRequest) -> dict[str, Any]:
    """Record a successful fix for future recommendations.

    Builds knowledge base for similar incidents.
    """
    service = OpsAssistantService()
    fix = await service.record_fix(
        incident_id=request.incident_id,
        fix_description=request.fix_description,
        runbook_id=request.runbook_id,
        resolution_minutes=request.resolution_minutes,
        tags=request.tags,
    )
    return fix.to_dict()


@router.get("/fixes")
async def list_historical_fixes(
    category: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """List historical fixes."""
    service = OpsAssistantService()

    cat = None
    if category:
        try:
            cat = TriageCategory(category)
        except ValueError:
            valid = [c.value for c in TriageCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    fixes = await service.list_historical_fixes(category=cat, limit=limit)
    return [f.to_dict() for f in fixes]


@router.get("/recommendations/{incident_id}")
async def get_fix_recommendations(
    incident_id: str,
    limit: int = Query(default=5, ge=1, le=20),
) -> list[dict[str, Any]]:
    """Get fix recommendations for an incident.

    Returns ranked recommendations based on:
    - Similar past incidents
    - Success rates
    - Resolution times
    """
    service = OpsAssistantService()
    recommendations = await service.get_fix_recommendations(incident_id, limit)
    return [r.to_dict() for r in recommendations]


# Reference endpoints
@router.get("/reference/severities")
async def list_triage_severities() -> list[str]:
    """List available triage severities."""
    return [s.value for s in TriageSeverity]


@router.get("/reference/categories")
async def list_triage_categories() -> list[str]:
    """List available triage categories."""
    return [c.value for c in TriageCategory]


@router.get("/reference/safety-levels")
async def list_runbook_safety_levels() -> list[str]:
    """List available runbook safety levels."""
    return [lv.value for lv in RunbookSafetyLevel]


@router.get("/reference/escalation-levels")
async def list_escalation_levels() -> list[str]:
    """List available escalation levels."""
    return [lv.value for lv in EscalationLevel]


@router.get("/reference/handoff-statuses")
async def list_handoff_statuses() -> list[str]:
    """List available handoff statuses."""
    return [s.value for s in HandoffStatus]
