"""Root cause analysis API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.root_cause_helper import (
    RootCauseHelperService,
    SymptomCategory,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rootcause", tags=["rootcause"])


# Request models
class RecordSymptomRequest(BaseModel):
    """Record symptom request."""

    category: str
    description: str
    severity: str = "medium"
    metrics: dict[str, Any] | None = None


class AnalyzeErrorRequest(BaseModel):
    """Analyze error request."""

    error_message: str
    stack_trace: str | None = None
    context: dict[str, Any] | None = None


# Endpoints
@router.post("/symptoms")
async def record_symptom(
    request: RecordSymptomRequest,
) -> dict[str, Any]:
    """Record symptom."""
    service = RootCauseHelperService()

    try:
        category = SymptomCategory(request.category)
    except ValueError:
        valid = [c.value for c in SymptomCategory]
        raise HTTPException(400, f"Invalid category. Valid: {valid}")

    symptom = await service.record_symptom(
        category=category,
        description=request.description,
        severity=request.severity,
        metrics=request.metrics,
    )
    return symptom.to_dict()


@router.get("/symptoms")
async def get_recent_symptoms(
    hours: int = Query(default=24, ge=1, le=168),
    category: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get recent symptoms."""
    service = RootCauseHelperService()

    cat = None
    if category:
        try:
            cat = SymptomCategory(category)
        except ValueError:
            valid = [c.value for c in SymptomCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    symptoms = await service.get_recent_symptoms(hours=hours, category=cat)
    return [s.to_dict() for s in symptoms]


@router.post("/analyze")
async def analyze_root_cause(
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    """Analyze root cause of recent symptoms."""
    service = RootCauseHelperService()
    analysis = await service.analyze(hours=hours)
    return analysis.to_dict()


@router.post("/analyze-error")
async def analyze_error(
    request: AnalyzeErrorRequest,
) -> dict[str, Any]:
    """Analyze specific error."""
    service = RootCauseHelperService()
    analysis = await service.analyze_error(
        error_message=request.error_message,
        stack_trace=request.stack_trace,
        context=request.context,
    )
    return analysis.to_dict()


@router.get("/history")
async def get_analysis_history(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Get analysis history."""
    service = RootCauseHelperService()
    analyses = await service.get_analysis_history(limit=limit)
    return [a.to_dict() for a in analyses]


@router.get("/common-causes")
async def get_common_causes(
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, int]:
    """Get common root causes."""
    service = RootCauseHelperService()
    return await service.get_common_causes(days=days)


# Reference endpoints
@router.get("/reference/categories")
async def list_symptom_categories() -> list[str]:
    """List available symptom categories."""
    return [c.value for c in SymptomCategory]
