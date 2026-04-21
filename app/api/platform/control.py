"""Control plane and policies API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.control_plane import (
    ControlAction,
    ControlPlaneService,
    ControlScope,
)
from app.services.policy_engine import (
    PolicyAction,
    PolicyEngineService,
    PolicyScope,
    PolicyType,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["control"])


# Request models
class IssueCommandRequest(BaseModel):
    """Issue command request."""

    action: str
    scope: str
    actor: str
    reason: str
    targets: list[str] | None = None


class CreatePolicyRequest(BaseModel):
    """Create policy request."""

    name: str
    description: str
    policy_type: str
    scope: str
    conditions: dict[str, Any]
    actions: list[str]
    priority: int = 0
    enabled: bool = True


class UpdatePolicyRequest(BaseModel):
    """Update policy request."""

    description: str | None = None
    conditions: dict[str, Any] | None = None
    actions: list[str] | None = None
    priority: int | None = None
    enabled: bool | None = None


class EvaluatePolicyRequest(BaseModel):
    """Evaluate policy request."""

    context: dict[str, Any]


# Control plane endpoints
@router.get("/control/state")
async def get_system_state() -> dict[str, Any]:
    """Get current system state."""
    service = ControlPlaneService()
    state = await service.get_system_state()
    return state.to_dict()


@router.post("/control/command")
async def issue_command(
    request: IssueCommandRequest,
) -> dict[str, Any]:
    """Issue control command."""
    service = ControlPlaneService()

    try:
        action = ControlAction(request.action)
    except ValueError:
        valid = [a.value for a in ControlAction]
        raise HTTPException(400, f"Invalid action. Valid: {valid}")

    try:
        scope = ControlScope(request.scope)
    except ValueError:
        valid = [s.value for s in ControlScope]
        raise HTTPException(400, f"Invalid scope. Valid: {valid}")

    command = await service.issue_command(
        action=action,
        scope=scope,
        actor=request.actor,
        reason=request.reason,
        targets=request.targets,
    )
    return command.to_dict()


@router.get("/control/commands")
async def get_command_history(
    action: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get command history."""
    service = ControlPlaneService()

    a = None
    if action:
        try:
            a = ControlAction(action)
        except ValueError:
            valid = [a.value for a in ControlAction]
            raise HTTPException(400, f"Invalid action. Valid: {valid}")

    commands = await service.get_command_history(action=a, limit=limit)
    return [c.to_dict() for c in commands]


@router.get("/control/metrics")
async def get_control_metrics() -> dict[str, Any]:
    """Get control plane metrics."""
    service = ControlPlaneService()
    return await service.get_metrics()


@router.post("/control/emergency/clear")
async def clear_emergency(
    actor: str,
    reason: str,
) -> dict[str, str]:
    """Clear emergency mode."""
    service = ControlPlaneService()
    success = await service.clear_emergency(actor, reason)
    if not success:
        raise HTTPException(400, "Not in emergency mode")
    return {"status": "cleared"}


# Policy endpoints
@router.get("/policies")
async def list_policies(
    policy_type: str = Query(default=None),
    scope: str = Query(default=None),
    enabled_only: bool = Query(default=False),
) -> list[dict[str, Any]]:
    """List policies."""
    service = PolicyEngineService()

    pt = None
    if policy_type:
        try:
            pt = PolicyType(policy_type)
        except ValueError:
            valid = [t.value for t in PolicyType]
            raise HTTPException(400, f"Invalid type. Valid: {valid}")

    sc = None
    if scope:
        try:
            sc = PolicyScope(scope)
        except ValueError:
            valid = [s.value for s in PolicyScope]
            raise HTTPException(400, f"Invalid scope. Valid: {valid}")

    policies = await service.list_policies(
        policy_type=pt,
        scope=sc,
        enabled_only=enabled_only,
    )
    return [p.to_dict() for p in policies]


