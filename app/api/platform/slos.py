"""SLO and error budgets API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.slo_budgets import SLOBudgetsService, SLOType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slos", tags=["slos"])


# Request models
class CreateSLORequest(BaseModel):
    """Create SLO request."""

    id: str
    name: str
    description: str
    slo_type: str
    target_percent: float
    window_days: int
    measurement_query: str
    service: str


class RecordSLOMetricRequest(BaseModel):
    """Record SLO metric request."""

    good_events: int
    total_events: int


# Endpoints
@router.get("")
async def list_slos(
    service_filter: str = Query(default=None, alias="service"),
) -> list[dict[str, Any]]:
    """List SLOs."""
    slo_service = SLOBudgetsService()
    slos = await slo_service.list_slos(service=service_filter)
    return [s.to_dict() for s in slos]


@router.post("")
async def create_slo(
    request: CreateSLORequest,
) -> dict[str, Any]:
    """Create SLO."""
    from app.services.slo_budgets import SLO

    slo_service = SLOBudgetsService()

    try:
        slo_type = SLOType(request.slo_type)
    except ValueError:
        valid = [t.value for t in SLOType]
        raise HTTPException(400, f"Invalid SLO type. Valid: {valid}")

    slo = SLO(
        id=request.id,
        name=request.name,
        description=request.description,
        slo_type=slo_type,
        target_percent=request.target_percent,
        window_days=request.window_days,
        measurement_query=request.measurement_query,
        service=request.service,
    )

    result = await slo_service.create_slo(slo)
    return result.to_dict()


@router.get("/{slo_id}/budget")
async def get_error_budget(slo_id: str) -> dict[str, Any]:
    """Get error budget for SLO."""
    slo_service = SLOBudgetsService()
    budget = await slo_service.get_error_budget(slo_id)
    if not budget:
        raise HTTPException(404, f"SLO {slo_id} not found")
    return budget.to_dict()


@router.post("/{slo_id}/metrics")
async def record_slo_metric(
    slo_id: str,
    request: RecordSLOMetricRequest,
) -> dict[str, str]:
    """Record SLO metric data."""
    slo_service = SLOBudgetsService()
    await slo_service.record_metric(
        slo_id=slo_id,
        good_events=request.good_events,
        total_events=request.total_events,
    )
    return {"status": "recorded"}


@router.get("/budgets")
async def get_all_budgets() -> list[dict[str, Any]]:
    """Get all error budgets."""
    slo_service = SLOBudgetsService()
    budgets = await slo_service.get_all_budgets()
    return [b.to_dict() for b in budgets]


@router.get("/report")
async def generate_slo_report(
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, Any]:
    """Generate SLO report."""
    slo_service = SLOBudgetsService()
    report = await slo_service.generate_report(period_days=days)
    return report.to_dict()


# Reference endpoints
@router.get("/reference/types")
async def list_slo_types() -> list[str]:
    """List available SLO types."""
    return [t.value for t in SLOType]
