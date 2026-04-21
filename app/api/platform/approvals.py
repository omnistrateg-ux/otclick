"""Approval gates API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.approval_gates import (
    ApprovalGatesService,
    ActionCategory as ApprovalCategory,
    RiskLevel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["approvals"])


# Request models
class RequestApprovalRequest(BaseModel):
    """Request approval request."""

    action: str
    category: str
    requester: str
    reason: str = ""
    context: dict[str, Any] | None = None


class ApprovalDecisionRequest(BaseModel):
    """Approval decision request."""

    actor: str
    role: str = ""
    reason: str | None = None


# Endpoints
@router.get("/rules")
async def list_approval_rules() -> list[dict[str, Any]]:
    """List approval rules."""
    service = ApprovalGatesService()
    rules = await service.list_rules()
    return [r.to_dict() for r in rules]


@router.post("/request")
async def request_approval(
    request: RequestApprovalRequest,
) -> dict[str, Any]:
    """Request approval for action."""
    service = ApprovalGatesService()

    try:
        category = ApprovalCategory(request.category)
    except ValueError:
        valid = [c.value for c in ApprovalCategory]
        raise HTTPException(400, f"Invalid category. Valid: {valid}")

    try:
        approval = await service.request_approval(
            action=request.action,
            category=category,
            requester=request.requester,
            reason=request.reason,
            context=request.context,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return approval.to_dict()


@router.get("/pending")
async def list_pending_approvals(
    category: str = Query(default=None),
) -> list[dict[str, Any]]:
    """List pending approvals."""
    service = ApprovalGatesService()

    cat = None
    if category:
        try:
            cat = ApprovalCategory(category)
        except ValueError:
            valid = [c.value for c in ApprovalCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    requests = await service.list_pending(category=cat)
    return [r.to_dict() for r in requests]


@router.get("/{request_id}")
async def get_approval_request(request_id: str) -> dict[str, Any]:
    """Get approval request."""
    service = ApprovalGatesService()
    request = await service.get_request(request_id)
    if not request:
        raise HTTPException(404, "Request not found")
    return request.to_dict()


@router.post("/{request_id}/approve")
async def approve_request(
    request_id: str,
    request: ApprovalDecisionRequest,
) -> dict[str, Any]:
    """Approve a request."""
    service = ApprovalGatesService()
    approval = await service.approve(
        request_id=request_id,
        approver=request.actor,
        approver_role=request.role,
        reason=request.reason,
    )
    if not approval:
        raise HTTPException(404, "Request not found")
    return approval.to_dict()


@router.post("/{request_id}/reject")
async def reject_request(
    request_id: str,
    request: ApprovalDecisionRequest,
) -> dict[str, Any]:
    """Reject a request."""
    service = ApprovalGatesService()

    if not request.reason:
        raise HTTPException(400, "Reason required for rejection")

    approval = await service.reject(
        request_id=request_id,
        rejector=request.actor,
        reason=request.reason,
    )
    if not approval:
        raise HTTPException(404, "Request not found")
    return approval.to_dict()


@router.get("/{request_id}/check")
async def check_approval_status(request_id: str) -> dict[str, Any]:
    """Check approval status."""
    service = ApprovalGatesService()
    approved, message = await service.check_approval(request_id)
    return {"approved": approved, "message": message}


@router.post("/initialize")
async def initialize_approval_rules() -> dict[str, int]:
    """Initialize default approval rules."""
    service = ApprovalGatesService()
    count = await service.initialize_defaults()
    return {"rules_created": count}


# Reference endpoints
@router.get("/reference/categories")
async def list_approval_categories() -> list[str]:
    """List available approval categories."""
    return [c.value for c in ApprovalCategory]


@router.get("/reference/risk-levels")
async def list_risk_levels() -> list[str]:
    """List available risk levels."""
    return [r.value for r in RiskLevel]
