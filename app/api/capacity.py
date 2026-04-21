"""Capacity Planning and Analytics API endpoints.

Manager capacity, workload forecasting, and cohort analytics.
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.capacity_planning import (
    CapacityPlanningService,
)
from app.services.cohort_analytics import (
    CohortAnalyticsService,
    CohortType,
    AnomalySeverity,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/capacity", tags=["capacity"])


# ============================================================================
# Request/Response Models
# ============================================================================


class SetManagerConfigRequest(BaseModel):
    """Set manager config request."""

    name: str | None = None
    max_handoffs: int | None = None
    max_deals: int | None = None
    skills: list[str] | None = None
    segments: list[str] | None = None
    is_active: bool | None = None


class SetUnavailableRequest(BaseModel):
    """Set manager unavailable request."""

    until: str | None = None  # ISO datetime
    reason: str | None = None


# ============================================================================
# Manager Capacity Endpoints
# ============================================================================


@router.get("/managers/{manager_id}")
async def get_manager_capacity(
    manager_id: str,
) -> dict[str, Any]:
    """Get capacity for a manager.

    Args:
        manager_id: Manager ID

    Returns:
        Manager capacity
    """
    service = CapacityPlanningService()
    capacity = await service.get_manager_capacity(manager_id)

    if not capacity:
        raise HTTPException(404, f"Manager {manager_id} not found")

    return capacity.to_dict()


@router.put("/managers/{manager_id}")
async def set_manager_config(
    manager_id: str,
    request: SetManagerConfigRequest,
) -> dict[str, Any]:
    """Configure manager capacity settings.

    Args:
        manager_id: Manager ID
        request: Config request

    Returns:
        Updated capacity
    """
    service = CapacityPlanningService()

    capacity = await service.set_manager_config(
        manager_id=manager_id,
        name=request.name,
        max_handoffs=request.max_handoffs,
        max_deals=request.max_deals,
        skills=request.skills,
        segments=request.segments,
        is_active=request.is_active,
    )

    return capacity.to_dict()


@router.post("/managers/{manager_id}/unavailable")
async def set_manager_unavailable(
    manager_id: str,
    request: SetUnavailableRequest,
) -> dict[str, Any]:
    """Mark manager as unavailable.

    Args:
        manager_id: Manager ID
        request: Unavailability details

    Returns:
        Updated capacity
    """
    service = CapacityPlanningService()

    until = None
    if request.until:
        try:
            until = datetime.fromisoformat(request.until)
        except ValueError:
            raise HTTPException(400, "Invalid datetime format for 'until'")

    capacity = await service.set_manager_unavailable(
        manager_id=manager_id,
        until=until,
        reason=request.reason,
    )

    return capacity.to_dict()


@router.get("/managers")
async def get_available_managers(
    segment: str = Query(default=None),
    skill: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get managers with available capacity.

    Args:
        segment: Filter by segment
        skill: Filter by skill

    Returns:
        List of available managers
    """
    service = CapacityPlanningService()
    managers = await service.get_available_managers(segment, skill)
    return [m.to_dict() for m in managers]


@router.get("/best-assignee")
async def get_best_assignee(
    segment: str = Query(default=None),
    skill: str = Query(default=None),
    exclude: str = Query(default=None),
) -> dict[str, Any]:
    """Get best manager to assign work to.

    Args:
        segment: Preferred segment
        skill: Required skill
        exclude: Comma-separated manager IDs to exclude

    Returns:
        Best manager ID
    """
    service = CapacityPlanningService()

    exclude_list = exclude.split(",") if exclude else None
    manager_id = await service.get_best_assignee(segment, skill, exclude_list)

    return {
        "manager_id": manager_id,
        "available": manager_id is not None,
    }


# ============================================================================
# Team Capacity Endpoints
# ============================================================================


@router.get("/team")
async def get_team_capacity() -> dict[str, Any]:
    """Get team-wide capacity summary.

    Returns:
        Team capacity
    """
    service = CapacityPlanningService()
    capacity = await service.get_team_capacity()
    return capacity.to_dict()


@router.get("/forecast")
async def forecast_workload(
    days: int = Query(default=7, ge=1, le=30),
) -> dict[str, Any]:
    """Forecast workload for coming period.

    Args:
        days: Days to forecast

    Returns:
        Workload forecast
    """
    service = CapacityPlanningService()
    forecast = await service.forecast_workload(days)
    return forecast.to_dict()


@router.get("/timeline")
async def get_capacity_timeline(
    days: int = Query(default=14, ge=1, le=90),
) -> list[dict[str, Any]]:
    """Get capacity utilization timeline.

    Args:
        days: Days of history

    Returns:
        Timeline data
    """
    service = CapacityPlanningService()
    timeline = await service.get_capacity_timeline(days)
    return timeline


# ============================================================================
# Cohort Analytics Endpoints
# ============================================================================


