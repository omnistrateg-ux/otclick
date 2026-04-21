"""Deployment safety and feature flags API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.deployment_safety import DeploymentSafetyService
from app.services.feature_flags import FeatureFlagsService, FlagStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["deployment"])


# Request models
class CreateDeploymentRequest(BaseModel):
    """Create deployment request."""

    version: str
    environment: str
    created_by: str
    notes: str | None = None


class ApproveDeploymentRequest(BaseModel):
    """Approve deployment request."""

    approved_by: str


class UpdateFlagRequest(BaseModel):
    """Update flag request."""

    status: str | None = None
    rollout_percentage: int | None = None
    allowed_users: list[str] | None = None
    allowed_segments: list[str] | None = None
    actor: str


# Deployment endpoints
@router.post("/deployments")
async def create_deployment(
    request: CreateDeploymentRequest,
) -> dict[str, Any]:
    """Create deployment plan with safety checks."""
    service = DeploymentSafetyService()
    plan = await service.create_deployment_plan(
        version=request.version,
        environment=request.environment,
        created_by=request.created_by,
        notes=request.notes,
    )
    return plan.to_dict()


@router.get("/deployments")
async def list_deployments(
    environment: str = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """List deployment plans."""
    service = DeploymentSafetyService()
    plans = await service.get_deployment_history(environment=environment, limit=limit)
    return [p.to_dict() for p in plans]


@router.get("/deployments/{plan_id}")
async def get_deployment(plan_id: str) -> dict[str, Any]:
    """Get deployment plan by ID."""
    service = DeploymentSafetyService()
    plan = await service.get_plan(plan_id)
    if not plan:
        raise HTTPException(404, "Deployment plan not found")
    return plan.to_dict()


@router.post("/deployments/{plan_id}/approve")
async def approve_deployment(
    plan_id: str,
    request: ApproveDeploymentRequest,
) -> dict[str, Any]:
    """Approve deployment plan."""
    service = DeploymentSafetyService()
    plan = await service.approve_deployment(plan_id, request.approved_by)
    if not plan:
        raise HTTPException(404, "Deployment plan not found or not pending")
    return plan.to_dict()


@router.get("/deployments/{plan_id}/rollback")
async def get_rollback_plan(plan_id: str) -> dict[str, Any]:
    """Get rollback plan for deployment."""
    service = DeploymentSafetyService()
    rollback = await service.get_rollback_plan(plan_id)
    if not rollback:
        raise HTTPException(404, "No rollback plan available")
    return rollback.to_dict()


# Feature flags endpoints
@router.get("/flags")
async def list_flags() -> list[dict[str, Any]]:
    """List all feature flags."""
    service = FeatureFlagsService()
    flags = await service.list_flags()
    return [f.to_dict() for f in flags]


@router.get("/flags/{flag_key}")
async def get_flag(flag_key: str) -> dict[str, Any]:
    """Get feature flag by key."""
    service = FeatureFlagsService()
    flag = await service.get_flag(flag_key)
    if not flag:
        raise HTTPException(404, f"Flag {flag_key} not found")
    return flag.to_dict()


@router.get("/flags/{flag_key}/evaluate")
async def evaluate_flag(
    flag_key: str,
    user_id: str = Query(default=None),
    segment: str = Query(default=None),
) -> dict[str, Any]:
    """Evaluate feature flag."""
    service = FeatureFlagsService()
    evaluation = await service.evaluate(flag_key, user_id, segment)
    return evaluation.to_dict()


@router.put("/flags/{flag_key}")
async def update_flag(
    flag_key: str,
    request: UpdateFlagRequest,
) -> dict[str, Any]:
    """Update feature flag."""
    service = FeatureFlagsService()

    updates = {}
    if request.status:
        updates["status"] = request.status
    if request.rollout_percentage is not None:
        updates["rollout_percentage"] = request.rollout_percentage
    if request.allowed_users is not None:
        updates["allowed_users"] = request.allowed_users
    if request.allowed_segments is not None:
        updates["allowed_segments"] = request.allowed_segments

    flag = await service.update_flag(flag_key, updates, request.actor)
    if not flag:
        raise HTTPException(404, f"Flag {flag_key} not found")
    return flag.to_dict()


@router.get("/flags/audit")
async def get_flag_audit(
    flag_key: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get flag audit log."""
    service = FeatureFlagsService()
    entries = await service.get_audit_log(flag_key=flag_key, limit=limit)
    return [e.to_dict() for e in entries]


# Reference endpoints
@router.get("/reference/flag-statuses")
async def list_flag_statuses() -> list[str]:
    """List available flag statuses."""
    return [s.value for s in FlagStatus]
