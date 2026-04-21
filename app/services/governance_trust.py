"""Governance and Trust Layer Service.

Unified trust scoring, stale knowledge detection, lifecycle/approval workflows,
sandbox for new rules, and recommendation explainability.
"""

import logging
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any
import uuid

UTC = timezone.utc

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================


class TrustableType(str, Enum):
    """Types of trustable entities."""

    RECOMMENDATION = "recommendation"
    RUNBOOK = "runbook"
    PATTERN = "pattern"
    POLICY = "policy"
    KNOWLEDGE = "knowledge"
    RULE = "rule"
    SIMULATION = "simulation"


class TrustLevel(str, Enum):
    """Trust level classification."""

    UNTRUSTED = "untrusted"  # 0-0.2: Not safe to use
    LOW = "low"  # 0.2-0.4: Use with extreme caution
    MEDIUM = "medium"  # 0.4-0.6: Use with caution
    HIGH = "high"  # 0.6-0.8: Generally safe
    VERIFIED = "verified"  # 0.8-1.0: Production-safe


class StalenessStatus(str, Enum):
    """Knowledge staleness status."""

    FRESH = "fresh"  # Recently updated, actively used
    AGING = "aging"  # Getting old, needs review
    STALE = "stale"  # Old and likely outdated
    EXPIRED = "expired"  # Past expiration, must be reviewed
    DEPRECATED = "deprecated"  # Explicitly marked as deprecated


class LifecycleState(str, Enum):
    """Entity lifecycle state."""

    DRAFT = "draft"  # Initial creation
    PENDING_REVIEW = "pending_review"  # Awaiting review
    IN_REVIEW = "in_review"  # Being reviewed
    APPROVED = "approved"  # Approved for production
    ACTIVE = "active"  # Active in production
    SUSPENDED = "suspended"  # Temporarily disabled
    DEPRECATED = "deprecated"  # Marked for removal
    ARCHIVED = "archived"  # No longer active


class ApprovalType(str, Enum):
    """Type of approval required."""

    NONE = "none"  # No approval needed
    SINGLE = "single"  # Single approver
    DUAL = "dual"  # Two approvers
    COMMITTEE = "committee"  # Committee approval
    AUTO = "auto"  # Auto-approved if criteria met


