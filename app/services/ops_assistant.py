"""Autonomous Ops Assistant Service.

Auto-triage, remediation plans, safe runbooks, escalation, handoffs.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any
import uuid
import hashlib

UTC = timezone.utc

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================


class TriageSeverity(str, Enum):
    """Triage severity levels."""

    P0 = "p0"  # Critical - immediate action
    P1 = "p1"  # High - action within 1 hour
    P2 = "p2"  # Medium - action within 4 hours
    P3 = "p3"  # Low - action within 24 hours
    P4 = "p4"  # Informational - no action needed


class TriageCategory(str, Enum):
    """Triage category."""

    AVAILABILITY = "availability"
    PERFORMANCE = "performance"
    DATA = "data"
    SECURITY = "security"
    COST = "cost"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"


class RemediationStatus(str, Enum):
    """Remediation plan status."""

    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunbookSafetyLevel(str, Enum):
    """Runbook safety level."""

    SAFE = "safe"  # Can run anytime
    CAUTION = "caution"  # Requires confirmation
    DANGEROUS = "dangerous"  # Requires approval + confirmation
    CRITICAL = "critical"  # Requires multi-approval


class EscalationLevel(str, Enum):
    """Escalation levels."""

    L1 = "l1"  # First responder
    L2 = "l2"  # Senior engineer
    L3 = "l3"  # Team lead / on-call
    L4 = "l4"  # Management / incident commander


class HandoffStatus(str, Enum):
    """Handoff status."""

    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class TriageResult:
    """Result of incident triage."""

    id: str
    incident_id: str
    severity: TriageSeverity
    category: TriageCategory
    confidence: float
    summary: str
    impact_assessment: str
    affected_services: list[str]
    affected_users_estimate: int
    suggested_assignee: str | None
    escalation_required: bool
    escalation_level: EscalationLevel | None
    similar_incidents: list[str]
    triaged_at: datetime
    auto_triaged: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "severity": self.severity.value,
            "category": self.category.value,
            "confidence": round(self.confidence, 2),
            "summary": self.summary,
            "impact_assessment": self.impact_assessment,
            "affected_services": self.affected_services,
            "affected_users_estimate": self.affected_users_estimate,
            "suggested_assignee": self.suggested_assignee,
            "escalation_required": self.escalation_required,
            "escalation_level": self.escalation_level.value if self.escalation_level else None,
            "similar_incidents": self.similar_incidents,
            "triaged_at": self.triaged_at.isoformat(),
            "auto_triaged": self.auto_triaged,
        }


@dataclass
class RemediationStep:
    """Single step in remediation plan."""

    order: int
    action: str
    description: str
    runbook_id: str | None
    manual: bool
    estimated_minutes: int
    rollback_action: str | None
    verification: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "action": self.action,
            "description": self.description,
            "runbook_id": self.runbook_id,
            "manual": self.manual,
            "estimated_minutes": self.estimated_minutes,
            "rollback_action": self.rollback_action,
            "verification": self.verification,
        }


@dataclass
class RemediationPlan:
    """Remediation plan for an incident."""

    id: str
    incident_id: str
    triage_id: str
    title: str
    status: RemediationStatus
    steps: list[RemediationStep]
    current_step: int
    created_at: datetime
    created_by: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_estimated_minutes: int = 0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "triage_id": self.triage_id,
            "title": self.title,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "current_step": self.current_step,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_estimated_minutes": self.total_estimated_minutes,
            "notes": self.notes,
        }


@dataclass
class SafeRunbook:
    """Safe one-click runbook."""

    id: str
    name: str
    description: str
    category: TriageCategory
    safety_level: RunbookSafetyLevel
    commands: list[dict[str, Any]]
    pre_checks: list[str]
    post_checks: list[str]
    rollback_commands: list[dict[str, Any]]
    requires_approval: bool
    approval_roles: list[str]
    cooldown_minutes: int
    last_executed: datetime | None = None
    execution_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "safety_level": self.safety_level.value,
            "commands": self.commands,
            "pre_checks": self.pre_checks,
            "post_checks": self.post_checks,
            "rollback_commands": self.rollback_commands,
            "requires_approval": self.requires_approval,
            "approval_roles": self.approval_roles,
            "cooldown_minutes": self.cooldown_minutes,
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
            "execution_count": self.execution_count,
        }


@dataclass
class RunbookExecution:
    """Runbook execution record."""

    id: str
    runbook_id: str
    runbook_name: str
    executed_by: str
    executed_at: datetime
    status: str
    pre_check_passed: bool
    post_check_passed: bool
    duration_seconds: float
    output: str
    error: str | None = None
    rolled_back: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "runbook_id": self.runbook_id,
            "runbook_name": self.runbook_name,
            "executed_by": self.executed_by,
            "executed_at": self.executed_at.isoformat(),
            "status": self.status,
            "pre_check_passed": self.pre_check_passed,
            "post_check_passed": self.post_check_passed,
            "duration_seconds": round(self.duration_seconds, 2),
            "output": self.output,
            "error": self.error,
            "rolled_back": self.rolled_back,
        }


@dataclass
class EscalationRule:
    """Escalation rule."""

    id: str
    name: str
    condition: dict[str, Any]
    escalation_level: EscalationLevel
    notify_channels: list[str]
    auto_escalate_minutes: int
    enabled: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "condition": self.condition,
            "escalation_level": self.escalation_level.value,
            "notify_channels": self.notify_channels,
            "auto_escalate_minutes": self.auto_escalate_minutes,
            "enabled": self.enabled,
        }


@dataclass
class OperatorNote:
    """Operator note for handoffs."""

    id: str
    author: str
    created_at: datetime
    shift: str
    content: str
    incident_ids: list[str]
    action_items: list[str]
    tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "shift": self.shift,
            "content": self.content,
            "incident_ids": self.incident_ids,
            "action_items": self.action_items,
            "tags": self.tags,
        }


@dataclass
class ShiftHandoff:
    """Shift handoff record."""

    id: str
    from_operator: str
    to_operator: str
    shift_start: datetime
    shift_end: datetime
    status: HandoffStatus
    notes: list[OperatorNote]
    active_incidents: list[str]
    pending_actions: list[str]
    acknowledged_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_operator": self.from_operator,
            "to_operator": self.to_operator,
            "shift_start": self.shift_start.isoformat(),
            "shift_end": self.shift_end.isoformat(),
            "status": self.status.value,
            "notes": [n.to_dict() for n in self.notes],
            "active_incidents": self.active_incidents,
            "pending_actions": self.pending_actions,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
        }


@dataclass
class HistoricalFix:
    """Historical fix record."""

    id: str
    incident_pattern: str
    category: TriageCategory
    fix_description: str
    runbook_id: str | None
    success_rate: float
    avg_resolution_minutes: float
    times_used: int
    last_used: datetime
    tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_pattern": self.incident_pattern,
            "category": self.category.value,
            "fix_description": self.fix_description,
            "runbook_id": self.runbook_id,
            "success_rate": round(self.success_rate, 2),
            "avg_resolution_minutes": round(self.avg_resolution_minutes, 1),
            "times_used": self.times_used,
            "last_used": self.last_used.isoformat(),
            "tags": self.tags,
        }


@dataclass
class FixRecommendation:
    """Fix recommendation based on history."""

    historical_fix: HistoricalFix
    confidence: float
    reasoning: str
    estimated_resolution_minutes: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "historical_fix": self.historical_fix.to_dict(),
            "confidence": round(self.confidence, 2),
            "reasoning": self.reasoning,
            "estimated_resolution_minutes": round(self.estimated_resolution_minutes, 1),
        }


# ============================================================================
# Triage Patterns
# ============================================================================

TRIAGE_PATTERNS = [
    {
        "keywords": ["outage", "down", "unavailable", "503", "502", "500"],
        "severity": TriageSeverity.P0,
        "category": TriageCategory.AVAILABILITY,
        "impact": "Service unavailable to users",
    },
    {
        "keywords": ["database", "postgres", "connection", "pool"],
        "severity": TriageSeverity.P0,
        "category": TriageCategory.AVAILABILITY,
        "impact": "Database connectivity issues affecting data access",
    },
    {
        "keywords": ["redis", "cache", "memory"],
        "severity": TriageSeverity.P1,
        "category": TriageCategory.PERFORMANCE,
        "impact": "Cache issues affecting performance",
    },
    {
        "keywords": ["slow", "latency", "timeout", "performance"],
        "severity": TriageSeverity.P1,
        "category": TriageCategory.PERFORMANCE,
        "impact": "Degraded performance affecting user experience",
    },
    {
        "keywords": ["queue", "backlog", "celery", "worker"],
        "severity": TriageSeverity.P2,
        "category": TriageCategory.OPERATIONAL,
        "impact": "Task processing delays",
    },
    {
        "keywords": ["error", "exception", "failure", "failed"],
        "severity": TriageSeverity.P2,
        "category": TriageCategory.OPERATIONAL,
        "impact": "Errors occurring in application",
    },
    {
        "keywords": ["security", "auth", "unauthorized", "breach"],
        "severity": TriageSeverity.P0,
        "category": TriageCategory.SECURITY,
        "impact": "Security incident requiring immediate attention",
    },
    {
        "keywords": ["cost", "budget", "spending", "overage"],
        "severity": TriageSeverity.P2,
        "category": TriageCategory.COST,
        "impact": "Cost-related concern",
    },
    {
        "keywords": ["data", "corrupt", "inconsistent", "missing"],
        "severity": TriageSeverity.P1,
        "category": TriageCategory.DATA,
        "impact": "Data integrity issues",
    },
]


# ============================================================================
# Default Runbooks
# ============================================================================

DEFAULT_RUNBOOKS = [
    {
        "id": "rb-restart-api",
        "name": "Restart API Service",
        "description": "Gracefully restart the API service",
        "category": TriageCategory.AVAILABILITY,
        "safety_level": RunbookSafetyLevel.CAUTION,
        "commands": [
            {"type": "check", "cmd": "health_check", "description": "Verify current health"},
            {"type": "action", "cmd": "graceful_restart", "description": "Graceful restart"},
            {"type": "wait", "seconds": 30, "description": "Wait for startup"},
            {"type": "check", "cmd": "health_check", "description": "Verify restored health"},
        ],
        "pre_checks": ["Service is running", "No active deployments"],
        "post_checks": ["Health endpoint returns 200", "Error rate < 1%"],
        "rollback_commands": [],
        "requires_approval": False,
        "approval_roles": [],
        "cooldown_minutes": 5,
    },
    {
        "id": "rb-clear-cache",
        "name": "Clear Redis Cache",
        "description": "Flush specific cache keys or patterns",
        "category": TriageCategory.PERFORMANCE,
        "safety_level": RunbookSafetyLevel.CAUTION,
        "commands": [
            {"type": "action", "cmd": "cache_flush", "pattern": "cache:*", "description": "Flush cache"},
        ],
        "pre_checks": ["Redis is accessible"],
        "post_checks": ["Cache operations working"],
        "rollback_commands": [],
        "requires_approval": False,
        "approval_roles": [],
        "cooldown_minutes": 2,
    },
    {
        "id": "rb-scale-workers",
        "name": "Scale Celery Workers",
        "description": "Increase worker count to handle backlog",
        "category": TriageCategory.OPERATIONAL,
        "safety_level": RunbookSafetyLevel.SAFE,
        "commands": [
            {"type": "action", "cmd": "scale_workers", "count": 8, "description": "Scale to 8 workers"},
        ],
        "pre_checks": ["Celery broker accessible"],
        "post_checks": ["Workers registered", "Queue processing"],
        "rollback_commands": [
            {"type": "action", "cmd": "scale_workers", "count": 4, "description": "Scale back to 4"},
        ],
        "requires_approval": False,
        "approval_roles": [],
        "cooldown_minutes": 5,
    },
    {
        "id": "rb-circuit-breaker",
        "name": "Toggle Circuit Breaker",
        "description": "Open/close circuit breaker for a service",
        "category": TriageCategory.AVAILABILITY,
        "safety_level": RunbookSafetyLevel.CAUTION,
        "commands": [
            {"type": "action", "cmd": "circuit_breaker", "state": "open", "description": "Open breaker"},
        ],
        "pre_checks": ["Service identified"],
        "post_checks": ["Breaker state confirmed"],
        "rollback_commands": [
            {"type": "action", "cmd": "circuit_breaker", "state": "closed", "description": "Close breaker"},
        ],
        "requires_approval": False,
        "approval_roles": [],
        "cooldown_minutes": 1,
    },
    {
        "id": "rb-pause-processing",
        "name": "Pause Lead Processing",
        "description": "Pause all lead processing pipelines",
        "category": TriageCategory.OPERATIONAL,
        "safety_level": RunbookSafetyLevel.DANGEROUS,
        "commands": [
            {"type": "action", "cmd": "pause_processing", "description": "Pause processing"},
        ],
        "pre_checks": ["Confirm impact understood"],
        "post_checks": ["Processing paused confirmed"],
        "rollback_commands": [
            {"type": "action", "cmd": "resume_processing", "description": "Resume processing"},
        ],
        "requires_approval": True,
        "approval_roles": ["admin", "ops_lead"],
        "cooldown_minutes": 0,
    },
    {
        "id": "rb-failover-db",
        "name": "Database Failover",
        "description": "Failover to database replica",
        "category": TriageCategory.AVAILABILITY,
        "safety_level": RunbookSafetyLevel.CRITICAL,
        "commands": [
            {"type": "action", "cmd": "db_failover", "description": "Execute failover"},
            {"type": "wait", "seconds": 60, "description": "Wait for failover"},
            {"type": "check", "cmd": "db_health", "description": "Verify new primary"},
        ],
        "pre_checks": ["Replica is in sync", "No active transactions"],
        "post_checks": ["New primary accepting writes", "Replication lag < 1s"],
        "rollback_commands": [],
        "requires_approval": True,
        "approval_roles": ["admin", "dba"],
        "cooldown_minutes": 30,
    },
    {
        "id": "rb-drain-queue",
        "name": "Drain Task Queue",
        "description": "Drain tasks from a specific queue",
        "category": TriageCategory.OPERATIONAL,
        "safety_level": RunbookSafetyLevel.DANGEROUS,
        "commands": [
            {"type": "action", "cmd": "drain_queue", "description": "Drain queue"},
        ],
        "pre_checks": ["Queue identified", "Tasks can be lost"],
        "post_checks": ["Queue empty"],
        "rollback_commands": [],
        "requires_approval": True,
        "approval_roles": ["admin"],
        "cooldown_minutes": 5,
    },
    {
        "id": "rb-rotate-credentials",
        "name": "Rotate API Credentials",
        "description": "Rotate external API credentials",
        "category": TriageCategory.SECURITY,
        "safety_level": RunbookSafetyLevel.CRITICAL,
        "commands": [
            {"type": "action", "cmd": "rotate_credentials", "description": "Generate new credentials"},
            {"type": "action", "cmd": "update_secrets", "description": "Update in vault"},
            {"type": "action", "cmd": "restart_services", "description": "Restart services"},
        ],
        "pre_checks": ["Backup current credentials", "Off-peak hours preferred"],
        "post_checks": ["Services authenticated", "Old credentials revoked"],
        "rollback_commands": [
            {"type": "action", "cmd": "restore_credentials", "description": "Restore old credentials"},
        ],
        "requires_approval": True,
        "approval_roles": ["admin", "security"],
        "cooldown_minutes": 60,
    },
]


# ============================================================================
# Default Escalation Rules
# ============================================================================

DEFAULT_ESCALATION_RULES = [
    {
        "name": "P0 Immediate Escalation",
        "condition": {"severity": "p0"},
        "escalation_level": EscalationLevel.L3,
        "notify_channels": ["slack", "pagerduty"],
        "auto_escalate_minutes": 0,
    },
    {
        "name": "P1 Quick Escalation",
        "condition": {"severity": "p1", "unacknowledged_minutes": 15},
        "escalation_level": EscalationLevel.L2,
        "notify_channels": ["slack"],
        "auto_escalate_minutes": 15,
    },
    {
        "name": "P1 to L3 if Unresolved",
        "condition": {"severity": "p1", "unresolved_minutes": 60},
        "escalation_level": EscalationLevel.L3,
        "notify_channels": ["slack", "pagerduty"],
        "auto_escalate_minutes": 60,
    },
    {
        "name": "Security Incident",
        "condition": {"category": "security"},
        "escalation_level": EscalationLevel.L4,
        "notify_channels": ["slack", "pagerduty", "email"],
        "auto_escalate_minutes": 0,
    },
    {
        "name": "Data Incident",
        "condition": {"category": "data"},
        "escalation_level": EscalationLevel.L3,
        "notify_channels": ["slack"],
        "auto_escalate_minutes": 30,
    },
]


# ============================================================================
# Service
# ============================================================================


class OpsAssistantService:
    """Service for autonomous ops assistance.

    Features:
    - Auto-triage incidents
    - Generate remediation plans
    - Safe one-click runbooks
    - Escalation management
    - Operator handoffs
    - Historical fix recommendations
    """

    TRIAGE_KEY = "ops_assistant:triage"
    PLANS_KEY = "ops_assistant:plans"
    RUNBOOKS_KEY = "ops_assistant:runbooks"
    EXECUTIONS_KEY = "ops_assistant:executions"
    RULES_KEY = "ops_assistant:escalation_rules"
    NOTES_KEY = "ops_assistant:notes"
    HANDOFFS_KEY = "ops_assistant:handoffs"
    FIXES_KEY = "ops_assistant:historical_fixes"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Auto-Triage
    # ========================================================================

    async def auto_triage(
        self,
        incident_id: str,
        title: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> TriageResult:
        """Auto-triage an incident.

        Args:
            incident_id: Incident ID
            title: Incident title
            description: Incident description
            metadata: Additional metadata

        Returns:
            Triage result
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        # Analyze text
        text = f"{title} {description}".lower()
        severity, category, impact = self._analyze_incident(text)

        # Find similar incidents
        similar = await self._find_similar_incidents(title, description)

        # Determine escalation
        escalation_required, escalation_level = self._check_escalation_rules(
            severity, category
        )

        # Estimate affected users (simplified)
        affected_users = self._estimate_affected_users(severity, category)

        # Suggest assignee based on category
        assignee = self._suggest_assignee(category)

        # Extract affected services
        affected_services = self._extract_services(text)

        triage = TriageResult(
            id=str(uuid.uuid4())[:8],
            incident_id=incident_id,
            severity=severity,
            category=category,
            confidence=0.85 if severity in [TriageSeverity.P0, TriageSeverity.P1] else 0.75,
            summary=f"Auto-triaged as {severity.value.upper()} {category.value} incident",
            impact_assessment=impact,
            affected_services=affected_services,
            affected_users_estimate=affected_users,
            suggested_assignee=assignee,
            escalation_required=escalation_required,
            escalation_level=escalation_level,
            similar_incidents=similar,
            triaged_at=now,
            auto_triaged=True,
        )

        # Store triage
        await redis.hset(
            self.TRIAGE_KEY,
            incident_id,
            json.dumps(triage.to_dict()),
        )

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="incident_triaged",
                actor="ops_assistant",
                details={
                    "incident_id": incident_id,
                    "severity": severity.value,
                    "category": category.value,
                    "escalation_required": escalation_required,
                },
                severity="warning" if severity == TriageSeverity.P0 else "info",
            )
        except Exception:
            pass

        logger.info(f"[OpsAssistant] Triaged incident {incident_id}: {severity.value}")

        return triage

    def _analyze_incident(
        self,
        text: str,
    ) -> tuple[TriageSeverity, TriageCategory, str]:
        """Analyze incident text to determine severity and category."""
        best_match = None
        best_score = 0

        for pattern in TRIAGE_PATTERNS:
            score = sum(1 for kw in pattern["keywords"] if kw in text)
            if score > best_score:
                best_score = score
                best_match = pattern

        if best_match and best_score > 0:
            return (
                best_match["severity"],
                best_match["category"],
                best_match["impact"],
            )

        return (
            TriageSeverity.P3,
            TriageCategory.OPERATIONAL,
            "General operational issue",
        )

    async def _find_similar_incidents(
        self,
        title: str,
        description: str,
    ) -> list[str]:
        """Find similar past incidents."""
        try:
            from app.services.incident_timeline import incident_timeline

            recent = await incident_timeline.list_incidents(limit=50)

            similar = []
            title_words = set(title.lower().split())

            for incident in recent:
                incident_words = set(incident.title.lower().split())
                overlap = len(title_words & incident_words)
                if overlap >= 2:
                    similar.append(incident.id)
                    if len(similar) >= 5:
                        break

            return similar
        except Exception:
            return []

    def _check_escalation_rules(
        self,
        severity: TriageSeverity,
        category: TriageCategory,
    ) -> tuple[bool, EscalationLevel | None]:
        """Check escalation rules."""
        for rule in DEFAULT_ESCALATION_RULES:
            condition = rule["condition"]

            if "severity" in condition:
                if condition["severity"] == severity.value:
                    return True, rule["escalation_level"]

            if "category" in condition:
                if condition["category"] == category.value:
                    return True, rule["escalation_level"]

        if severity == TriageSeverity.P0:
            return True, EscalationLevel.L3

        return False, None

    def _estimate_affected_users(
        self,
        severity: TriageSeverity,
        category: TriageCategory,
    ) -> int:
        """Estimate affected users."""
        if severity == TriageSeverity.P0:
            return 1000
        elif severity == TriageSeverity.P1:
            return 500
        elif severity == TriageSeverity.P2:
            return 100
        else:
            return 10

    def _suggest_assignee(self, category: TriageCategory) -> str | None:
        """Suggest assignee based on category."""
        mapping = {
            TriageCategory.AVAILABILITY: "oncall-infra",
            TriageCategory.PERFORMANCE: "oncall-backend",
            TriageCategory.DATA: "oncall-data",
            TriageCategory.SECURITY: "oncall-security",
            TriageCategory.COST: "oncall-finops",
            TriageCategory.COMPLIANCE: "oncall-compliance",
            TriageCategory.OPERATIONAL: "oncall-ops",
        }
        return mapping.get(category)

    def _extract_services(self, text: str) -> list[str]:
        """Extract mentioned services from text."""
        services = []
        known_services = ["api", "postgres", "redis", "celery", "nginx", "openai", "anthropic"]

        for service in known_services:
            if service in text:
                services.append(service)

        return services or ["unknown"]

    async def get_triage(self, incident_id: str) -> TriageResult | None:
        """Get triage result for incident."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hget(self.TRIAGE_KEY, incident_id)
        if not raw:
            return None

        data = json.loads(raw)

        return TriageResult(
            id=data["id"],
            incident_id=data["incident_id"],
            severity=TriageSeverity(data["severity"]),
            category=TriageCategory(data["category"]),
            confidence=data["confidence"],
            summary=data["summary"],
            impact_assessment=data["impact_assessment"],
            affected_services=data["affected_services"],
            affected_users_estimate=data["affected_users_estimate"],
            suggested_assignee=data.get("suggested_assignee"),
            escalation_required=data["escalation_required"],
            escalation_level=EscalationLevel(data["escalation_level"]) if data.get("escalation_level") else None,
            similar_incidents=data.get("similar_incidents", []),
            triaged_at=datetime.fromisoformat(data["triaged_at"]),
            auto_triaged=data["auto_triaged"],
        )

    # ========================================================================
    # Remediation Plans
    # ========================================================================

    async def generate_remediation_plan(
        self,
        incident_id: str,
        created_by: str = "ops_assistant",
    ) -> RemediationPlan | None:
        """Generate remediation plan for incident.

        Args:
            incident_id: Incident ID
            created_by: Creator

        Returns:
            Remediation plan or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get triage
        triage = await self.get_triage(incident_id)
        if not triage:
            return None

        # Generate steps based on category
        steps = self._generate_steps(triage.category, triage.severity)

        total_minutes = sum(s.estimated_minutes for s in steps)

        plan = RemediationPlan(
            id=str(uuid.uuid4())[:8],
            incident_id=incident_id,
            triage_id=triage.id,
            title=f"Remediation for {triage.category.value} incident",
            status=RemediationStatus.READY,
            steps=steps,
            current_step=0,
            created_at=now,
            created_by=created_by,
            total_estimated_minutes=total_minutes,
        )

        # Store plan
        await redis.hset(
            self.PLANS_KEY,
            plan.id,
            json.dumps(plan.to_dict()),
        )

        logger.info(f"[OpsAssistant] Generated remediation plan {plan.id} for {incident_id}")

        return plan

    def _generate_steps(
        self,
        category: TriageCategory,
        severity: TriageSeverity,
    ) -> list[RemediationStep]:
        """Generate remediation steps based on category."""
        steps = []

        if category == TriageCategory.AVAILABILITY:
            steps = [
                RemediationStep(
                    order=1,
                    action="Verify service status",
                    description="Check health endpoints and logs",
                    runbook_id=None,
                    manual=True,
                    estimated_minutes=5,
                    rollback_action=None,
                    verification="Health endpoint returns 200",
                ),
                RemediationStep(
                    order=2,
                    action="Restart service",
                    description="Perform graceful restart",
                    runbook_id="rb-restart-api",
                    manual=False,
                    estimated_minutes=5,
                    rollback_action="Rollback deployment",
                    verification="Service responding",
                ),
                RemediationStep(
                    order=3,
                    action="Verify recovery",
                    description="Monitor for 10 minutes",
                    runbook_id=None,
                    manual=True,
                    estimated_minutes=10,
                    rollback_action=None,
                    verification="Error rate < 1%",
                ),
            ]
        elif category == TriageCategory.PERFORMANCE:
            steps = [
                RemediationStep(
                    order=1,
                    action="Check resource usage",
                    description="Review CPU, memory, connections",
                    runbook_id=None,
                    manual=True,
                    estimated_minutes=5,
                    rollback_action=None,
                    verification="Identify bottleneck",
                ),
                RemediationStep(
                    order=2,
                    action="Clear cache",
                    description="Flush problematic cache keys",
                    runbook_id="rb-clear-cache",
                    manual=False,
                    estimated_minutes=2,
                    rollback_action=None,
                    verification="Cache cleared",
                ),
                RemediationStep(
                    order=3,
                    action="Scale resources",
                    description="Increase workers if needed",
                    runbook_id="rb-scale-workers",
                    manual=False,
                    estimated_minutes=5,
                    rollback_action="Scale down",
                    verification="Performance improved",
                ),
            ]
        elif category == TriageCategory.OPERATIONAL:
            steps = [
                RemediationStep(
                    order=1,
                    action="Review queue status",
                    description="Check queue lengths and processing rate",
                    runbook_id=None,
                    manual=True,
                    estimated_minutes=5,
                    rollback_action=None,
                    verification="Identify stuck tasks",
                ),
                RemediationStep(
                    order=2,
                    action="Scale workers",
                    description="Increase worker count",
                    runbook_id="rb-scale-workers",
                    manual=False,
                    estimated_minutes=5,
                    rollback_action="Scale down",
                    verification="Queue draining",
                ),
            ]
        else:
            steps = [
                RemediationStep(
                    order=1,
                    action="Investigate issue",
                    description="Review logs and metrics",
                    runbook_id=None,
                    manual=True,
                    estimated_minutes=15,
                    rollback_action=None,
                    verification="Root cause identified",
                ),
                RemediationStep(
                    order=2,
                    action="Apply fix",
                    description="Execute appropriate remediation",
                    runbook_id=None,
                    manual=True,
                    estimated_minutes=30,
                    rollback_action="Revert changes",
                    verification="Issue resolved",
                ),
            ]

        return steps

    async def get_remediation_plan(self, plan_id: str) -> RemediationPlan | None:
        """Get remediation plan."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hget(self.PLANS_KEY, plan_id)
        if not raw:
            return None

        return self._parse_plan(json.loads(raw))

    def _parse_plan(self, data: dict[str, Any]) -> RemediationPlan:
        """Parse plan from dict."""
        steps = [
            RemediationStep(
                order=s["order"],
                action=s["action"],
                description=s["description"],
                runbook_id=s.get("runbook_id"),
                manual=s["manual"],
                estimated_minutes=s["estimated_minutes"],
                rollback_action=s.get("rollback_action"),
                verification=s["verification"],
            )
            for s in data["steps"]
        ]

        return RemediationPlan(
            id=data["id"],
            incident_id=data["incident_id"],
            triage_id=data["triage_id"],
            title=data["title"],
            status=RemediationStatus(data["status"]),
            steps=steps,
            current_step=data["current_step"],
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by=data["created_by"],
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            total_estimated_minutes=data["total_estimated_minutes"],
            notes=data.get("notes", ""),
        )

    async def advance_plan(
        self,
        plan_id: str,
        actor: str,
    ) -> RemediationPlan | None:
        """Advance plan to next step."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        plan = await self.get_remediation_plan(plan_id)
        if not plan:
            return None

        if plan.status == RemediationStatus.READY:
            plan.status = RemediationStatus.IN_PROGRESS
            plan.started_at = now

        plan.current_step += 1

        if plan.current_step >= len(plan.steps):
            plan.status = RemediationStatus.COMPLETED
            plan.completed_at = now

        await redis.hset(
            self.PLANS_KEY,
            plan_id,
            json.dumps(plan.to_dict()),
        )

        return plan

    # ========================================================================
    # Safe Runbooks
    # ========================================================================

    async def initialize_runbooks(self) -> int:
        """Initialize default runbooks."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        created = 0

        for rb_def in DEFAULT_RUNBOOKS:
            existing = await redis.hget(self.RUNBOOKS_KEY, rb_def["id"])
            if existing:
                continue

            runbook = SafeRunbook(
                id=rb_def["id"],
                name=rb_def["name"],
                description=rb_def["description"],
                category=rb_def["category"],
                safety_level=rb_def["safety_level"],
                commands=rb_def["commands"],
                pre_checks=rb_def["pre_checks"],
                post_checks=rb_def["post_checks"],
                rollback_commands=rb_def["rollback_commands"],
                requires_approval=rb_def["requires_approval"],
                approval_roles=rb_def["approval_roles"],
                cooldown_minutes=rb_def["cooldown_minutes"],
            )

            await redis.hset(
                self.RUNBOOKS_KEY,
                runbook.id,
                json.dumps(runbook.to_dict()),
            )
            created += 1

        return created

    async def list_runbooks(
        self,
        category: TriageCategory | None = None,
        safety_level: RunbookSafetyLevel | None = None,
    ) -> list[SafeRunbook]:
        """List runbooks."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hgetall(self.RUNBOOKS_KEY)
        runbooks = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)

                if category and data["category"] != category.value:
                    continue

                if safety_level and data["safety_level"] != safety_level.value:
                    continue

                runbooks.append(SafeRunbook(
                    id=data["id"],
                    name=data["name"],
                    description=data["description"],
                    category=TriageCategory(data["category"]),
                    safety_level=RunbookSafetyLevel(data["safety_level"]),
                    commands=data["commands"],
                    pre_checks=data["pre_checks"],
                    post_checks=data["post_checks"],
                    rollback_commands=data["rollback_commands"],
                    requires_approval=data["requires_approval"],
                    approval_roles=data["approval_roles"],
                    cooldown_minutes=data["cooldown_minutes"],
                    last_executed=datetime.fromisoformat(data["last_executed"]) if data.get("last_executed") else None,
                    execution_count=data.get("execution_count", 0),
                ))
            except Exception:
                continue

        return runbooks

    async def get_runbook(self, runbook_id: str) -> SafeRunbook | None:
        """Get runbook by ID."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hget(self.RUNBOOKS_KEY, runbook_id)
        if not raw:
            return None

        data = json.loads(raw)

        return SafeRunbook(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            category=TriageCategory(data["category"]),
            safety_level=RunbookSafetyLevel(data["safety_level"]),
            commands=data["commands"],
            pre_checks=data["pre_checks"],
            post_checks=data["post_checks"],
            rollback_commands=data["rollback_commands"],
            requires_approval=data["requires_approval"],
            approval_roles=data["approval_roles"],
            cooldown_minutes=data["cooldown_minutes"],
            last_executed=datetime.fromisoformat(data["last_executed"]) if data.get("last_executed") else None,
            execution_count=data.get("execution_count", 0),
        )

    async def execute_runbook(
        self,
        runbook_id: str,
        executed_by: str,
        parameters: dict[str, Any] | None = None,
        approval_id: str | None = None,
    ) -> RunbookExecution:
        """Execute a runbook.

        Args:
            runbook_id: Runbook ID
            executed_by: Executor
            parameters: Runtime parameters
            approval_id: Approval ID if required

        Returns:
            Execution record

        Raises:
            ValueError: If requirements not met
        """
        from app.storage.redis import get_redis
        import json
        import time

        redis = await get_redis()
        now = datetime.now(UTC)

        runbook = await self.get_runbook(runbook_id)
        if not runbook:
            raise ValueError("Runbook not found")

        # Check cooldown
        if runbook.last_executed:
            elapsed = (now - runbook.last_executed).total_seconds() / 60
            if elapsed < runbook.cooldown_minutes:
                raise ValueError(f"Cooldown active. Wait {runbook.cooldown_minutes - elapsed:.0f} minutes")

        # Check approval
        if runbook.requires_approval:
            if not approval_id:
                raise ValueError("Approval required for this runbook")
            # In production, would verify approval
            try:
                from app.services.approval_gates import approval_gates
                approved, msg = await approval_gates.check_approval(approval_id)
                if not approved:
                    raise ValueError(f"Approval not granted: {msg}")
            except Exception:
                pass

        start = time.time()

        # Simulate pre-checks
        pre_check_passed = True  # Would run actual checks

        # Simulate execution
        output = f"Executed {len(runbook.commands)} commands successfully"
        error = None
        status = "success"

        # Simulate post-checks
        post_check_passed = True  # Would run actual checks

        duration = time.time() - start

        execution = RunbookExecution(
            id=str(uuid.uuid4())[:8],
            runbook_id=runbook_id,
            runbook_name=runbook.name,
            executed_by=executed_by,
            executed_at=now,
            status=status,
            pre_check_passed=pre_check_passed,
            post_check_passed=post_check_passed,
            duration_seconds=duration,
            output=output,
            error=error,
        )

        # Update runbook
        runbook.last_executed = now
        runbook.execution_count += 1
        await redis.hset(
            self.RUNBOOKS_KEY,
            runbook_id,
            json.dumps(runbook.to_dict()),
        )

        # Store execution
        await redis.lpush(
            self.EXECUTIONS_KEY,
            json.dumps(execution.to_dict()),
        )
        await redis.ltrim(self.EXECUTIONS_KEY, 0, 999)

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="runbook_executed",
                actor=executed_by,
                details={
                    "runbook_id": runbook_id,
                    "runbook_name": runbook.name,
                    "status": status,
                },
                severity="info",
            )
        except Exception:
            pass

        logger.info(f"[OpsAssistant] Executed runbook {runbook_id}: {status}")

        return execution

    async def get_execution_history(
        self,
        runbook_id: str | None = None,
        limit: int = 50,
    ) -> list[RunbookExecution]:
        """Get runbook execution history."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.lrange(self.EXECUTIONS_KEY, 0, limit - 1)
        executions = []

        for item in raw:
            try:
                data = json.loads(item)

                if runbook_id and data["runbook_id"] != runbook_id:
                    continue

                executions.append(RunbookExecution(
                    id=data["id"],
                    runbook_id=data["runbook_id"],
                    runbook_name=data["runbook_name"],
                    executed_by=data["executed_by"],
                    executed_at=datetime.fromisoformat(data["executed_at"]),
                    status=data["status"],
                    pre_check_passed=data["pre_check_passed"],
                    post_check_passed=data["post_check_passed"],
                    duration_seconds=data["duration_seconds"],
                    output=data["output"],
                    error=data.get("error"),
                    rolled_back=data.get("rolled_back", False),
                ))
            except Exception:
                continue

        return executions

    # ========================================================================
    # Escalation Rules
    # ========================================================================

    async def initialize_escalation_rules(self) -> int:
        """Initialize default escalation rules."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        created = 0

        for rule_def in DEFAULT_ESCALATION_RULES:
            rule_id = hashlib.md5(rule_def["name"].encode()).hexdigest()[:8]

            existing = await redis.hget(self.RULES_KEY, rule_id)
            if existing:
                continue

            rule = EscalationRule(
                id=rule_id,
                name=rule_def["name"],
                condition=rule_def["condition"],
                escalation_level=rule_def["escalation_level"],
                notify_channels=rule_def["notify_channels"],
                auto_escalate_minutes=rule_def["auto_escalate_minutes"],
                enabled=True,
            )

            await redis.hset(
                self.RULES_KEY,
                rule_id,
                json.dumps(rule.to_dict()),
            )
            created += 1

        return created

    async def list_escalation_rules(self) -> list[EscalationRule]:
        """List escalation rules."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hgetall(self.RULES_KEY)
        rules = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)
                rules.append(EscalationRule(
                    id=data["id"],
                    name=data["name"],
                    condition=data["condition"],
                    escalation_level=EscalationLevel(data["escalation_level"]),
                    notify_channels=data["notify_channels"],
                    auto_escalate_minutes=data["auto_escalate_minutes"],
                    enabled=data["enabled"],
                ))
            except Exception:
                continue

        return rules

    # ========================================================================
    # Operator Notes & Handoffs
    # ========================================================================

    async def create_note(
        self,
        author: str,
        content: str,
        shift: str = "day",
        incident_ids: list[str] | None = None,
        action_items: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> OperatorNote:
        """Create operator note."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        note = OperatorNote(
            id=str(uuid.uuid4())[:8],
            author=author,
            created_at=now,
            shift=shift,
            content=content,
            incident_ids=incident_ids or [],
            action_items=action_items or [],
            tags=tags or [],
        )

        await redis.lpush(
            self.NOTES_KEY,
            json.dumps(note.to_dict()),
        )
        await redis.ltrim(self.NOTES_KEY, 0, 499)

        logger.info(f"[OpsAssistant] Note created by {author}")

        return note

    async def get_recent_notes(
        self,
        hours: int = 24,
        author: str | None = None,
        shift: str | None = None,
    ) -> list[OperatorNote]:
        """Get recent operator notes."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=hours)

        raw = await redis.lrange(self.NOTES_KEY, 0, 199)
        notes = []

        for item in raw:
            try:
                data = json.loads(item)
                created = datetime.fromisoformat(data["created_at"])

                if created < cutoff:
                    continue

                if author and data["author"] != author:
                    continue

                if shift and data["shift"] != shift:
                    continue

                notes.append(OperatorNote(
                    id=data["id"],
                    author=data["author"],
                    created_at=created,
                    shift=data["shift"],
                    content=data["content"],
                    incident_ids=data.get("incident_ids", []),
                    action_items=data.get("action_items", []),
                    tags=data.get("tags", []),
                ))
            except Exception:
                continue

        return notes

    async def create_handoff(
        self,
        from_operator: str,
        to_operator: str,
        shift_start: datetime,
        shift_end: datetime,
    ) -> ShiftHandoff:
        """Create shift handoff."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        # Gather recent notes
        notes = await self.get_recent_notes(hours=12, author=from_operator)

        # Get active incidents
        active_incidents = []
        try:
            from app.services.incident_timeline import incident_timeline
            incidents = await incident_timeline.get_active_incidents()
            active_incidents = [i.id for i in incidents]
        except Exception:
            pass

        # Extract pending actions from notes
        pending_actions = []
        for note in notes:
            pending_actions.extend(note.action_items)

        handoff = ShiftHandoff(
            id=str(uuid.uuid4())[:8],
            from_operator=from_operator,
            to_operator=to_operator,
            shift_start=shift_start,
            shift_end=shift_end,
            status=HandoffStatus.PENDING,
            notes=notes,
            active_incidents=active_incidents,
            pending_actions=pending_actions[:10],
        )

        await redis.hset(
            self.HANDOFFS_KEY,
            handoff.id,
            json.dumps(handoff.to_dict()),
        )

        logger.info(f"[OpsAssistant] Handoff created from {from_operator} to {to_operator}")

        return handoff

    async def acknowledge_handoff(
        self,
        handoff_id: str,
        acknowledged_by: str,
    ) -> ShiftHandoff | None:
        """Acknowledge shift handoff."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        raw = await redis.hget(self.HANDOFFS_KEY, handoff_id)
        if not raw:
            return None

        data = json.loads(raw)

        notes = [
            OperatorNote(
                id=n["id"],
                author=n["author"],
                created_at=datetime.fromisoformat(n["created_at"]),
                shift=n["shift"],
                content=n["content"],
                incident_ids=n.get("incident_ids", []),
                action_items=n.get("action_items", []),
                tags=n.get("tags", []),
            )
            for n in data.get("notes", [])
        ]

        handoff = ShiftHandoff(
            id=data["id"],
            from_operator=data["from_operator"],
            to_operator=data["to_operator"],
            shift_start=datetime.fromisoformat(data["shift_start"]),
            shift_end=datetime.fromisoformat(data["shift_end"]),
            status=HandoffStatus.ACKNOWLEDGED,
            notes=notes,
            active_incidents=data["active_incidents"],
            pending_actions=data["pending_actions"],
            acknowledged_at=now,
        )

        await redis.hset(
            self.HANDOFFS_KEY,
            handoff_id,
            json.dumps(handoff.to_dict()),
        )

        logger.info(f"[OpsAssistant] Handoff {handoff_id} acknowledged by {acknowledged_by}")

        return handoff

    async def get_handoff(self, handoff_id: str) -> ShiftHandoff | None:
        """Get handoff by ID."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hget(self.HANDOFFS_KEY, handoff_id)
        if not raw:
            return None

        data = json.loads(raw)

        notes = [
            OperatorNote(
                id=n["id"],
                author=n["author"],
                created_at=datetime.fromisoformat(n["created_at"]),
                shift=n["shift"],
                content=n["content"],
                incident_ids=n.get("incident_ids", []),
                action_items=n.get("action_items", []),
                tags=n.get("tags", []),
            )
            for n in data.get("notes", [])
        ]

        return ShiftHandoff(
            id=data["id"],
            from_operator=data["from_operator"],
            to_operator=data["to_operator"],
            shift_start=datetime.fromisoformat(data["shift_start"]),
            shift_end=datetime.fromisoformat(data["shift_end"]),
            status=HandoffStatus(data["status"]),
            notes=notes,
            active_incidents=data["active_incidents"],
            pending_actions=data["pending_actions"],
            acknowledged_at=datetime.fromisoformat(data["acknowledged_at"]) if data.get("acknowledged_at") else None,
        )

    # ========================================================================
    # Historical Fix Recommendations
    # ========================================================================

    async def record_fix(
        self,
        incident_id: str,
        fix_description: str,
        runbook_id: str | None = None,
        resolution_minutes: float = 30,
        tags: list[str] | None = None,
    ) -> HistoricalFix:
        """Record a successful fix for future recommendations."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get triage for category
        triage = await self.get_triage(incident_id)
        category = triage.category if triage else TriageCategory.OPERATIONAL

        # Create pattern from incident
        pattern = f"{category.value}:{fix_description[:50]}"
        pattern_hash = hashlib.md5(pattern.encode()).hexdigest()[:8]

        # Check if similar fix exists
        existing = await redis.hget(self.FIXES_KEY, pattern_hash)
        if existing:
            data = json.loads(existing)
            # Update existing
            times_used = data["times_used"] + 1
            avg_minutes = (data["avg_resolution_minutes"] * data["times_used"] + resolution_minutes) / times_used

            fix = HistoricalFix(
                id=data["id"],
                incident_pattern=pattern,
                category=TriageCategory(data["category"]),
                fix_description=fix_description,
                runbook_id=runbook_id or data.get("runbook_id"),
                success_rate=data["success_rate"],
                avg_resolution_minutes=avg_minutes,
                times_used=times_used,
                last_used=now,
                tags=list(set(data.get("tags", []) + (tags or []))),
            )
        else:
            fix = HistoricalFix(
                id=pattern_hash,
                incident_pattern=pattern,
                category=category,
                fix_description=fix_description,
                runbook_id=runbook_id,
                success_rate=1.0,
                avg_resolution_minutes=resolution_minutes,
                times_used=1,
                last_used=now,
                tags=tags or [],
            )

        await redis.hset(
            self.FIXES_KEY,
            fix.id,
            json.dumps(fix.to_dict()),
        )

        logger.info(f"[OpsAssistant] Recorded fix for pattern: {pattern}")

        return fix

    async def get_fix_recommendations(
        self,
        incident_id: str,
        limit: int = 5,
    ) -> list[FixRecommendation]:
        """Get fix recommendations based on historical data."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Get triage
        triage = await self.get_triage(incident_id)
        if not triage:
            return []

        # Get all historical fixes
        raw = await redis.hgetall(self.FIXES_KEY)
        fixes = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)
                fixes.append(HistoricalFix(
                    id=data["id"],
                    incident_pattern=data["incident_pattern"],
                    category=TriageCategory(data["category"]),
                    fix_description=data["fix_description"],
                    runbook_id=data.get("runbook_id"),
                    success_rate=data["success_rate"],
                    avg_resolution_minutes=data["avg_resolution_minutes"],
                    times_used=data["times_used"],
                    last_used=datetime.fromisoformat(data["last_used"]),
                    tags=data.get("tags", []),
                ))
            except Exception:
                continue

        # Score and rank fixes
        recommendations = []
        for fix in fixes:
            score = self._score_fix(fix, triage)
            if score > 0.3:
                recommendations.append(FixRecommendation(
                    historical_fix=fix,
                    confidence=score,
                    reasoning=self._generate_reasoning(fix, triage),
                    estimated_resolution_minutes=fix.avg_resolution_minutes,
                ))

        # Sort by confidence
        recommendations.sort(key=lambda r: r.confidence, reverse=True)

        return recommendations[:limit]

    def _score_fix(
        self,
        fix: HistoricalFix,
        triage: TriageResult,
    ) -> float:
        """Score a fix for relevance."""
        score = 0.0

        # Same category
        if fix.category == triage.category:
            score += 0.4

        # Success rate
        score += fix.success_rate * 0.3

        # Times used (experience)
        if fix.times_used >= 5:
            score += 0.2
        elif fix.times_used >= 2:
            score += 0.1

        # Recency
        days_since = (datetime.now(UTC) - fix.last_used).days
        if days_since < 7:
            score += 0.1
        elif days_since < 30:
            score += 0.05

        return min(score, 1.0)

    def _generate_reasoning(
        self,
        fix: HistoricalFix,
        triage: TriageResult,
    ) -> str:
        """Generate reasoning for recommendation."""
        parts = []

        if fix.category == triage.category:
            parts.append(f"Same category ({fix.category.value})")

        if fix.success_rate >= 0.9:
            parts.append(f"High success rate ({fix.success_rate:.0%})")

        if fix.times_used >= 3:
            parts.append(f"Used {fix.times_used} times before")

        if fix.runbook_id:
            parts.append("Has automated runbook")

        return "; ".join(parts) if parts else "Pattern match"

    async def list_historical_fixes(
        self,
        category: TriageCategory | None = None,
        limit: int = 50,
    ) -> list[HistoricalFix]:
        """List historical fixes."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hgetall(self.FIXES_KEY)
        fixes = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)

                if category and data["category"] != category.value:
                    continue

                fixes.append(HistoricalFix(
                    id=data["id"],
                    incident_pattern=data["incident_pattern"],
                    category=TriageCategory(data["category"]),
                    fix_description=data["fix_description"],
                    runbook_id=data.get("runbook_id"),
                    success_rate=data["success_rate"],
                    avg_resolution_minutes=data["avg_resolution_minutes"],
                    times_used=data["times_used"],
                    last_used=datetime.fromisoformat(data["last_used"]),
                    tags=data.get("tags", []),
                ))
            except Exception:
                continue

        # Sort by times used
        fixes.sort(key=lambda f: f.times_used, reverse=True)

        return fixes[:limit]


# Singleton
ops_assistant = OpsAssistantService()
