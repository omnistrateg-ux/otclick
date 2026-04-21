"""Drift detection API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.drift_detection import (
    DriftDetectionService,
    DriftType,
    DriftSeverity,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drift", tags=["drift"])


# Request models
class CaptureBaselineRequest(BaseModel):
    """Capture drift baseline request."""

    resource: str
    drift_type: str
    state_data: dict[str, Any]
    captured_by: str = "system"


class CheckDriftRequest(BaseModel):
    """Check drift request."""

    resource: str
    current_state: dict[str, Any]
    critical_keys: list[str] | None = None


# Endpoints
@router.post("/baseline")
async def capture_baseline(
    request: CaptureBaselineRequest,
) -> dict[str, Any]:
    """Capture drift baseline."""
    service = DriftDetectionService()

    try:
        drift_type = DriftType(request.drift_type)
    except ValueError:
        valid = [t.value for t in DriftType]
        raise HTTPException(400, f"Invalid drift type. Valid: {valid}")

    snapshot = await service.capture_baseline(
        resource=request.resource,
        drift_type=drift_type,
        state_data=request.state_data,
        captured_by=request.captured_by,
    )
    return snapshot.to_dict()


@router.get("/baseline/{resource}")
async def get_baseline(resource: str) -> dict[str, Any]:
    """Get baseline for resource."""
    service = DriftDetectionService()
    baseline = await service.get_baseline(resource)
    if not baseline:
        raise HTTPException(404, "Baseline not found")
    return baseline.to_dict()


@router.post("/check")
async def check_drift(
    request: CheckDriftRequest,
) -> dict[str, Any]:
    """Check for drift."""
    service = DriftDetectionService()
    event = await service.check_drift(
        resource=request.resource,
        current_state=request.current_state,
        critical_keys=request.critical_keys,
    )
    if event:
        return {"drift_detected": True, "event": event.to_dict()}
    return {"drift_detected": False}


@router.post("/check-all")
async def run_drift_check_all() -> list[dict[str, Any]]:
    """Run drift check on all monitored resources."""
    service = DriftDetectionService()
    events = await service.run_check_all()
    return [e.to_dict() for e in events]


@router.get("/events")
async def get_drift_events(
    severity: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get drift events."""
    service = DriftDetectionService()

    sev = None
    if severity:
        try:
            sev = DriftSeverity(severity)
        except ValueError:
            valid = [s.value for s in DriftSeverity]
            raise HTTPException(400, f"Invalid severity. Valid: {valid}")

    events = await service.get_events(limit=limit, severity=sev)
    return [e.to_dict() for e in events]


@router.post("/events/{event_id}/acknowledge")
async def acknowledge_drift(
    event_id: str,
    acknowledged_by: str = Query(...),
) -> dict[str, Any]:
    """Acknowledge drift event."""
    service = DriftDetectionService()
    event = await service.acknowledge_drift(event_id, acknowledged_by)
    if not event:
        raise HTTPException(404, "Event not found")
    return event.to_dict()


@router.get("/report")
async def get_drift_report() -> dict[str, Any]:
    """Generate drift report."""
    service = DriftDetectionService()
    report = await service.generate_report()
    return report.to_dict()


# Reference endpoints
@router.get("/reference/types")
async def list_drift_types() -> list[str]:
    """List available drift types."""
    return [t.value for t in DriftType]


@router.get("/reference/severities")
async def list_drift_severities() -> list[str]:
    """List available drift severities."""
    return [s.value for s in DriftSeverity]
