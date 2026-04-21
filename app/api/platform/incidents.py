"""Incident timeline API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.incident_timeline import (
    IncidentSeverity,
    IncidentStatus,
    IncidentTimelineService,
    TimelineEventType,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])


# Request models
class CreateIncidentRequest(BaseModel):
    """Create incident request."""

    title: str
    description: str
    severity: str
    created_by: str
    affected_services: list[str] | None = None
    assignee: str | None = None
    tags: list[str] | None = None


class UpdateIncidentStatusRequest(BaseModel):
    """Update incident status request."""

    status: str
    actor: str
    comment: str | None = None


class ResolveIncidentRequest(BaseModel):
    """Resolve incident request."""

    actor: str
    resolution_summary: str


class AddTimelineEventRequest(BaseModel):
    """Add timeline event request."""

    event_type: str
    actor: str
    content: str
    metadata: dict[str, Any] | None = None


# Endpoints
@router.post("")
async def create_incident(
    request: CreateIncidentRequest,
) -> dict[str, Any]:
    """Create new incident."""
    inc_service = IncidentTimelineService()

    try:
        severity = IncidentSeverity(request.severity)
    except ValueError:
        valid = [s.value for s in IncidentSeverity]
        raise HTTPException(400, f"Invalid severity. Valid: {valid}")

    incident = await inc_service.create_incident(
        title=request.title,
        description=request.description,
        severity=severity,
        created_by=request.created_by,
        affected_services=request.affected_services,
        assignee=request.assignee,
        tags=request.tags,
    )
    return incident.to_dict()


@router.get("")
async def list_incidents(
    status: str = Query(default=None),
    severity: str = Query(default=None),
    active_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """List incidents."""
    inc_service = IncidentTimelineService()

    st = None
    if status:
        try:
            st = IncidentStatus(status)
        except ValueError:
            valid = [s.value for s in IncidentStatus]
            raise HTTPException(400, f"Invalid status. Valid: {valid}")

    sev = None
    if severity:
        try:
            sev = IncidentSeverity(severity)
        except ValueError:
            valid = [s.value for s in IncidentSeverity]
            raise HTTPException(400, f"Invalid severity. Valid: {valid}")

    incidents = await inc_service.list_incidents(
        status=st,
        severity=sev,
        active_only=active_only,
        limit=limit,
    )
    return [i.to_dict() for i in incidents]


@router.get("/active")
async def get_active_incidents() -> list[dict[str, Any]]:
    """Get active incidents."""
    inc_service = IncidentTimelineService()
    incidents = await inc_service.get_active_incidents()
    return [i.to_dict() for i in incidents]


@router.get("/stats")
async def get_incident_stats(
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, Any]:
    """Get incident statistics."""
    inc_service = IncidentTimelineService()
    stats = await inc_service.get_stats(days=days)
    return stats.to_dict()


@router.get("/{incident_id}")
async def get_incident(incident_id: str) -> dict[str, Any]:
    """Get incident by ID."""
    inc_service = IncidentTimelineService()
    incident = await inc_service.get_incident(incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    return incident.to_dict()


@router.post("/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    request: UpdateIncidentStatusRequest,
) -> dict[str, Any]:
    """Update incident status."""
    inc_service = IncidentTimelineService()

    try:
        status = IncidentStatus(request.status)
    except ValueError:
        valid = [s.value for s in IncidentStatus]
        raise HTTPException(400, f"Invalid status. Valid: {valid}")

    incident = await inc_service.update_status(
        incident_id=incident_id,
        new_status=status,
        actor=request.actor,
        comment=request.comment,
    )
    if not incident:
        raise HTTPException(404, "Incident not found")
    return incident.to_dict()


@router.post("/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    request: ResolveIncidentRequest,
) -> dict[str, Any]:
    """Resolve incident."""
    inc_service = IncidentTimelineService()
    incident = await inc_service.resolve_incident(
        incident_id=incident_id,
        actor=request.actor,
        resolution_summary=request.resolution_summary,
    )
    if not incident:
        raise HTTPException(404, "Incident not found")
    return incident.to_dict()


@router.post("/{incident_id}/timeline")
async def add_timeline_event(
    incident_id: str,
    request: AddTimelineEventRequest,
) -> dict[str, Any]:
    """Add event to incident timeline."""
    inc_service = IncidentTimelineService()

    try:
        event_type = TimelineEventType(request.event_type)
    except ValueError:
        valid = [t.value for t in TimelineEventType]
        raise HTTPException(400, f"Invalid event type. Valid: {valid}")

    incident = await inc_service.add_timeline_event(
        incident_id=incident_id,
        event_type=event_type,
        actor=request.actor,
        content=request.content,
        metadata=request.metadata,
    )
    if not incident:
        raise HTTPException(404, "Incident not found")
    return incident.to_dict()


# Reference endpoints
@router.get("/reference/severities")
async def list_incident_severities() -> list[str]:
    """List available severities."""
    return [s.value for s in IncidentSeverity]


@router.get("/reference/statuses")
async def list_incident_statuses() -> list[str]:
    """List available statuses."""
    return [s.value for s in IncidentStatus]


@router.get("/reference/event-types")
async def list_timeline_event_types() -> list[str]:
    """List available timeline event types."""
    return [t.value for t in TimelineEventType]
