"""Revenue Loop API endpoints.

Deal management and pipeline tracking.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.revenue_loop import (
    RevenueLoopService,
    DealStage,
    LostReason,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/revenue", tags=["revenue"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateDealRequest(BaseModel):
    """Create deal request."""

    lead_id: str
    account_id: str
    value: float = Field(..., gt=0)
    manager_id: str | None = None
    campaign_id: str | None = None
    source: str | None = None
    expected_close_days: int = 30


class AdvanceStageRequest(BaseModel):
    """Advance stage request."""

    stage: str
    actor: str
    notes: str | None = None


class CloseLostRequest(BaseModel):
    """Close lost request."""

    reason: str
    actor: str
    notes: str | None = None


class CloseWonRequest(BaseModel):
    """Close won request."""

    actual_revenue: float = Field(..., gt=0)
    actor: str
    notes: str | None = None


class DealResponse(BaseModel):
    """Deal response."""

    id: str
    lead_id: str
    account_id: str
    stage: str
    value: float
    probability: float
    manager_id: str | None
    created_at: str | None
    expected_close_date: str | None


# ============================================================================
# Deal Endpoints
# ============================================================================


@router.post("/deals")
async def create_deal(
    request: CreateDealRequest,
) -> dict[str, Any]:
    """Create a new deal.

    Args:
        request: Deal creation request

    Returns:
        Created deal
    """
    from datetime import datetime, timedelta, timezone

    service = RevenueLoopService()

    expected_close = datetime.now(timezone.utc) + timedelta(days=request.expected_close_days)

    deal = await service.create_deal(
        lead_id=request.lead_id,
        account_id=request.account_id,
        value=request.value,
        manager_id=request.manager_id,
        campaign_id=request.campaign_id,
        source=request.source,
        expected_close_date=expected_close,
    )

    return deal.to_dict()


@router.get("/deals/{deal_id}")
async def get_deal(
    deal_id: str,
) -> dict[str, Any]:
    """Get deal by ID.

    Args:
        deal_id: Deal ID

    Returns:
        Deal details
    """
    service = RevenueLoopService()
    deal = await service.get_deal(deal_id)

    if not deal:
        raise HTTPException(404, f"Deal {deal_id} not found")

    return deal.to_dict()


@router.post("/deals/{deal_id}/advance")
async def advance_deal_stage(
    deal_id: str,
    request: AdvanceStageRequest,
) -> dict[str, Any]:
    """Advance deal to next stage.

    Args:
        deal_id: Deal ID
        request: Stage advance request

    Returns:
        Updated deal
    """
    service = RevenueLoopService()

    try:
        stage = DealStage(request.stage)
    except ValueError:
        valid_stages = [s.value for s in DealStage]
        raise HTTPException(400, f"Invalid stage. Valid: {valid_stages}")

    try:
        deal = await service.advance_stage(
            deal_id=deal_id,
            new_stage=stage,
            actor=request.actor,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return deal.to_dict()


@router.post("/deals/{deal_id}/close-lost")
async def close_deal_lost(
    deal_id: str,
    request: CloseLostRequest,
) -> dict[str, Any]:
    """Close deal as lost.

    Args:
        deal_id: Deal ID
        request: Close lost request

    Returns:
        Updated deal
    """
    service = RevenueLoopService()

    try:
        reason = LostReason(request.reason)
    except ValueError:
        valid_reasons = [r.value for r in LostReason]
        raise HTTPException(400, f"Invalid reason. Valid: {valid_reasons}")

    try:
        deal = await service.close_lost(
            deal_id=deal_id,
            reason=reason,
            actor=request.actor,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return deal.to_dict()


@router.post("/deals/{deal_id}/close-won")
async def close_deal_won(
    deal_id: str,
    request: CloseWonRequest,
) -> dict[str, Any]:
    """Close deal as won.

    Args:
        deal_id: Deal ID
        request: Close won request

    Returns:
        Updated deal
    """
    service = RevenueLoopService()

    try:
        deal = await service.close_won(
            deal_id=deal_id,
            actual_revenue=request.actual_revenue,
            actor=request.actor,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return deal.to_dict()


@router.get("/deals/manager/{manager_id}")
async def get_manager_deals(
    manager_id: str,
    active_only: bool = Query(default=True),
) -> list[dict[str, Any]]:
    """Get deals for a manager.

    Args:
        manager_id: Manager ID
        active_only: Only active deals

    Returns:
        List of deals
    """
    service = RevenueLoopService()
    deals = await service.get_deals_by_manager(manager_id, active_only)
    return [d.to_dict() for d in deals]


# ============================================================================
# Pipeline Metrics
# ============================================================================


@router.get("/pipeline/metrics")
async def get_pipeline_metrics(
    days: int = Query(default=30, ge=1, le=90),
    campaign_id: str = Query(default=None),
) -> dict[str, Any]:
    """Get pipeline metrics.

    Args:
        days: Days to analyze
        campaign_id: Filter by campaign

    Returns:
        Pipeline metrics
    """
    service = RevenueLoopService()
    metrics = await service.get_pipeline_metrics(days=days, campaign_id=campaign_id)
    return metrics.to_dict()


@router.get("/pipeline/conversion-rates")
async def get_conversion_rates() -> list[dict[str, Any]]:
    """Get stage conversion rates.

    Returns:
        Conversion rates between stages
    """
    service = RevenueLoopService()
    rates = await service.get_conversion_rates()
    return [r.to_dict() for r in rates]


@router.get("/stages")
async def get_deal_stages() -> list[dict[str, Any]]:
    """Get all deal stages with probabilities.

    Returns:
        List of stages
    """
    from app.services.revenue_loop import STAGE_PROBABILITIES, STAGE_TRANSITIONS

    return [
        {
            "stage": stage.value,
            "probability": STAGE_PROBABILITIES.get(stage, 0.5),
            "allowed_transitions": [s.value for s in STAGE_TRANSITIONS.get(stage, [])],
        }
        for stage in DealStage
    ]


@router.get("/lost-reasons")
async def get_lost_reasons() -> list[dict[str, str]]:
    """Get all lost reasons.

    Returns:
        List of lost reasons
    """
    return [{"reason": r.value} for r in LostReason]
