"""Handoff API endpoints.

Управление передачей лидов менеджерам.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.storage.database import async_session_factory
from app.storage.repositories.handoff_repo import HandoffRepository

UTC = timezone.utc
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


def _to_response(handoff) -> HandoffResponse:
    """Convert DB model to response."""
    return HandoffResponse(
        id=str(handoff.id),
        lead_id=str(handoff.lead_id),
        manager_id=handoff.manager_id or "",
        status=handoff.status,
        priority=handoff.priority or "normal",
        company_name=handoff.company_name or "Unknown",
        talking_points=handoff.talking_points or [],
        created_at=handoff.created_at,
        accepted_at=handoff.accepted_at,
        completed_at=handoff.completed_at,
    )


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
    async with async_session_factory() as db:
        repo = HandoffRepository(db)
        handoffs, total = await repo.list_all(
            manager_id=manager_id,
            status=status,
            page=page,
            page_size=page_size,
        )

        return HandoffListResponse(
            items=[_to_response(h) for h in handoffs],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/stats", response_model=HandoffStatsResponse)
async def get_handoff_stats() -> HandoffStatsResponse:
    """Get handoff statistics.

    Returns:
        Handoff statistics
    """
    async with async_session_factory() as db:
        repo = HandoffRepository(db)
        stats = await repo.get_stats()

        return HandoffStatsResponse(
            total=stats["total"],
            pending=stats["pending"],
            accepted=stats["accepted"],
            completed=stats["completed"],
            rejected=stats["rejected"],
            avg_acceptance_time_hours=stats["avg_acceptance_time_hours"],
            avg_completion_time_hours=stats["avg_completion_time_hours"],
        )


@router.get("/{handoff_id}", response_model=HandoffResponse)
async def get_handoff(handoff_id: str) -> HandoffResponse:
    """Get handoff by ID.

    Args:
        handoff_id: Handoff ID

    Returns:
        Handoff details
    """
    async with async_session_factory() as db:
        repo = HandoffRepository(db)
        handoff = await repo.get_by_id(handoff_id)

        if not handoff:
            raise HTTPException(404, f"Handoff {handoff_id} not found")

        return _to_response(handoff)


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

        # Generate talking points
        talking_points = await generate_talking_points(lead)

        repo = HandoffRepository(db)
        handoff = await repo.create(
            lead_id=request.lead_id,
            manager_id=request.manager_id,
            company_name=lead.company_name,
            priority=request.priority,
            talking_points=talking_points,
            notes=request.notes,
        )
        await db.commit()

        # Notify manager
        from workers.outreach_tasks import notify_manager

        notify_manager.delay(
            handoff_id=str(handoff.id),
            manager_id=request.manager_id,
            lead_id=request.lead_id,
        )

        return _to_response(handoff)


@router.post("/{handoff_id}/accept")
async def accept_handoff(handoff_id: str) -> HandoffResponse:
    """Accept a handoff.

    Args:
        handoff_id: Handoff ID

    Returns:
        Updated handoff
    """
    async with async_session_factory() as db:
        repo = HandoffRepository(db)

        handoff = await repo.get_by_id(handoff_id)
        if not handoff:
            raise HTTPException(404, f"Handoff {handoff_id} not found")

        if handoff.status != "pending":
            raise HTTPException(400, f"Cannot accept handoff with status: {handoff.status}")

        handoff = await repo.accept(handoff_id)
        await db.commit()

        return _to_response(handoff)


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
    async with async_session_factory() as db:
        repo = HandoffRepository(db)

        handoff = await repo.get_by_id(handoff_id)
        if not handoff:
            raise HTTPException(404, f"Handoff {handoff_id} not found")

        if handoff.status != "pending":
            raise HTTPException(400, f"Cannot reject handoff with status: {handoff.status}")

        handoff = await repo.reject(handoff_id, reason=reason)
        await db.commit()

        return _to_response(handoff)


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
    async with async_session_factory() as db:
        repo = HandoffRepository(db)

        handoff = await repo.get_by_id(handoff_id)
        if not handoff:
            raise HTTPException(404, f"Handoff {handoff_id} not found")

        if handoff.status != "accepted":
            raise HTTPException(400, f"Cannot complete handoff with status: {handoff.status}")

        handoff = await repo.complete(handoff_id, outcome=outcome, deal_value=deal_value)

        # Update lead status
        from app.orchestrator.engine import LeadOrchestrator
        from app.storage.repositories.lead_repo import LeadRepository

        lead_repo = LeadRepository(db)
        lead = await lead_repo.get(str(handoff.lead_id))

        if lead:
            orchestrator = LeadOrchestrator()
            lead, event = orchestrator.mark_converted(
                lead,
                deal_value=deal_value,
                actor="handoff_api",
            )
            await lead_repo.update(lead)

        await db.commit()

        return _to_response(handoff)


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
    async with async_session_factory() as db:
        repo = HandoffRepository(db)

        handoff = await repo.get_by_id(handoff_id)
        if not handoff:
            raise HTTPException(404, f"Handoff {handoff_id} not found")

        if handoff.status == "completed":
            raise HTTPException(400, "Cannot reassign completed handoff")

        handoff = await repo.reassign(handoff_id, new_manager_id)
        await db.commit()

        # Notify new manager
        from workers.outreach_tasks import notify_manager

        notify_manager.delay(
            handoff_id=str(handoff.id),
            manager_id=new_manager_id,
            lead_id=str(handoff.lead_id),
        )

        return _to_response(handoff)


@router.delete("/{handoff_id}")
async def delete_handoff(handoff_id: str) -> dict[str, str]:
    """Delete a handoff.

    Args:
        handoff_id: Handoff ID

    Returns:
        Deletion confirmation
    """
    async with async_session_factory() as db:
        repo = HandoffRepository(db)

        deleted = await repo.delete(handoff_id)
        if not deleted:
            raise HTTPException(404, f"Handoff {handoff_id} not found")

        await db.commit()

        return {"message": f"Handoff {handoff_id} deleted"}
