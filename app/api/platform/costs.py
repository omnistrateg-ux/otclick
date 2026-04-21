"""Cost observability API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.cost_observability import (
    CostCategory,
    CostObservabilityService,
    CostPeriod,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/costs", tags=["costs"])


# Request models
class SetBudgetRequest(BaseModel):
    """Set budget request."""

    category: str | None = None
    period: str
    budget_usd: float
    alert_threshold_percent: int = 80


# Endpoints
@router.get("/summary")
async def get_cost_summary(
    period: str = Query(default="daily"),
) -> dict[str, Any]:
    """Get cost summary for period."""
    service = CostObservabilityService()

    try:
        p = CostPeriod(period)
    except ValueError:
        valid = [p.value for p in CostPeriod]
        raise HTTPException(400, f"Invalid period. Valid: {valid}")

    summary = await service.get_summary(p)
    return summary.to_dict()


@router.get("/budgets")
async def get_budget_status(
    category: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get budget status."""
    service = CostObservabilityService()

    cat = None
    if category:
        try:
            cat = CostCategory(category)
        except ValueError:
            valid = [c.value for c in CostCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    statuses = await service.get_budget_status(cat)
    return [s.to_dict() for s in statuses]


@router.post("/budgets")
async def set_budget(
    request: SetBudgetRequest,
) -> dict[str, Any]:
    """Set cost budget."""
    from app.services.cost_observability import CostBudget

    service = CostObservabilityService()

    cat = None
    if request.category:
        try:
            cat = CostCategory(request.category)
        except ValueError:
            valid = [c.value for c in CostCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    try:
        period = CostPeriod(request.period)
    except ValueError:
        valid = [p.value for p in CostPeriod]
        raise HTTPException(400, f"Invalid period. Valid: {valid}")

    budget = CostBudget(
        category=cat,
        period=period,
        budget_usd=request.budget_usd,
        alert_threshold_percent=request.alert_threshold_percent,
    )

    result = await service.set_budget(budget)
    return result.to_dict()


@router.get("/trend")
async def get_cost_trend(
    category: str = Query(default=None),
    days: int = Query(default=30, ge=1, le=90),
) -> list[dict[str, Any]]:
    """Get cost trend."""
    service = CostObservabilityService()

    cat = None
    if category:
        try:
            cat = CostCategory(category)
        except ValueError:
            valid = [c.value for c in CostCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    return await service.get_cost_trend(category=cat, days=days)


# Reference endpoints
@router.get("/reference/categories")
async def list_cost_categories() -> list[str]:
    """List available cost categories."""
    return [c.value for c in CostCategory]


@router.get("/reference/periods")
async def list_cost_periods() -> list[str]:
    """List available cost periods."""
    return [p.value for p in CostPeriod]
