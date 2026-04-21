"""Account Score and Forecasting API endpoints.

Account scoring, engagement tracking, and forecasting.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.account_score import AccountScoreService, AccountTier
from app.services.forecasting import ForecastingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounts", tags=["accounts"])


# ============================================================================
# Request/Response Models
# ============================================================================


class RecordEngagementRequest(BaseModel):
    """Record engagement request."""

    account_id: str
    engagement_type: str  # open, click, reply, meeting
    metadata: dict[str, Any] | None = None


class AccountScoreResponse(BaseModel):
    """Account score response."""

    account_id: str
    overall_score: float
    tier: str
    engagement_level: str
    signals: list[str]
    recommendations: list[str]


# ============================================================================
# Account Score Endpoints
# ============================================================================


@router.get("/{account_id}/score")
async def get_account_score(
    account_id: str,
    lead_id: str = Query(default=None),
) -> dict[str, Any]:
    """Calculate and get account score.

    Args:
        account_id: Account/company ID
        lead_id: Optional associated lead ID

    Returns:
        Account score
    """
    service = AccountScoreService()
    score = await service.calculate_account_score(account_id, lead_id)
    return score.to_dict()


@router.get("/{account_id}/health")
async def get_account_health(
    account_id: str,
) -> list[dict[str, Any]]:
    """Get account health indicators.

    Args:
        account_id: Account ID

    Returns:
        Health indicators
    """
    service = AccountScoreService()
    indicators = await service.get_health_indicators(account_id)
    return [i.to_dict() for i in indicators]


@router.post("/engagement")
async def record_engagement(
    request: RecordEngagementRequest,
) -> dict[str, Any]:
    """Record an engagement event.

    Args:
        request: Engagement details

    Returns:
        Success status
    """
    service = AccountScoreService()

    valid_types = ["open", "click", "reply", "meeting", "call"]
    if request.engagement_type not in valid_types:
        raise HTTPException(400, f"Invalid engagement_type. Valid: {valid_types}")

    await service.record_engagement(
        account_id=request.account_id,
        engagement_type=request.engagement_type,
        metadata=request.metadata,
    )

    return {
        "success": True,
        "account_id": request.account_id,
        "engagement_type": request.engagement_type,
    }


@router.get("/{account_id}/engagement/timeline")
async def get_engagement_timeline(
    account_id: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Get engagement timeline for account.

    Args:
        account_id: Account ID
        limit: Max events

    Returns:
        Timeline events
    """
    service = AccountScoreService()
    timeline = await service.get_engagement_timeline(account_id, limit)
    return timeline


@router.get("/top")
async def get_top_accounts(
    limit: int = Query(default=20, ge=1, le=100),
    tier: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get top scored accounts.

    Args:
        limit: Max accounts
        tier: Filter by tier

    Returns:
        Top accounts
    """
    service = AccountScoreService()

    tier_filter = None
    if tier:
        try:
            tier_filter = AccountTier(tier)
        except ValueError:
            valid_tiers = [t.value for t in AccountTier]
            raise HTTPException(400, f"Invalid tier. Valid: {valid_tiers}")

    accounts = await service.get_top_accounts(limit, tier_filter)
    return accounts


@router.get("/tiers")
async def get_account_tiers() -> list[dict[str, Any]]:
    """Get all account tiers.

    Returns:
        List of tiers with score ranges
    """
    return [
        {"tier": "enterprise", "min_score": 80, "description": "Large enterprise accounts"},
        {"tier": "mid_market", "min_score": 60, "description": "Mid-market companies"},
        {"tier": "smb", "min_score": 40, "description": "Small-medium businesses"},
        {"tier": "startup", "min_score": 20, "description": "Early-stage companies"},
        {"tier": "unqualified", "min_score": 0, "description": "Not yet qualified"},
    ]


# ============================================================================
# Forecasting Endpoints
# ============================================================================


@router.get("/forecast/summary")
async def get_forecast_summary(
    days: int = Query(default=30, ge=7, le=90),
) -> dict[str, Any]:
    """Get comprehensive forecast summary.

    Args:
        days: Forecast period

    Returns:
        Forecast summary
    """
    service = ForecastingService()
    summary = await service.get_forecast_summary(days)
    return summary.to_dict()


@router.get("/forecast/conversions")
async def get_conversion_forecasts(
    days: int = Query(default=30, ge=7, le=90),
) -> list[dict[str, Any]]:
    """Get conversion rate forecasts.

    Args:
        days: Forecast period

    Returns:
        Conversion forecasts
    """
    service = ForecastingService()
    forecasts = await service.forecast_conversion_rates(days)
    return [f.to_dict() for f in forecasts]


@router.get("/forecast/pipeline")
async def get_pipeline_forecast(
    days: int = Query(default=30, ge=7, le=90),
) -> dict[str, Any]:
    """Get pipeline revenue forecast.

    Args:
        days: Forecast period

    Returns:
        Pipeline forecast
    """
    service = ForecastingService()
    forecast = await service.forecast_pipeline(days)
    return forecast.to_dict()


@router.get("/forecast/segments")
async def get_segment_forecasts(
    days: int = Query(default=30, ge=7, le=90),
) -> list[dict[str, Any]]:
    """Get forecasts by segment.

    Args:
        days: Forecast period

    Returns:
        Segment forecasts
    """
    service = ForecastingService()
    forecasts = await service.forecast_by_segment(days)
    return [f.to_dict() for f in forecasts]


@router.get("/forecast/metrics/{metric}/history")
async def get_metric_history(
    metric: str,
    days: int = Query(default=30, ge=7, le=90),
) -> list[dict[str, Any]]:
    """Get historical metric data.

    Args:
        metric: Metric name
        days: Days to retrieve

    Returns:
        Historical data
    """
    service = ForecastingService()

    valid_metrics = ["reply_rate", "qualified_rate", "handoff_rate", "win_rate"]
    if metric not in valid_metrics:
        raise HTTPException(400, f"Invalid metric. Valid: {valid_metrics}")

    history = await service.get_historical_metrics(metric, days)
    return history


@router.post("/forecast/record")
async def record_metric_data(
    metric: str,
    numerator: int,
    denominator: int,
    segment: str = Query(default=None),
) -> dict[str, Any]:
    """Record metric data for forecasting.

    Args:
        metric: Metric name
        numerator: Metric numerator
        denominator: Metric denominator
        segment: Optional segment

    Returns:
        Success status
    """
    service = ForecastingService()

    await service.record_metric_data(
        metric=metric,
        numerator=numerator,
        denominator=denominator,
        segment=segment,
    )

    return {
        "success": True,
        "metric": metric,
        "rate": round(numerator / denominator, 4) if denominator > 0 else 0,
    }
