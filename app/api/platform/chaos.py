"""Chaos drills API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.chaos_drills import ChaosDrillsService, DrillType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chaos", tags=["chaos"])


# Request models
class StartDrillRequest(BaseModel):
    """Start drill request."""

    initiated_by: str
    approved_by: str | None = None
    environment: str = "development"


class StopDrillRequest(BaseModel):
    """Stop drill request."""

    actor: str
    reason: str = "manual_stop"


# Endpoints
@router.get("/drills")
async def list_drills(
    drill_type: str = Query(default=None),
    safe_for_production: bool = Query(default=None),
) -> list[dict[str, Any]]:
    """List available chaos drills."""
    drill_service = ChaosDrillsService()

    dt = None
    if drill_type:
        try:
            dt = DrillType(drill_type)
        except ValueError:
            valid = [t.value for t in DrillType]
            raise HTTPException(400, f"Invalid drill type. Valid: {valid}")

    drills = drill_service.list_drills(
        drill_type=dt,
        safe_for_production=safe_for_production,
    )
    return [d.to_dict() for d in drills]


@router.get("/drills/{drill_id}")
async def get_drill(drill_id: str) -> dict[str, Any]:
    """Get drill by ID."""
    drill_service = ChaosDrillsService()
    drill = drill_service.get_drill(drill_id)
    if not drill:
        raise HTTPException(404, "Drill not found")
    return drill.to_dict()


@router.post("/drills/{drill_id}/start")
async def start_drill(
    drill_id: str,
    request: StartDrillRequest,
) -> dict[str, Any]:
    """Start a chaos drill."""
    drill_service = ChaosDrillsService()

    try:
        execution = await drill_service.start_drill(
            drill_id=drill_id,
            initiated_by=request.initiated_by,
            approved_by=request.approved_by,
            environment=request.environment,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return execution.to_dict()


@router.post("/executions/{execution_id}/stop")
async def stop_drill(
    execution_id: str,
    request: StopDrillRequest,
) -> dict[str, Any]:
    """Stop a running drill."""
    drill_service = ChaosDrillsService()
    execution = await drill_service.stop_drill(
        execution_id=execution_id,
        actor=request.actor,
        reason=request.reason,
    )
    if not execution:
        raise HTTPException(404, "Execution not found or not running")
    return execution.to_dict()


@router.get("/active")
async def get_active_drill() -> dict[str, Any] | None:
    """Get currently active drill."""
    drill_service = ChaosDrillsService()
    return await drill_service.get_active_drill()


@router.get("/executions")
async def get_drill_history(
    drill_id: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get drill execution history."""
    drill_service = ChaosDrillsService()
    executions = await drill_service.get_execution_history(drill_id=drill_id, limit=limit)
    return [e.to_dict() for e in executions]


@router.get("/executions/{execution_id}")
async def get_drill_execution(execution_id: str) -> dict[str, Any]:
    """Get drill execution by ID."""
    drill_service = ChaosDrillsService()
    execution = await drill_service.get_execution(execution_id)
    if not execution:
        raise HTTPException(404, "Execution not found")
    return execution.to_dict()


@router.get("/executions/{execution_id}/report")
async def get_drill_report(execution_id: str) -> dict[str, Any]:
    """Generate drill report."""
    drill_service = ChaosDrillsService()
    report = await drill_service.generate_report(execution_id)
    if not report:
        raise HTTPException(404, "Execution not found")
    return report.to_dict()


# Reference endpoints
@router.get("/reference/types")
async def list_drill_types() -> list[str]:
    """List available drill types."""
    return [t.value for t in DrillType]
