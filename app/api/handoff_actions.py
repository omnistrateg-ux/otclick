"""Manager Handoff Actions API endpoints.

Actions managers can take on handoffs.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.manager_actions import (
    ManagerActionsService,
    HandoffAction,
    HandoffStatus,
    RejectionReason,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/handoff-actions", tags=["handoff-actions"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateHandoffRequest(BaseModel):
    """Create handoff request."""

    lead_id: str
    account_id: str
    contact_id: str | None = None
    assigned_to: str | None = None
    lead_score: float | None = None
    qualified_reason: str | None = None
    reply_summary: str | None = None
    interest_signals: list[str] | None = None


class TakeActionRequest(BaseModel):
    """Take action request."""

    action: str
    actor: str
    notes: str | None = None
    metadata: dict[str, Any] | None = None


class ReassignRequest(BaseModel):
    """Reassign handoff request."""

    actor: str
    new_manager: str
    notes: str | None = None


class RejectRequest(BaseModel):
    """Reject handoff request."""

    actor: str
    reason: str
    notes: str | None = None


class QualifyRequest(BaseModel):
    """Qualify handoff request."""

    actor: str
    deal_value: float | None = None
    notes: str | None = None


class ScheduleMeetingRequest(BaseModel):
    """Schedule meeting request."""

    actor: str
    meeting_date: str  # ISO format
    notes: str | None = None


class HandoffResponse(BaseModel):
    """Handoff response."""

    id: str
    lead_id: str
    account_id: str
    status: str
    assigned_to: str | None
    sla_deadline: str | None
    lead_score: float | None


# ============================================================================
# Handoff Endpoints
# ============================================================================


@router.post("/handoffs")
async def create_handoff(
    request: CreateHandoffRequest,
) -> dict[str, Any]:
    """Create a new handoff.

    Args:
        request: Handoff creation request

    Returns:
        Created handoff
    """
    service = ManagerActionsService()

    handoff = await service.create_handoff(
        lead_id=request.lead_id,
        account_id=request.account_id,
        contact_id=request.contact_id,
        assigned_to=request.assigned_to,
        lead_score=request.lead_score,
        qualified_reason=request.qualified_reason,
        reply_summary=request.reply_summary,
        interest_signals=request.interest_signals,
    )

    return handoff.to_dict()


@router.get("/handoffs/{handoff_id}")
async def get_handoff(
    handoff_id: str,
) -> dict[str, Any]:
    """Get handoff by ID.

    Args:
        handoff_id: Handoff ID

    Returns:
        Handoff details
    """
    service = ManagerActionsService()
    handoff = await service.get_handoff(handoff_id)

    if not handoff:
        raise HTTPException(404, f"Handoff {handoff_id} not found")

    return handoff.to_dict()


@router.post("/handoffs/{handoff_id}/action")
async def take_action(
    handoff_id: str,
    request: TakeActionRequest,
) -> dict[str, Any]:
    """Take an action on a handoff.

    Args:
        handoff_id: Handoff ID
        request: Action request

    Returns:
        Action result
    """
    service = ManagerActionsService()

    try:
        action = HandoffAction(request.action)
    except ValueError:
        valid_actions = [a.value for a in HandoffAction]
        raise HTTPException(400, f"Invalid action. Valid: {valid_actions}")

    try:
        result = await service.take_action(
            handoff_id=handoff_id,
            action=action,
            actor=request.actor,
            notes=request.notes,
            metadata=request.metadata,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return result.to_dict()


@router.post("/handoffs/{handoff_id}/accept")
async def accept_handoff(
    handoff_id: str,
    actor: str,
    notes: str = Query(default=None),
) -> dict[str, Any]:
    """Accept a handoff.

    Args:
        handoff_id: Handoff ID
        actor: Manager accepting
        notes: Optional notes

    Returns:
        Action result
    """
    service = ManagerActionsService()

    result = await service.take_action(
        handoff_id=handoff_id,
        action=HandoffAction.ACCEPT,
        actor=actor,
        notes=notes,
    )

    return result.to_dict()


@router.post("/handoffs/{handoff_id}/reject")
async def reject_handoff(
    handoff_id: str,
    request: RejectRequest,
) -> dict[str, Any]:
    """Reject a handoff.

    Args:
        handoff_id: Handoff ID
        request: Reject request

    Returns:
        Action result
    """
    service = ManagerActionsService()

    try:
        reason = RejectionReason(request.reason)
    except ValueError:
        valid_reasons = [r.value for r in RejectionReason]
        raise HTTPException(400, f"Invalid reason. Valid: {valid_reasons}")

    result = await service.take_action(
        handoff_id=handoff_id,
        action=HandoffAction.REJECT,
        actor=request.actor,
        notes=request.notes,
        metadata={"reason": request.reason},
    )

    return result.to_dict()


@router.post("/handoffs/{handoff_id}/reassign")
async def reassign_handoff(
    handoff_id: str,
    request: ReassignRequest,
) -> dict[str, Any]:
    """Reassign a handoff to another manager.

    Args:
        handoff_id: Handoff ID
        request: Reassign request

    Returns:
        Action result
    """
    service = ManagerActionsService()

    result = await service.take_action(
        handoff_id=handoff_id,
        action=HandoffAction.REASSIGN,
        actor=request.actor,
        notes=request.notes,
        metadata={"new_manager": request.new_manager},
    )

    return result.to_dict()


@router.post("/handoffs/{handoff_id}/qualify")
async def qualify_handoff(
    handoff_id: str,
    request: QualifyRequest,
) -> dict[str, Any]:
    """Mark handoff as qualified and optionally create deal.

    Args:
        handoff_id: Handoff ID
        request: Qualify request

    Returns:
        Action result with optional deal ID
    """
    service = ManagerActionsService()

    metadata = {}
    if request.deal_value:
        metadata["deal_value"] = request.deal_value

    result = await service.take_action(
        handoff_id=handoff_id,
        action=HandoffAction.MARK_QUALIFIED,
        actor=request.actor,
        notes=request.notes,
        metadata=metadata if metadata else None,
    )

    return result.to_dict()


@router.post("/handoffs/{handoff_id}/schedule-meeting")
async def schedule_meeting(
    handoff_id: str,
    request: ScheduleMeetingRequest,
) -> dict[str, Any]:
    """Schedule a meeting for handoff.

    Args:
        handoff_id: Handoff ID
        request: Meeting request

    Returns:
        Action result
    """
    service = ManagerActionsService()

    result = await service.take_action(
        handoff_id=handoff_id,
        action=HandoffAction.SCHEDULE_MEETING,
        actor=request.actor,
        notes=request.notes,
        metadata={"meeting_date": request.meeting_date},
    )

    return result.to_dict()


@router.post("/handoffs/{handoff_id}/follow-up")
async def schedule_follow_up(
    handoff_id: str,
    actor: str,
    follow_up_date: str = Query(default=None),
    notes: str = Query(default=None),
) -> dict[str, Any]:
    """Schedule a follow-up.

    Args:
        handoff_id: Handoff ID
        actor: Manager
        follow_up_date: Follow-up date (ISO format)
        notes: Optional notes

    Returns:
        Action result
    """
    service = ManagerActionsService()

    metadata = {}
    if follow_up_date:
        metadata["follow_up_date"] = follow_up_date

    result = await service.take_action(
        handoff_id=handoff_id,
        action=HandoffAction.FOLLOW_UP,
        actor=actor,
        notes=notes,
        metadata=metadata if metadata else None,
    )

    return result.to_dict()


@router.post("/handoffs/{handoff_id}/close")
async def close_handoff(
    handoff_id: str,
    actor: str,
    notes: str = Query(default=None),
) -> dict[str, Any]:
    """Close a handoff.

    Args:
        handoff_id: Handoff ID
        actor: Manager
        notes: Optional notes

    Returns:
        Action result
    """
    service = ManagerActionsService()

    result = await service.take_action(
        handoff_id=handoff_id,
        action=HandoffAction.CLOSE,
        actor=actor,
        notes=notes,
    )

    return result.to_dict()


# ============================================================================
# Workload Endpoints
# ============================================================================


@router.get("/managers/{manager_id}/workload")
async def get_manager_workload(
    manager_id: str,
) -> dict[str, Any]:
    """Get workload for a manager.

    Args:
        manager_id: Manager ID

    Returns:
        Workload summary
    """
    service = ManagerActionsService()
    workload = await service.get_manager_workload(manager_id)
    return workload.to_dict()


@router.get("/managers/{manager_id}/handoffs")
async def get_manager_handoffs(
    manager_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get pending handoffs for a manager.

    Args:
        manager_id: Manager ID
        limit: Max results

    Returns:
        List of handoffs
    """
    service = ManagerActionsService()
    handoffs = await service.get_pending_handoffs(manager_id, limit)
    return [h.to_dict() for h in handoffs]