@router.post("/policies")
async def create_policy(
    request: CreatePolicyRequest,
) -> dict[str, Any]:
    """Create policy."""
    from app.services.policy_engine import Policy

    service = PolicyEngineService()

    try:
        policy_type = PolicyType(request.policy_type)
    except ValueError:
        valid = [t.value for t in PolicyType]
        raise HTTPException(400, f"Invalid type. Valid: {valid}")

    try:
        scope = PolicyScope(request.scope)
    except ValueError:
        valid = [s.value for s in PolicyScope]
        raise HTTPException(400, f"Invalid scope. Valid: {valid}")

    actions = []
    for a in request.actions:
        try:
            actions.append(PolicyAction(a))
        except ValueError:
            valid = [a.value for a in PolicyAction]
            raise HTTPException(400, f"Invalid action. Valid: {valid}")

    policy = Policy(
        name=request.name,
        description=request.description,
        policy_type=policy_type,
        scope=scope,
        conditions=request.conditions,
        actions=actions,
        priority=request.priority,
        enabled=request.enabled,
    )

    result = await service.create_policy(policy)
    return result.to_dict()


@router.get("/policies/{name}")
async def get_policy(name: str) -> dict[str, Any]:
    """Get policy by name."""
    service = PolicyEngineService()
    policy = await service.get_policy(name)
    if not policy:
        raise HTTPException(404, "Policy not found")
    return policy.to_dict()


@router.put("/policies/{name}")
async def update_policy(
    name: str,
    request: UpdatePolicyRequest,
) -> dict[str, Any]:
    """Update policy."""
    service = PolicyEngineService()

    updates = {}
    if request.description is not None:
        updates["description"] = request.description
    if request.conditions is not None:
        updates["conditions"] = request.conditions
    if request.actions is not None:
        actions = []
        for a in request.actions:
            try:
                actions.append(PolicyAction(a))
            except ValueError:
                valid = [a.value for a in PolicyAction]
                raise HTTPException(400, f"Invalid action. Valid: {valid}")
        updates["actions"] = actions
    if request.priority is not None:
        updates["priority"] = request.priority
    if request.enabled is not None:
        updates["enabled"] = request.enabled

    policy = await service.update_policy(name, updates)
    if not policy:
        raise HTTPException(404, "Policy not found")
    return policy.to_dict()


@router.delete("/policies/{name}")
async def delete_policy(name: str) -> dict[str, str]:
    """Delete policy."""
    service = PolicyEngineService()
    success = await service.delete_policy(name)
    if not success:
        raise HTTPException(404, "Policy not found")
    return {"status": "deleted"}


@router.post("/policies/evaluate")
async def evaluate_policies(
    request: EvaluatePolicyRequest,
) -> dict[str, Any]:
    """Evaluate policies against context."""
    service = PolicyEngineService()
    result = await service.evaluate(request.context)
    return result.to_dict()


@router.get("/policies/violations")
async def get_policy_violations(
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get policy violations."""
    service = PolicyEngineService()
    violations = await service.get_violations(limit=limit)
    return [v.to_dict() for v in violations]


@router.post("/policies/initialize")
async def initialize_default_policies() -> dict[str, str]:
    """Initialize default policies."""
    service = PolicyEngineService()
    await service.initialize_defaults()
    return {"status": "initialized"}


# Reference endpoints
@router.get("/reference/control-actions")
async def list_control_actions() -> list[str]:
    """List available control actions."""
    return [a.value for a in ControlAction]


@router.get("/reference/control-scopes")
async def list_control_scopes() -> list[str]:
    """List available control scopes."""
    return [s.value for s in ControlScope]


@router.get("/reference/policy-types")
async def list_policy_types() -> list[str]:
    """List available policy types."""
    return [t.value for t in PolicyType]


@router.get("/reference/policy-scopes")
async def list_policy_scopes() -> list[str]:
    """List available policy scopes."""
    return [s.value for s in PolicyScope]


@router.get("/reference/policy-actions")
async def list_policy_actions() -> list[str]:
    """List available policy actions."""
    return [a.value for a in PolicyAction]
