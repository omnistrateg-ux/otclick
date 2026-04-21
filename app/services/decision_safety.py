"""Decision Safety Service for Ops Assistant.

Confidence scoring, approval-aware remediation, rollback suggestions,
post-incident reviews, incident-to-policy learning, and hard prod guards.
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


class ConfidenceLevel(str, Enum):
    """Confidence level for recommendations."""

    VERY_HIGH = "very_high"  # 90-100% - Auto-execute safe
    HIGH = "high"  # 75-89% - Auto-execute with notification
    MEDIUM = "medium"  # 50-74% - Requires confirmation
    LOW = "low"  # 25-49% - Requires approval
    VERY_LOW = "very_low"  # 0-24% - Manual only


class AutoRemediationMode(str, Enum):
    """Auto-remediation mode."""

    DISABLED = "disabled"  # No auto-remediation
    SAFE_ONLY = "safe_only"  # Only safe runbooks
    WITH_APPROVAL = "with_approval"  # Requires pre-approval
    FULL_AUTO = "full_auto"  # Full automation (dangerous)


class RollbackUrgency(str, Enum):
    """Rollback urgency level."""

    IMMEDIATE = "immediate"  # Rollback now
    RECOMMENDED = "recommended"  # Should rollback soon
    OPTIONAL = "optional"  # Consider rollback
    NOT_NEEDED = "not_needed"  # No rollback required


class ReviewStatus(str, Enum):
    """Post-incident review status."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"


class PolicyLearningType(str, Enum):
    """Type of policy learned from incident."""

    PREVENTION = "prevention"  # Prevent similar incidents
    DETECTION = "detection"  # Detect similar patterns earlier
    RESPONSE = "response"  # Improve response procedures
    GUARDRAIL = "guardrail"  # Add safety guardrails


class ProdGuardLevel(str, Enum):
    """Production guard strictness level."""

    RELAXED = "relaxed"  # Minimal guards (staging)
    STANDARD = "standard"  # Normal production
    STRICT = "strict"  # High-value production
    LOCKDOWN = "lockdown"  # Emergency lockdown


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class ConfidenceScore:
    """Confidence score for a recommendation."""

    score: float  # 0.0 - 1.0
    level: ConfidenceLevel
    factors: dict[str, float]
    reasoning: str
    auto_executable: bool
    requires_approval: bool
    human_review_recommended: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 3),
            "level": self.level.value,
            "factors": {k: round(v, 3) for k, v in self.factors.items()},
            "reasoning": self.reasoning,
            "auto_executable": self.auto_executable,
            "requires_approval": self.requires_approval,
            "human_review_recommended": self.human_review_recommended,
        }


@dataclass
class ApprovalContext:
    """Context for approval-aware remediation."""

    action_id: str
    action_type: str
    severity_impact: str
    required_approvers: list[str]
    current_approvals: list[str]
    auto_approve_conditions: list[str]
    expires_at: datetime
    is_approved: bool
    approval_bypassed: bool
    bypass_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "severity_impact": self.severity_impact,
            "required_approvers": self.required_approvers,
            "current_approvals": self.current_approvals,
            "auto_approve_conditions": self.auto_approve_conditions,
            "expires_at": self.expires_at.isoformat(),
            "is_approved": self.is_approved,
            "approval_bypassed": self.approval_bypassed,
            "bypass_reason": self.bypass_reason,
        }


@dataclass
class AutoRemediationDecision:
    """Decision for auto-remediation."""

    incident_id: str
    runbook_id: str
    decision: str  # execute, defer, reject
    confidence: ConfidenceScore
    approval_context: ApprovalContext | None
    pre_conditions_met: bool
    safety_checks_passed: bool
    estimated_risk: float
    estimated_benefit: float
    decided_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "runbook_id": self.runbook_id,
            "decision": self.decision,
            "confidence": self.confidence.to_dict(),
            "approval_context": self.approval_context.to_dict() if self.approval_context else None,
            "pre_conditions_met": self.pre_conditions_met,
            "safety_checks_passed": self.safety_checks_passed,
            "estimated_risk": round(self.estimated_risk, 3),
            "estimated_benefit": round(self.estimated_benefit, 3),
            "decided_at": self.decided_at.isoformat(),
        }


@dataclass
class RollbackSuggestion:
    """Rollback suggestion for an action."""

    id: str
    action_id: str
    action_description: str
    urgency: RollbackUrgency
    rollback_steps: list[dict[str, Any]]
    estimated_rollback_time_minutes: int
    data_loss_risk: str
    service_impact: str
    confidence: float
    auto_rollback_available: bool
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action_id": self.action_id,
            "action_description": self.action_description,
            "urgency": self.urgency.value,
            "rollback_steps": self.rollback_steps,
            "estimated_rollback_time_minutes": self.estimated_rollback_time_minutes,
            "data_loss_risk": self.data_loss_risk,
            "service_impact": self.service_impact,
            "confidence": round(self.confidence, 2),
            "auto_rollback_available": self.auto_rollback_available,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class TimelineEntry:
    """Entry in post-incident review timeline."""

    timestamp: datetime
    event_type: str
    description: str
    actor: str
    impact: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "description": self.description,
            "actor": self.actor,
            "impact": self.impact,
        }


@dataclass
class PostIncidentReview:
    """Post-incident review (PIR)."""

    id: str
    incident_id: str
    title: str
    status: ReviewStatus
    severity: str
    duration_minutes: int
    affected_services: list[str]
    affected_users_estimate: int
    summary: str
    timeline: list[TimelineEntry]
    root_causes: list[str]
    contributing_factors: list[str]
    what_went_well: list[str]
    what_went_wrong: list[str]
    action_items: list[dict[str, Any]]
    lessons_learned: list[str]
    created_at: datetime
    created_by: str
    reviewed_by: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "title": self.title,
            "status": self.status.value,
            "severity": self.severity,
            "duration_minutes": self.duration_minutes,
            "affected_services": self.affected_services,
            "affected_users_estimate": self.affected_users_estimate,
            "summary": self.summary,
            "timeline": [t.to_dict() for t in self.timeline],
            "root_causes": self.root_causes,
            "contributing_factors": self.contributing_factors,
            "what_went_well": self.what_went_well,
            "what_went_wrong": self.what_went_wrong,
            "action_items": self.action_items,
            "lessons_learned": self.lessons_learned,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "reviewed_by": self.reviewed_by,
        }


