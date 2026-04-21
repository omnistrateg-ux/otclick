"""Operational cockpit API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.services.ops_cockpit import (
    OpsCockpitService,
    ActionPriority as CockpitActionPriority,
    ActionCategory as CockpitActionCategory,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cockpit", tags=["cockpit"])


# Endpoints
@router.get("")
async def get_cockpit() -> dict[str, Any]:
    """Get full operational cockpit.

    Returns unified view of all operational data including:
    - Health status
    - Active incidents
    - Queue status
    - SLO/error budgets
    - Cost overview
    - Drift status
    - Pending approvals
    - Risky actions
    - Recommended actions
    """
    service = OpsCockpitService()
    cockpit = await service.get_cockpit()
    return cockpit.to_dict()


@router.get("/status")
async def get_quick_status() -> dict[str, Any]:
    """Get quick status overview.

    Lightweight endpoint for dashboards and monitoring.
    """
    service = OpsCockpitService()
    return await service.get_quick_status()


@router.get("/actions")
async def get_recommended_actions(
    priority: str = Query(default=None),
    category: str = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Get recommended actions.

    Args:
        priority: Filter by priority (critical, high, medium, low)
        category: Filter by category
        limit: Max actions to return
    """
    service = OpsCockpitService()

    prio = None
    if priority:
        try:
            prio = CockpitActionPriority(priority)
        except ValueError:
            valid = [p.value for p in CockpitActionPriority]
            raise HTTPException(400, f"Invalid priority. Valid: {valid}")

    cat = None
    if category:
        try:
            cat = CockpitActionCategory(category)
        except ValueError:
            valid = [c.value for c in CockpitActionCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    actions = await service.get_actions_only(priority=prio, category=cat, limit=limit)
    return [a.to_dict() for a in actions]


@router.get("/health")
async def get_health_summary() -> dict[str, Any]:
    """Get health summary only."""
    service = OpsCockpitService()
    summary = await service._get_health_summary()
    return summary.to_dict()


@router.get("/incidents")
async def get_cockpit_incidents() -> dict[str, Any]:
    """Get incident summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_incident_summary()
    return summary.to_dict()


@router.get("/queues")
async def get_cockpit_queues() -> dict[str, Any]:
    """Get queue summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_queue_summary()
    return summary.to_dict()


@router.get("/slos")
async def get_cockpit_slos() -> dict[str, Any]:
    """Get SLO summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_slo_summary()
    return summary.to_dict()


@router.get("/costs")
async def get_cockpit_costs() -> dict[str, Any]:
    """Get cost summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_cost_summary()
    return summary.to_dict()


@router.get("/drift")
async def get_cockpit_drift() -> dict[str, Any]:
    """Get drift summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_drift_summary()
    return summary.to_dict()


@router.get("/approvals")
async def get_cockpit_approvals() -> dict[str, Any]:
    """Get approval summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_approval_summary()
    return summary.to_dict()


@router.get("/risky-actions")
async def get_cockpit_risky_actions() -> dict[str, Any]:
    """Get risky actions summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_risky_actions_summary()
    return summary.to_dict()


# Reference endpoints
@router.get("/reference/priorities")
async def list_action_priorities() -> list[str]:
    """List available action priorities."""
    return [p.value for p in CockpitActionPriority]


@router.get("/reference/categories")
async def list_cockpit_categories() -> list[str]:
    """List available cockpit action categories."""
    return [c.value for c in CockpitActionCategory]
