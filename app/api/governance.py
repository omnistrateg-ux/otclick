"""Governance and Trust API endpoints.

Unified trust scoring, stale knowledge detection, lifecycle workflows,
sandbox testing, and recommendation explainability.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime

from app.services.governance_trust import (
    governance_trust,
    TrustableType,
    TrustLevel,
    LifecycleState,
    ApprovalType,
    ExplainabilityLevel,
    StalenessStatus,
)

router = APIRouter(prefix="/governance", tags=["governance"])


# ============================================================================
# Request/Response Models
# ============================================================================


class TrustScoreRequest(BaseModel):
    """Request for trust score calculation."""

    entity_id: str
    entity_type: str
    context: dict[str, Any] = Field(default_factory=dict)


class TrustScoreResponse(BaseModel):
    """Trust score response."""

    entity_id: str
    entity_type: str
    score: float
    level: str
    components: dict[str, float]
    evidence: list[dict[str, Any]]
    trend: str
    confidence: float
    warnings: list[str]
    recommendations: list[str]


class StalenessDetectionRequest(BaseModel):
    """Request for staleness detection."""

    entity_id: str
    entity_type: str
    entity_name: str
    context: dict[str, Any] = Field(default_factory=dict)


class StalenessReportResponse(BaseModel):
    """Staleness report response."""

    entity_id: str
    entity_type: str
    entity_name: str
    status: str
    age_days: int
    staleness_score: float
    needs_review: bool
    suggested_actions: list[str]


class LifecycleCreateRequest(BaseModel):
    """Request to create lifecycle entry."""

    entity_id: str
    entity_type: str
    entity_name: str
    created_by: str
    approval_type: str = "single"
    auto_approve_criteria: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StateTransitionRequest(BaseModel):
    """Request for state transition."""

    new_state: str
    by: str
    reason: str | None = None


class ApprovalRequestCreate(BaseModel):
    """Request to create approval."""

    entity_name: str
    requested_state: str
    requested_by: str
    context: dict[str, Any] = Field(default_factory=dict)
    urgency: str = "normal"


class ApprovalActionRequest(BaseModel):
    """Request for approval action."""

    actor: str
    comment: str | None = None
    reason: str | None = None  # For rejections


class SandboxTestRequest(BaseModel):
    """Request for sandbox test."""

    entity_id: str
    entity_type: str
    entity_name: str
    rule_definition: dict[str, Any]
    test_cases: list[dict[str, Any]] | None = None


class SandboxResultResponse(BaseModel):
    """Sandbox result response."""

    id: str
    entity_id: str
    status: str
    test_cases_run: int
    test_cases_passed: int
    test_cases_failed: int
    errors: list[dict[str, Any]]
    warnings: list[str]
    safety_violations: list[str]
    recommendation: str


class ExplanationRequest(BaseModel):
    """Request for recommendation explanation."""

    recommendation_id: str
    recommendation_type: str
    recommendation_text: str
    decision_context: dict[str, Any]
    level: str = "standard"


class ExplanationResponse(BaseModel):
    """Explanation response."""

    recommendation_id: str
    summary: str
    decision_factors: list[dict[str, Any]]
    confidence_breakdown: dict[str, float]
    assumptions: list[str]
    limitations: list[str]
    human_readable: str


class ValidationRequest(BaseModel):
    """Request to mark entity as validated."""

    validated_by: str


# ============================================================================
# Trust Score Endpoints
# ============================================================================


@router.post("/trust/calculate", response_model=TrustScoreResponse)
async def calculate_trust_score(request: TrustScoreRequest):
    """Calculate unified trust score for an entity.

    Trust score combines multiple factors:
    - Historical accuracy (20%)
    - Usage success rate (20%)
    - Recency (15%)
    - Validation status (15%)
    - Source credibility (10%)
    - Peer review (10%)
    - Production track record (10%)
    """
    try:
        entity_type = TrustableType(request.entity_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity type: {request.entity_type}",
        )

    score = await governance_trust.calculate_trust_score(
        entity_id=request.entity_id,
        entity_type=entity_type,
        context=request.context,
    )

    return TrustScoreResponse(
        entity_id=score.entity_id,
        entity_type=score.entity_type.value,
        score=score.score,
        level=score.level.value,
        components=score.components,
        evidence=score.evidence,
        trend=score.trend,
        confidence=score.confidence,
        warnings=score.warnings,
        recommendations=score.recommendations,
    )


@router.get("/trust/{entity_type}/{entity_id}")
async def get_trust_score(entity_type: str, entity_id: str):
    """Get stored trust score for an entity."""
    try:
        e_type = TrustableType(entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    score = await governance_trust.get_trust_score(entity_id, e_type)
    if not score:
        raise HTTPException(status_code=404, detail="Trust score not found")

    return score.to_dict()


@router.get("/trust/low-trust")
async def get_low_trust_entities(
    threshold: float = Query(0.4, ge=0, le=1),
    entity_type: str | None = None,
):
    """Get entities with low trust scores.

    Returns entities that may need review or validation.
    """
    e_type = None
    if entity_type:
        try:
            e_type = TrustableType(entity_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    entities = await governance_trust.get_low_trust_entities(threshold, e_type)

    return {
        "count": len(entities),
        "threshold": threshold,
        "entities": [e.to_dict() for e in entities],
    }


# ============================================================================
# Staleness Detection Endpoints
# ============================================================================


@router.post("/staleness/detect")
async def detect_staleness(request: StalenessDetectionRequest):
    """Detect staleness of a knowledge entity.

    Analyzes entity age, usage patterns, and validation status
    to determine if content needs review.
    """
    try:
        entity_type = TrustableType(request.entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {request.entity_type}")

    report = await governance_trust.detect_staleness(
        entity_id=request.entity_id,
        entity_type=entity_type,
        entity_name=request.entity_name,
        context=request.context,
    )

    return report.to_dict()


@router.get("/staleness/stale")
async def get_stale_entities(
    entity_type: str | None = None,
    include_aging: bool = True,
):
    """Get all stale entities that need review.

    Returns entities with status: stale, expired, deprecated,
    and optionally aging entities.
    """
    e_type = None
    if entity_type:
        try:
            e_type = TrustableType(entity_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    entities = await governance_trust.get_stale_entities(e_type, include_aging)

    return {
        "count": len(entities),
        "include_aging": include_aging,
        "entities": [e.to_dict() for e in entities],
    }


@router.post("/staleness/{entity_type}/{entity_id}/validate")
async def mark_as_validated(
    entity_type: str,
    entity_id: str,
    request: ValidationRequest,
):
    """Mark an entity as validated.

    Updates the last_validated timestamp and resets staleness status.
    """
    try:
        e_type = TrustableType(entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    success = await governance_trust.mark_as_validated(
        entity_id=entity_id,
        entity_type=e_type,
        validated_by=request.validated_by,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Entity not found")

    return {"status": "validated", "validated_by": request.validated_by}


# ============================================================================
# Lifecycle Management Endpoints
# ============================================================================


@router.post("/lifecycle/create")
async def create_lifecycle_entry(request: LifecycleCreateRequest):
    """Create lifecycle tracking for an entity.

    Entities start in DRAFT state and progress through:
    DRAFT -> PENDING_REVIEW -> IN_REVIEW -> APPROVED -> ACTIVE
    """
    try:
        entity_type = TrustableType(request.entity_type)
        approval_type = ApprovalType(request.approval_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    entry = await governance_trust.create_lifecycle_entry(
        entity_id=request.entity_id,
        entity_type=entity_type,
        entity_name=request.entity_name,
        created_by=request.created_by,
        approval_type=approval_type,
        auto_approve_criteria=request.auto_approve_criteria,
        metadata=request.metadata,
    )

    return entry.to_dict()


@router.get("/lifecycle/{entity_type}/{entity_id}")
async def get_lifecycle_entry(entity_type: str, entity_id: str):
    """Get lifecycle entry for an entity."""
    try:
        e_type = TrustableType(entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    entry = await governance_trust.get_lifecycle_entry(entity_id, e_type)
    if not entry:
        raise HTTPException(status_code=404, detail="Lifecycle entry not found")

    return entry.to_dict()


@router.post("/lifecycle/{entity_type}/{entity_id}/transition")
async def transition_state(
    entity_type: str,
    entity_id: str,
    request: StateTransitionRequest,
):
    """Transition entity to new lifecycle state.

    Valid transitions:
    - DRAFT -> PENDING_REVIEW, ARCHIVED
    - PENDING_REVIEW -> IN_REVIEW, DRAFT
    - IN_REVIEW -> APPROVED, DRAFT
    - APPROVED -> ACTIVE, DRAFT
    - ACTIVE -> SUSPENDED, DEPRECATED
    - SUSPENDED -> ACTIVE, DEPRECATED
    - DEPRECATED -> ARCHIVED
    """
    try:
        e_type = TrustableType(entity_type)
        new_state = LifecycleState(request.new_state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    entry = await governance_trust.transition_state(
        entity_id=entity_id,
        entity_type=e_type,
        new_state=new_state,
        by=request.by,
        reason=request.reason,
    )

    if not entry:
        raise HTTPException(
            status_code=400,
            detail="Invalid state transition or entity not found",
        )

    return entry.to_dict()


# ============================================================================
# Approval Workflow Endpoints
# ============================================================================


@router.post("/approvals/{entity_type}/{entity_id}/request")
async def request_approval(
    entity_type: str,
    entity_id: str,
    request: ApprovalRequestCreate,
):
    """Request approval for state transition.

    Creates an approval request that must be approved before
    the entity can transition to the requested state.
    """
    try:
        e_type = TrustableType(entity_type)
        requested_state = LifecycleState(request.requested_state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    approval = await governance_trust.request_approval(
        entity_id=entity_id,
        entity_type=e_type,
        entity_name=request.entity_name,
        requested_state=requested_state,
        requested_by=request.requested_by,
        context=request.context,
        urgency=request.urgency,
    )

    return approval.to_dict()


@router.post("/approvals/{entity_type}/{entity_id}/approve")
async def approve_request(
    entity_type: str,
    entity_id: str,
    request: ApprovalActionRequest,
):
    """Approve an approval request."""
    try:
        e_type = TrustableType(entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    approval = await governance_trust.approve(
        entity_id=entity_id,
        entity_type=e_type,
        approver=request.actor,
        comment=request.comment,
    )

    if not approval:
        raise HTTPException(
            status_code=400,
            detail="Approval request not found or already processed",
        )

    return approval.to_dict()


@router.post("/approvals/{entity_type}/{entity_id}/reject")
async def reject_request(
    entity_type: str,
    entity_id: str,
    request: ApprovalActionRequest,
):
    """Reject an approval request."""
    try:
        e_type = TrustableType(entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    if not request.reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    approval = await governance_trust.reject(
        entity_id=entity_id,
        entity_type=e_type,
        rejector=request.actor,
        reason=request.reason,
    )

    if not approval:
        raise HTTPException(
            status_code=400,
            detail="Approval request not found or already processed",
        )

    return approval.to_dict()


@router.get("/approvals/pending")
async def get_pending_approvals(entity_type: str | None = None):
    """Get all pending approval requests."""
    e_type = None
    if entity_type:
        try:
            e_type = TrustableType(entity_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    approvals = await governance_trust.get_pending_approvals(e_type)

    return {
        "count": len(approvals),
        "approvals": [a.to_dict() for a in approvals],
    }


# ============================================================================
# Sandbox Testing Endpoints
# ============================================================================


@router.post("/sandbox/test")
async def run_sandbox_test(request: SandboxTestRequest):
    """Run sandbox test for a new rule/policy.

    Executes the rule in an isolated environment against test cases
    to verify correctness and safety before production deployment.

    Returns:
    - Test results (passed/failed)
    - Safety violations detected
    - Side effects detected
    - Recommendation: promote, fix, or reject
    """
    try:
        entity_type = TrustableType(request.entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {request.entity_type}")

    result = await governance_trust.run_sandbox_test(
        entity_id=request.entity_id,
        entity_type=entity_type,
        entity_name=request.entity_name,
        rule_definition=request.rule_definition,
        test_cases=request.test_cases,
    )

    return result.to_dict()


@router.get("/sandbox/{entity_type}/{entity_id}")
async def get_sandbox_result(entity_type: str, entity_id: str):
    """Get sandbox test result for an entity."""
    try:
        e_type = TrustableType(entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    result = await governance_trust.get_sandbox_result(entity_id, e_type)
    if not result:
        raise HTTPException(status_code=404, detail="Sandbox result not found")

    return result.to_dict()


# ============================================================================
# Explainability Endpoints
# ============================================================================


@router.post("/explain")
async def generate_explanation(request: ExplanationRequest):
    """Generate explanation for a recommendation.

    Provides transparency into how a recommendation was made,
    including decision factors, confidence breakdown, assumptions,
    and limitations.

    Explanation levels:
    - minimal: Just the decision
    - standard: Decision + key factors
    - detailed: Full explanation with assumptions and limitations
    - debug: All internal reasoning
    """
    try:
        level = ExplainabilityLevel(request.level)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid level: {request.level}")

    explanation = await governance_trust.generate_explanation(
        recommendation_id=request.recommendation_id,
        recommendation_type=request.recommendation_type,
        recommendation_text=request.recommendation_text,
        decision_context=request.decision_context,
        level=level,
    )

    return explanation.to_dict()


@router.get("/explain/{recommendation_id}")
async def get_explanation(recommendation_id: str):
    """Get stored explanation for a recommendation."""
    explanation = await governance_trust.get_explanation(recommendation_id)
    if not explanation:
        raise HTTPException(status_code=404, detail="Explanation not found")

    return explanation.to_dict()


# ============================================================================
# Dashboard Endpoints
# ============================================================================


@router.get("/summary")
async def get_governance_summary():
    """Get governance summary dashboard.

    Returns overview of:
    - Trust score distribution
    - Stale entities count
    - Pending approvals
    - Sandbox test failures
    - Overall health status
    """
    summary = await governance_trust.get_governance_summary()
    return summary


@router.get("/health")
async def governance_health():
    """Check governance layer health."""
    summary = await governance_trust.get_governance_summary()

    health_issues = []
    if summary["low_trust_entities"] > 10:
        health_issues.append(f"High number of low-trust entities: {summary['low_trust_entities']}")
    if summary["stale_entities"] > 20:
        health_issues.append(f"Many stale entities need review: {summary['stale_entities']}")
    if summary["pending_approvals"] > 50:
        health_issues.append(f"Approval backlog: {summary['pending_approvals']}")

    return {
        "status": "healthy" if not health_issues else "degraded",
        "issues": health_issues,
        "summary": summary,
    }
