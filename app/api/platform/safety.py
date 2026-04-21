"""Decision safety API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.decision_safety import (
    DecisionSafetyService,
    ConfidenceLevel,
    AutoRemediationMode,
    RollbackUrgency,
    ReviewStatus,
    PolicyLearningType,
    ProdGuardLevel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/safety", tags=["safety"])


# Request models
class CalculateConfidenceRequest(BaseModel):
    """Calculate confidence request."""

    recommendation_type: str
    recommendation_id: str
    context: dict[str, Any]


class EvaluateRemediationRequest(BaseModel):
    """Evaluate auto-remediation request."""

    incident_id: str
    runbook_id: str
    context: dict[str, Any]


class SetRemediationModeRequest(BaseModel):
    """Set remediation mode request."""

    mode: str
    set_by: str


class GenerateRollbackRequest(BaseModel):
    """Generate rollback suggestion request."""

    action_id: str
    action_type: str
    action_details: dict[str, Any]


class GenerateReviewRequest(BaseModel):
    """Generate post-incident review request."""

    incident_id: str
    created_by: str


class LearnPoliciesRequest(BaseModel):
    """Learn policies from incident request."""

    incident_id: str


class ApprovePolicyRequest(BaseModel):
    """Approve learned policy request."""

    approved_by: str


class CheckGuardRequest(BaseModel):
    """Check guard request."""

    action: str
    actor: str
    context: dict[str, Any]
    bypass_reason: str | None = None


class ToggleGuardRequest(BaseModel):
    """Toggle guard request."""

    active: bool
    toggled_by: str


# Confidence scoring endpoints
@router.post("/confidence")
async def calculate_confidence(
    request: CalculateConfidenceRequest,
) -> dict[str, Any]:
    """Calculate confidence score for a recommendation.

    Scores based on:
    - Historical success rate
    - Pattern match strength
    - Data completeness
    - Similar incident count
    - Environmental stability
    """
    service = DecisionSafetyService()
    score = await service.calculate_confidence(
        recommendation_type=request.recommendation_type,
        recommendation_id=request.recommendation_id,
        context=request.context,
    )
    return score.to_dict()


# Auto-remediation endpoints
@router.post("/remediation/evaluate")
async def evaluate_auto_remediation(
    request: EvaluateRemediationRequest,
) -> dict[str, Any]:
    """Evaluate whether to auto-remediate.

    Returns decision (execute/defer/reject) with confidence
    and approval context.
    """
    service = DecisionSafetyService()
    decision = await service.evaluate_auto_remediation(
        incident_id=request.incident_id,
        runbook_id=request.runbook_id,
        context=request.context,
    )
    return decision.to_dict()


@router.post("/remediation/mode")
async def set_remediation_mode(
    request: SetRemediationModeRequest,
) -> dict[str, Any]:
    """Set auto-remediation mode.

    Modes:
    - disabled: No auto-remediation
    - safe_only: Only safe runbooks
    - with_approval: Requires pre-approval
    - full_auto: Full automation (dangerous)
    """
    service = DecisionSafetyService()

    try:
        mode = AutoRemediationMode(request.mode)
    except ValueError:
        valid = [m.value for m in AutoRemediationMode]
        raise HTTPException(400, f"Invalid mode. Valid: {valid}")

    return await service.set_auto_remediation_mode(mode, request.set_by)


@router.get("/remediation/mode")
async def get_remediation_mode() -> dict[str, Any]:
    """Get current auto-remediation mode."""
    service = DecisionSafetyService()
    mode = await service.get_auto_remediation_mode()
    return {"mode": mode.value}


# Rollback endpoints
@router.post("/rollback/generate")
async def generate_rollback_suggestion(
    request: GenerateRollbackRequest,
) -> dict[str, Any]:
    """Generate rollback suggestion for an action.

    Includes urgency level, rollback steps, and risk assessment.
    """
    service = DecisionSafetyService()
    suggestion = await service.generate_rollback_suggestion(
        action_id=request.action_id,
        action_type=request.action_type,
        action_details=request.action_details,
    )
    return suggestion.to_dict()


@router.get("/rollback/{action_id}")
async def get_rollback_suggestion(action_id: str) -> dict[str, Any]:
    """Get rollback suggestion for an action."""
    service = DecisionSafetyService()
    suggestion = await service.get_rollback_suggestion(action_id)
    if not suggestion:
        raise HTTPException(404, "Rollback suggestion not found")
    return suggestion.to_dict()


# Post-incident review endpoints
@router.post("/reviews/generate")
async def generate_post_incident_review(
    request: GenerateReviewRequest,
) -> dict[str, Any]:
    """Generate post-incident review (PIR).

    Includes timeline, root causes, action items, and lessons learned.
    """
    service = DecisionSafetyService()
    review = await service.generate_post_incident_review(
        incident_id=request.incident_id,
        created_by=request.created_by,
    )
    if not review:
        raise HTTPException(404, "Incident not found")
    return review.to_dict()


@router.get("/reviews/{review_id}")
async def get_review(review_id: str) -> dict[str, Any]:
    """Get post-incident review."""
    service = DecisionSafetyService()
    review = await service.get_review(review_id)
    if not review:
        raise HTTPException(404, "Review not found")
    return review.to_dict()


@router.get("/reviews")
async def list_reviews(
    status: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """List post-incident reviews."""
    service = DecisionSafetyService()

    review_status = None
    if status:
        try:
            review_status = ReviewStatus(status)
        except ValueError:
            valid = [s.value for s in ReviewStatus]
            raise HTTPException(400, f"Invalid status. Valid: {valid}")

    reviews = await service.list_reviews(status=review_status, limit=limit)
    return [r.to_dict() for r in reviews]


# Policy learning endpoints
@router.post("/policies/learn")
async def learn_policies_from_incident(
    request: LearnPoliciesRequest,
) -> list[dict[str, Any]]:
    """Learn policies from incident.

    Generates prevention, detection, and response policies
    based on incident analysis.
    """
    service = DecisionSafetyService()
    policies = await service.learn_policy_from_incident(request.incident_id)
    return [p.to_dict() for p in policies]


@router.get("/policies")
async def list_learned_policies(
    incident_id: str = Query(default=None),
    policy_type: str = Query(default=None),
    status: str = Query(default=None),
) -> list[dict[str, Any]]:
    """List learned policies."""
    service = DecisionSafetyService()

    ptype = None
    if policy_type:
        try:
            ptype = PolicyLearningType(policy_type)
        except ValueError:
            valid = [t.value for t in PolicyLearningType]
            raise HTTPException(400, f"Invalid policy_type. Valid: {valid}")

    policies = await service.list_learned_policies(
        incident_id=incident_id,
        policy_type=ptype,
        status=status,
    )
    return [p.to_dict() for p in policies]


@router.post("/policies/{policy_id}/approve")
async def approve_learned_policy(
    policy_id: str,
    request: ApprovePolicyRequest,
) -> dict[str, Any]:
    """Approve a learned policy."""
    service = DecisionSafetyService()
    policy = await service.approve_learned_policy(policy_id, request.approved_by)
    if not policy:
        raise HTTPException(404, "Policy not found")
    return policy.to_dict()


# Production guards endpoints
@router.post("/guards/initialize")
async def initialize_guards() -> dict[str, Any]:
    """Initialize default production guards."""
    service = DecisionSafetyService()
    created = await service.initialize_guards()
    return {"created": created, "message": f"Created {created} guards"}


@router.post("/guards/check")
async def check_guard(request: CheckGuardRequest) -> dict[str, Any]:
    """Check if action violates any guards.

    Returns whether action is allowed and any violations.
    """
    service = DecisionSafetyService()
    allowed, message, violation = await service.check_guard(
        action=request.action,
        actor=request.actor,
        context=request.context,
        bypass_reason=request.bypass_reason,
    )
    return {
        "allowed": allowed,
        "message": message,
        "violation": violation.to_dict() if violation else None,
    }


@router.get("/guards")
async def list_guards(
    active_only: bool = Query(default=False),
    guard_level: str = Query(default=None),
) -> list[dict[str, Any]]:
    """List production guards."""
    service = DecisionSafetyService()

    level = None
    if guard_level:
        try:
            level = ProdGuardLevel(guard_level)
        except ValueError:
            valid = [lv.value for lv in ProdGuardLevel]
            raise HTTPException(400, f"Invalid guard_level. Valid: {valid}")

    guards = await service.list_guards(active_only=active_only, guard_level=level)
    return [g.to_dict() for g in guards]


@router.get("/guards/{guard_id}")
async def get_guard(guard_id: str) -> dict[str, Any]:
    """Get guard details."""
    service = DecisionSafetyService()
    guard = await service.get_guard(guard_id)
    if not guard:
        raise HTTPException(404, "Guard not found")
    return guard.to_dict()


@router.post("/guards/{guard_id}/toggle")
async def toggle_guard(
    guard_id: str,
    request: ToggleGuardRequest,
) -> dict[str, Any]:
    """Toggle guard active state."""
    service = DecisionSafetyService()
    guard = await service.toggle_guard(guard_id, request.active, request.toggled_by)
    if not guard:
        raise HTTPException(404, "Guard not found")
    return guard.to_dict()


@router.get("/violations")
async def get_violations(
    guard_id: str = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Get guard violations."""
    service = DecisionSafetyService()
    violations = await service.get_violations(guard_id=guard_id, limit=limit)
    return [v.to_dict() for v in violations]


# Reference endpoints
@router.get("/reference/confidence-levels")
async def list_confidence_levels() -> list[str]:
    """List available confidence levels."""
    return [lv.value for lv in ConfidenceLevel]


@router.get("/reference/remediation-modes")
async def list_remediation_modes() -> list[str]:
    """List available auto-remediation modes."""
    return [m.value for m in AutoRemediationMode]


@router.get("/reference/rollback-urgencies")
async def list_rollback_urgencies() -> list[str]:
    """List available rollback urgency levels."""
    return [u.value for u in RollbackUrgency]


@router.get("/reference/review-statuses")
async def list_review_statuses() -> list[str]:
    """List available review statuses."""
    return [s.value for s in ReviewStatus]


@router.get("/reference/policy-types")
async def list_policy_learning_types() -> list[str]:
    """List available policy learning types."""
    return [t.value for t in PolicyLearningType]


@router.get("/reference/guard-levels")
async def list_guard_levels() -> list[str]:
    """List available production guard levels."""
    return [lv.value for lv in ProdGuardLevel]