@router.get("/cohorts/weekly")
async def get_weekly_cohorts(
    weeks: int = Query(default=12, ge=1, le=52),
) -> list[dict[str, Any]]:
    """Get weekly cohort analysis.

    Args:
        weeks: Number of weeks

    Returns:
        Weekly cohort metrics
    """
    service = CohortAnalyticsService()
    cohorts = await service.get_weekly_cohorts(weeks)
    return [c.to_dict() for c in cohorts]


@router.get("/cohorts/sources")
async def get_source_cohorts() -> list[dict[str, Any]]:
    """Get cohort analysis by lead source.

    Returns:
        Source cohort metrics
    """
    service = CohortAnalyticsService()
    cohorts = await service.get_source_cohorts()
    return [c.to_dict() for c in cohorts]


@router.get("/cohorts/{cohort_type}/{cohort_value}")
async def get_cohort_metrics(
    cohort_type: str,
    cohort_value: str,
) -> dict[str, Any]:
    """Get metrics for a specific cohort.

    Args:
        cohort_type: Type of cohort
        cohort_value: Cohort identifier

    Returns:
        Cohort metrics
    """
    service = CohortAnalyticsService()

    try:
        ct = CohortType(cohort_type)
    except ValueError:
        valid_types = [t.value for t in CohortType]
        raise HTTPException(400, f"Invalid cohort type. Valid: {valid_types}")

    cohort = await service.get_cohort_metrics(ct, cohort_value)

    if not cohort:
        raise HTTPException(404, f"Cohort {cohort_type}/{cohort_value} not found")

    return cohort.to_dict()


@router.get("/cohorts/compare")
async def compare_cohorts(
    cohort_a_type: str,
    cohort_a_value: str,
    cohort_b_type: str,
    cohort_b_value: str,
) -> dict[str, Any]:
    """Compare two cohorts.

    Args:
        cohort_a_type: First cohort type
        cohort_a_value: First cohort value
        cohort_b_type: Second cohort type
        cohort_b_value: Second cohort value

    Returns:
        Cohort comparison
    """
    service = CohortAnalyticsService()

    try:
        ct_a = CohortType(cohort_a_type)
        ct_b = CohortType(cohort_b_type)
    except ValueError:
        valid_types = [t.value for t in CohortType]
        raise HTTPException(400, f"Invalid cohort type. Valid: {valid_types}")

    comparison = await service.compare_cohorts(
        ct_a, cohort_a_value,
        ct_b, cohort_b_value,
    )

    if not comparison:
        raise HTTPException(404, "One or both cohorts not found")

    return comparison.to_dict()


@router.get("/retention")
async def get_retention_matrix(
    weeks: int = Query(default=8, ge=1, le=24),
) -> dict[str, Any]:
    """Get retention matrix.

    Args:
        weeks: Number of weeks

    Returns:
        Retention matrix
    """
    service = CohortAnalyticsService()
    matrix = await service.get_retention_matrix(weeks)
    return matrix


# ============================================================================
# Anomaly Detection Endpoints
# ============================================================================


@router.get("/anomalies")
async def detect_anomalies(
    metric: str = Query(default=None),
    lookback_days: int = Query(default=30, ge=7, le=90),
) -> list[dict[str, Any]]:
    """Detect anomalies in metrics.

    Args:
        metric: Specific metric to check
        lookback_days: Days of history

    Returns:
        Detected anomalies
    """
    service = CohortAnalyticsService()
    anomalies = await service.detect_anomalies(metric, lookback_days)
    return [a.to_dict() for a in anomalies]


@router.get("/anomalies/history")
async def get_anomaly_history(
    days: int = Query(default=7, ge=1, le=30),
    severity: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get historical anomalies.

    Args:
        days: Days of history
        severity: Filter by severity

    Returns:
        Past anomalies
    """
    service = CohortAnalyticsService()

    sev = None
    if severity:
        try:
            sev = AnomalySeverity(severity)
        except ValueError:
            valid_sev = [s.value for s in AnomalySeverity]
            raise HTTPException(400, f"Invalid severity. Valid: {valid_sev}")

    anomalies = await service.get_anomaly_history(days, sev)
    return [a.to_dict() for a in anomalies]


@router.get("/analytics/summary")
async def get_analytics_summary(
    days: int = Query(default=7, ge=1, le=30),
) -> dict[str, Any]:
    """Get analytics summary.

    Args:
        days: Days to analyze

    Returns:
        Analytics summary
    """
    service = CohortAnalyticsService()
    summary = await service.get_analytics_summary(days)
    return summary


# ============================================================================
# Reference Data
# ============================================================================


@router.get("/cohort-types")
async def get_cohort_types() -> list[dict[str, str]]:
    """Get all cohort types.

    Returns:
        List of cohort types
    """
    return [{"type": t.value} for t in CohortType]


@router.get("/anomaly-severities")
async def get_anomaly_severities() -> list[dict[str, str]]:
    """Get all anomaly severities.

    Returns:
        List of severities
    """
    return [{"severity": s.value} for s in AnomalySeverity]
