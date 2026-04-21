"""Synthetic probes API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.services.synthetic_probes import ProbeType, SyntheticProbesService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/probes", tags=["probes"])


# Endpoints
@router.get("")
async def list_probes(
    probe_type: str = Query(default=None),
) -> list[dict[str, Any]]:
    """List synthetic probes."""
    probe_service = SyntheticProbesService()

    pt = None
    if probe_type:
        try:
            pt = ProbeType(probe_type)
        except ValueError:
            valid = [t.value for t in ProbeType]
            raise HTTPException(400, f"Invalid probe type. Valid: {valid}")

    probes = await probe_service.list_probes(probe_type=pt)
    return [p.to_dict() for p in probes]


@router.get("/status")
async def get_all_probe_status() -> list[dict[str, Any]]:
    """Get status of all probes."""
    probe_service = SyntheticProbesService()
    return await probe_service.get_all_probe_status()


@router.post("/{probe_id}/execute")
async def execute_probe(probe_id: str) -> dict[str, Any]:
    """Execute a probe."""
    probe_service = SyntheticProbesService()
    result = await probe_service.execute_probe(probe_id)
    return result.to_dict()


@router.post("/run-all")
async def run_all_probes() -> list[dict[str, Any]]:
    """Run all enabled probes."""
    probe_service = SyntheticProbesService()
    results = await probe_service.run_all_probes()
    return [r.to_dict() for r in results]


@router.get("/{probe_id}/history")
async def get_probe_history(
    probe_id: str,
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    """Get probe execution history."""
    probe_service = SyntheticProbesService()
    history = await probe_service.get_probe_history(probe_id, hours)
    if not history:
        raise HTTPException(404, "Probe not found")
    return history.to_dict()


@router.get("/alerts")
async def get_probe_alerts(
    unacknowledged_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get probe alerts."""
    probe_service = SyntheticProbesService()
    alerts = await probe_service.get_alerts(
        unacknowledged_only=unacknowledged_only,
        limit=limit,
    )
    return [a.to_dict() for a in alerts]


# Reference endpoints
@router.get("/reference/types")
async def list_probe_types() -> list[str]:
    """List available probe types."""
    return [t.value for t in ProbeType]