@dataclass
class LearnedPolicy:
    """Policy learned from incident."""

    id: str
    incident_id: str
    policy_type: PolicyLearningType
    name: str
    description: str
    rule_template: dict[str, Any]
    confidence: float
    effectiveness_estimate: float
    implementation_effort: str  # low, medium, high
    priority: str  # p0, p1, p2, p3
    status: str  # suggested, approved, implemented, rejected
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "policy_type": self.policy_type.value,
            "name": self.name,
            "description": self.description,
            "rule_template": self.rule_template,
            "confidence": round(self.confidence, 2),
            "effectiveness_estimate": round(self.effectiveness_estimate, 2),
            "implementation_effort": self.implementation_effort,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ProdGuard:
    """Production guard rule."""

    id: str
    name: str
    description: str
    guard_level: ProdGuardLevel
    action_patterns: list[str]
    conditions: dict[str, Any]
    enforcement: str  # block, warn, audit
    bypass_roles: list[str]
    bypass_requires_reason: bool
    active: bool
    violations_count: int = 0
    last_violation: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "guard_level": self.guard_level.value,
            "action_patterns": self.action_patterns,
            "conditions": self.conditions,
            "enforcement": self.enforcement,
            "bypass_roles": self.bypass_roles,
            "bypass_requires_reason": self.bypass_requires_reason,
            "active": self.active,
            "violations_count": self.violations_count,
            "last_violation": self.last_violation.isoformat() if self.last_violation else None,
        }


@dataclass
class GuardViolation:
    """Record of a guard violation."""

    id: str
    guard_id: str
    guard_name: str
    action_attempted: str
    actor: str
    enforcement_result: str  # blocked, warned, audited
    bypass_used: bool
    bypass_reason: str | None
    context: dict[str, Any]
    occurred_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "guard_id": self.guard_id,
            "guard_name": self.guard_name,
            "action_attempted": self.action_attempted,
            "actor": self.actor,
            "enforcement_result": self.enforcement_result,
            "bypass_used": self.bypass_used,
            "bypass_reason": self.bypass_reason,
            "context": self.context,
            "occurred_at": self.occurred_at.isoformat(),
        }


# ============================================================================
# Default Production Guards
# ============================================================================

DEFAULT_PROD_GUARDS = [
    {
        "name": "No Database Drops",
        "description": "Block DROP TABLE/DATABASE commands in production",
        "guard_level": ProdGuardLevel.STRICT,
        "action_patterns": ["drop_table", "drop_database", "truncate"],
        "conditions": {"environment": "production"},
        "enforcement": "block",
        "bypass_roles": ["dba_admin"],
        "bypass_requires_reason": True,
    },
    {
        "name": "No Mass Deletes",
        "description": "Block deletion of more than 1000 records",
        "guard_level": ProdGuardLevel.STANDARD,
        "action_patterns": ["bulk_delete", "mass_delete"],
        "conditions": {"record_count_gt": 1000},
        "enforcement": "block",
        "bypass_roles": ["admin"],
        "bypass_requires_reason": True,
    },
    {
        "name": "No Force Push to Main",
        "description": "Block force push to main/master branches",
        "guard_level": ProdGuardLevel.STRICT,
        "action_patterns": ["git_force_push"],
        "conditions": {"branch": ["main", "master"]},
        "enforcement": "block",
        "bypass_roles": [],  # No bypass allowed
        "bypass_requires_reason": True,
    },
    {
        "name": "Critical Runbook Approval",
        "description": "Require dual approval for critical runbooks",
        "guard_level": ProdGuardLevel.STRICT,
        "action_patterns": ["runbook_execute"],
        "conditions": {"safety_level": "critical"},
        "enforcement": "block",
        "bypass_roles": ["incident_commander"],
        "bypass_requires_reason": True,
    },
    {
        "name": "Off-Hours Deploy Warning",
        "description": "Warn about deployments outside business hours",
        "guard_level": ProdGuardLevel.STANDARD,
        "action_patterns": ["deploy", "release"],
        "conditions": {"hour_not_between": [9, 17]},
        "enforcement": "warn",
        "bypass_roles": ["oncall"],
        "bypass_requires_reason": False,
    },
    {
        "name": "High Error Rate Block",
        "description": "Block deployments when error rate > 5%",
        "guard_level": ProdGuardLevel.STANDARD,
        "action_patterns": ["deploy", "release"],
        "conditions": {"error_rate_gt": 5.0},
        "enforcement": "block",
        "bypass_roles": ["admin", "incident_commander"],
        "bypass_requires_reason": True,
    },
    {
        "name": "Concurrent Incident Caution",
        "description": "Warn about risky actions during active P0/P1 incidents",
        "guard_level": ProdGuardLevel.STANDARD,
        "action_patterns": ["deploy", "config_change", "runbook_execute"],
        "conditions": {"active_p0_p1_incidents": True},
        "enforcement": "warn",
        "bypass_roles": ["incident_commander"],
        "bypass_requires_reason": True,
    },
    {
        "name": "Credentials Exposure Block",
        "description": "Block actions that might expose credentials",
        "guard_level": ProdGuardLevel.STRICT,
        "action_patterns": ["log_secrets", "export_env", "dump_config"],
        "conditions": {},
        "enforcement": "block",
        "bypass_roles": [],
        "bypass_requires_reason": True,
    },
]


# ============================================================================
# Confidence Factors
# ============================================================================

CONFIDENCE_FACTORS = {
    "historical_success_rate": 0.25,
    "pattern_match_strength": 0.20,
    "data_completeness": 0.15,
    "similar_incident_count": 0.15,
    "runbook_reliability": 0.10,
    "time_since_last_success": 0.10,
    "environmental_stability": 0.05,
}


# ============================================================================
# Service
# ============================================================================


