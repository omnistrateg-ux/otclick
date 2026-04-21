"""Change impact analysis API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.change_impact import (
    ChangeImpactService,
    ChangeType,
    RiskLevel as ImpactRiskLevel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/impact", tags=["impact"])


# Request models
class AnalyzeChangeRequest(BaseModel):
    """Analyze change impact request."""

    change_type: str
    title: str
    description: str
    requested_by: str
    target_components: list[str] | None = None
    metadata: dict[str, Any] | None = None


# Endpoints
@router.post("/analyze")
async def analyze_change_impact(
    request: AnalyzeChangeRequest,
) -> dict[str, Any]:
    """Analyze change impact."""
    service = ChangeImpactService()

    try:
        change_type = ChangeType(request.change_type)
    except ValueError:
        valid = [t.value for t in ChangeType]
        raise HTTPException(400, f"Invalid change type. Valid: {valid}")

    report = await service.analyze(
        change_type=change_type,
        title=request.title,
        description=request.description,
        requested_by=request.requested_by,
        target_components=request.target_components,
        metadata=request.metadata,
    )
    return report.to_dict()


@router.get("/quick-assess")
async def quick_assess(
    change_type: str = Query(...),
    components: list[str] = Query(default=[]),
) -> dict[str, Any]:
    """Quick risk assessment."""
    service = ChangeImpactService()

    try:
        ct = ChangeType(change_type)
    except ValueError:
        valid = [t.value for t in ChangeType]
        raise HTTPException(400, f"Invalid change type. Valid: {valid}")

    return await service.quick_assess(ct, components)


@router.get("/reports/{report_id}")
async def get_impact_report(report_id: str) -> dict[str, Any]:
    """Get impact report by ID."""
    service = ChangeImpactService()
    report = await service.get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return report.to_dict()


@router.get("/history")
async def get_impact_history(
    change_type: str = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Get impact analysis history."""
    service = ChangeImpactService()

    ct = None
    if change_type:
        try:
            ct = ChangeType(change_type)
        except ValueError:
            valid = [t.value for t in ChangeType]
            raise HTTPException(400, f"Invalid change type. Valid: {valid}")

    reports = await service.get_history(limit=limit, change_type=ct)
    return [r.to_dict() for r in reports]


# Reference endpoints
@router.get("/reference/change-types")
async def list_change_types() -> list[str]:
    """List available change types."""
    return [t.value for t in ChangeType]


@router.get("/reference/risk-levels")
async def list_risk_levels() -> list[str]:
    """List available risk levels."""
    return [r.value for r in ImpactRiskLevel]
