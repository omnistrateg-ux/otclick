"""Handoff API endpoints.

Управление передачей лидов менеджерам.
"""

from datetime import datetime, timezone

UTC = timezone.utc
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.storage.database import async_session_factory

router = APIRouter(prefix="/handoffs", tags=["handoffs"])


# Request/Response models
class HandoffResponse(BaseModel):
    """Handoff response model."""

    id: str
    lead_id: str
    manager_id: str
    status: str
    priority: str
    company_name: str
    talking_points: list[str]
    created_at: datetime
    accepted_at: datetime | None = None
    completed_at: datetime | None = None


class HandoffListResponse(BaseModel):
    """Handoff list response."""

    items: list[HandoffResponse]
    total: int
    page: int
    page_size: int


class HandoffCreateRequest(BaseModel):
    """Create handoff request."""

    lead_id: str
    manager_id: str
    priority: str = "normal"
    notes: str | None = None


class HandoffUpdateRequest(BaseModel):
    """Update handoff request."""

    status: str | None = None
    manager_id: str | None = None
    notes: str | None = None


class HandoffStatsResponse(BaseModel):
    """Handoff statistics."""

    total: int
    pending: int
    accepted: int
    completed: int
    rejected: int
    avg_acceptance_time_hours: float | None
    avg_completion_time_hours: float | None


# In-memory storage (would be database in production)
_handoffs: dict[str, dict[str, Any]] = {}