class DecisionSafetyService:
    """Service for decision safety in ops assistant.

    Features:
    - Confidence scoring for recommendations
    - Approval-aware auto-remediation
    - Rollback suggestions
    - Post-incident review generation
    - Incident-to-policy learning
    - Hard production guards
    """

    CONFIDENCE_KEY = "decision_safety:confidence"
    DECISIONS_KEY = "decision_safety:decisions"
    ROLLBACKS_KEY = "decision_safety:rollbacks"
    REVIEWS_KEY = "decision_safety:reviews"
    POLICIES_KEY = "decision_safety:learned_policies"
    GUARDS_KEY = "decision_safety:guards"
    VIOLATIONS_KEY = "decision_safety:violations"
    CONFIG_KEY = "decision_safety:config"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Confidence Scoring
    # ========================================================================

    async def calculate_confidence(
        self,
        recommendation_type: str,
        recommendation_id: str,
        context: dict[str, Any],
    ) -> ConfidenceScore:
        """Calculate confidence score for a recommendation.

        Args:
            recommendation_type: Type of recommendation (runbook, fix, triage)
            recommendation_id: ID of the recommendation
            context: Context data for scoring

        Returns:
            Confidence score with breakdown
        """
        factors = {}

        # Historical success rate
        success_rate = context.get("historical_success_rate", 0.5)
        factors["historical_success_rate"] = success_rate

        # Pattern match strength
        pattern_strength = context.get("pattern_match_strength", 0.5)
        factors["pattern_match_strength"] = pattern_strength

        # Data completeness
        required_fields = ["incident_id", "category", "severity"]
        present_fields = sum(1 for f in required_fields if context.get(f))
        factors["data_completeness"] = present_fields / len(required_fields)

        # Similar incident count
        similar_count = context.get("similar_incident_count", 0)
        factors["similar_incident_count"] = min(similar_count / 10, 1.0)

        # Runbook reliability
        runbook_reliability = context.get("runbook_reliability", 0.7)
        factors["runbook_reliability"] = runbook_reliability

        # Time since last success
        hours_since = context.get("hours_since_last_success", 168)
        factors["time_since_last_success"] = max(0, 1 - (hours_since / 720))

        # Environmental stability
        stability = context.get("environmental_stability", 0.8)
        factors["environmental_stability"] = stability

        # Calculate weighted score
        score = sum(
            factors[k] * CONFIDENCE_FACTORS[k]
            for k in CONFIDENCE_FACTORS
        )

        # Determine level
        if score >= 0.9:
            level = ConfidenceLevel.VERY_HIGH
        elif score >= 0.75:
            level = ConfidenceLevel.HIGH
        elif score >= 0.5:
            level = ConfidenceLevel.MEDIUM
        elif score >= 0.25:
            level = ConfidenceLevel.LOW
        else:
            level = ConfidenceLevel.VERY_LOW

        # Determine execution permissions
        auto_executable = level in [ConfidenceLevel.VERY_HIGH, ConfidenceLevel.HIGH]
        requires_approval = level in [ConfidenceLevel.LOW, ConfidenceLevel.VERY_LOW]
        human_review = level != ConfidenceLevel.VERY_HIGH

        # Generate reasoning
        top_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)[:3]
        reasoning_parts = []
        for factor, value in top_factors:
            if value >= 0.8:
                reasoning_parts.append(f"Strong {factor.replace('_', ' ')}")
            elif value >= 0.5:
                reasoning_parts.append(f"Moderate {factor.replace('_', ' ')}")
            else:
                reasoning_parts.append(f"Weak {factor.replace('_', ' ')}")

        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "Insufficient data"

        return ConfidenceScore(
            score=score,
            level=level,
            factors=factors,
            reasoning=reasoning,
            auto_executable=auto_executable,
            requires_approval=requires_approval,
            human_review_recommended=human_review,
        )

    # ========================================================================
    # Approval-Aware Auto-Remediation
    # ========================================================================

    async def evaluate_auto_remediation(
        self,
        incident_id: str,
        runbook_id: str,
        context: dict[str, Any],
    ) -> AutoRemediationDecision:
        """Evaluate whether to auto-remediate.

        Args:
            incident_id: Incident ID
            runbook_id: Proposed runbook
            context: Evaluation context

        Returns:
            Auto-remediation decision
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get current mode
        mode_str = await redis.get(f"{self.CONFIG_KEY}:auto_remediation_mode")
        mode = AutoRemediationMode(mode_str) if mode_str else AutoRemediationMode.SAFE_ONLY

        # Calculate confidence
        confidence = await self.calculate_confidence(
            recommendation_type="runbook",
            recommendation_id=runbook_id,
            context=context,
        )

        # Check safety level
        safety_level = context.get("runbook_safety_level", "caution")
        is_safe = safety_level == "safe"

        # Pre-conditions check
        pre_conditions_met = self._check_pre_conditions(context)

        # Safety checks
        safety_checks_passed = await self._run_safety_checks(context)

        # Estimate risk and benefit
        estimated_risk = self._estimate_risk(context, safety_level)
        estimated_benefit = self._estimate_benefit(context)

        # Build approval context
        approval_context = None
        if not is_safe or mode == AutoRemediationMode.WITH_APPROVAL:
            approval_context = await self._build_approval_context(
                runbook_id, context, now
            )

        # Make decision
        decision = "reject"

        if mode == AutoRemediationMode.DISABLED:
            decision = "reject"
        elif mode == AutoRemediationMode.SAFE_ONLY:
            if is_safe and confidence.auto_executable and safety_checks_passed:
                decision = "execute"
            elif is_safe and confidence.level == ConfidenceLevel.MEDIUM:
                decision = "defer"
            else:
                decision = "reject"
        elif mode == AutoRemediationMode.WITH_APPROVAL:
            if approval_context and approval_context.is_approved:
                if safety_checks_passed:
                    decision = "execute"
                else:
                    decision = "defer"
            else:
                decision = "defer"
        elif mode == AutoRemediationMode.FULL_AUTO:
            if safety_checks_passed and confidence.score >= 0.5:
                decision = "execute"
            else:
                decision = "defer"

        result = AutoRemediationDecision(
            incident_id=incident_id,
            runbook_id=runbook_id,
            decision=decision,
            confidence=confidence,
            approval_context=approval_context,
            pre_conditions_met=pre_conditions_met,
            safety_checks_passed=safety_checks_passed,
            estimated_risk=estimated_risk,
            estimated_benefit=estimated_benefit,
            decided_at=now,
        )

        # Store decision
        await redis.lpush(
            self.DECISIONS_KEY,
            json.dumps(result.to_dict()),
        )
        await redis.ltrim(self.DECISIONS_KEY, 0, 999)

        logger.info(f"[DecisionSafety] Auto-remediation decision for {incident_id}: {decision}")

        return result

    def _check_pre_conditions(self, context: dict[str, Any]) -> bool:
        """Check pre-conditions for remediation."""
        required = ["incident_id", "runbook_id"]
        return all(context.get(k) for k in required)

    async def _run_safety_checks(self, context: dict[str, Any]) -> bool:
        """Run safety checks before remediation."""
        checks_passed = True

        # Check error rate
        error_rate = context.get("current_error_rate", 0)
        if error_rate > 50:
            checks_passed = False

        # Check active incidents
        active_p0 = context.get("active_p0_incidents", 0)
        if active_p0 > 3:
            checks_passed = False

        # Check recent failures
        recent_failures = context.get("recent_runbook_failures", 0)
        if recent_failures > 2:
            checks_passed = False

        return checks_passed

    def _estimate_risk(self, context: dict[str, Any], safety_level: str) -> float:
        """Estimate risk of action."""
        base_risk = {
            "safe": 0.1,
            "caution": 0.3,
            "dangerous": 0.6,
            "critical": 0.9,
        }.get(safety_level, 0.5)

        # Adjust for context
        if context.get("production_environment", False):
            base_risk *= 1.2

        if context.get("peak_hours", False):
            base_risk *= 1.1

        return min(base_risk, 1.0)

    def _estimate_benefit(self, context: dict[str, Any]) -> float:
        """Estimate benefit of action."""
        severity = context.get("incident_severity", "p2")

        base_benefit = {
            "p0": 0.95,
            "p1": 0.85,
            "p2": 0.65,
            "p3": 0.45,
            "p4": 0.25,
        }.get(severity, 0.5)

        # Adjust for user impact
        affected_users = context.get("affected_users", 0)
        if affected_users > 1000:
            base_benefit *= 1.1

        return min(base_benefit, 1.0)

    async def _build_approval_context(
        self,
        runbook_id: str,
        context: dict[str, Any],
        now: datetime,
    ) -> ApprovalContext:
        """Build approval context for action."""
        action_id = f"remediation-{runbook_id}-{now.timestamp()}"

        safety_level = context.get("runbook_safety_level", "caution")
        required_approvers = []

        if safety_level == "critical":
            required_approvers = ["admin", "incident_commander"]
        elif safety_level == "dangerous":
            required_approvers = ["admin"]
        else:
            required_approvers = ["oncall"]

        # Check for pre-approvals
        pre_approved = context.get("pre_approved_runbooks", [])
        is_approved = runbook_id in pre_approved

        return ApprovalContext(
            action_id=action_id,
            action_type="runbook_execution",
            severity_impact=safety_level,
            required_approvers=required_approvers,
            current_approvals=context.get("current_approvals", []),
            auto_approve_conditions=["severity >= p0", "safe_runbook"],
            expires_at=now + timedelta(hours=1),
            is_approved=is_approved,
            approval_bypassed=False,
            bypass_reason=None,
        )

    async def set_auto_remediation_mode(
        self,
        mode: AutoRemediationMode,
        set_by: str,
    ) -> dict[str, Any]:
        """Set auto-remediation mode."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        await redis.set(f"{self.CONFIG_KEY}:auto_remediation_mode", mode.value)

        logger.info(f"[DecisionSafety] Auto-remediation mode set to {mode.value} by {set_by}")

        return {"mode": mode.value, "set_by": set_by}

    async def get_auto_remediation_mode(self) -> AutoRemediationMode:
        """Get current auto-remediation mode."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        mode_str = await redis.get(f"{self.CONFIG_KEY}:auto_remediation_mode")

        return AutoRemediationMode(mode_str) if mode_str else AutoRemediationMode.SAFE_ONLY

    # ========================================================================
    # Rollback Suggestions
    # ========================================================================

    async def generate_rollback_suggestion(
        self,
        action_id: str,
        action_type: str,
        action_details: dict[str, Any],
    ) -> RollbackSuggestion:
        """Generate rollback suggestion for an action.

        Args:
            action_id: ID of the action
            action_type: Type of action
            action_details: Details of the action

        Returns:
            Rollback suggestion
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Determine rollback urgency
        urgency = self._determine_rollback_urgency(action_type, action_details)

        # Generate rollback steps
        steps = self._generate_rollback_steps(action_type, action_details)

        # Estimate time
        estimated_time = sum(s.get("estimated_minutes", 5) for s in steps)

        # Assess risks
        data_loss_risk = self._assess_data_loss_risk(action_type, action_details)
        service_impact = self._assess_service_impact(action_type)

        # Check auto-rollback availability
        auto_available = action_type in ["config_change", "feature_flag", "scale_workers"]

        suggestion = RollbackSuggestion(
            id=str(uuid.uuid4())[:8],
            action_id=action_id,
            action_description=action_details.get("description", action_type),
            urgency=urgency,
            rollback_steps=steps,
            estimated_rollback_time_minutes=estimated_time,
            data_loss_risk=data_loss_risk,
            service_impact=service_impact,
            confidence=0.85 if auto_available else 0.65,
            auto_rollback_available=auto_available,
            created_at=now,
        )

        # Store suggestion
        await redis.hset(
            self.ROLLBACKS_KEY,
            action_id,
            json.dumps(suggestion.to_dict()),
        )

        logger.info(f"[DecisionSafety] Generated rollback suggestion for {action_id}")

        return suggestion

    def _determine_rollback_urgency(
        self,
        action_type: str,
        details: dict[str, Any],
    ) -> RollbackUrgency:
        """Determine rollback urgency."""
        error_rate = details.get("current_error_rate", 0)
        latency_increase = details.get("latency_increase_percent", 0)

        if error_rate > 50 or latency_increase > 200:
            return RollbackUrgency.IMMEDIATE
        elif error_rate > 10 or latency_increase > 50:
            return RollbackUrgency.RECOMMENDED
        elif error_rate > 1 or latency_increase > 20:
            return RollbackUrgency.OPTIONAL
        else:
            return RollbackUrgency.NOT_NEEDED

    def _generate_rollback_steps(
        self,
        action_type: str,
        details: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate rollback steps."""
        steps = []

        if action_type == "deploy":
            steps = [
                {
                    "order": 1,
                    "action": "Identify previous version",
                    "command": "git log --oneline -5",
                    "estimated_minutes": 2,
                },
                {
                    "order": 2,
                    "action": "Trigger rollback deployment",
                    "command": f"deploy --version {details.get('previous_version', 'PREV')}",
                    "estimated_minutes": 5,
                },
                {
                    "order": 3,
                    "action": "Verify rollback",
                    "command": "health_check --full",
                    "estimated_minutes": 3,
                },
            ]
        elif action_type == "config_change":
            steps = [
                {
                    "order": 1,
                    "action": "Restore previous config",
                    "command": "config restore --backup-id LATEST",
                    "estimated_minutes": 2,
                },
                {
                    "order": 2,
                    "action": "Reload services",
                    "command": "service reload all",
                    "estimated_minutes": 3,
                },
            ]
        elif action_type == "runbook_execute":
            # Check if runbook has rollback commands
            rollback_cmds = details.get("rollback_commands", [])
            if rollback_cmds:
                for i, cmd in enumerate(rollback_cmds):
                    steps.append({
                        "order": i + 1,
                        "action": cmd.get("description", f"Rollback step {i+1}"),
                        "command": cmd.get("cmd", ""),
                        "estimated_minutes": 3,
                    })
            else:
                steps = [
                    {
                        "order": 1,
                        "action": "Manual rollback required",
                        "command": "Contact oncall for manual intervention",
                        "estimated_minutes": 15,
                    },
                ]
        else:
            steps = [
                {
                    "order": 1,
                    "action": "Assess current state",
                    "command": "system_status --verbose",
                    "estimated_minutes": 5,
                },
                {
                    "order": 2,
                    "action": "Manual intervention",
                    "command": "Contact oncall",
                    "estimated_minutes": 15,
                },
            ]

        return steps

    def _assess_data_loss_risk(
        self,
        action_type: str,
        details: dict[str, Any],
    ) -> str:
        """Assess data loss risk from rollback."""
        if action_type in ["database_migration", "data_delete"]:
            return "high"
        elif action_type in ["deploy", "config_change"]:
            return "low"
        else:
            return "medium"

    def _assess_service_impact(self, action_type: str) -> str:
        """Assess service impact from rollback."""
        if action_type in ["deploy", "database_migration"]:
            return "Brief downtime possible"
        elif action_type == "config_change":
            return "Service reload required"
        else:
            return "Minimal impact"

    async def get_rollback_suggestion(self, action_id: str) -> RollbackSuggestion | None:
        """Get rollback suggestion for an action."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.ROLLBACKS_KEY, action_id)

        if not raw:
            return None

        data = json.loads(raw)
        return RollbackSuggestion(
            id=data["id"],
            action_id=data["action_id"],
            action_description=data["action_description"],
            urgency=RollbackUrgency(data["urgency"]),
            rollback_steps=data["rollback_steps"],
            estimated_rollback_time_minutes=data["estimated_rollback_time_minutes"],
            data_loss_risk=data["data_loss_risk"],
            service_impact=data["service_impact"],
            confidence=data["confidence"],
            auto_rollback_available=data["auto_rollback_available"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    # ========================================================================
    # Post-Incident Review Generator
    # ========================================================================

    async def generate_post_incident_review(
        self,
        incident_id: str,
        created_by: str,
    ) -> PostIncidentReview | None:
        """Generate post-incident review.

        Args:
            incident_id: Incident ID
            created_by: Creator

        Returns:
            Generated PIR or None
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get incident data
        incident_data = await self._get_incident_data(incident_id)
        if not incident_data:
            return None

        # Get triage data
        triage_data = await self._get_triage_data(incident_id)

        # Build timeline
        timeline = await self._build_incident_timeline(incident_id)

        # Calculate duration
        started_at = incident_data.get("created_at")
        resolved_at = incident_data.get("resolved_at")
        if started_at and resolved_at:
            duration = int((
                datetime.fromisoformat(resolved_at) -
                datetime.fromisoformat(started_at)
            ).total_seconds() / 60)
        else:
            duration = 0

        # Generate analysis
        root_causes = self._identify_root_causes(incident_data, triage_data)
        contributing_factors = self._identify_contributing_factors(incident_data)
        what_went_well = self._identify_what_went_well(incident_data, timeline)
        what_went_wrong = self._identify_what_went_wrong(incident_data, timeline)
        action_items = self._generate_action_items(root_causes, contributing_factors)
        lessons_learned = self._generate_lessons(root_causes, what_went_wrong)

        review = PostIncidentReview(
            id=str(uuid.uuid4())[:8],
            incident_id=incident_id,
            title=f"PIR: {incident_data.get('title', 'Unknown Incident')}",
            status=ReviewStatus.DRAFT,
            severity=incident_data.get("severity", "p2"),
            duration_minutes=duration,
            affected_services=incident_data.get("affected_services", []),
            affected_users_estimate=triage_data.get("affected_users_estimate", 0) if triage_data else 0,
            summary=self._generate_summary(incident_data, duration),
            timeline=timeline,
            root_causes=root_causes,
            contributing_factors=contributing_factors,
            what_went_well=what_went_well,
            what_went_wrong=what_went_wrong,
            action_items=action_items,
            lessons_learned=lessons_learned,
            created_at=now,
            created_by=created_by,
        )

        # Store review
        await redis.hset(
            self.REVIEWS_KEY,
            review.id,
            json.dumps(review.to_dict()),
        )

        logger.info(f"[DecisionSafety] Generated PIR {review.id} for incident {incident_id}")

        return review

    async def _get_incident_data(self, incident_id: str) -> dict[str, Any] | None:
        """Get incident data."""
        try:
            from app.services.incident_timeline import incident_timeline
            incident = await incident_timeline.get_incident(incident_id)
            return incident.to_dict() if incident else None
        except Exception:
            return None

    async def _get_triage_data(self, incident_id: str) -> dict[str, Any] | None:
        """Get triage data."""
        try:
            from app.services.ops_assistant import ops_assistant
            triage = await ops_assistant.get_triage(incident_id)
            return triage.to_dict() if triage else None
        except Exception:
            return None

    async def _build_incident_timeline(self, incident_id: str) -> list[TimelineEntry]:
        """Build incident timeline."""
        entries = []

        try:
            from app.services.incident_timeline import incident_timeline
            events = await incident_timeline.get_timeline_events(incident_id)

            for event in events:
                entries.append(TimelineEntry(
                    timestamp=event.timestamp,
                    event_type=event.event_type.value if hasattr(event.event_type, 'value') else event.event_type,
                    description=event.content,
                    actor=event.actor,
                    impact=event.metadata.get("impact") if event.metadata else None,
                ))
        except Exception:
            pass

        return entries

    def _identify_root_causes(
        self,
        incident: dict[str, Any],
        triage: dict[str, Any] | None,
    ) -> list[str]:
        """Identify root causes."""
        causes = []

        category = triage.get("category") if triage else None

        if category == "availability":
            causes.append("Service dependency failure")
            causes.append("Resource exhaustion")
        elif category == "performance":
            causes.append("Inefficient query patterns")
            causes.append("Cache invalidation issue")
        elif category == "data":
            causes.append("Data consistency issue")
        elif category == "security":
            causes.append("Security control gap")

        if not causes:
            causes.append("Root cause under investigation")

        return causes

    def _identify_contributing_factors(self, incident: dict[str, Any]) -> list[str]:
        """Identify contributing factors."""
        factors = []

        severity = incident.get("severity", "p2")
        if severity == "p0":
            factors.append("High system load at time of incident")
            factors.append("Limited observability into affected components")

        factors.append("Detection delay - monitoring gap identified")

        return factors

    def _identify_what_went_well(
        self,
        incident: dict[str, Any],
        timeline: list[TimelineEntry],
    ) -> list[str]:
        """Identify what went well."""
        well = []

        # Check response time
        if len(timeline) >= 2:
            well.append("Quick initial response")

        if incident.get("resolved_at"):
            well.append("Incident successfully resolved")

        well.append("Team collaboration effective")

        return well

    def _identify_what_went_wrong(
        self,
        incident: dict[str, Any],
        timeline: list[TimelineEntry],
    ) -> list[str]:
        """Identify what went wrong."""
        wrong = []

        severity = incident.get("severity", "p2")
        if severity in ["p0", "p1"]:
            wrong.append("High-severity incident reached production")

        wrong.append("Prevention measures were insufficient")

        return wrong

    def _generate_action_items(
        self,
        root_causes: list[str],
        contributing_factors: list[str],
    ) -> list[dict[str, Any]]:
        """Generate action items."""
        items = []

        for i, cause in enumerate(root_causes[:3]):
            items.append({
                "id": f"action-{i+1}",
                "title": f"Address: {cause}",
                "description": f"Implement fix for root cause: {cause}",
                "priority": "p1" if i == 0 else "p2",
                "owner": "TBD",
                "due_date": "TBD",
                "status": "open",
            })

        items.append({
            "id": f"action-{len(items)+1}",
            "title": "Improve monitoring",
            "description": "Add monitoring/alerting to detect this issue earlier",
            "priority": "p2",
            "owner": "TBD",
            "due_date": "TBD",
            "status": "open",
        })

        return items

    def _generate_lessons(
        self,
        root_causes: list[str],
        what_went_wrong: list[str],
    ) -> list[str]:
        """Generate lessons learned."""
        lessons = []

        lessons.append("Need better monitoring for early detection")
        lessons.append("Runbook procedures should be updated")
        lessons.append("Consider adding automated remediation")

        return lessons

    def _generate_summary(
        self,
        incident: dict[str, Any],
        duration_minutes: int,
    ) -> str:
        """Generate incident summary."""
        title = incident.get("title", "Unknown incident")
        severity = incident.get("severity", "P2").upper()
        services = ", ".join(incident.get("affected_services", ["unknown"]))

        return (
            f"{severity} incident affecting {services}. "
            f"Duration: {duration_minutes} minutes. "
            f"Summary: {title}"
        )

    async def get_review(self, review_id: str) -> PostIncidentReview | None:
        """Get post-incident review."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.REVIEWS_KEY, review_id)

        if not raw:
            return None

        data = json.loads(raw)
        return self._parse_review(data)

    def _parse_review(self, data: dict[str, Any]) -> PostIncidentReview:
        """Parse review from dict."""
        timeline = [
            TimelineEntry(
                timestamp=datetime.fromisoformat(t["timestamp"]),
                event_type=t["event_type"],
                description=t["description"],
                actor=t["actor"],
                impact=t.get("impact"),
            )
            for t in data.get("timeline", [])
        ]

        return PostIncidentReview(
            id=data["id"],
            incident_id=data["incident_id"],
            title=data["title"],
            status=ReviewStatus(data["status"]),
            severity=data["severity"],
            duration_minutes=data["duration_minutes"],
            affected_services=data["affected_services"],
            affected_users_estimate=data["affected_users_estimate"],
            summary=data["summary"],
            timeline=timeline,
            root_causes=data["root_causes"],
            contributing_factors=data["contributing_factors"],
            what_went_well=data["what_went_well"],
            what_went_wrong=data["what_went_wrong"],
            action_items=data["action_items"],
            lessons_learned=data["lessons_learned"],
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by=data["created_by"],
            reviewed_by=data.get("reviewed_by", []),
        )

    async def list_reviews(
        self,
        status: ReviewStatus | None = None,
        limit: int = 50,
    ) -> list[PostIncidentReview]:
        """List post-incident reviews."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hgetall(self.REVIEWS_KEY)
        reviews = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)
                if status and data["status"] != status.value:
                    continue
                reviews.append(self._parse_review(data))
            except Exception:
                continue

        reviews.sort(key=lambda r: r.created_at, reverse=True)
        return reviews[:limit]

    # ========================================================================
    # Incident-to-Policy Learning
    # ========================================================================

    async def learn_policy_from_incident(
        self,
        incident_id: str,
    ) -> list[LearnedPolicy]:
        """Learn policies from incident.

        Args:
            incident_id: Incident ID

        Returns:
            List of suggested policies
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get incident and triage data
        incident_data = await self._get_incident_data(incident_id)
        triage_data = await self._get_triage_data(incident_id)

        if not incident_data:
            return []

        policies = []

        # Generate prevention policy
        prevention = self._generate_prevention_policy(incident_id, incident_data, triage_data, now)
        if prevention:
            policies.append(prevention)

        # Generate detection policy
        detection = self._generate_detection_policy(incident_id, incident_data, triage_data, now)
        if detection:
            policies.append(detection)

        # Generate response policy
        response = self._generate_response_policy(incident_id, incident_data, triage_data, now)
        if response:
            policies.append(response)

        # Store policies
        for policy in policies:
            await redis.hset(
                self.POLICIES_KEY,
                policy.id,
                json.dumps(policy.to_dict()),
            )

        logger.info(f"[DecisionSafety] Learned {len(policies)} policies from incident {incident_id}")

        return policies

    def _generate_prevention_policy(
        self,
        incident_id: str,
        incident: dict[str, Any],
        triage: dict[str, Any] | None,
        now: datetime,
    ) -> LearnedPolicy | None:
        """Generate prevention policy."""
        category = triage.get("category") if triage else "operational"
        severity = incident.get("severity", "p2")

        if severity not in ["p0", "p1"]:
            return None

        policy_id = hashlib.md5(f"prevention-{incident_id}".encode()).hexdigest()[:8]

        rule_template = {
            "type": "rate_limit",
            "condition": f"category == {category}",
            "action": "block",
            "threshold": {"requests_per_minute": 100},
        }

        return LearnedPolicy(
            id=policy_id,
            incident_id=incident_id,
            policy_type=PolicyLearningType.PREVENTION,
            name=f"Prevent {category} overload",
            description=f"Rate limit to prevent {category} incidents similar to {incident_id}",
            rule_template=rule_template,
            confidence=0.75,
            effectiveness_estimate=0.8,
            implementation_effort="medium",
            priority="p1",
            status="suggested",
            created_at=now,
        )

    def _generate_detection_policy(
        self,
        incident_id: str,
        incident: dict[str, Any],
        triage: dict[str, Any] | None,
        now: datetime,
    ) -> LearnedPolicy | None:
        """Generate detection policy."""
        category = triage.get("category") if triage else "operational"

        policy_id = hashlib.md5(f"detection-{incident_id}".encode()).hexdigest()[:8]

        rule_template = {
            "type": "alert",
            "condition": f"error_rate > 1% AND category == {category}",
            "action": "alert",
            "channels": ["slack", "pagerduty"],
        }

        return LearnedPolicy(
            id=policy_id,
            incident_id=incident_id,
            policy_type=PolicyLearningType.DETECTION,
            name=f"Early {category} detection",
            description=f"Alert on early signs of {category} issues",
            rule_template=rule_template,
            confidence=0.85,
            effectiveness_estimate=0.75,
            implementation_effort="low",
            priority="p2",
            status="suggested",
            created_at=now,
        )

    def _generate_response_policy(
        self,
        incident_id: str,
        incident: dict[str, Any],
        triage: dict[str, Any] | None,
        now: datetime,
    ) -> LearnedPolicy | None:
        """Generate response policy."""
        category = triage.get("category") if triage else "operational"

        policy_id = hashlib.md5(f"response-{incident_id}".encode()).hexdigest()[:8]

        rule_template = {
            "type": "runbook_trigger",
            "condition": f"incident.category == {category}",
            "action": "suggest_runbook",
            "runbook_pattern": f"rb-{category}*",
        }

        return LearnedPolicy(
            id=policy_id,
            incident_id=incident_id,
            policy_type=PolicyLearningType.RESPONSE,
            name=f"Auto-suggest {category} runbooks",
            description=f"Automatically suggest relevant runbooks for {category} incidents",
            rule_template=rule_template,
            confidence=0.70,
            effectiveness_estimate=0.65,
            implementation_effort="low",
            priority="p2",
            status="suggested",
            created_at=now,
        )

    async def list_learned_policies(
        self,
        incident_id: str | None = None,
        policy_type: PolicyLearningType | None = None,
        status: str | None = None,
    ) -> list[LearnedPolicy]:
        """List learned policies."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hgetall(self.POLICIES_KEY)
        policies = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)

                if incident_id and data["incident_id"] != incident_id:
                    continue
                if policy_type and data["policy_type"] != policy_type.value:
                    continue
                if status and data["status"] != status:
                    continue

                policies.append(LearnedPolicy(
                    id=data["id"],
                    incident_id=data["incident_id"],
                    policy_type=PolicyLearningType(data["policy_type"]),
                    name=data["name"],
                    description=data["description"],
                    rule_template=data["rule_template"],
                    confidence=data["confidence"],
                    effectiveness_estimate=data["effectiveness_estimate"],
                    implementation_effort=data["implementation_effort"],
                    priority=data["priority"],
                    status=data["status"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                ))
            except Exception:
                continue

        return policies

    async def approve_learned_policy(
        self,
        policy_id: str,
        approved_by: str,
    ) -> LearnedPolicy | None:
        """Approve a learned policy."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.POLICIES_KEY, policy_id)

        if not raw:
            return None

        data = json.loads(raw)
        data["status"] = "approved"

        await redis.hset(self.POLICIES_KEY, policy_id, json.dumps(data))

        logger.info(f"[DecisionSafety] Policy {policy_id} approved by {approved_by}")

        return LearnedPolicy(
            id=data["id"],
            incident_id=data["incident_id"],
            policy_type=PolicyLearningType(data["policy_type"]),
            name=data["name"],
            description=data["description"],
            rule_template=data["rule_template"],
            confidence=data["confidence"],
            effectiveness_estimate=data["effectiveness_estimate"],
            implementation_effort=data["implementation_effort"],
            priority=data["priority"],
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    # ========================================================================
    # Hard Production Guards
    # ========================================================================

    async def initialize_guards(self) -> int:
        """Initialize default production guards."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        created = 0

        for guard_def in DEFAULT_PROD_GUARDS:
            guard_id = hashlib.md5(guard_def["name"].encode()).hexdigest()[:8]

            existing = await redis.hget(self.GUARDS_KEY, guard_id)
            if existing:
                continue

            guard = ProdGuard(
                id=guard_id,
                name=guard_def["name"],
                description=guard_def["description"],
                guard_level=guard_def["guard_level"],
                action_patterns=guard_def["action_patterns"],
                conditions=guard_def["conditions"],
                enforcement=guard_def["enforcement"],
                bypass_roles=guard_def["bypass_roles"],
                bypass_requires_reason=guard_def["bypass_requires_reason"],
                active=True,
            )

            await redis.hset(
                self.GUARDS_KEY,
                guard_id,
                json.dumps(guard.to_dict()),
            )
            created += 1

        return created

    async def check_guard(
        self,
        action: str,
        actor: str,
        context: dict[str, Any],
        bypass_reason: str | None = None,
    ) -> tuple[bool, str, GuardViolation | None]:
        """Check if action violates any guards.

        Args:
            action: Action being attempted
            actor: Actor performing action
            context: Action context
            bypass_reason: Reason for bypass if requesting

        Returns:
            Tuple of (allowed, message, violation_record)
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        guards = await self.list_guards(active_only=True)

        for guard in guards:
            # Check if action matches guard patterns
            if not any(p in action for p in guard.action_patterns):
                continue

            # Check conditions
            if not self._check_guard_conditions(guard.conditions, context):
                continue

            # Guard matches - check enforcement
            actor_roles = context.get("actor_roles", [])
            can_bypass = any(role in guard.bypass_roles for role in actor_roles)

            if can_bypass and bypass_reason:
                # Bypass allowed
                violation = GuardViolation(
                    id=str(uuid.uuid4())[:8],
                    guard_id=guard.id,
                    guard_name=guard.name,
                    action_attempted=action,
                    actor=actor,
                    enforcement_result="bypassed",
                    bypass_used=True,
                    bypass_reason=bypass_reason,
                    context=context,
                    occurred_at=now,
                )
                await self._record_violation(redis, violation, guard)
                return True, f"Guard {guard.name} bypassed", violation

            if guard.enforcement == "block":
                violation = GuardViolation(
                    id=str(uuid.uuid4())[:8],
                    guard_id=guard.id,
                    guard_name=guard.name,
                    action_attempted=action,
                    actor=actor,
                    enforcement_result="blocked",
                    bypass_used=False,
                    bypass_reason=None,
                    context=context,
                    occurred_at=now,
                )
                await self._record_violation(redis, violation, guard)
                return False, f"Blocked by guard: {guard.name}", violation

            elif guard.enforcement == "warn":
                violation = GuardViolation(
                    id=str(uuid.uuid4())[:8],
                    guard_id=guard.id,
                    guard_name=guard.name,
                    action_attempted=action,
                    actor=actor,
                    enforcement_result="warned",
                    bypass_used=False,
                    bypass_reason=None,
                    context=context,
                    occurred_at=now,
                )
                await self._record_violation(redis, violation, guard)
                return True, f"Warning from guard: {guard.name}", violation

            else:  # audit
                violation = GuardViolation(
                    id=str(uuid.uuid4())[:8],
                    guard_id=guard.id,
                    guard_name=guard.name,
                    action_attempted=action,
                    actor=actor,
                    enforcement_result="audited",
                    bypass_used=False,
                    bypass_reason=None,
                    context=context,
                    occurred_at=now,
                )
                await self._record_violation(redis, violation, guard)
                return True, "Action audited", violation

        return True, "No guards triggered", None

    def _check_guard_conditions(
        self,
        conditions: dict[str, Any],
        context: dict[str, Any],
    ) -> bool:
        """Check if guard conditions are met."""
        for key, expected in conditions.items():
            if key == "environment":
                if context.get("environment") != expected:
                    return False
            elif key == "record_count_gt":
                if context.get("record_count", 0) <= expected:
                    return False
            elif key == "branch":
                if context.get("branch") not in expected:
                    return False
            elif key == "safety_level":
                if context.get("safety_level") != expected:
                    return False
            elif key == "hour_not_between":
                current_hour = datetime.now(UTC).hour
                if expected[0] <= current_hour <= expected[1]:
                    return False
            elif key == "error_rate_gt":
                if context.get("error_rate", 0) <= expected:
                    return False
            elif key == "active_p0_p1_incidents":
                if not context.get("active_p0_p1_incidents", False):
                    return False

        return True

    async def _record_violation(
        self,
        redis: Any,
        violation: GuardViolation,
        guard: ProdGuard,
    ) -> None:
        """Record a guard violation."""
        # Store violation
        await redis.lpush(
            self.VIOLATIONS_KEY,
            json.dumps(violation.to_dict()),
        )
        await redis.ltrim(self.VIOLATIONS_KEY, 0, 999)

        # Update guard stats
        guard.violations_count += 1
        guard.last_violation = violation.occurred_at
        await redis.hset(
            self.GUARDS_KEY,
            guard.id,
            json.dumps(guard.to_dict()),
        )

        logger.warning(f"[DecisionSafety] Guard violation: {guard.name} - {violation.enforcement_result}")

    async def list_guards(
        self,
        active_only: bool = False,
        guard_level: ProdGuardLevel | None = None,
    ) -> list[ProdGuard]:
        """List production guards."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hgetall(self.GUARDS_KEY)
        guards = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)

                if active_only and not data["active"]:
                    continue

                if guard_level and data["guard_level"] != guard_level.value:
                    continue

                guards.append(ProdGuard(
                    id=data["id"],
                    name=data["name"],
                    description=data["description"],
                    guard_level=ProdGuardLevel(data["guard_level"]),
                    action_patterns=data["action_patterns"],
                    conditions=data["conditions"],
                    enforcement=data["enforcement"],
                    bypass_roles=data["bypass_roles"],
                    bypass_requires_reason=data["bypass_requires_reason"],
                    active=data["active"],
                    violations_count=data.get("violations_count", 0),
                    last_violation=datetime.fromisoformat(data["last_violation"]) if data.get("last_violation") else None,
                ))
            except Exception:
                continue

        return guards

    async def get_guard(self, guard_id: str) -> ProdGuard | None:
        """Get guard by ID."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.GUARDS_KEY, guard_id)

        if not raw:
            return None

        data = json.loads(raw)
        return ProdGuard(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            guard_level=ProdGuardLevel(data["guard_level"]),
            action_patterns=data["action_patterns"],
            conditions=data["conditions"],
            enforcement=data["enforcement"],
            bypass_roles=data["bypass_roles"],
            bypass_requires_reason=data["bypass_requires_reason"],
            active=data["active"],
            violations_count=data.get("violations_count", 0),
            last_violation=datetime.fromisoformat(data["last_violation"]) if data.get("last_violation") else None,
        )

    async def toggle_guard(
        self,
        guard_id: str,
        active: bool,
        toggled_by: str,
    ) -> ProdGuard | None:
        """Toggle guard active state."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        guard = await self.get_guard(guard_id)

        if not guard:
            return None

        guard.active = active
        await redis.hset(self.GUARDS_KEY, guard_id, json.dumps(guard.to_dict()))

        logger.info(f"[DecisionSafety] Guard {guard_id} {'activated' if active else 'deactivated'} by {toggled_by}")

        return guard

    async def get_violations(
        self,
        guard_id: str | None = None,
        limit: int = 100,
    ) -> list[GuardViolation]:
        """Get guard violations."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.lrange(self.VIOLATIONS_KEY, 0, limit - 1)
        violations = []

        for item in raw:
            try:
                data = json.loads(item)

                if guard_id and data["guard_id"] != guard_id:
                    continue

                violations.append(GuardViolation(
                    id=data["id"],
                    guard_id=data["guard_id"],
                    guard_name=data["guard_name"],
                    action_attempted=data["action_attempted"],
                    actor=data["actor"],
                    enforcement_result=data["enforcement_result"],
                    bypass_used=data["bypass_used"],
                    bypass_reason=data.get("bypass_reason"),
                    context=data["context"],
                    occurred_at=datetime.fromisoformat(data["occurred_at"]),
                ))
            except Exception:
                continue

        return violations


# Singleton
decision_safety = DecisionSafetyService()
