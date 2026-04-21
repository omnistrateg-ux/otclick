"""Environment guardrails API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.environment_guardrails import (
    ActionCategory,
    EnvironmentGuardrailsService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/guardrails", tags=["guardrails"])


# Request models
class CheckActionRequest(BaseModel):
    """Check action request."""

    action: str
    actor: str
    details: dict[str, Any] | None = None
    batch_size: int = 1


# Endpoints
@router.get("/environment")
async def get_current_environment() -> dict[str, Any]:
    """Get current environment info."""
    service = EnvironmentGuardrailsService()
    env = service.detect_environment()
    config = service.get_config(env)
    return config.to_dict()


@router.post("/check")
async def check_action(
    request: CheckActionRequest,
) -> dict[str, Any]:
    """Check if action is allowed.

    Args:
        request: Action check request

    Returns:
        Check result
    """
    service = EnvironmentGuardrailsService()

    try:
        action = ActionCategory(request.action)
    except ValueError:
        valid = [a.value for a in ActionCategory]
        raise HTTPException(400, f"Invalid action. Valid: {valid}")

    return await service.check_action(
        action=action,
        actor=request.actor,
        details=request.details,
        batch_size=request.batch_size,
    )


@router.get("/violations")
async def get_violations(
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Get guardrail violations."""
    service = EnvironmentGuardrailsService()
    violations = await service.get_violations(hours=hours, limit=limit)
    return [v.to_dict() for v in violations]


# Reference endpoints
@router.get("/reference/action-categories")
async def list_action_categories() -> list[str]:
    """List available action categories."""
    return [a.value for a in ActionCategory]