class SandboxStatus(str, Enum):
    """Sandbox execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class ExplainabilityLevel(str, Enum):
    """Level of explanation detail."""

    MINIMAL = "minimal"  # Just the decision
    STANDARD = "standard"  # Decision + key factors
    DETAILED = "detailed"  # Full explanation
    DEBUG = "debug"  # All internal reasoning


class DriftType(str, Enum):
    """Types of knowledge drift."""

    ACCURACY_DRIFT = "accuracy_drift"  # Predictions becoming less accurate
    USAGE_DRIFT = "usage_drift"  # Usage patterns changing
    PERFORMANCE_DRIFT = "performance_drift"  # Performance degrading
    RELEVANCE_DRIFT = "relevance_drift"  # Content becoming less relevant
    CONFLICT_DRIFT = "conflict_drift"  # Conflicts with other knowledge


class DriftSeverity(str, Enum):
    """Severity of knowledge drift."""

    INFO = "info"  # Informational only
    WARNING = "warning"  # Needs attention
    CRITICAL = "critical"  # Requires immediate action
    EMERGENCY = "emergency"  # System integrity at risk


class PromotionGateType(str, Enum):
    """Types of promotion gates."""

    SANDBOX_PASS = "sandbox_pass"  # Must pass sandbox testing
    TRUST_THRESHOLD = "trust_threshold"  # Must meet trust score
    APPROVAL_REQUIRED = "approval_required"  # Must have approval
    REVIEW_COMPLETE = "review_complete"  # Must complete review
    NO_CONFLICTS = "no_conflicts"  # No policy conflicts
    STABILITY_PERIOD = "stability_period"  # Must be stable for period
    ROLLBACK_READY = "rollback_ready"  # Must have rollback plan


class ReviewRequirement(str, Enum):
    """Review requirement levels."""

    NONE = "none"
    OPTIONAL = "optional"
    RECOMMENDED = "recommended"
    MANDATORY = "mandatory"
    EMERGENCY = "emergency"  # Immediate mandatory review


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class TrustScore:
    """Unified trust score for any trustable entity."""

    entity_id: str
    entity_type: TrustableType
    score: float  # 0.0 - 1.0
    level: TrustLevel
    components: dict[str, float]
    evidence: list[dict[str, Any]]
    last_evaluated: datetime
    evaluations_count: int
    trend: str  # improving, stable, declining
    confidence: float  # How confident we are in the score
    warnings: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "score": round(self.score, 3),
            "level": self.level.value,
            "components": {k: round(v, 3) for k, v in self.components.items()},
            "evidence": self.evidence,
            "last_evaluated": self.last_evaluated.isoformat(),
            "evaluations_count": self.evaluations_count,
            "trend": self.trend,
            "confidence": round(self.confidence, 3),
            "warnings": self.warnings,
            "recommendations": self.recommendations,
        }


@dataclass
class TrustComponent:
    """Individual component of trust score."""

    name: str
    weight: float
    score: float
    description: str
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weight": round(self.weight, 3),
            "score": round(self.score, 3),
            "description": self.description,
            "evidence": self.evidence,
        }


@dataclass
class StalenessReport:
    """Report on knowledge staleness."""

    entity_id: str
    entity_type: TrustableType
    entity_name: str
    status: StalenessStatus
    age_days: int
    last_updated: datetime
    last_used: datetime | None
    last_validated: datetime | None
    usage_count_30d: int
    staleness_score: float  # 0 = fresh, 1 = completely stale
    expiration_date: datetime | None
    needs_review: bool
    suggested_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "entity_name": self.entity_name,
            "status": self.status.value,
            "age_days": self.age_days,
            "last_updated": self.last_updated.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "last_validated": self.last_validated.isoformat() if self.last_validated else None,
            "usage_count_30d": self.usage_count_30d,
            "staleness_score": round(self.staleness_score, 3),
            "expiration_date": self.expiration_date.isoformat() if self.expiration_date else None,
            "needs_review": self.needs_review,
            "suggested_actions": self.suggested_actions,
        }


@dataclass
class LifecycleEntry:
    """Lifecycle management entry for an entity."""

    entity_id: str
    entity_type: TrustableType
    entity_name: str
    state: LifecycleState
    version: int
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: str
    state_history: list[dict[str, Any]]
    approval_type: ApprovalType
    approvers: list[str]
    pending_approvers: list[str]
    rejection_reason: str | None
    auto_approve_criteria: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "entity_name": self.entity_name,
            "state": self.state.value,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "updated_at": self.updated_at.isoformat(),
            "updated_by": self.updated_by,
            "state_history": self.state_history,
            "approval_type": self.approval_type.value,
            "approvers": self.approvers,
            "pending_approvers": self.pending_approvers,
            "rejection_reason": self.rejection_reason,
            "auto_approve_criteria": self.auto_approve_criteria,
            "metadata": self.metadata,
        }


@dataclass
class ApprovalRequest:
    """Request for approval in workflow."""

    id: str
    entity_id: str
    entity_type: TrustableType
    entity_name: str
    requested_state: LifecycleState
    requested_by: str
    requested_at: datetime
    approval_type: ApprovalType
    required_approvers: list[str]
    current_approvals: list[dict[str, Any]]
    rejections: list[dict[str, Any]]
    status: str  # pending, approved, rejected, expired
    expires_at: datetime
    context: dict[str, Any]
    urgency: str  # normal, high, critical

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "entity_name": self.entity_name,
            "requested_state": self.requested_state.value,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at.isoformat(),
            "approval_type": self.approval_type.value,
            "required_approvers": self.required_approvers,
            "current_approvals": self.current_approvals,
            "rejections": self.rejections,
            "status": self.status,
            "expires_at": self.expires_at.isoformat(),
            "context": self.context,
            "urgency": self.urgency,
        }


@dataclass
class SandboxResult:
    """Result of sandbox execution for a rule/policy."""

    id: str
    entity_id: str
    entity_type: TrustableType
    entity_name: str
    status: SandboxStatus
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int
    test_cases_run: int
    test_cases_passed: int
    test_cases_failed: int
    errors: list[dict[str, Any]]
    warnings: list[str]
    side_effects_detected: list[str]
    resource_usage: dict[str, float]
    safety_violations: list[str]
    recommendation: str  # promote, fix, reject
    detailed_results: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "entity_name": self.entity_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "test_cases_run": self.test_cases_run,
            "test_cases_passed": self.test_cases_passed,
            "test_cases_failed": self.test_cases_failed,
            "errors": self.errors,
            "warnings": self.warnings,
            "side_effects_detected": self.side_effects_detected,
            "resource_usage": self.resource_usage,
            "safety_violations": self.safety_violations,
            "recommendation": self.recommendation,
            "detailed_results": self.detailed_results,
        }


@dataclass
class RecommendationExplanation:
    """Explanation for a recommendation."""

    recommendation_id: str
    recommendation_type: str
    recommendation_text: str
    explanation_level: ExplainabilityLevel
    summary: str
    decision_factors: list[dict[str, Any]]
    data_sources: list[dict[str, Any]]
    confidence_breakdown: dict[str, float]
    alternatives_considered: list[dict[str, Any]]
    why_not_alternatives: list[str]
    assumptions: list[str]
    limitations: list[str]
    supporting_evidence: list[dict[str, Any]]
    contradicting_evidence: list[dict[str, Any]]
    human_readable: str
    generated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "recommendation_type": self.recommendation_type,
            "recommendation_text": self.recommendation_text,
            "explanation_level": self.explanation_level.value,
            "summary": self.summary,
            "decision_factors": self.decision_factors,
            "data_sources": self.data_sources,
            "confidence_breakdown": {k: round(v, 3) for k, v in self.confidence_breakdown.items()},
            "alternatives_considered": self.alternatives_considered,
            "why_not_alternatives": self.why_not_alternatives,
            "assumptions": self.assumptions,
            "limitations": self.limitations,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "human_readable": self.human_readable,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class TrustPropagation:
    """Trust propagation between related entities."""

    source_entity_id: str
    source_entity_type: TrustableType
    target_entity_id: str
    target_entity_type: TrustableType
    relationship: str  # depends_on, derived_from, references, uses
    propagation_factor: float  # How much trust propagates (0-1)
    propagated_score: float
    original_target_score: float
    new_target_score: float
    propagated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_entity_id": self.source_entity_id,
            "source_entity_type": self.source_entity_type.value,
            "target_entity_id": self.target_entity_id,
            "target_entity_type": self.target_entity_type.value,
            "relationship": self.relationship,
            "propagation_factor": round(self.propagation_factor, 3),
            "propagated_score": round(self.propagated_score, 3),
            "original_target_score": round(self.original_target_score, 3),
            "new_target_score": round(self.new_target_score, 3),
            "propagated_at": self.propagated_at.isoformat(),
        }


@dataclass
class DriftAlert:
    """Alert for knowledge drift detection."""

    id: str
    entity_id: str
    entity_type: TrustableType
    entity_name: str
    drift_type: DriftType
    severity: DriftSeverity
    current_value: float
    baseline_value: float
    drift_percentage: float
    detected_at: datetime
    description: str
    evidence: list[dict[str, Any]]
    recommended_actions: list[str]
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved: bool = False
    resolution: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "entity_name": self.entity_name,
            "drift_type": self.drift_type.value,
            "severity": self.severity.value,
            "current_value": round(self.current_value, 3),
            "baseline_value": round(self.baseline_value, 3),
            "drift_percentage": round(self.drift_percentage, 1),
            "detected_at": self.detected_at.isoformat(),
            "description": self.description,
            "evidence": self.evidence,
            "recommended_actions": self.recommended_actions,
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


@dataclass
class MandatoryReview:
    """Mandatory review requirement for low-trust critical items."""

    id: str
    entity_id: str
    entity_type: TrustableType
    entity_name: str
    requirement: ReviewRequirement
    reason: str
    trust_score: float
    criticality: str  # low, medium, high, critical
    created_at: datetime
    due_date: datetime
    assigned_reviewers: list[str]
    completed_reviews: list[dict[str, Any]]
    status: str  # pending, in_progress, completed, overdue, escalated
    blocking: bool  # Whether this blocks production use
    escalation_level: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "entity_name": self.entity_name,
            "requirement": self.requirement.value,
            "reason": self.reason,
            "trust_score": round(self.trust_score, 3),
            "criticality": self.criticality,
            "created_at": self.created_at.isoformat(),
            "due_date": self.due_date.isoformat(),
            "assigned_reviewers": self.assigned_reviewers,
            "completed_reviews": self.completed_reviews,
            "status": self.status,
            "blocking": self.blocking,
            "escalation_level": self.escalation_level,
        }


@dataclass
class PromotionGate:
    """Gate that must be passed for promotion from sandbox to active."""

    gate_type: PromotionGateType
    name: str
    description: str
    required: bool
    passed: bool
    details: dict[str, Any]
    checked_at: datetime
    blocker_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_type": self.gate_type.value,
            "name": self.name,
            "description": self.description,
            "required": self.required,
            "passed": self.passed,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
            "blocker_reason": self.blocker_reason,
        }


@dataclass
class PromotionRequest:
    """Request to promote entity from sandbox to active."""

    id: str
    entity_id: str
    entity_type: TrustableType
    entity_name: str
    requested_by: str
    requested_at: datetime
    gates: list[PromotionGate]
    all_gates_passed: bool
    blocking_gates: list[str]
    status: str  # pending, approved, rejected, promoted
    promoted_at: datetime | None = None
    promoted_by: str | None = None
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "entity_name": self.entity_name,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at.isoformat(),
            "gates": [g.to_dict() for g in self.gates],
            "all_gates_passed": self.all_gates_passed,
            "blocking_gates": self.blocking_gates,
            "status": self.status,
            "promoted_at": self.promoted_at.isoformat() if self.promoted_at else None,
            "promoted_by": self.promoted_by,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class GovernanceDashboardData:
    """Comprehensive governance dashboard data."""

    generated_at: datetime
    # Trust overview
    total_entities: int
    trust_distribution: dict[str, int]  # level -> count
    low_trust_critical: list[dict[str, Any]]
    trust_trend: str  # improving, stable, declining
    # Staleness overview
    stale_count: int
    expired_count: int
    aging_count: int
    staleness_by_type: dict[str, int]
    # Approval status
    pending_approvals: int
    overdue_approvals: int
    approval_backlog_hours: float
    # Sandbox status
    sandbox_queue: int
    sandbox_pass_rate: float
    recent_failures: list[dict[str, Any]]
    # Drift alerts
    active_drift_alerts: int
    critical_drift_alerts: int
    drift_by_type: dict[str, int]
    # Mandatory reviews
    pending_reviews: int
    overdue_reviews: int
    blocking_reviews: int
    # Promotion gates
    pending_promotions: int
    blocked_promotions: int
    # Health indicators
    overall_health: str  # healthy, warning, critical
    health_issues: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "trust_overview": {
                "total_entities": self.total_entities,
                "distribution": self.trust_distribution,
                "low_trust_critical": self.low_trust_critical,
                "trend": self.trust_trend,
            },
            "staleness_overview": {
                "stale_count": self.stale_count,
                "expired_count": self.expired_count,
                "aging_count": self.aging_count,
                "by_type": self.staleness_by_type,
            },
            "approval_status": {
                "pending": self.pending_approvals,
                "overdue": self.overdue_approvals,
                "backlog_hours": round(self.approval_backlog_hours, 1),
            },
            "sandbox_status": {
                "queue": self.sandbox_queue,
                "pass_rate": round(self.sandbox_pass_rate, 2),
                "recent_failures": self.recent_failures,
            },
            "drift_alerts": {
                "active": self.active_drift_alerts,
                "critical": self.critical_drift_alerts,
                "by_type": self.drift_by_type,
            },
            "mandatory_reviews": {
                "pending": self.pending_reviews,
                "overdue": self.overdue_reviews,
                "blocking": self.blocking_reviews,
            },
            "promotion_gates": {
                "pending": self.pending_promotions,
                "blocked": self.blocked_promotions,
            },
            "health": {
                "status": self.overall_health,
                "issues": self.health_issues,
                "recommendations": self.recommendations,
            },
        }


# ============================================================================
# Trust Score Weights
# ============================================================================

TRUST_WEIGHTS = {
    "historical_accuracy": 0.20,
    "usage_success_rate": 0.20,
    "recency": 0.15,
    "validation_status": 0.15,
    "source_credibility": 0.10,
    "peer_review": 0.10,
    "production_track_record": 0.10,
}

# Staleness thresholds (days)
STALENESS_THRESHOLDS = {
    TrustableType.RECOMMENDATION: {"fresh": 7, "aging": 30, "stale": 90},
    TrustableType.RUNBOOK: {"fresh": 30, "aging": 90, "stale": 180},
    TrustableType.PATTERN: {"fresh": 30, "aging": 90, "stale": 180},
    TrustableType.POLICY: {"fresh": 60, "aging": 180, "stale": 365},
    TrustableType.KNOWLEDGE: {"fresh": 30, "aging": 90, "stale": 180},
    TrustableType.RULE: {"fresh": 60, "aging": 180, "stale": 365},
    TrustableType.SIMULATION: {"fresh": 14, "aging": 30, "stale": 60},
}

# Lifecycle transitions
VALID_TRANSITIONS = {
    LifecycleState.DRAFT: [LifecycleState.PENDING_REVIEW, LifecycleState.ARCHIVED],
    LifecycleState.PENDING_REVIEW: [LifecycleState.IN_REVIEW, LifecycleState.DRAFT],
    LifecycleState.IN_REVIEW: [LifecycleState.APPROVED, LifecycleState.DRAFT],
    LifecycleState.APPROVED: [LifecycleState.ACTIVE, LifecycleState.DRAFT],
    LifecycleState.ACTIVE: [LifecycleState.SUSPENDED, LifecycleState.DEPRECATED],
    LifecycleState.SUSPENDED: [LifecycleState.ACTIVE, LifecycleState.DEPRECATED],
    LifecycleState.DEPRECATED: [LifecycleState.ARCHIVED],
    LifecycleState.ARCHIVED: [],
}

# Trust propagation factors by relationship type
PROPAGATION_FACTORS = {
    "depends_on": 0.7,  # Heavy dependency = high propagation
    "derived_from": 0.6,  # Derived content inherits trust
    "references": 0.3,  # Loose reference = lower propagation
    "uses": 0.5,  # Uses relationship
    "validates": 0.4,  # Validation relationship
    "extends": 0.5,  # Extension relationship
}

# Drift detection thresholds
DRIFT_THRESHOLDS = {
    DriftType.ACCURACY_DRIFT: {"warning": 0.10, "critical": 0.25},
    DriftType.USAGE_DRIFT: {"warning": 0.30, "critical": 0.50},
    DriftType.PERFORMANCE_DRIFT: {"warning": 0.15, "critical": 0.30},
    DriftType.RELEVANCE_DRIFT: {"warning": 0.20, "critical": 0.40},
    DriftType.CONFLICT_DRIFT: {"warning": 0.05, "critical": 0.15},
}

# Mandatory review triggers
MANDATORY_REVIEW_TRIGGERS = {
    "low_trust_critical": {"trust_threshold": 0.4, "criticality": ["high", "critical"]},
    "production_incident": {"incident_count": 1},
    "significant_drift": {"drift_threshold": 0.25},
    "expired_validation": {"days_since_validation": 180},
}

# Default promotion gates configuration
DEFAULT_PROMOTION_GATES = [
    {
        "gate_type": PromotionGateType.SANDBOX_PASS,
        "name": "Sandbox Tests",
        "description": "All sandbox tests must pass",
        "required": True,
    },
    {
        "gate_type": PromotionGateType.TRUST_THRESHOLD,
        "name": "Trust Score",
        "description": "Trust score must be >= 0.6",
        "required": True,
        "threshold": 0.6,
    },
    {
        "gate_type": PromotionGateType.APPROVAL_REQUIRED,
        "name": "Approval",
        "description": "Must have required approvals",
        "required": True,
    },
    {
        "gate_type": PromotionGateType.NO_CONFLICTS,
        "name": "No Conflicts",
        "description": "No policy conflicts detected",
        "required": True,
    },
    {
        "gate_type": PromotionGateType.ROLLBACK_READY,
        "name": "Rollback Ready",
        "description": "Rollback plan must be defined",
        "required": False,
    },
]


# ============================================================================
# Service
# ============================================================================


class GovernanceTrustService:
    """Service for governance and trust management.

    Features:
    - Unified trust scoring for all trustable entities
    - Trust propagation across related entities
    - Stale knowledge detection and alerting
    - Knowledge drift detection and alerts
    - Lifecycle and approval workflows
    - Mandatory review for low-trust critical items
    - Sandbox for testing new rules/policies
    - Promotion gates from sandbox to active
    - Recommendation explainability
    - Unified governance dashboard
    """

    TRUST_KEY = "governance:trust"
    STALENESS_KEY = "governance:staleness"
    LIFECYCLE_KEY = "governance:lifecycle"
    APPROVALS_KEY = "governance:approvals"
    SANDBOX_KEY = "governance:sandbox"
    EXPLANATIONS_KEY = "governance:explanations"
    METRICS_KEY = "governance:metrics"
    PROPAGATION_KEY = "governance:propagation"
    DRIFT_KEY = "governance:drift"
    REVIEWS_KEY = "governance:reviews"
    PROMOTIONS_KEY = "governance:promotions"
    RELATIONS_KEY = "governance:relations"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Unified Trust Score
    # ========================================================================

    async def calculate_trust_score(
        self,
        entity_id: str,
        entity_type: TrustableType,
        context: dict[str, Any] | None = None,
    ) -> TrustScore:
        """Calculate unified trust score for an entity.

        Args:
            entity_id: Entity identifier
            entity_type: Type of entity
            context: Additional context for scoring

        Returns:
            Calculated trust score
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        ctx = context or {}

        # Get historical data
        history_key = f"{self.TRUST_KEY}:history:{entity_type.value}:{entity_id}"
        history_raw = await redis.lrange(history_key, 0, 99)
        history = [json.loads(h) for h in history_raw] if history_raw else []

        # Calculate components
        components = {}
        evidence = []

        # Historical accuracy
        historical_success = ctx.get("historical_success_rate", 0.7)
        total_uses = ctx.get("total_uses", 0)
        if total_uses > 10:
            components["historical_accuracy"] = historical_success
            evidence.append({
                "component": "historical_accuracy",
                "value": historical_success,
                "sample_size": total_uses,
            })
        else:
            components["historical_accuracy"] = 0.5  # Neutral for new entities
            evidence.append({
                "component": "historical_accuracy",
                "value": 0.5,
                "reason": "insufficient_data",
            })

        # Usage success rate
        recent_successes = ctx.get("recent_successes", 0)
        recent_failures = ctx.get("recent_failures", 0)
        recent_total = recent_successes + recent_failures
        if recent_total > 0:
            components["usage_success_rate"] = recent_successes / recent_total
        else:
            components["usage_success_rate"] = 0.5
        evidence.append({
            "component": "usage_success_rate",
            "successes": recent_successes,
            "failures": recent_failures,
        })

        # Recency
        last_updated = ctx.get("last_updated")
        if last_updated:
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated)
            age_days = (now - last_updated).days
            recency_score = max(0, 1 - (age_days / 365))
            components["recency"] = recency_score
        else:
            components["recency"] = 0.5
        evidence.append({"component": "recency", "age_days": age_days if last_updated else None})

        # Validation status
        validated = ctx.get("validated", False)
        validation_date = ctx.get("validation_date")
        if validated and validation_date:
            val_date = datetime.fromisoformat(validation_date) if isinstance(validation_date, str) else validation_date
            validation_age = (now - val_date).days
            components["validation_status"] = max(0.5, 1 - (validation_age / 180))
        elif validated:
            components["validation_status"] = 0.8
        else:
            components["validation_status"] = 0.3
        evidence.append({"component": "validation_status", "validated": validated})

        # Source credibility
        source = ctx.get("source", "unknown")
        source_scores = {
            "system": 0.9,
            "verified": 0.85,
            "trusted": 0.75,
            "community": 0.5,
            "experimental": 0.3,
            "unknown": 0.4,
        }
        components["source_credibility"] = source_scores.get(source, 0.4)
        evidence.append({"component": "source_credibility", "source": source})

        # Peer review
        reviews = ctx.get("peer_reviews", 0)
        positive_reviews = ctx.get("positive_reviews", 0)
        if reviews > 0:
            components["peer_review"] = min(1.0, (positive_reviews / reviews) * (min(reviews, 10) / 10))
        else:
            components["peer_review"] = 0.4
        evidence.append({"component": "peer_review", "reviews": reviews, "positive": positive_reviews})

        # Production track record
        prod_uses = ctx.get("production_uses", 0)
        prod_incidents = ctx.get("production_incidents", 0)
        if prod_uses > 0:
            incident_rate = prod_incidents / prod_uses
            components["production_track_record"] = max(0, 1 - (incident_rate * 10))
        else:
            components["production_track_record"] = 0.5
        evidence.append({
            "component": "production_track_record",
            "prod_uses": prod_uses,
            "incidents": prod_incidents,
        })

        # Calculate weighted score
        score = sum(
            components[k] * TRUST_WEIGHTS[k]
            for k in TRUST_WEIGHTS
        )

        # Determine level
        if score >= 0.8:
            level = TrustLevel.VERIFIED
        elif score >= 0.6:
            level = TrustLevel.HIGH
        elif score >= 0.4:
            level = TrustLevel.MEDIUM
        elif score >= 0.2:
            level = TrustLevel.LOW
        else:
            level = TrustLevel.UNTRUSTED

        # Calculate trend
        if len(history) >= 3:
            recent_scores = [h["score"] for h in history[:3]]
            avg_recent = sum(recent_scores) / len(recent_scores)
            if score > avg_recent + 0.05:
                trend = "improving"
            elif score < avg_recent - 0.05:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # Calculate confidence
        data_points = sum([
            1 if total_uses > 10 else 0,
            1 if recent_total > 5 else 0,
            1 if validated else 0,
            1 if reviews > 0 else 0,
            1 if prod_uses > 0 else 0,
        ])
        confidence = min(1.0, 0.3 + (data_points * 0.14))

        # Get previous evaluations count
        prev_raw = await redis.hget(f"{self.TRUST_KEY}:scores", f"{entity_type.value}:{entity_id}")
        prev_count = 0
        if prev_raw:
            prev_data = json.loads(prev_raw)
            prev_count = prev_data.get("evaluations_count", 0)

        # Generate warnings
        warnings = []
        if score < 0.4:
            warnings.append("Low trust score - use with caution")
        if trend == "declining":
            warnings.append("Trust score is declining")
        if not validated:
            warnings.append("Entity has not been validated")
        if prod_incidents > 0:
            warnings.append(f"{prod_incidents} production incidents recorded")

        # Generate recommendations
        recommendations = []
        if not validated:
            recommendations.append("Validate this entity to improve trust")
        if reviews == 0:
            recommendations.append("Get peer reviews to improve confidence")
        if score < 0.6:
            recommendations.append("Consider sandbox testing before production use")

        trust_score = TrustScore(
            entity_id=entity_id,
            entity_type=entity_type,
            score=score,
            level=level,
            components=components,
            evidence=evidence,
            last_evaluated=now,
            evaluations_count=prev_count + 1,
            trend=trend,
            confidence=confidence,
            warnings=warnings,
            recommendations=recommendations,
        )

        # Store score
        await redis.hset(
            f"{self.TRUST_KEY}:scores",
            f"{entity_type.value}:{entity_id}",
            json.dumps(trust_score.to_dict()),
        )

        # Store in history
        await redis.lpush(history_key, json.dumps({"score": score, "timestamp": now.isoformat()}))
        await redis.ltrim(history_key, 0, 99)

        logger.info(f"[GovernanceTrust] Calculated trust score for {entity_type.value}:{entity_id}: {score:.3f}")

        return trust_score

    async def get_trust_score(
        self,
        entity_id: str,
        entity_type: TrustableType,
    ) -> TrustScore | None:
        """Get stored trust score for an entity."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(f"{self.TRUST_KEY}:scores", f"{entity_type.value}:{entity_id}")

        if not raw:
            return None

        data = json.loads(raw)
        return TrustScore(
            entity_id=data["entity_id"],
            entity_type=TrustableType(data["entity_type"]),
            score=data["score"],
            level=TrustLevel(data["level"]),
            components=data["components"],
            evidence=data["evidence"],
            last_evaluated=datetime.fromisoformat(data["last_evaluated"]),
            evaluations_count=data["evaluations_count"],
            trend=data["trend"],
            confidence=data["confidence"],
            warnings=data["warnings"],
            recommendations=data["recommendations"],
        )

    async def batch_calculate_trust(
        self,
        entities: list[tuple[str, TrustableType, dict[str, Any]]],
    ) -> list[TrustScore]:
        """Calculate trust scores for multiple entities."""
        results = []
        for entity_id, entity_type, context in entities:
            score = await self.calculate_trust_score(entity_id, entity_type, context)
            results.append(score)
        return results

    async def get_low_trust_entities(
        self,
        threshold: float = 0.4,
        entity_type: TrustableType | None = None,
    ) -> list[TrustScore]:
        """Get entities with low trust scores."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hgetall(f"{self.TRUST_KEY}:scores")
        results = []

        for key, data_str in raw.items():
            try:
                data = json.loads(data_str)
                if data["score"] < threshold:
                    if entity_type and data["entity_type"] != entity_type.value:
                        continue
                    results.append(TrustScore(
                        entity_id=data["entity_id"],
                        entity_type=TrustableType(data["entity_type"]),
                        score=data["score"],
                        level=TrustLevel(data["level"]),
                        components=data["components"],
                        evidence=data["evidence"],
                        last_evaluated=datetime.fromisoformat(data["last_evaluated"]),
                        evaluations_count=data["evaluations_count"],
                        trend=data["trend"],
                        confidence=data["confidence"],
                        warnings=data["warnings"],
                        recommendations=data["recommendations"],
                    ))
            except Exception:
                continue

        results.sort(key=lambda x: x.score)
        return results

    # ========================================================================
    # Stale Knowledge Detection
    # ========================================================================

    async def detect_staleness(
        self,
        entity_id: str,
        entity_type: TrustableType,
        entity_name: str,
        context: dict[str, Any],
    ) -> StalenessReport:
        """Detect staleness of a knowledge entity.

        Args:
            entity_id: Entity identifier
            entity_type: Type of entity
            entity_name: Human-readable name
            context: Entity context (dates, usage stats)

        Returns:
            Staleness report
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Parse dates
        last_updated = context.get("last_updated")
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        elif last_updated is None:
            last_updated = now - timedelta(days=365)

        last_used = context.get("last_used")
        if isinstance(last_used, str):
            last_used = datetime.fromisoformat(last_used)

        last_validated = context.get("last_validated")
        if isinstance(last_validated, str):
            last_validated = datetime.fromisoformat(last_validated)

        # Calculate age
        age_days = (now - last_updated).days

        # Get thresholds
        thresholds = STALENESS_THRESHOLDS.get(entity_type, {"fresh": 30, "aging": 90, "stale": 180})

        # Determine status
        if context.get("deprecated", False):
            status = StalenessStatus.DEPRECATED
        elif context.get("expiration_date"):
            exp_date = context["expiration_date"]
            if isinstance(exp_date, str):
                exp_date = datetime.fromisoformat(exp_date)
            if now > exp_date:
                status = StalenessStatus.EXPIRED
            elif age_days > thresholds["stale"]:
                status = StalenessStatus.STALE
            elif age_days > thresholds["aging"]:
                status = StalenessStatus.AGING
            else:
                status = StalenessStatus.FRESH
        elif age_days > thresholds["stale"]:
            status = StalenessStatus.STALE
        elif age_days > thresholds["aging"]:
            status = StalenessStatus.AGING
        else:
            status = StalenessStatus.FRESH

        # Calculate staleness score (0 = fresh, 1 = stale)
        staleness_score = min(1.0, age_days / thresholds["stale"])

        # Adjust for usage
        usage_count_30d = context.get("usage_count_30d", 0)
        if usage_count_30d > 10:
            staleness_score *= 0.8  # Active usage reduces staleness

        # Determine if review needed
        needs_review = status in [StalenessStatus.STALE, StalenessStatus.EXPIRED, StalenessStatus.DEPRECATED]
        if last_validated:
            validation_age = (now - last_validated).days
            if validation_age > 90:
                needs_review = True

        # Generate suggested actions
        actions = []
        if status == StalenessStatus.STALE:
            actions.append("Review and update content")
            actions.append("Validate with subject matter expert")
        elif status == StalenessStatus.EXPIRED:
            actions.append("Urgent: Review expired content immediately")
            actions.append("Consider archiving if no longer relevant")
        elif status == StalenessStatus.AGING:
            actions.append("Schedule review in next sprint")
        elif status == StalenessStatus.DEPRECATED:
            actions.append("Migrate users to replacement")
            actions.append("Archive when migration complete")

        if not last_validated:
            actions.append("Perform initial validation")
        elif last_validated and (now - last_validated).days > 180:
            actions.append("Re-validate content")

        report = StalenessReport(
            entity_id=entity_id,
            entity_type=entity_type,
            entity_name=entity_name,
            status=status,
            age_days=age_days,
            last_updated=last_updated,
            last_used=last_used,
            last_validated=last_validated,
            usage_count_30d=usage_count_30d,
            staleness_score=staleness_score,
            expiration_date=datetime.fromisoformat(context["expiration_date"]) if context.get("expiration_date") else None,
            needs_review=needs_review,
            suggested_actions=actions,
        )

        # Store report
        await redis.hset(
            self.STALENESS_KEY,
            f"{entity_type.value}:{entity_id}",
            json.dumps(report.to_dict()),
        )

        logger.info(f"[GovernanceTrust] Staleness detected for {entity_name}: {status.value}")

        return report

    async def get_stale_entities(
        self,
        entity_type: TrustableType | None = None,
        include_aging: bool = True,
    ) -> list[StalenessReport]:
        """Get all stale entities."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hgetall(self.STALENESS_KEY)
        results = []

        target_statuses = [StalenessStatus.STALE, StalenessStatus.EXPIRED, StalenessStatus.DEPRECATED]
        if include_aging:
            target_statuses.append(StalenessStatus.AGING)

        for data_str in raw.values():
            try:
                data = json.loads(data_str)
                if StalenessStatus(data["status"]) not in target_statuses:
                    continue
                if entity_type and data["entity_type"] != entity_type.value:
                    continue

                results.append(StalenessReport(
                    entity_id=data["entity_id"],
                    entity_type=TrustableType(data["entity_type"]),
                    entity_name=data["entity_name"],
                    status=StalenessStatus(data["status"]),
                    age_days=data["age_days"],
                    last_updated=datetime.fromisoformat(data["last_updated"]),
                    last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
                    last_validated=datetime.fromisoformat(data["last_validated"]) if data.get("last_validated") else None,
                    usage_count_30d=data["usage_count_30d"],
                    staleness_score=data["staleness_score"],
                    expiration_date=datetime.fromisoformat(data["expiration_date"]) if data.get("expiration_date") else None,
                    needs_review=data["needs_review"],
                    suggested_actions=data["suggested_actions"],
                ))
            except Exception:
                continue

        results.sort(key=lambda x: x.staleness_score, reverse=True)
        return results

    async def mark_as_validated(
        self,
        entity_id: str,
        entity_type: TrustableType,
        validated_by: str,
    ) -> bool:
        """Mark an entity as validated."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        key = f"{entity_type.value}:{entity_id}"

        raw = await redis.hget(self.STALENESS_KEY, key)
        if not raw:
            return False

        data = json.loads(raw)
        data["last_validated"] = datetime.now(UTC).isoformat()
        data["status"] = StalenessStatus.FRESH.value
        data["needs_review"] = False

        await redis.hset(self.STALENESS_KEY, key, json.dumps(data))

        logger.info(f"[GovernanceTrust] Entity {key} validated by {validated_by}")
        return True

    # ========================================================================
    # Lifecycle and Approval Workflows
    # ========================================================================

    async def create_lifecycle_entry(
        self,
        entity_id: str,
        entity_type: TrustableType,
        entity_name: str,
        created_by: str,
        approval_type: ApprovalType = ApprovalType.SINGLE,
        auto_approve_criteria: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LifecycleEntry:
        """Create lifecycle tracking for an entity.

        Args:
            entity_id: Entity identifier
            entity_type: Type of entity
            entity_name: Human-readable name
            created_by: Creator
            approval_type: Type of approval required
            auto_approve_criteria: Criteria for auto-approval
            metadata: Additional metadata

        Returns:
            Created lifecycle entry
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        entry = LifecycleEntry(
            entity_id=entity_id,
            entity_type=entity_type,
            entity_name=entity_name,
            state=LifecycleState.DRAFT,
            version=1,
            created_at=now,
            created_by=created_by,
            updated_at=now,
            updated_by=created_by,
            state_history=[{
                "state": LifecycleState.DRAFT.value,
                "timestamp": now.isoformat(),
                "by": created_by,
                "reason": "Initial creation",
            }],
            approval_type=approval_type,
            approvers=[],
            pending_approvers=[],
            rejection_reason=None,
            auto_approve_criteria=auto_approve_criteria or {},
            metadata=metadata or {},
        )

        await redis.hset(
            self.LIFECYCLE_KEY,
            f"{entity_type.value}:{entity_id}",
            json.dumps(entry.to_dict()),
        )

        logger.info(f"[GovernanceTrust] Created lifecycle entry for {entity_name}")
        return entry

    async def transition_state(
        self,
        entity_id: str,
        entity_type: TrustableType,
        new_state: LifecycleState,
        by: str,
        reason: str | None = None,
    ) -> LifecycleEntry | None:
        """Transition entity to new lifecycle state.

        Args:
            entity_id: Entity identifier
            entity_type: Type of entity
            new_state: Target state
            by: Actor performing transition
            reason: Reason for transition

        Returns:
            Updated lifecycle entry or None if invalid
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        key = f"{entity_type.value}:{entity_id}"

        raw = await redis.hget(self.LIFECYCLE_KEY, key)
        if not raw:
            return None

        data = json.loads(raw)
        current_state = LifecycleState(data["state"])

        # Validate transition
        valid_targets = VALID_TRANSITIONS.get(current_state, [])
        if new_state not in valid_targets:
            logger.warning(f"[GovernanceTrust] Invalid transition {current_state.value} -> {new_state.value}")
            return None

        # Check if approval needed
        if new_state == LifecycleState.APPROVED:
            approval_type = ApprovalType(data["approval_type"])
            if approval_type != ApprovalType.NONE:
                # Check for pending approval request
                approval = await self._get_approval_request(entity_id, entity_type)
                if not approval or approval.status != "approved":
                    logger.warning(f"[GovernanceTrust] Approval required for {key}")
                    return None

        # Update state
        data["state"] = new_state.value
        data["updated_at"] = now.isoformat()
        data["updated_by"] = by
        data["state_history"].append({
            "state": new_state.value,
            "timestamp": now.isoformat(),
            "by": by,
            "reason": reason or f"Transitioned to {new_state.value}",
        })
        data["version"] = data["version"] + 1

        await redis.hset(self.LIFECYCLE_KEY, key, json.dumps(data))

        logger.info(f"[GovernanceTrust] State transition {key}: {current_state.value} -> {new_state.value}")

        return LifecycleEntry(
            entity_id=data["entity_id"],
            entity_type=TrustableType(data["entity_type"]),
            entity_name=data["entity_name"],
            state=new_state,
            version=data["version"],
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by=data["created_by"],
            updated_at=datetime.fromisoformat(data["updated_at"]),
            updated_by=data["updated_by"],
            state_history=data["state_history"],
            approval_type=ApprovalType(data["approval_type"]),
            approvers=data["approvers"],
            pending_approvers=data["pending_approvers"],
            rejection_reason=data.get("rejection_reason"),
            auto_approve_criteria=data.get("auto_approve_criteria", {}),
            metadata=data.get("metadata", {}),
        )

    async def request_approval(
        self,
        entity_id: str,
        entity_type: TrustableType,
        entity_name: str,
        requested_state: LifecycleState,
        requested_by: str,
        context: dict[str, Any] | None = None,
        urgency: str = "normal",
    ) -> ApprovalRequest:
        """Request approval for state transition.

        Args:
            entity_id: Entity identifier
            entity_type: Type of entity
            entity_name: Human-readable name
            requested_state: Target state
            requested_by: Requester
            context: Additional context
            urgency: Request urgency

        Returns:
            Created approval request
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get lifecycle entry
        lifecycle = await self.get_lifecycle_entry(entity_id, entity_type)

        approval_type = lifecycle.approval_type if lifecycle else ApprovalType.SINGLE

        # Determine required approvers
        required_approvers = []
        if approval_type == ApprovalType.SINGLE:
            required_approvers = ["any_approver"]
        elif approval_type == ApprovalType.DUAL:
            required_approvers = ["approver_1", "approver_2"]
        elif approval_type == ApprovalType.COMMITTEE:
            required_approvers = ["committee"]

        # Expiration
        expiry_hours = {"normal": 72, "high": 24, "critical": 4}.get(urgency, 72)

        request = ApprovalRequest(
            id=str(uuid.uuid4())[:8],
            entity_id=entity_id,
            entity_type=entity_type,
            entity_name=entity_name,
            requested_state=requested_state,
            requested_by=requested_by,
            requested_at=now,
            approval_type=approval_type,
            required_approvers=required_approvers,
            current_approvals=[],
            rejections=[],
            status="pending",
            expires_at=now + timedelta(hours=expiry_hours),
            context=context or {},
            urgency=urgency,
        )

        await redis.hset(
            self.APPROVALS_KEY,
            f"{entity_type.value}:{entity_id}",
            json.dumps(request.to_dict()),
        )

        logger.info(f"[GovernanceTrust] Approval requested for {entity_name} by {requested_by}")
        return request

    async def approve(
        self,
        entity_id: str,
        entity_type: TrustableType,
        approver: str,
        comment: str | None = None,
    ) -> ApprovalRequest | None:
        """Approve an approval request."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        key = f"{entity_type.value}:{entity_id}"

        raw = await redis.hget(self.APPROVALS_KEY, key)
        if not raw:
            return None

        data = json.loads(raw)
        if data["status"] != "pending":
            return None

        # Check expiration
        if datetime.fromisoformat(data["expires_at"]) < now:
            data["status"] = "expired"
            await redis.hset(self.APPROVALS_KEY, key, json.dumps(data))
            return None

        # Add approval
        data["current_approvals"].append({
            "approver": approver,
            "approved_at": now.isoformat(),
            "comment": comment,
        })

        # Check if fully approved
        approval_type = ApprovalType(data["approval_type"])
        if approval_type == ApprovalType.SINGLE:
            data["status"] = "approved"
        elif approval_type == ApprovalType.DUAL:
            if len(data["current_approvals"]) >= 2:
                data["status"] = "approved"
        elif approval_type == ApprovalType.COMMITTEE:
            if len(data["current_approvals"]) >= 3:
                data["status"] = "approved"

        await redis.hset(self.APPROVALS_KEY, key, json.dumps(data))

        logger.info(f"[GovernanceTrust] Approval granted by {approver} for {key}")

        return ApprovalRequest(
            id=data["id"],
            entity_id=data["entity_id"],
            entity_type=TrustableType(data["entity_type"]),
            entity_name=data["entity_name"],
            requested_state=LifecycleState(data["requested_state"]),
            requested_by=data["requested_by"],
            requested_at=datetime.fromisoformat(data["requested_at"]),
            approval_type=ApprovalType(data["approval_type"]),
            required_approvers=data["required_approvers"],
            current_approvals=data["current_approvals"],
            rejections=data["rejections"],
            status=data["status"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            context=data["context"],
            urgency=data["urgency"],
        )

    async def reject(
        self,
        entity_id: str,
        entity_type: TrustableType,
        rejector: str,
        reason: str,
    ) -> ApprovalRequest | None:
        """Reject an approval request."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        key = f"{entity_type.value}:{entity_id}"

        raw = await redis.hget(self.APPROVALS_KEY, key)
        if not raw:
            return None

        data = json.loads(raw)
        if data["status"] != "pending":
            return None

        data["rejections"].append({
            "rejector": rejector,
            "rejected_at": now.isoformat(),
            "reason": reason,
        })
        data["status"] = "rejected"

        await redis.hset(self.APPROVALS_KEY, key, json.dumps(data))

        # Update lifecycle entry
        lifecycle_raw = await redis.hget(self.LIFECYCLE_KEY, key)
        if lifecycle_raw:
            lifecycle_data = json.loads(lifecycle_raw)
            lifecycle_data["rejection_reason"] = reason
            await redis.hset(self.LIFECYCLE_KEY, key, json.dumps(lifecycle_data))

        logger.info(f"[GovernanceTrust] Rejection by {rejector} for {key}: {reason}")

        return ApprovalRequest(
            id=data["id"],
            entity_id=data["entity_id"],
            entity_type=TrustableType(data["entity_type"]),
            entity_name=data["entity_name"],
            requested_state=LifecycleState(data["requested_state"]),
            requested_by=data["requested_by"],
            requested_at=datetime.fromisoformat(data["requested_at"]),
            approval_type=ApprovalType(data["approval_type"]),
            required_approvers=data["required_approvers"],
            current_approvals=data["current_approvals"],
            rejections=data["rejections"],
            status=data["status"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            context=data["context"],
            urgency=data["urgency"],
        )

    async def get_lifecycle_entry(
        self,
        entity_id: str,
        entity_type: TrustableType,
    ) -> LifecycleEntry | None:
        """Get lifecycle entry for an entity."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.LIFECYCLE_KEY, f"{entity_type.value}:{entity_id}")

        if not raw:
            return None

        data = json.loads(raw)
        return LifecycleEntry(
            entity_id=data["entity_id"],
            entity_type=TrustableType(data["entity_type"]),
            entity_name=data["entity_name"],
            state=LifecycleState(data["state"]),
            version=data["version"],
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by=data["created_by"],
            updated_at=datetime.fromisoformat(data["updated_at"]),
            updated_by=data["updated_by"],
            state_history=data["state_history"],
            approval_type=ApprovalType(data["approval_type"]),
            approvers=data["approvers"],
            pending_approvers=data["pending_approvers"],
            rejection_reason=data.get("rejection_reason"),
            auto_approve_criteria=data.get("auto_approve_criteria", {}),
            metadata=data.get("metadata", {}),
        )

    async def _get_approval_request(
        self,
        entity_id: str,
        entity_type: TrustableType,
    ) -> ApprovalRequest | None:
        """Get approval request for an entity."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.APPROVALS_KEY, f"{entity_type.value}:{entity_id}")

        if not raw:
            return None

        data = json.loads(raw)
        return ApprovalRequest(
            id=data["id"],
            entity_id=data["entity_id"],
            entity_type=TrustableType(data["entity_type"]),
            entity_name=data["entity_name"],
            requested_state=LifecycleState(data["requested_state"]),
            requested_by=data["requested_by"],
            requested_at=datetime.fromisoformat(data["requested_at"]),
            approval_type=ApprovalType(data["approval_type"]),
            required_approvers=data["required_approvers"],
            current_approvals=data["current_approvals"],
            rejections=data["rejections"],
            status=data["status"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            context=data["context"],
            urgency=data["urgency"],
        )

    async def get_pending_approvals(
        self,
        entity_type: TrustableType | None = None,
    ) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hgetall(self.APPROVALS_KEY)
        results = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)
                if data["status"] != "pending":
                    continue
                if entity_type and data["entity_type"] != entity_type.value:
                    continue

                results.append(ApprovalRequest(
                    id=data["id"],
                    entity_id=data["entity_id"],
                    entity_type=TrustableType(data["entity_type"]),
                    entity_name=data["entity_name"],
                    requested_state=LifecycleState(data["requested_state"]),
                    requested_by=data["requested_by"],
                    requested_at=datetime.fromisoformat(data["requested_at"]),
                    approval_type=ApprovalType(data["approval_type"]),
                    required_approvers=data["required_approvers"],
                    current_approvals=data["current_approvals"],
                    rejections=data["rejections"],
                    status=data["status"],
                    expires_at=datetime.fromisoformat(data["expires_at"]),
                    context=data["context"],
                    urgency=data["urgency"],
                ))
            except Exception:
                continue

        results.sort(key=lambda x: x.requested_at)
        return results

    # ========================================================================
    # Sandbox for New Rules
    # ========================================================================

    async def run_sandbox_test(
        self,
        entity_id: str,
        entity_type: TrustableType,
        entity_name: str,
        rule_definition: dict[str, Any],
        test_cases: list[dict[str, Any]] | None = None,
    ) -> SandboxResult:
        """Run sandbox test for a new rule/policy.

        Args:
            entity_id: Entity identifier
            entity_type: Type of entity
            entity_name: Human-readable name
            rule_definition: Rule definition to test
            test_cases: Custom test cases

        Returns:
            Sandbox execution result
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Default test cases if none provided
        if not test_cases:
            test_cases = self._generate_default_test_cases(entity_type, rule_definition)

        # Execute tests
        results = []
        errors = []
        warnings = []
        side_effects = []
        safety_violations = []

        passed = 0
        failed = 0

        for tc in test_cases:
            try:
                result = self._execute_test_case(rule_definition, tc)
                results.append({
                    "test_case": tc.get("name", "unnamed"),
                    "input": tc.get("input"),
                    "expected": tc.get("expected"),
                    "actual": result.get("output"),
                    "passed": result.get("passed", False),
                    "duration_ms": result.get("duration_ms", 0),
                })

                if result.get("passed"):
                    passed += 1
                else:
                    failed += 1

                if result.get("warning"):
                    warnings.append(result["warning"])

                if result.get("side_effect"):
                    side_effects.append(result["side_effect"])

            except Exception as e:
                errors.append({
                    "test_case": tc.get("name", "unnamed"),
                    "error": str(e),
                })
                failed += 1

        # Check for safety violations
        safety_violations = self._check_safety_violations(rule_definition)

        # Calculate duration
        completed_at = datetime.now(UTC)
        duration_ms = int((completed_at - now).total_seconds() * 1000)

        # Determine status
        if errors:
            status = SandboxStatus.FAILED
        elif failed > 0:
            status = SandboxStatus.FAILED
        elif safety_violations:
            status = SandboxStatus.FAILED
        else:
            status = SandboxStatus.PASSED

        # Generate recommendation
        if status == SandboxStatus.PASSED and not warnings:
            recommendation = "promote"
        elif status == SandboxStatus.PASSED and warnings:
            recommendation = "fix"
        else:
            recommendation = "reject"

        sandbox_result = SandboxResult(
            id=str(uuid.uuid4())[:8],
            entity_id=entity_id,
            entity_type=entity_type,
            entity_name=entity_name,
            status=status,
            started_at=now,
            completed_at=completed_at,
            duration_ms=duration_ms,
            test_cases_run=len(test_cases),
            test_cases_passed=passed,
            test_cases_failed=failed,
            errors=errors,
            warnings=warnings,
            side_effects_detected=side_effects,
            resource_usage={"cpu_percent": 0.1, "memory_mb": 10},
            safety_violations=safety_violations,
            recommendation=recommendation,
            detailed_results=results,
        )

        # Store result
        await redis.hset(
            self.SANDBOX_KEY,
            f"{entity_type.value}:{entity_id}",
            json.dumps(sandbox_result.to_dict()),
        )

        logger.info(f"[GovernanceTrust] Sandbox test for {entity_name}: {status.value}")

        return sandbox_result

    def _generate_default_test_cases(
        self,
        entity_type: TrustableType,
        rule_definition: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate default test cases for a rule."""
        test_cases = []

        # Basic validity test
        test_cases.append({
            "name": "basic_validity",
            "input": {},
            "expected": {"valid": True},
        })

        # Boundary test
        if "threshold" in rule_definition:
            threshold = rule_definition["threshold"]
            test_cases.append({
                "name": "below_threshold",
                "input": {"value": threshold - 1},
                "expected": {"triggered": False},
            })
            test_cases.append({
                "name": "at_threshold",
                "input": {"value": threshold},
                "expected": {"triggered": True},
            })
            test_cases.append({
                "name": "above_threshold",
                "input": {"value": threshold + 1},
                "expected": {"triggered": True},
            })

        # Null input test
        test_cases.append({
            "name": "null_input",
            "input": None,
            "expected": {"error": False},
        })

        return test_cases

    def _execute_test_case(
        self,
        rule_definition: dict[str, Any],
        test_case: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single test case."""
        import time

        start = time.time()

        input_data = test_case.get("input", {})
        expected = test_case.get("expected", {})

        # Simulate rule execution
        output = {}
        passed = True
        warning = None
        side_effect = None

        # Check threshold-based rules
        if "threshold" in rule_definition and input_data:
            value = input_data.get("value", 0) if input_data else 0
            threshold = rule_definition["threshold"]
            output["triggered"] = value >= threshold

            if "triggered" in expected:
                passed = output["triggered"] == expected["triggered"]

        # Check validity
        if "valid" in expected:
            output["valid"] = True
            passed = output["valid"] == expected["valid"]

        # Check for errors
        if input_data is None:
            output["error"] = False
            if "error" in expected:
                passed = output["error"] == expected["error"]

        duration_ms = int((time.time() - start) * 1000)

        return {
            "output": output,
            "passed": passed,
            "duration_ms": duration_ms,
            "warning": warning,
            "side_effect": side_effect,
        }

    def _check_safety_violations(
        self,
        rule_definition: dict[str, Any],
    ) -> list[str]:
        """Check for safety violations in rule definition."""
        violations = []

        # Check for dangerous patterns
        dangerous_patterns = ["DROP", "DELETE", "TRUNCATE", "rm -rf", "sudo"]
        rule_str = json.dumps(rule_definition).upper()

        for pattern in dangerous_patterns:
            if pattern.upper() in rule_str:
                violations.append(f"Dangerous pattern detected: {pattern}")

        # Check for missing safety guards
        if rule_definition.get("action") == "execute":
            if not rule_definition.get("rollback"):
                violations.append("Missing rollback definition for execute action")

        return violations

    async def get_sandbox_result(
        self,
        entity_id: str,
        entity_type: TrustableType,
    ) -> SandboxResult | None:
        """Get sandbox result for an entity."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.SANDBOX_KEY, f"{entity_type.value}:{entity_id}")

        if not raw:
            return None

        data = json.loads(raw)
        return SandboxResult(
            id=data["id"],
            entity_id=data["entity_id"],
            entity_type=TrustableType(data["entity_type"]),
            entity_name=data["entity_name"],
            status=SandboxStatus(data["status"]),
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            duration_ms=data["duration_ms"],
            test_cases_run=data["test_cases_run"],
            test_cases_passed=data["test_cases_passed"],
            test_cases_failed=data["test_cases_failed"],
            errors=data["errors"],
            warnings=data["warnings"],
            side_effects_detected=data["side_effects_detected"],
            resource_usage=data["resource_usage"],
            safety_violations=data["safety_violations"],
            recommendation=data["recommendation"],
            detailed_results=data["detailed_results"],
        )

    # ========================================================================
    # Recommendation Explainability
    # ========================================================================

    async def generate_explanation(
        self,
        recommendation_id: str,
        recommendation_type: str,
        recommendation_text: str,
        decision_context: dict[str, Any],
        level: ExplainabilityLevel = ExplainabilityLevel.STANDARD,
    ) -> RecommendationExplanation:
        """Generate explanation for a recommendation.

        Args:
            recommendation_id: Recommendation identifier
            recommendation_type: Type of recommendation
            recommendation_text: The recommendation text
            decision_context: Context used for decision
            level: Level of explanation detail

        Returns:
            Generated explanation
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Extract decision factors
        decision_factors = self._extract_decision_factors(decision_context)

        # Identify data sources
        data_sources = self._identify_data_sources(decision_context)

        # Calculate confidence breakdown
        confidence_breakdown = self._calculate_confidence_breakdown(decision_context)

        # Find alternatives
        alternatives = self._find_alternatives(recommendation_type, decision_context)

        # Generate why not alternatives
        why_not = self._generate_why_not(alternatives, decision_context)

        # Identify assumptions
        assumptions = self._identify_assumptions(decision_context)

        # Identify limitations
        limitations = self._identify_limitations(decision_context)

        # Gather evidence
        supporting = self._gather_supporting_evidence(decision_context)
        contradicting = self._gather_contradicting_evidence(decision_context)

        # Generate summary
        summary = self._generate_summary(
            recommendation_text,
            decision_factors,
            confidence_breakdown,
        )

        # Generate human-readable explanation
        human_readable = self._generate_human_readable(
            recommendation_text,
            summary,
            decision_factors,
            assumptions,
            limitations,
            level,
        )

        explanation = RecommendationExplanation(
            recommendation_id=recommendation_id,
            recommendation_type=recommendation_type,
            recommendation_text=recommendation_text,
            explanation_level=level,
            summary=summary,
            decision_factors=decision_factors,
            data_sources=data_sources,
            confidence_breakdown=confidence_breakdown,
            alternatives_considered=alternatives,
            why_not_alternatives=why_not,
            assumptions=assumptions,
            limitations=limitations,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            human_readable=human_readable,
            generated_at=now,
        )

        # Store explanation
        await redis.hset(
            self.EXPLANATIONS_KEY,
            recommendation_id,
            json.dumps(explanation.to_dict()),
        )

        logger.info(f"[GovernanceTrust] Generated explanation for recommendation {recommendation_id}")

        return explanation

    def _extract_decision_factors(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract decision factors from context."""
        factors = []

        # Historical performance
        if "historical_success_rate" in context:
            factors.append({
                "name": "Historical Success Rate",
                "value": context["historical_success_rate"],
                "weight": 0.25,
                "impact": "positive" if context["historical_success_rate"] > 0.7 else "negative",
                "description": f"Past success rate: {context['historical_success_rate']:.1%}",
            })

        # Pattern match
        if "pattern_match_score" in context:
            factors.append({
                "name": "Pattern Match",
                "value": context["pattern_match_score"],
                "weight": 0.20,
                "impact": "positive" if context["pattern_match_score"] > 0.6 else "neutral",
                "description": f"Match with known patterns: {context['pattern_match_score']:.1%}",
            })

        # Severity
        if "incident_severity" in context:
            severity_map = {"p0": 1.0, "p1": 0.8, "p2": 0.6, "p3": 0.4}
            factors.append({
                "name": "Incident Severity",
                "value": severity_map.get(context["incident_severity"], 0.5),
                "weight": 0.15,
                "impact": "high_priority" if context["incident_severity"] in ["p0", "p1"] else "normal",
                "description": f"Severity: {context['incident_severity'].upper()}",
            })

        # Time sensitivity
        if "time_sensitive" in context:
            factors.append({
                "name": "Time Sensitivity",
                "value": 1.0 if context["time_sensitive"] else 0.5,
                "weight": 0.10,
                "impact": "urgent" if context["time_sensitive"] else "normal",
                "description": "Time-sensitive action required" if context["time_sensitive"] else "Normal priority",
            })

        # Resource availability
        if "resources_available" in context:
            factors.append({
                "name": "Resource Availability",
                "value": context["resources_available"],
                "weight": 0.10,
                "impact": "feasible" if context["resources_available"] > 0.5 else "constrained",
                "description": f"Resource availability: {context['resources_available']:.1%}",
            })

        return factors

    def _identify_data_sources(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Identify data sources used in decision."""
        sources = []

        if context.get("incident_data"):
            sources.append({
                "name": "Incident Data",
                "type": "real-time",
                "freshness": "current",
                "reliability": 0.95,
            })

        if context.get("historical_incidents"):
            sources.append({
                "name": "Historical Incidents",
                "type": "historical",
                "freshness": "last_90_days",
                "reliability": 0.85,
            })

        if context.get("runbook_database"):
            sources.append({
                "name": "Runbook Database",
                "type": "knowledge_base",
                "freshness": "last_updated",
                "reliability": 0.90,
            })

        if context.get("metrics"):
            sources.append({
                "name": "System Metrics",
                "type": "real-time",
                "freshness": "current",
                "reliability": 0.95,
            })

        return sources

    def _calculate_confidence_breakdown(
        self,
        context: dict[str, Any],
    ) -> dict[str, float]:
        """Calculate confidence breakdown."""
        breakdown = {}

        breakdown["data_quality"] = context.get("data_quality_score", 0.7)
        breakdown["model_confidence"] = context.get("model_confidence", 0.75)
        breakdown["historical_accuracy"] = context.get("historical_accuracy", 0.8)
        breakdown["expert_validation"] = 0.9 if context.get("expert_validated") else 0.5

        return breakdown

    def _find_alternatives(
        self,
        recommendation_type: str,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Find alternative recommendations."""
        alternatives = []

        if recommendation_type == "runbook":
            alternatives.append({
                "option": "Manual investigation",
                "confidence": 0.4,
                "risk": "medium",
                "time_estimate": "30-60 minutes",
            })
            alternatives.append({
                "option": "Escalate to senior engineer",
                "confidence": 0.6,
                "risk": "low",
                "time_estimate": "15-30 minutes",
            })

        elif recommendation_type == "fix":
            alternatives.append({
                "option": "Workaround instead of fix",
                "confidence": 0.5,
                "risk": "medium",
                "time_estimate": "10-15 minutes",
            })
            alternatives.append({
                "option": "Rollback to previous version",
                "confidence": 0.7,
                "risk": "low",
                "time_estimate": "5-10 minutes",
            })

        return alternatives

    def _generate_why_not(
        self,
        alternatives: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[str]:
        """Generate reasons for not choosing alternatives."""
        reasons = []

        for alt in alternatives:
            if alt.get("confidence", 0) < 0.6:
                reasons.append(f"'{alt['option']}' has lower confidence ({alt['confidence']:.0%})")
            if alt.get("risk") == "high":
                reasons.append(f"'{alt['option']}' carries higher risk")
            if "60 minutes" in alt.get("time_estimate", ""):
                reasons.append(f"'{alt['option']}' takes longer to execute")

        return reasons

    def _identify_assumptions(
        self,
        context: dict[str, Any],
    ) -> list[str]:
        """Identify assumptions in the recommendation."""
        assumptions = []

        if context.get("assumes_healthy_dependencies", True):
            assumptions.append("Dependencies are functioning normally")

        if context.get("assumes_sufficient_resources", True):
            assumptions.append("Sufficient system resources are available")

        if context.get("assumes_no_concurrent_changes", True):
            assumptions.append("No concurrent changes are being deployed")

        if context.get("historical_data_available", True):
            assumptions.append("Historical data is representative of current state")

        return assumptions

    def _identify_limitations(
        self,
        context: dict[str, Any],
    ) -> list[str]:
        """Identify limitations of the recommendation."""
        limitations = []

        if context.get("limited_data", False):
            limitations.append("Limited historical data available for this scenario")

        if context.get("novel_situation", False):
            limitations.append("This appears to be a novel situation not seen before")

        if not context.get("expert_validated", False):
            limitations.append("Recommendation has not been validated by domain expert")

        limitations.append("Recommendation based on available data at time of analysis")

        return limitations

    def _gather_supporting_evidence(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Gather supporting evidence."""
        evidence = []

        if context.get("similar_incidents"):
            evidence.append({
                "type": "similar_incidents",
                "count": len(context["similar_incidents"]),
                "success_rate": context.get("similar_resolution_rate", 0.8),
                "description": "Similar incidents were resolved using this approach",
            })

        if context.get("pattern_matches"):
            evidence.append({
                "type": "pattern_match",
                "patterns": context["pattern_matches"],
                "description": "Known patterns match this incident",
            })

        return evidence

    def _gather_contradicting_evidence(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Gather contradicting evidence."""
        evidence = []

        if context.get("failed_similar_attempts"):
            evidence.append({
                "type": "failed_attempts",
                "count": context["failed_similar_attempts"],
                "description": "Some similar attempts have failed in the past",
            })

        if context.get("risk_factors"):
            evidence.append({
                "type": "risk_factors",
                "factors": context["risk_factors"],
                "description": "Risk factors that may affect outcome",
            })

        return evidence

    def _generate_summary(
        self,
        recommendation_text: str,
        factors: list[dict[str, Any]],
        confidence: dict[str, float],
    ) -> str:
        """Generate explanation summary."""
        avg_confidence = sum(confidence.values()) / len(confidence) if confidence else 0.5

        top_factors = sorted(factors, key=lambda x: x.get("weight", 0), reverse=True)[:2]
        factor_names = [f["name"] for f in top_factors]

        return (
            f"Recommendation based on {', '.join(factor_names)}. "
            f"Overall confidence: {avg_confidence:.0%}."
        )

    def _generate_human_readable(
        self,
        recommendation_text: str,
        summary: str,
        factors: list[dict[str, Any]],
        assumptions: list[str],
        limitations: list[str],
        level: ExplainabilityLevel,
    ) -> str:
        """Generate human-readable explanation."""
        parts = [f"**Recommendation:** {recommendation_text}", "", f"**Summary:** {summary}"]

        if level in [ExplainabilityLevel.STANDARD, ExplainabilityLevel.DETAILED, ExplainabilityLevel.DEBUG]:
            parts.append("")
            parts.append("**Key Factors:**")
            for factor in factors[:3]:
                parts.append(f"- {factor['name']}: {factor['description']}")

        if level in [ExplainabilityLevel.DETAILED, ExplainabilityLevel.DEBUG]:
            if assumptions:
                parts.append("")
                parts.append("**Assumptions:**")
                for assumption in assumptions:
                    parts.append(f"- {assumption}")

            if limitations:
                parts.append("")
                parts.append("**Limitations:**")
                for limitation in limitations:
                    parts.append(f"- {limitation}")

        return "\n".join(parts)

    async def get_explanation(
        self,
        recommendation_id: str,
    ) -> RecommendationExplanation | None:
        """Get stored explanation for a recommendation."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.EXPLANATIONS_KEY, recommendation_id)

        if not raw:
            return None

        data = json.loads(raw)
        return RecommendationExplanation(
            recommendation_id=data["recommendation_id"],
            recommendation_type=data["recommendation_type"],
            recommendation_text=data["recommendation_text"],
            explanation_level=ExplainabilityLevel(data["explanation_level"]),
            summary=data["summary"],
            decision_factors=data["decision_factors"],
            data_sources=data["data_sources"],
            confidence_breakdown=data["confidence_breakdown"],
            alternatives_considered=data["alternatives_considered"],
            why_not_alternatives=data["why_not_alternatives"],
            assumptions=data["assumptions"],
            limitations=data["limitations"],
            supporting_evidence=data["supporting_evidence"],
            contradicting_evidence=data["contradicting_evidence"],
            human_readable=data["human_readable"],
            generated_at=datetime.fromisoformat(data["generated_at"]),
        )

    # ========================================================================
    # Trust Propagation
    # ========================================================================

    async def register_relationship(
        self,
        source_entity_id: str,
        source_entity_type: TrustableType,
        target_entity_id: str,
        target_entity_type: TrustableType,
        relationship: str,
    ) -> dict[str, Any]:
        """Register a relationship between entities for trust propagation.

        Args:
            source_entity_id: Source entity ID
            source_entity_type: Source entity type
            target_entity_id: Target entity ID
            target_entity_type: Target entity type
            relationship: Relationship type (depends_on, derived_from, etc.)

        Returns:
            Registered relationship
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        relation = {
            "source_entity_id": source_entity_id,
            "source_entity_type": source_entity_type.value,
            "target_entity_id": target_entity_id,
            "target_entity_type": target_entity_type.value,
            "relationship": relationship,
            "created_at": now.isoformat(),
        }

        key = f"{source_entity_type.value}:{source_entity_id}:{target_entity_type.value}:{target_entity_id}"
        await redis.hset(self.RELATIONS_KEY, key, json.dumps(relation))

        logger.info(f"[GovernanceTrust] Registered relationship: {source_entity_id} --{relationship}--> {target_entity_id}")

        return relation

    async def propagate_trust(
        self,
        source_entity_id: str,
        source_entity_type: TrustableType,
    ) -> list[TrustPropagation]:
        """Propagate trust from source entity to all related entities.

        Args:
            source_entity_id: Source entity ID
            source_entity_type: Source entity type

        Returns:
            List of trust propagation results
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get source trust score
        source_score = await self.get_trust_score(source_entity_id, source_entity_type)
        if not source_score:
            return []

        # Find related entities
        relations = await redis.hgetall(self.RELATIONS_KEY)
        propagations = []

        for key, rel_str in relations.items():
            try:
                rel = json.loads(rel_str)
                if (rel["source_entity_id"] == source_entity_id and
                    rel["source_entity_type"] == source_entity_type.value):

                    target_id = rel["target_entity_id"]
                    target_type = TrustableType(rel["target_entity_type"])
                    relationship = rel["relationship"]

                    # Get propagation factor
                    factor = PROPAGATION_FACTORS.get(relationship, 0.3)

                    # Get target's current score
                    target_score = await self.get_trust_score(target_id, target_type)
                    original_score = target_score.score if target_score else 0.5

                    # Calculate propagated contribution
                    propagated_contribution = source_score.score * factor

                    # Blend with existing score (weighted average)
                    new_score = (original_score * 0.7) + (propagated_contribution * 0.3)
                    new_score = max(0, min(1, new_score))

                    # Update target score
                    if target_score:
                        target_score_data = await redis.hget(
                            f"{self.TRUST_KEY}:scores",
                            f"{target_type.value}:{target_id}"
                        )
                        if target_score_data:
                            data = json.loads(target_score_data)
                            data["score"] = new_score
                            data["components"]["propagated_trust"] = propagated_contribution
                            await redis.hset(
                                f"{self.TRUST_KEY}:scores",
                                f"{target_type.value}:{target_id}",
                                json.dumps(data)
                            )

                    propagation = TrustPropagation(
                        source_entity_id=source_entity_id,
                        source_entity_type=source_entity_type,
                        target_entity_id=target_id,
                        target_entity_type=target_type,
                        relationship=relationship,
                        propagation_factor=factor,
                        propagated_score=propagated_contribution,
                        original_target_score=original_score,
                        new_target_score=new_score,
                        propagated_at=now,
                    )
                    propagations.append(propagation)

                    # Store propagation record
                    await redis.lpush(
                        f"{self.PROPAGATION_KEY}:history",
                        json.dumps(propagation.to_dict())
                    )
                    await redis.ltrim(f"{self.PROPAGATION_KEY}:history", 0, 999)

            except Exception as e:
                logger.error(f"[GovernanceTrust] Propagation error: {e}")
                continue

        logger.info(f"[GovernanceTrust] Propagated trust from {source_entity_id} to {len(propagations)} entities")

        return propagations

    async def get_trust_chain(
        self,
        entity_id: str,
        entity_type: TrustableType,
    ) -> dict[str, Any]:
        """Get trust chain for an entity showing all trust influences."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Get entity's score
        score = await self.get_trust_score(entity_id, entity_type)

        # Find incoming relationships (what affects this entity)
        relations = await redis.hgetall(self.RELATIONS_KEY)
        influences = []

        for rel_str in relations.values():
            try:
                rel = json.loads(rel_str)
                if (rel["target_entity_id"] == entity_id and
                    rel["target_entity_type"] == entity_type.value):

                    source_score = await self.get_trust_score(
                        rel["source_entity_id"],
                        TrustableType(rel["source_entity_type"])
                    )

                    influences.append({
                        "source_id": rel["source_entity_id"],
                        "source_type": rel["source_entity_type"],
                        "relationship": rel["relationship"],
                        "source_trust": source_score.score if source_score else None,
                        "propagation_factor": PROPAGATION_FACTORS.get(rel["relationship"], 0.3),
                    })
            except Exception:
                continue

        return {
            "entity_id": entity_id,
            "entity_type": entity_type.value,
            "current_score": score.score if score else None,
            "influences": influences,
            "influence_count": len(influences),
        }

    # ========================================================================
    # Knowledge Drift Detection
    # ========================================================================

    async def detect_drift(
        self,
        entity_id: str,
        entity_type: TrustableType,
        entity_name: str,
        current_metrics: dict[str, float],
        baseline_metrics: dict[str, float] | None = None,
    ) -> list[DriftAlert]:
        """Detect knowledge drift by comparing current vs baseline metrics.

        Args:
            entity_id: Entity identifier
            entity_type: Type of entity
            entity_name: Human-readable name
            current_metrics: Current metric values
            baseline_metrics: Baseline metric values (fetched if not provided)

        Returns:
            List of drift alerts
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        alerts = []

        # Get baseline if not provided
        if baseline_metrics is None:
            baseline_key = f"{self.DRIFT_KEY}:baseline:{entity_type.value}:{entity_id}"
            baseline_raw = await redis.get(baseline_key)
            if baseline_raw:
                baseline_metrics = json.loads(baseline_raw)
            else:
                # No baseline - store current as baseline
                await redis.set(baseline_key, json.dumps(current_metrics))
                return []

        # Check each drift type
        drift_mappings = {
            "accuracy": DriftType.ACCURACY_DRIFT,
            "success_rate": DriftType.ACCURACY_DRIFT,
            "usage_count": DriftType.USAGE_DRIFT,
            "usage_frequency": DriftType.USAGE_DRIFT,
            "response_time": DriftType.PERFORMANCE_DRIFT,
            "latency": DriftType.PERFORMANCE_DRIFT,
            "relevance_score": DriftType.RELEVANCE_DRIFT,
            "conflict_count": DriftType.CONFLICT_DRIFT,
        }

        for metric_name, current_value in current_metrics.items():
            baseline_value = baseline_metrics.get(metric_name)
            if baseline_value is None or baseline_value == 0:
                continue

            # Calculate drift percentage
            drift_pct = abs(current_value - baseline_value) / baseline_value

            # Determine drift type
            drift_type = drift_mappings.get(metric_name, DriftType.ACCURACY_DRIFT)
            thresholds = DRIFT_THRESHOLDS.get(drift_type, {"warning": 0.15, "critical": 0.30})

            # Check severity
            severity = None
            if drift_pct >= thresholds["critical"]:
                severity = DriftSeverity.CRITICAL
            elif drift_pct >= thresholds["warning"]:
                severity = DriftSeverity.WARNING

            if severity:
                direction = "increased" if current_value > baseline_value else "decreased"
                alert = DriftAlert(
                    id=str(uuid.uuid4())[:8],
                    entity_id=entity_id,
                    entity_type=entity_type,
                    entity_name=entity_name,
                    drift_type=drift_type,
                    severity=severity,
                    current_value=current_value,
                    baseline_value=baseline_value,
                    drift_percentage=drift_pct * 100,
                    detected_at=now,
                    description=f"{metric_name} {direction} by {drift_pct:.1%} from baseline",
                    evidence=[{
                        "metric": metric_name,
                        "baseline": baseline_value,
                        "current": current_value,
                        "change": drift_pct,
                    }],
                    recommended_actions=self._generate_drift_actions(drift_type, severity),
                )
                alerts.append(alert)

                # Store alert
                await redis.hset(
                    f"{self.DRIFT_KEY}:alerts",
                    alert.id,
                    json.dumps(alert.to_dict())
                )

        if alerts:
            logger.warning(f"[GovernanceTrust] Detected {len(alerts)} drift alerts for {entity_name}")

        return alerts

    def _generate_drift_actions(
        self,
        drift_type: DriftType,
        severity: DriftSeverity,
    ) -> list[str]:
        """Generate recommended actions for drift."""
        actions = []

        if severity == DriftSeverity.CRITICAL:
            actions.append("Immediate investigation required")
            actions.append("Consider suspending entity until resolved")

        if drift_type == DriftType.ACCURACY_DRIFT:
            actions.append("Review and retrain model/rules")
            actions.append("Check for data quality issues")
        elif drift_type == DriftType.USAGE_DRIFT:
            actions.append("Analyze usage pattern changes")
            actions.append("Check for alternative solutions being used")
        elif drift_type == DriftType.PERFORMANCE_DRIFT:
            actions.append("Profile and optimize performance")
            actions.append("Check resource constraints")
        elif drift_type == DriftType.RELEVANCE_DRIFT:
            actions.append("Update content with current information")
            actions.append("Review against current requirements")
        elif drift_type == DriftType.CONFLICT_DRIFT:
            actions.append("Resolve policy conflicts")
            actions.append("Review overlapping rules")

        return actions

    async def get_drift_alerts(
        self,
        entity_type: TrustableType | None = None,
        severity: DriftSeverity | None = None,
        include_resolved: bool = False,
    ) -> list[DriftAlert]:
        """Get drift alerts with optional filtering."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hgetall(f"{self.DRIFT_KEY}:alerts")
        alerts = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)

                if not include_resolved and data.get("resolved", False):
                    continue
                if entity_type and data["entity_type"] != entity_type.value:
                    continue
                if severity and data["severity"] != severity.value:
                    continue

                alerts.append(DriftAlert(
                    id=data["id"],
                    entity_id=data["entity_id"],
                    entity_type=TrustableType(data["entity_type"]),
                    entity_name=data["entity_name"],
                    drift_type=DriftType(data["drift_type"]),
                    severity=DriftSeverity(data["severity"]),
                    current_value=data["current_value"],
                    baseline_value=data["baseline_value"],
                    drift_percentage=data["drift_percentage"],
                    detected_at=datetime.fromisoformat(data["detected_at"]),
                    description=data["description"],
                    evidence=data["evidence"],
                    recommended_actions=data["recommended_actions"],
                    acknowledged=data.get("acknowledged", False),
                    acknowledged_by=data.get("acknowledged_by"),
                    acknowledged_at=datetime.fromisoformat(data["acknowledged_at"]) if data.get("acknowledged_at") else None,
                    resolved=data.get("resolved", False),
                    resolution=data.get("resolution"),
                ))
            except Exception:
                continue

        alerts.sort(key=lambda x: (0 if x.severity == DriftSeverity.CRITICAL else 1, x.detected_at), reverse=True)
        return alerts

    async def acknowledge_drift_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
    ) -> DriftAlert | None:
        """Acknowledge a drift alert."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        raw = await redis.hget(f"{self.DRIFT_KEY}:alerts", alert_id)
        if not raw:
            return None

        data = json.loads(raw)
        data["acknowledged"] = True
        data["acknowledged_by"] = acknowledged_by
        data["acknowledged_at"] = now.isoformat()

        await redis.hset(f"{self.DRIFT_KEY}:alerts", alert_id, json.dumps(data))

        logger.info(f"[GovernanceTrust] Drift alert {alert_id} acknowledged by {acknowledged_by}")

        return await self._parse_drift_alert(data)

    async def resolve_drift_alert(
        self,
        alert_id: str,
        resolution: str,
        resolved_by: str,
    ) -> DriftAlert | None:
        """Resolve a drift alert."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        raw = await redis.hget(f"{self.DRIFT_KEY}:alerts", alert_id)
        if not raw:
            return None

        data = json.loads(raw)
        data["resolved"] = True
        data["resolution"] = resolution

        await redis.hset(f"{self.DRIFT_KEY}:alerts", alert_id, json.dumps(data))

        logger.info(f"[GovernanceTrust] Drift alert {alert_id} resolved by {resolved_by}")

        return await self._parse_drift_alert(data)

    async def _parse_drift_alert(self, data: dict[str, Any]) -> DriftAlert:
        """Parse drift alert from dict."""
        return DriftAlert(
            id=data["id"],
            entity_id=data["entity_id"],
            entity_type=TrustableType(data["entity_type"]),
            entity_name=data["entity_name"],
            drift_type=DriftType(data["drift_type"]),
            severity=DriftSeverity(data["severity"]),
            current_value=data["current_value"],
            baseline_value=data["baseline_value"],
            drift_percentage=data["drift_percentage"],
            detected_at=datetime.fromisoformat(data["detected_at"]),
            description=data["description"],
            evidence=data["evidence"],
            recommended_actions=data["recommended_actions"],
            acknowledged=data.get("acknowledged", False),
            acknowledged_by=data.get("acknowledged_by"),
            acknowledged_at=datetime.fromisoformat(data["acknowledged_at"]) if data.get("acknowledged_at") else None,
            resolved=data.get("resolved", False),
            resolution=data.get("resolution"),
        )

    # ========================================================================
    # Mandatory Review for Low-Trust Critical Items
    # ========================================================================

    async def check_mandatory_review(
        self,
        entity_id: str,
        entity_type: TrustableType,
        entity_name: str,
        criticality: str,
        trust_score: float | None = None,
    ) -> MandatoryReview | None:
        """Check if entity requires mandatory review.

        Args:
            entity_id: Entity identifier
            entity_type: Type of entity
            entity_name: Human-readable name
            criticality: Criticality level (low, medium, high, critical)
            trust_score: Trust score (fetched if not provided)

        Returns:
            Mandatory review requirement if needed, None otherwise
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get trust score if not provided
        if trust_score is None:
            score = await self.get_trust_score(entity_id, entity_type)
            trust_score = score.score if score else 0.5

        # Check triggers
        trigger = MANDATORY_REVIEW_TRIGGERS["low_trust_critical"]
        needs_review = (
            trust_score < trigger["trust_threshold"] and
            criticality in trigger["criticality"]
        )

        if not needs_review:
            return None

        # Determine requirement level
        if trust_score < 0.2:
            requirement = ReviewRequirement.EMERGENCY
            due_hours = 4
        elif trust_score < 0.3:
            requirement = ReviewRequirement.MANDATORY
            due_hours = 24
        else:
            requirement = ReviewRequirement.MANDATORY
            due_hours = 72

        # Determine reviewers based on criticality
        reviewers = []
        if criticality == "critical":
            reviewers = ["security-team", "senior-engineer"]
        elif criticality == "high":
            reviewers = ["senior-engineer"]
        else:
            reviewers = ["any-reviewer"]

        review = MandatoryReview(
            id=str(uuid.uuid4())[:8],
            entity_id=entity_id,
            entity_type=entity_type,
            entity_name=entity_name,
            requirement=requirement,
            reason=f"Low trust score ({trust_score:.2f}) for {criticality} criticality item",
            trust_score=trust_score,
            criticality=criticality,
            created_at=now,
            due_date=now + timedelta(hours=due_hours),
            assigned_reviewers=reviewers,
            completed_reviews=[],
            status="pending",
            blocking=criticality in ["high", "critical"],
        )

        # Store review
        await redis.hset(
            self.REVIEWS_KEY,
            f"{entity_type.value}:{entity_id}",
            json.dumps(review.to_dict())
        )

        logger.warning(f"[GovernanceTrust] Mandatory review required for {entity_name}: {requirement.value}")

        return review

    async def submit_review(
        self,
        entity_id: str,
        entity_type: TrustableType,
        reviewer: str,
        approved: bool,
        comments: str,
        new_trust_assessment: float | None = None,
    ) -> MandatoryReview | None:
        """Submit a review for mandatory review requirement."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        key = f"{entity_type.value}:{entity_id}"
        raw = await redis.hget(self.REVIEWS_KEY, key)
        if not raw:
            return None

        data = json.loads(raw)

        # Add review
        data["completed_reviews"].append({
            "reviewer": reviewer,
            "approved": approved,
            "comments": comments,
            "new_trust_assessment": new_trust_assessment,
            "reviewed_at": now.isoformat(),
        })

        # Check if all required reviews completed
        required_count = len(data["assigned_reviewers"])
        completed_count = len(data["completed_reviews"])
        all_approved = all(r["approved"] for r in data["completed_reviews"])

        if completed_count >= required_count:
            data["status"] = "completed" if all_approved else "rejected"
            data["blocking"] = False
        else:
            data["status"] = "in_progress"

        await redis.hset(self.REVIEWS_KEY, key, json.dumps(data))

        logger.info(f"[GovernanceTrust] Review submitted for {entity_id} by {reviewer}: {'approved' if approved else 'rejected'}")

        return self._parse_mandatory_review(data)

    async def get_pending_reviews(
        self,
        entity_type: TrustableType | None = None,
        blocking_only: bool = False,
    ) -> list[MandatoryReview]:
        """Get pending mandatory reviews."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        raw = await redis.hgetall(self.REVIEWS_KEY)
        reviews = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)

                if data["status"] not in ["pending", "in_progress"]:
                    continue
                if entity_type and data["entity_type"] != entity_type.value:
                    continue
                if blocking_only and not data["blocking"]:
                    continue

                review = self._parse_mandatory_review(data)

                # Check if overdue
                if review.due_date < now:
                    data["status"] = "overdue"
                    data["escalation_level"] = data.get("escalation_level", 0) + 1
                    await redis.hset(
                        self.REVIEWS_KEY,
                        f"{data['entity_type']}:{data['entity_id']}",
                        json.dumps(data)
                    )
                    review = self._parse_mandatory_review(data)

                reviews.append(review)
            except Exception:
                continue

        reviews.sort(key=lambda r: (r.blocking, r.due_date), reverse=True)
        return reviews

    def _parse_mandatory_review(self, data: dict[str, Any]) -> MandatoryReview:
        """Parse mandatory review from dict."""
        return MandatoryReview(
            id=data["id"],
            entity_id=data["entity_id"],
            entity_type=TrustableType(data["entity_type"]),
            entity_name=data["entity_name"],
            requirement=ReviewRequirement(data["requirement"]),
            reason=data["reason"],
            trust_score=data["trust_score"],
            criticality=data["criticality"],
            created_at=datetime.fromisoformat(data["created_at"]),
            due_date=datetime.fromisoformat(data["due_date"]),
            assigned_reviewers=data["assigned_reviewers"],
            completed_reviews=data["completed_reviews"],
            status=data["status"],
            blocking=data["blocking"],
            escalation_level=data.get("escalation_level", 0),
        )

    # ========================================================================
    # Promotion Gates (Sandbox to Active)
    # ========================================================================

    async def check_promotion_gates(
        self,
        entity_id: str,
        entity_type: TrustableType,
        entity_name: str,
        context: dict[str, Any] | None = None,
    ) -> PromotionRequest:
        """Check all promotion gates for entity.

        Args:
            entity_id: Entity identifier
            entity_type: Type of entity
            entity_name: Human-readable name
            context: Additional context

        Returns:
            Promotion request with gate status
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        ctx = context or {}

        gates = []
        blocking_gates = []

        for gate_config in DEFAULT_PROMOTION_GATES:
            gate_type = gate_config["gate_type"]
            passed = False
            details = {}
            blocker_reason = None

            if gate_type == PromotionGateType.SANDBOX_PASS:
                # Check sandbox result
                sandbox_result = await self.get_sandbox_result(entity_id, entity_type)
                passed = sandbox_result is not None and sandbox_result.status == SandboxStatus.PASSED
                details = {
                    "sandbox_status": sandbox_result.status.value if sandbox_result else "not_run",
                    "tests_passed": sandbox_result.test_cases_passed if sandbox_result else 0,
                }
                if not passed:
                    blocker_reason = "Sandbox tests not passed"

            elif gate_type == PromotionGateType.TRUST_THRESHOLD:
                # Check trust score
                threshold = gate_config.get("threshold", 0.6)
                score = await self.get_trust_score(entity_id, entity_type)
                current_score = score.score if score else 0
                passed = current_score >= threshold
                details = {"current_score": current_score, "threshold": threshold}
                if not passed:
                    blocker_reason = f"Trust score {current_score:.2f} below threshold {threshold}"

            elif gate_type == PromotionGateType.APPROVAL_REQUIRED:
                # Check approval status
                approval = await self._get_approval_request(entity_id, entity_type)
                passed = approval is not None and approval.status == "approved"
                details = {"approval_status": approval.status if approval else "none"}
                if not passed:
                    blocker_reason = "Required approval not obtained"

            elif gate_type == PromotionGateType.NO_CONFLICTS:
                # Check for policy conflicts
                conflicts = ctx.get("conflicts", [])
                passed = len(conflicts) == 0
                details = {"conflict_count": len(conflicts)}
                if not passed:
                    blocker_reason = f"{len(conflicts)} policy conflicts detected"

            elif gate_type == PromotionGateType.ROLLBACK_READY:
                # Check rollback plan
                has_rollback = ctx.get("rollback_defined", False)
                passed = has_rollback
                details = {"rollback_defined": has_rollback}
                if not passed and gate_config["required"]:
                    blocker_reason = "No rollback plan defined"

            elif gate_type == PromotionGateType.REVIEW_COMPLETE:
                # Check mandatory review
                review_raw = await redis.hget(self.REVIEWS_KEY, f"{entity_type.value}:{entity_id}")
                if review_raw:
                    review_data = json.loads(review_raw)
                    passed = review_data["status"] == "completed"
                    details = {"review_status": review_data["status"]}
                else:
                    passed = True  # No review required
                    details = {"review_status": "not_required"}
                if not passed:
                    blocker_reason = "Mandatory review not completed"

            elif gate_type == PromotionGateType.STABILITY_PERIOD:
                # Check stability period
                stability_days = ctx.get("days_since_last_change", 0)
                required_days = gate_config.get("days", 7)
                passed = stability_days >= required_days
                details = {"days_stable": stability_days, "required_days": required_days}
                if not passed:
                    blocker_reason = f"Only {stability_days} days stable, need {required_days}"

            gate = PromotionGate(
                gate_type=gate_type,
                name=gate_config["name"],
                description=gate_config["description"],
                required=gate_config["required"],
                passed=passed,
                details=details,
                checked_at=now,
                blocker_reason=blocker_reason,
            )
            gates.append(gate)

            if gate_config["required"] and not passed:
                blocking_gates.append(gate_config["name"])

        all_passed = len(blocking_gates) == 0

        promotion = PromotionRequest(
            id=str(uuid.uuid4())[:8],
            entity_id=entity_id,
            entity_type=entity_type,
            entity_name=entity_name,
            requested_by=ctx.get("requested_by", "system"),
            requested_at=now,
            gates=gates,
            all_gates_passed=all_passed,
            blocking_gates=blocking_gates,
            status="approved" if all_passed else "pending",
        )

        # Store promotion request
        await redis.hset(
            self.PROMOTIONS_KEY,
            f"{entity_type.value}:{entity_id}",
            json.dumps(promotion.to_dict())
        )

        logger.info(f"[GovernanceTrust] Promotion gates checked for {entity_name}: {'all passed' if all_passed else f'{len(blocking_gates)} blockers'}")

        return promotion

    async def promote_to_active(
        self,
        entity_id: str,
        entity_type: TrustableType,
        promoted_by: str,
        force: bool = False,
    ) -> PromotionRequest | None:
        """Promote entity from sandbox to active state.

        Args:
            entity_id: Entity identifier
            entity_type: Type of entity
            promoted_by: Actor promoting
            force: Force promotion even with blockers

        Returns:
            Updated promotion request
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        key = f"{entity_type.value}:{entity_id}"
        raw = await redis.hget(self.PROMOTIONS_KEY, key)
        if not raw:
            return None

        data = json.loads(raw)

        if not data["all_gates_passed"] and not force:
            logger.warning(f"[GovernanceTrust] Cannot promote {entity_id}: gates not passed")
            return None

        data["status"] = "promoted"
        data["promoted_at"] = now.isoformat()
        data["promoted_by"] = promoted_by

        await redis.hset(self.PROMOTIONS_KEY, key, json.dumps(data))

        # Update lifecycle state
        await self.transition_state(
            entity_id=entity_id,
            entity_type=entity_type,
            new_state=LifecycleState.ACTIVE,
            by=promoted_by,
            reason="Promotion gates passed" if data["all_gates_passed"] else "Force promoted",
        )

        logger.info(f"[GovernanceTrust] Entity {entity_id} promoted to ACTIVE by {promoted_by}")

        return self._parse_promotion_request(data)

    async def get_pending_promotions(
        self,
        entity_type: TrustableType | None = None,
    ) -> list[PromotionRequest]:
        """Get pending promotion requests."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hgetall(self.PROMOTIONS_KEY)
        promotions = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)
                if data["status"] not in ["pending", "approved"]:
                    continue
                if entity_type and data["entity_type"] != entity_type.value:
                    continue

                promotions.append(self._parse_promotion_request(data))
            except Exception:
                continue

        return promotions

    def _parse_promotion_request(self, data: dict[str, Any]) -> PromotionRequest:
        """Parse promotion request from dict."""
        gates = [
            PromotionGate(
                gate_type=PromotionGateType(g["gate_type"]),
                name=g["name"],
                description=g["description"],
                required=g["required"],
                passed=g["passed"],
                details=g["details"],
                checked_at=datetime.fromisoformat(g["checked_at"]),
                blocker_reason=g.get("blocker_reason"),
            )
            for g in data["gates"]
        ]

        return PromotionRequest(
            id=data["id"],
            entity_id=data["entity_id"],
            entity_type=TrustableType(data["entity_type"]),
            entity_name=data["entity_name"],
            requested_by=data["requested_by"],
            requested_at=datetime.fromisoformat(data["requested_at"]),
            gates=gates,
            all_gates_passed=data["all_gates_passed"],
            blocking_gates=data["blocking_gates"],
            status=data["status"],
            promoted_at=datetime.fromisoformat(data["promoted_at"]) if data.get("promoted_at") else None,
            promoted_by=data.get("promoted_by"),
            rejection_reason=data.get("rejection_reason"),
        )

    # ========================================================================
    # Unified Governance Dashboard
    # ========================================================================

    async def get_full_dashboard(self) -> GovernanceDashboardData:
        """Get comprehensive governance dashboard data."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Trust distribution
        trust_scores = await redis.hgetall(f"{self.TRUST_KEY}:scores")
        trust_distribution = {"untrusted": 0, "low": 0, "medium": 0, "high": 0, "verified": 0}
        low_trust_critical = []
        prev_scores = []

        for data_str in trust_scores.values():
            try:
                data = json.loads(data_str)
                level = data.get("level", "medium")
                trust_distribution[level] = trust_distribution.get(level, 0) + 1

                # Collect low trust critical items
                if data["score"] < 0.4:
                    low_trust_critical.append({
                        "entity_id": data["entity_id"],
                        "entity_type": data["entity_type"],
                        "score": data["score"],
                        "warnings": data.get("warnings", []),
                    })

                prev_scores.append(data["score"])
            except Exception:
                pass

        # Trust trend
        avg_score = sum(prev_scores) / len(prev_scores) if prev_scores else 0.5
        trust_trend = "stable"

        # Staleness counts
        staleness_reports = await redis.hgetall(self.STALENESS_KEY)
        stale_count = expired_count = aging_count = 0
        staleness_by_type = {}

        for data_str in staleness_reports.values():
            try:
                data = json.loads(data_str)
                status = data["status"]
                entity_type = data["entity_type"]

                if status == "stale":
                    stale_count += 1
                elif status == "expired":
                    expired_count += 1
                elif status == "aging":
                    aging_count += 1

                staleness_by_type[entity_type] = staleness_by_type.get(entity_type, 0) + 1
            except Exception:
                pass

        # Approval status
        approvals = await redis.hgetall(self.APPROVALS_KEY)
        pending_approvals = overdue_approvals = 0
        oldest_approval_time = now

        for data_str in approvals.values():
            try:
                data = json.loads(data_str)
                if data["status"] == "pending":
                    pending_approvals += 1
                    requested_at = datetime.fromisoformat(data["requested_at"])
                    expires_at = datetime.fromisoformat(data["expires_at"])
                    if expires_at < now:
                        overdue_approvals += 1
                    if requested_at < oldest_approval_time:
                        oldest_approval_time = requested_at
            except Exception:
                pass

        backlog_hours = (now - oldest_approval_time).total_seconds() / 3600 if pending_approvals else 0

        # Sandbox status
        sandbox_results = await redis.hgetall(self.SANDBOX_KEY)
        sandbox_queue = passed_count = failed_count = 0
        recent_failures = []

        for data_str in sandbox_results.values():
            try:
                data = json.loads(data_str)
                if data["status"] == "pending":
                    sandbox_queue += 1
                elif data["status"] == "passed":
                    passed_count += 1
                elif data["status"] == "failed":
                    failed_count += 1
                    recent_failures.append({
                        "entity_id": data["entity_id"],
                        "entity_name": data["entity_name"],
                        "errors": data.get("errors", [])[:2],
                    })
            except Exception:
                pass

        total_sandbox = passed_count + failed_count
        sandbox_pass_rate = passed_count / total_sandbox if total_sandbox > 0 else 0

        # Drift alerts
        drift_alerts = await redis.hgetall(f"{self.DRIFT_KEY}:alerts")
        active_drift = critical_drift = 0
        drift_by_type = {}

        for data_str in drift_alerts.values():
            try:
                data = json.loads(data_str)
                if not data.get("resolved", False):
                    active_drift += 1
                    if data["severity"] == "critical":
                        critical_drift += 1
                    drift_type = data["drift_type"]
                    drift_by_type[drift_type] = drift_by_type.get(drift_type, 0) + 1
            except Exception:
                pass

        # Mandatory reviews
        reviews = await redis.hgetall(self.REVIEWS_KEY)
        pending_reviews = overdue_reviews = blocking_reviews = 0

        for data_str in reviews.values():
            try:
                data = json.loads(data_str)
                if data["status"] in ["pending", "in_progress"]:
                    pending_reviews += 1
                    due_date = datetime.fromisoformat(data["due_date"])
                    if due_date < now:
                        overdue_reviews += 1
                    if data.get("blocking", False):
                        blocking_reviews += 1
            except Exception:
                pass

        # Promotion gates
        promotions = await redis.hgetall(self.PROMOTIONS_KEY)
        pending_promotions = blocked_promotions = 0

        for data_str in promotions.values():
            try:
                data = json.loads(data_str)
                if data["status"] == "pending":
                    pending_promotions += 1
                    if len(data.get("blocking_gates", [])) > 0:
                        blocked_promotions += 1
            except Exception:
                pass

        # Health assessment
        health_issues = []
        if len(low_trust_critical) > 5:
            health_issues.append(f"{len(low_trust_critical)} low-trust critical items")
        if critical_drift > 0:
            health_issues.append(f"{critical_drift} critical drift alerts")
        if overdue_reviews > 0:
            health_issues.append(f"{overdue_reviews} overdue reviews")
        if blocking_reviews > 3:
            health_issues.append(f"{blocking_reviews} blocking reviews")
        if sandbox_pass_rate < 0.7:
            health_issues.append(f"Low sandbox pass rate: {sandbox_pass_rate:.0%}")

        if critical_drift > 0 or blocking_reviews > 5 or overdue_reviews > 3:
            overall_health = "critical"
        elif len(health_issues) > 2:
            overall_health = "warning"
        else:
            overall_health = "healthy"

        recommendations = []
        if len(low_trust_critical) > 0:
            recommendations.append("Review and improve low-trust critical items")
        if stale_count > 10:
            recommendations.append("Schedule knowledge refresh for stale entities")
        if pending_approvals > 20:
            recommendations.append("Clear approval backlog")
        if sandbox_pass_rate < 0.8:
            recommendations.append("Improve rule quality before sandbox testing")

        return GovernanceDashboardData(
            generated_at=now,
            total_entities=len(trust_scores),
            trust_distribution=trust_distribution,
            low_trust_critical=low_trust_critical[:10],
            trust_trend=trust_trend,
            stale_count=stale_count,
            expired_count=expired_count,
            aging_count=aging_count,
            staleness_by_type=staleness_by_type,
            pending_approvals=pending_approvals,
            overdue_approvals=overdue_approvals,
            approval_backlog_hours=backlog_hours,
            sandbox_queue=sandbox_queue,
            sandbox_pass_rate=sandbox_pass_rate,
            recent_failures=recent_failures[:5],
            active_drift_alerts=active_drift,
            critical_drift_alerts=critical_drift,
            drift_by_type=drift_by_type,
            pending_reviews=pending_reviews,
            overdue_reviews=overdue_reviews,
            blocking_reviews=blocking_reviews,
            pending_promotions=pending_promotions,
            blocked_promotions=blocked_promotions,
            overall_health=overall_health,
            health_issues=health_issues,
            recommendations=recommendations,
        )

    # ========================================================================
    # Governance Dashboard (Legacy)
    # ========================================================================

    async def get_governance_summary(self) -> dict[str, Any]:
        """Get summary of governance state."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Count trust scores
        trust_scores = await redis.hgetall(f"{self.TRUST_KEY}:scores")
        low_trust_count = 0
        for data_str in trust_scores.values():
            try:
                data = json.loads(data_str)
                if data["score"] < 0.4:
                    low_trust_count += 1
            except Exception:
                pass

        # Count stale entities
        staleness_reports = await redis.hgetall(self.STALENESS_KEY)
        stale_count = 0
        for data_str in staleness_reports.values():
            try:
                data = json.loads(data_str)
                if data["status"] in ["stale", "expired"]:
                    stale_count += 1
            except Exception:
                pass

        # Count pending approvals
        approvals = await redis.hgetall(self.APPROVALS_KEY)
        pending_count = 0
        for data_str in approvals.values():
            try:
                data = json.loads(data_str)
                if data["status"] == "pending":
                    pending_count += 1
            except Exception:
                pass

        # Count sandbox failures
        sandbox_results = await redis.hgetall(self.SANDBOX_KEY)
        sandbox_failed = 0
        for data_str in sandbox_results.values():
            try:
                data = json.loads(data_str)
                if data["status"] == "failed":
                    sandbox_failed += 1
            except Exception:
                pass

        return {
            "total_trust_scores": len(trust_scores),
            "low_trust_entities": low_trust_count,
            "stale_entities": stale_count,
            "pending_approvals": pending_count,
            "sandbox_failures": sandbox_failed,
            "health_status": "healthy" if (low_trust_count < 5 and stale_count < 10 and pending_count < 20) else "needs_attention",
        }


# Singleton
governance_trust = GovernanceTrustService()