@router.get("/managers/best-assignee")
async def get_best_assignee(
    exclude: str = Query(default=None),
) -> dict[str, Any]:
    """Get best manager to assign based on workload.

    Args:
        exclude: Comma-separated manager IDs to exclude

    Returns:
        Best assignee
    """
    service = ManagerActionsService()

    exclude_list = exclude.split(",") if exclude else None
    manager_id = await service.get_best_assignee(exclude_list)

    return {
        "manager_id": manager_id,
        "available": manager_id is not None,
    }


# ============================================================================
# Queue Endpoints
# ============================================================================


@router.get("/handoffs/pending")
async def get_pending_handoffs(
    manager_id: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get pending handoffs.

    Args:
        manager_id: Filter by manager
        limit: Max results

    Returns:
        List of pending handoffs
    """
    service = ManagerActionsService()
    handoffs = await service.get_pending_handoffs(manager_id, limit)
    return [h.to_dict() for h in handoffs]


@router.get("/handoffs/overdue")
async def get_overdue_handoffs(
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get overdue handoffs.

    Args:
        limit: Max results

    Returns:
        List of overdue handoffs
    """
    service = ManagerActionsService()
    handoffs = await service.get_overdue_handoffs(limit)
    return [h.to_dict() for h in handoffs]


@router.get("/stats")
async def get_handoff_stats(
    days: int = Query(default=7, ge=1, le=90),
) -> dict[str, Any]:
    """Get handoff statistics.

    Args:
        days: Days to analyze

    Returns:
        Statistics
    """
    service = ManagerActionsService()
    stats = await service.get_handoff_stats(days)
    return stats


# ============================================================================
# Reference Data
# ============================================================================


@router.get("/actions")
async def get_available_actions() -> list[dict[str, str]]:
    """Get all available actions.

    Returns:
        List of actions
    """
    return [
        {"action": a.value, "description": _action_descriptions.get(a.value, "")}
        for a in HandoffAction
    ]


@router.get("/rejection-reasons")
async def get_rejection_reasons() -> list[dict[str, str]]:
    """Get all rejection reasons.

    Returns:
        List of reasons
    """
    return [{"reason": r.value} for r in RejectionReason]


@router.get("/statuses")
async def get_handoff_statuses() -> list[dict[str, str]]:
    """Get all handoff statuses.

    Returns:
        List of statuses
    """
    return [{"status": s.value} for s in HandoffStatus]


_action_descriptions = {
    "accept": "Accept and take ownership of the handoff",
    "reject": "Reject the handoff with a reason",
    "reassign": "Reassign to another manager",
    "follow_up": "Schedule a follow-up",
    "schedule_meeting": "Schedule a meeting with the contact",
    "mark_qualified": "Mark as qualified and optionally create deal",
    "mark_unqualified": "Mark as unqualified",
    "request_info": "Request additional information",
    "close": "Close the handoff",
}