@router.get("", response_model=HandoffListResponse)
async def list_handoffs(
    manager_id: str | None = Query(None, description="Filter by manager"),
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> HandoffListResponse:
    """List handoffs with optional filters.

    Args:
        manager_id: Filter by manager
        status: Filter by status
        page: Page number
        page_size: Items per page

    Returns:
        Paginated list of handoffs
    """
    handoffs = []

    for handoff_id, handoff_data in _handoffs.items():
        if manager_id and handoff_data.get("manager_id") != manager_id:
            continue
        if status and handoff_data.get("status") != status:
            continue

        handoffs.append(
            HandoffResponse(
                id=handoff_id,
                lead_id=handoff_data["lead_id"],
                manager_id=handoff_data["manager_id"],
                status=handoff_data["status"],
                priority=handoff_data.get("priority", "normal"),
                company_name=handoff_data.get("company_name", "Unknown"),
                talking_points=handoff_data.get("talking_points", []),
                created_at=handoff_data["created_at"],
                accepted_at=handoff_data.get("accepted_at"),
                completed_at=handoff_data.get("completed_at"),
            )
        )

    # Sort by created_at descending
    handoffs.sort(key=lambda h: h.created_at, reverse=True)

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    paginated = handoffs[start:end]

    return HandoffListResponse(
        items=paginated,
        total=len(handoffs),
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=HandoffStatsResponse)
async def get_handoff_stats() -> HandoffStatsResponse:
    """Get handoff statistics.

    Returns:
        Handoff statistics
    """
    status_counts = {
        "pending": 0,
        "accepted": 0,
        "completed": 0,
        "rejected": 0,
    }

    for handoff_data in _handoffs.values():
        status = handoff_data.get("status", "pending")
        if status in status_counts:
            status_counts[status] += 1

    return HandoffStatsResponse(
        total=len(_handoffs),
        pending=status_counts["pending"],
        accepted=status_counts["accepted"],
        completed=status_counts["completed"],
        rejected=status_counts["rejected"],
        avg_acceptance_time_hours=None,  # Would calculate from timestamps
        avg_completion_time_hours=None,
    )


@router.get("/{handoff_id}", response_model=HandoffResponse)
async def get_handoff(handoff_id: str) -> HandoffResponse:
    """Get handoff by ID.

    Args:
        handoff_id: Handoff ID

    Returns:
        Handoff details
    """
    if handoff_id not in _handoffs:
        raise HTTPException(404, f"Handoff {handoff_id} not found")

    handoff_data = _handoffs[handoff_id]

    return HandoffResponse(
        id=handoff_id,
        lead_id=handoff_data["lead_id"],
        manager_id=handoff_data["manager_id"],
        status=handoff_data["status"],
        priority=handoff_data.get("priority", "normal"),
        company_name=handoff_data.get("company_name", "Unknown"),
        talking_points=handoff_data.get("talking_points", []),
        created_at=handoff_data["created_at"],
        accepted_at=handoff_data.get("accepted_at"),
        completed_at=handoff_data.get("completed_at"),
    )


@router.post("", response_model=HandoffResponse, status_code=201)
async def create_handoff(request: HandoffCreateRequest) -> HandoffResponse:
    """Create a new handoff.

    Args:
        request: Handoff creation data

    Returns:
        Created handoff
    """
    from app.storage.repositories.lead_repo import LeadRepository
    from app.tools.handoff_tools import generate_talking_points

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        lead = await lead_repo.get(request.lead_id)

        if not lead:
            raise HTTPException(404, f"Lead {request.lead_id} not found")

        handoff_id = str(uuid4())
        now = datetime.now(UTC)

        # Generate talking points
        talking_points = await generate_talking_points(lead)

        handoff_data = {
            "lead_id": request.lead_id,
            "manager_id": request.manager_id,
            "status": "pending",
            "priority": request.priority,
            "company_name": lead.company_name,
            "talking_points": talking_points,
            "notes": request.notes,
            "created_at": now,
        }

        _handoffs[handoff_id] = handoff_data

        # Notify manager
        from workers.outreach_tasks import notify_manager

        notify_manager.delay(
            handoff_id=handoff_id,
            manager_id=request.manager_id,
            lead_id=request.lead_id,
        )

        return HandoffResponse(
            id=handoff_id,
            lead_id=handoff_data["lead_id"],
            manager_id=handoff_data["manager_id"],
            status=handoff_data["status"],
            priority=handoff_data["priority"],
            company_name=handoff_data["company_name"],
            talking_points=handoff_data["talking_points"],
            created_at=now,
            accepted_at=None,
            completed_at=None,
        )


@router.post("/{handoff_id}/accept")
async def accept_handoff(handoff_id: str) -> HandoffResponse:
    """Accept a handoff.

    Args:
        handoff_id: Handoff ID

    Returns:
        Updated handoff
    """
    if handoff_id not in _handoffs:
        raise HTTPException(404, f"Handoff {handoff_id} not found")

    handoff_data = _handoffs[handoff_id]

    if handoff_data["status"] != "pending":
        raise HTTPException(400, f"Cannot accept handoff with status: {handoff_data['status']}")

    handoff_data["status"] = "accepted"
    handoff_data["accepted_at"] = datetime.now(UTC)

    return HandoffResponse(
        id=handoff_id,
        lead_id=handoff_data["lead_id"],
        manager_id=handoff_data["manager_id"],
        status=handoff_data["status"],
        priority=handoff_data.get("priority", "normal"),
        company_name=handoff_data.get("company_name", "Unknown"),
        talking_points=handoff_data.get("talking_points", []),
        created_at=handoff_data["created_at"],
        accepted_at=handoff_data["accepted_at"],
        completed_at=None,
    )


@router.post("/{handoff_id}/reject")
async def reject_handoff(
    handoff_id: str,
    reason: str | None = None,
) -> HandoffResponse:
    """Reject a handoff.

    Args:
        handoff_id: Handoff ID
        reason: Rejection reason

    Returns:
        Updated handoff
    """
    if handoff_id not in _handoffs:
        raise HTTPException(404, f"Handoff {handoff_id} not found")

    handoff_data = _handoffs[handoff_id]

    if handoff_data["status"] != "pending":
        raise HTTPException(400, f"Cannot reject handoff with status: {handoff_data['status']}")

    handoff_data["status"] = "rejected"
    handoff_data["rejected_at"] = datetime.now(UTC)
    handoff_data["rejection_reason"] = reason

    return HandoffResponse(
        id=handoff_id,
        lead_id=handoff_data["lead_id"],
        manager_id=handoff_data["manager_id"],
        status=handoff_data["status"],
        priority=handoff_data.get("priority", "normal"),
        company_name=handoff_data.get("company_name", "Unknown"),
        talking_points=handoff_data.get("talking_points", []),
        created_at=handoff_data["created_at"],
        accepted_at=None,
        completed_at=None,
    )


@router.post("/{handoff_id}/complete")
async def complete_handoff(
    handoff_id: str,
    outcome: str | None = None,
    deal_value: float | None = None,
) -> HandoffResponse:
    """Complete a handoff.

    Args:
        handoff_id: Handoff ID
        outcome: Outcome description
        deal_value: Deal value if converted

    Returns:
        Updated handoff
    """
    if handoff_id not in _handoffs:
        raise HTTPException(404, f"Handoff {handoff_id} not found")

    handoff_data = _handoffs[handoff_id]

    if handoff_data["status"] != "accepted":
        raise HTTPException(400, f"Cannot complete handoff with status: {handoff_data['status']}")

    handoff_data["status"] = "completed"
    handoff_data["completed_at"] = datetime.now(UTC)
    handoff_data["outcome"] = outcome
    handoff_data["deal_value"] = deal_value

    # Update lead status
    from app.orchestrator.engine import LeadOrchestrator
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        lead = await lead_repo.get(handoff_data["lead_id"])

        if lead:
            orchestrator = LeadOrchestrator()
            lead, event = orchestrator.mark_converted(
                lead,
                deal_value=deal_value,
                actor="handoff_api",
            )
            await lead_repo.update(lead)

    return HandoffResponse(
        id=handoff_id,
        lead_id=handoff_data["lead_id"],
        manager_id=handoff_data["manager_id"],
        status=handoff_data["status"],
        priority=handoff_data.get("priority", "normal"),
        company_name=handoff_data.get("company_name", "Unknown"),
        talking_points=handoff_data.get("talking_points", []),
        created_at=handoff_data["created_at"],
        accepted_at=handoff_data.get("accepted_at"),
        completed_at=handoff_data["completed_at"],
    )


@router.post("/{handoff_id}/reassign")
async def reassign_handoff(
    handoff_id: str,
    new_manager_id: str,
) -> HandoffResponse:
    """Reassign handoff to another manager.

    Args:
        handoff_id: Handoff ID
        new_manager_id: New manager ID

    Returns:
        Updated handoff
    """
    if handoff_id not in _handoffs:
        raise HTTPException(404, f"Handoff {handoff_id} not found")

    handoff_data = _handoffs[handoff_id]

    if handoff_data["status"] == "completed":
        raise HTTPException(400, "Cannot reassign completed handoff")

    old_manager = handoff_data["manager_id"]
    handoff_data["manager_id"] = new_manager_id
    handoff_data["status"] = "pending"
    handoff_data["accepted_at"] = None

    # Notify new manager
    from workers.outreach_tasks import notify_manager

    notify_manager.delay(
        handoff_id=handoff_id,
        manager_id=new_manager_id,
        lead_id=handoff_data["lead_id"],
    )

    return HandoffResponse(
        id=handoff_id,
        lead_id=handoff_data["lead_id"],
        manager_id=handoff_data["manager_id"],
        status=handoff_data["status"],
        priority=handoff_data.get("priority", "normal"),
        company_name=handoff_data.get("company_name", "Unknown"),
        talking_points=handoff_data.get("talking_points", []),
        created_at=handoff_data["created_at"],
        accepted_at=None,
        completed_at=None,
    )


@router.delete("/{handoff_id}")
async def delete_handoff(handoff_id: str) -> dict[str, str]:
    """Delete a handoff.

    Args:
        handoff_id: Handoff ID

    Returns:
        Deletion confirmation
    """
    if handoff_id not in _handoffs:
        raise HTTPException(404, f"Handoff {handoff_id} not found")

    del _handoffs[handoff_id]

    return {"message": f"Handoff {handoff_id} deleted"}
