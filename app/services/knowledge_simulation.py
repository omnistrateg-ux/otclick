"""Knowledge and Simulation Layer Service.

Operational knowledge base, incident patterns, what-if simulation,
policy conflict detection, recommendation scoring, and training mode.
"""

import logging
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any
import uuid
import random

UTC = timezone.utc

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================


class KnowledgeCategory(str, Enum):
    """Knowledge category."""

    RUNBOOK = "runbook"
    TROUBLESHOOTING = "troubleshooting"
    ARCHITECTURE = "architecture"
    PROCEDURE = "procedure"
    ALERT = "alert"
    METRIC = "metric"
    DEPENDENCY = "dependency"
    CONTACT = "contact"


class KnowledgeConfidence(str, Enum):
    """Knowledge confidence level."""

    VERIFIED = "verified"  # Officially verified
    TRUSTED = "trusted"  # From trusted source
    COMMUNITY = "community"  # Community contributed
    EXPERIMENTAL = "experimental"  # Experimental/untested


class PatternType(str, Enum):
    """Incident pattern type."""

    SYMPTOM = "symptom"
    CAUSE = "cause"
    RESOLUTION = "resolution"
    CORRELATION = "correlation"
    SEQUENCE = "sequence"


class SimulationStatus(str, Enum):
    """Simulation status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SimulationOutcome(str, Enum):
    """Simulation outcome prediction."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


class ConflictSeverity(str, Enum):
    """Policy conflict severity."""

    CRITICAL = "critical"  # Must resolve before proceeding
    HIGH = "high"  # Should resolve
    MEDIUM = "medium"  # Consider resolving
    LOW = "low"  # Informational


class TrainingScenarioType(str, Enum):
    """Training scenario type."""

    INCIDENT_RESPONSE = "incident_response"
    RUNBOOK_EXECUTION = "runbook_execution"
    ESCALATION = "escalation"
    TRIAGE = "triage"
    COMMUNICATION = "communication"


class TrainingDifficulty(str, Enum):
    """Training difficulty level."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class KnowledgeEntry:
    """Knowledge base entry."""

    id: str
    title: str
    category: KnowledgeCategory
    content: str
    tags: list[str]
    confidence: KnowledgeConfidence
    source: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    views: int = 0
    helpful_votes: int = 0
    related_entries: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category.value,
            "content": self.content,
            "tags": self.tags,
            "confidence": self.confidence.value,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "views": self.views,
            "helpful_votes": self.helpful_votes,
            "related_entries": self.related_entries,
            "metadata": self.metadata,
        }


@dataclass
class IncidentPattern:
    """Incident pattern memory."""

    id: str
    pattern_type: PatternType
    name: str
    description: str
    indicators: list[str]
    regex_patterns: list[str]
    severity_correlation: dict[str, float]
    category_correlation: dict[str, float]
    resolution_hints: list[str]
    avg_resolution_minutes: float
    occurrence_count: int
    last_seen: datetime
    confidence: float
    tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pattern_type": self.pattern_type.value,
            "name": self.name,
            "description": self.description,
            "indicators": self.indicators,
            "regex_patterns": self.regex_patterns,
            "severity_correlation": self.severity_correlation,
            "category_correlation": self.category_correlation,
            "resolution_hints": self.resolution_hints,
            "avg_resolution_minutes": round(self.avg_resolution_minutes, 1),
            "occurrence_count": self.occurrence_count,
            "last_seen": self.last_seen.isoformat(),
            "confidence": round(self.confidence, 2),
            "tags": self.tags,
        }


@dataclass
class PatternMatch:
    """Pattern match result."""

    pattern: IncidentPattern
    match_score: float
    matched_indicators: list[str]
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern.to_dict(),
            "match_score": round(self.match_score, 2),
            "matched_indicators": self.matched_indicators,
            "reasoning": self.reasoning,
        }


@dataclass
class SimulationScenario:
    """What-if simulation scenario."""

    id: str
    name: str
    action_type: str
    action_parameters: dict[str, Any]
    pre_conditions: dict[str, Any]
    created_by: str
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "action_type": self.action_type,
            "action_parameters": self.action_parameters,
            "pre_conditions": self.pre_conditions,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SimulationResult:
    """Simulation result."""

    id: str
    scenario_id: str
    status: SimulationStatus
    outcome: SimulationOutcome
    confidence: float
    predicted_impacts: list[dict[str, Any]]
    risk_factors: list[dict[str, Any]]
    mitigation_suggestions: list[str]
    estimated_duration_minutes: int
    estimated_rollback_time_minutes: int
    side_effects: list[str]
    dependencies_affected: list[str]
    executed_at: datetime
    completed_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "status": self.status.value,
            "outcome": self.outcome.value,
            "confidence": round(self.confidence, 2),
            "predicted_impacts": self.predicted_impacts,
            "risk_factors": self.risk_factors,
            "mitigation_suggestions": self.mitigation_suggestions,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "estimated_rollback_time_minutes": self.estimated_rollback_time_minutes,
            "side_effects": self.side_effects,
            "dependencies_affected": self.dependencies_affected,
            "executed_at": self.executed_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class PolicyConflict:
    """Policy conflict detection result."""

    id: str
    policy_a_id: str
    policy_a_name: str
    policy_b_id: str
    policy_b_name: str
    conflict_type: str
    severity: ConflictSeverity
    description: str
    resolution_options: list[str]
    detected_at: datetime
    resolved: bool = False
    resolution: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "policy_a_id": self.policy_a_id,
            "policy_a_name": self.policy_a_name,
            "policy_b_id": self.policy_b_id,
            "policy_b_name": self.policy_b_name,
            "conflict_type": self.conflict_type,
            "severity": self.severity.value,
            "description": self.description,
            "resolution_options": self.resolution_options,
            "detected_at": self.detected_at.isoformat(),
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


@dataclass
class RecommendationQuality:
    """Recommendation quality score."""

    recommendation_id: str
    recommendation_type: str
    accuracy_score: float
    relevance_score: float
    timeliness_score: float
    completeness_score: float
    overall_score: float
    feedback_count: int
    positive_feedback: int
    negative_feedback: int
    improvement_suggestions: list[str]
    scored_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "recommendation_type": self.recommendation_type,
            "accuracy_score": round(self.accuracy_score, 2),
            "relevance_score": round(self.relevance_score, 2),
            "timeliness_score": round(self.timeliness_score, 2),
            "completeness_score": round(self.completeness_score, 2),
            "overall_score": round(self.overall_score, 2),
            "feedback_count": self.feedback_count,
            "positive_feedback": self.positive_feedback,
            "negative_feedback": self.negative_feedback,
            "improvement_suggestions": self.improvement_suggestions,
            "scored_at": self.scored_at.isoformat(),
        }


@dataclass
class TrainingScenario:
    """Training scenario for operators."""

    id: str
    name: str
    scenario_type: TrainingScenarioType
    difficulty: TrainingDifficulty
    description: str
    objectives: list[str]
    initial_state: dict[str, Any]
    expected_actions: list[dict[str, Any]]
    hints: list[str]
    time_limit_minutes: int
    passing_score: float
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "scenario_type": self.scenario_type.value,
            "difficulty": self.difficulty.value,
            "description": self.description,
            "objectives": self.objectives,
            "initial_state": self.initial_state,
            "expected_actions": self.expected_actions,
            "hints": self.hints,
            "time_limit_minutes": self.time_limit_minutes,
            "passing_score": round(self.passing_score, 2),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class TrainingSession:
    """Training session for an operator."""

    id: str
    scenario_id: str
    operator_id: str
    started_at: datetime
    completed_at: datetime | None
    actions_taken: list[dict[str, Any]]
    hints_used: int
    score: float | None
    passed: bool | None
    feedback: str
    time_spent_minutes: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "operator_id": self.operator_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "actions_taken": self.actions_taken,
            "hints_used": self.hints_used,
            "score": round(self.score, 2) if self.score else None,
            "passed": self.passed,
            "feedback": self.feedback,
            "time_spent_minutes": round(self.time_spent_minutes, 1),
        }


@dataclass
class OperatorSkillProfile:
    """Operator skill profile."""

    operator_id: str
    scenarios_completed: int
    scenarios_passed: int
    total_training_minutes: float
    skill_scores: dict[str, float]
    certifications: list[str]
    last_training: datetime | None
    strengths: list[str]
    areas_for_improvement: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "scenarios_completed": self.scenarios_completed,
            "scenarios_passed": self.scenarios_passed,
            "total_training_minutes": round(self.total_training_minutes, 1),
            "skill_scores": {k: round(v, 2) for k, v in self.skill_scores.items()},
            "certifications": self.certifications,
            "last_training": self.last_training.isoformat() if self.last_training else None,
            "strengths": self.strengths,
            "areas_for_improvement": self.areas_for_improvement,
        }


# ============================================================================
# Default Knowledge Entries
# ============================================================================

DEFAULT_KNOWLEDGE = [
    {
        "title": "API 503 Error Troubleshooting",
        "category": KnowledgeCategory.TROUBLESHOOTING,
        "content": """
## Symptoms
- HTTP 503 Service Unavailable responses
- Load balancer health checks failing
- High latency before failure

## Common Causes
1. Backend service crashed or unresponsive
2. Database connection pool exhausted
3. Memory/CPU exhaustion
4. Upstream dependency failure

## Resolution Steps
1. Check service health: `curl localhost:8080/health`
2. Review logs: `kubectl logs -f deployment/api`
3. Check database connections: `SELECT count(*) FROM pg_stat_activity`
4. Restart if needed: `kubectl rollout restart deployment/api`
        """,
        "tags": ["api", "503", "troubleshooting", "availability"],
        "confidence": KnowledgeConfidence.VERIFIED,
    },
    {
        "title": "Redis Connection Issues",
        "category": KnowledgeCategory.TROUBLESHOOTING,
        "content": """
## Symptoms
- Connection timeouts to Redis
- Increased latency
- Cache miss rate spike

## Common Causes
1. Redis server overloaded
2. Network connectivity issues
3. Max connections reached
4. Memory pressure

## Resolution Steps
1. Check Redis status: `redis-cli ping`
2. Review memory: `redis-cli info memory`
3. Check connections: `redis-cli info clients`
4. Clear cache if needed: `redis-cli flushdb`
        """,
        "tags": ["redis", "cache", "connection", "performance"],
        "confidence": KnowledgeConfidence.VERIFIED,
    },
    {
        "title": "Database Connection Pool Exhaustion",
        "category": KnowledgeCategory.TROUBLESHOOTING,
        "content": """
## Symptoms
- Connection errors in application logs
- "Too many connections" errors
- Slow queries or timeouts

## Common Causes
1. Connection leaks in application
2. Long-running queries holding connections
3. Pool size too small for load
4. Sudden traffic spike

## Resolution Steps
1. Check active connections: `SELECT * FROM pg_stat_activity`
2. Kill idle connections if needed
3. Review connection pool settings
4. Scale up pool size temporarily
        """,
        "tags": ["database", "postgres", "connection", "pool"],
        "confidence": KnowledgeConfidence.VERIFIED,
    },
    {
        "title": "Celery Worker Queue Backlog",
        "category": KnowledgeCategory.PROCEDURE,
        "content": """
## Symptoms
- Task queue length increasing
- Delayed task execution
- Worker processes idle or crashed

## Common Causes
1. Insufficient worker count
2. Slow task execution
3. Worker crashes
4. Broker connectivity issues

## Resolution Steps
1. Check queue length: `celery -A app inspect active`
2. Scale workers: `celery -A app worker --concurrency=8`
3. Check broker: `redis-cli llen celery`
4. Review failed tasks: Check Flower dashboard
        """,
        "tags": ["celery", "queue", "worker", "async"],
        "confidence": KnowledgeConfidence.TRUSTED,
    },
    {
        "title": "Deployment Rollback Procedure",
        "category": KnowledgeCategory.RUNBOOK,
        "content": """
## Pre-requisites
- Identify the problematic deployment
- Confirm rollback is the right action
- Notify stakeholders

## Steps
1. Identify previous version: `git log --oneline -5`
2. Trigger rollback: `kubectl rollout undo deployment/api`
3. Monitor rollout: `kubectl rollout status deployment/api`
4. Verify health: `curl -s localhost:8080/health`
5. Update incident ticket

## Post-rollback
- Investigate root cause
- Update deployment pipeline if needed
- Document lessons learned
        """,
        "tags": ["deployment", "rollback", "kubernetes", "procedure"],
        "confidence": KnowledgeConfidence.VERIFIED,
    },
]


# ============================================================================
# Default Incident Patterns
# ============================================================================

DEFAULT_PATTERNS = [
    {
        "pattern_type": PatternType.SYMPTOM,
        "name": "Memory Leak Pattern",
        "description": "Gradual memory increase leading to OOM",
        "indicators": ["memory_usage_increasing", "oom_killed", "slow_gc"],
        "regex_patterns": [r"Out of memory", r"OOM", r"memory pressure"],
        "severity_correlation": {"p0": 0.3, "p1": 0.5, "p2": 0.2},
        "category_correlation": {"performance": 0.6, "availability": 0.4},
        "resolution_hints": ["Restart service", "Increase memory limit", "Fix memory leak"],
        "avg_resolution_minutes": 30,
    },
    {
        "pattern_type": PatternType.CAUSE,
        "name": "Database Overload",
        "description": "Database unable to handle query load",
        "indicators": ["slow_queries", "connection_exhaustion", "high_cpu_db"],
        "regex_patterns": [r"connection.*exhaust", r"query.*timeout", r"lock.*wait"],
        "severity_correlation": {"p0": 0.4, "p1": 0.4, "p2": 0.2},
        "category_correlation": {"performance": 0.5, "availability": 0.5},
        "resolution_hints": ["Scale database", "Optimize queries", "Add read replicas"],
        "avg_resolution_minutes": 45,
    },
    {
        "pattern_type": PatternType.CORRELATION,
        "name": "Deploy-Incident Correlation",
        "description": "Incidents often occur shortly after deployments",
        "indicators": ["recent_deploy", "new_version", "config_change"],
        "regex_patterns": [r"deploy", r"release", r"version"],
        "severity_correlation": {"p0": 0.2, "p1": 0.5, "p2": 0.3},
        "category_correlation": {"availability": 0.6, "performance": 0.4},
        "resolution_hints": ["Rollback deployment", "Check deployment logs", "Review changes"],
        "avg_resolution_minutes": 20,
    },
    {
        "pattern_type": PatternType.SEQUENCE,
        "name": "Cascading Failure",
        "description": "One service failure causes downstream failures",
        "indicators": ["multiple_services_affected", "dependency_failure", "timeout_cascade"],
        "regex_patterns": [r"timeout", r"upstream", r"circuit.*open"],
        "severity_correlation": {"p0": 0.6, "p1": 0.3, "p2": 0.1},
        "category_correlation": {"availability": 0.8, "performance": 0.2},
        "resolution_hints": ["Identify root service", "Open circuit breakers", "Isolate failure"],
        "avg_resolution_minutes": 60,
    },
]


# ============================================================================
# Default Training Scenarios
# ============================================================================

DEFAULT_TRAINING_SCENARIOS = [
    {
        "name": "P0 API Outage Response",
        "scenario_type": TrainingScenarioType.INCIDENT_RESPONSE,
        "difficulty": TrainingDifficulty.INTERMEDIATE,
        "description": "Respond to a P0 API outage affecting all users",
        "objectives": [
            "Acknowledge incident within 5 minutes",
            "Correctly identify root cause",
            "Execute appropriate runbook",
            "Communicate with stakeholders",
        ],
        "initial_state": {
            "incident": {"severity": "p0", "title": "API returning 503 errors"},
            "services": {"api": "unhealthy", "database": "healthy", "redis": "healthy"},
            "alerts": ["API health check failing", "Error rate > 50%"],
        },
        "expected_actions": [
            {"action": "acknowledge_incident", "points": 10},
            {"action": "check_logs", "points": 10},
            {"action": "identify_cause", "cause": "api_crash", "points": 20},
            {"action": "execute_runbook", "runbook": "rb-restart-api", "points": 30},
            {"action": "notify_stakeholders", "points": 15},
            {"action": "verify_recovery", "points": 15},
        ],
        "hints": [
            "Check the API logs for crash information",
            "Consider restarting the API service",
            "Don't forget to notify stakeholders",
        ],
        "time_limit_minutes": 15,
        "passing_score": 0.7,
    },
    {
        "name": "Triage Practice - Mixed Incidents",
        "scenario_type": TrainingScenarioType.TRIAGE,
        "difficulty": TrainingDifficulty.BEGINNER,
        "description": "Practice triaging various incident types",
        "objectives": [
            "Correctly assign severity to 5 incidents",
            "Correctly categorize incidents",
            "Identify escalation requirements",
        ],
        "initial_state": {
            "incidents": [
                {"title": "Minor UI glitch", "expected_severity": "p3"},
                {"title": "Database connection timeout", "expected_severity": "p1"},
                {"title": "Complete service outage", "expected_severity": "p0"},
                {"title": "Slow page load time", "expected_severity": "p2"},
                {"title": "Security vulnerability detected", "expected_severity": "p0"},
            ],
        },
        "expected_actions": [
            {"action": "triage", "incident_index": 0, "severity": "p3", "points": 20},
            {"action": "triage", "incident_index": 1, "severity": "p1", "points": 20},
            {"action": "triage", "incident_index": 2, "severity": "p0", "points": 20},
            {"action": "triage", "incident_index": 3, "severity": "p2", "points": 20},
            {"action": "triage", "incident_index": 4, "severity": "p0", "points": 20},
        ],
        "hints": [
            "P0 = Critical, immediate action required",
            "P1 = High, action within 1 hour",
            "P2 = Medium, action within 4 hours",
        ],
        "time_limit_minutes": 10,
        "passing_score": 0.8,
    },
    {
        "name": "Escalation Decision Making",
        "scenario_type": TrainingScenarioType.ESCALATION,
        "difficulty": TrainingDifficulty.ADVANCED,
        "description": "Practice when and how to escalate incidents",
        "objectives": [
            "Correctly decide when to escalate",
            "Choose appropriate escalation level",
            "Provide proper context in escalation",
        ],
        "initial_state": {
            "incident": {"severity": "p1", "duration_minutes": 45},
            "attempts": ["Restarted service", "Cleared cache"],
            "current_status": "Still degraded",
        },
        "expected_actions": [
            {"action": "decide_escalate", "decision": True, "points": 30},
            {"action": "select_level", "level": "l3", "points": 30},
            {"action": "provide_context", "includes": ["attempts", "duration"], "points": 40},
        ],
        "hints": [
            "Consider the incident duration",
            "Think about what you've already tried",
            "Who needs to know about this?",
        ],
        "time_limit_minutes": 10,
        "passing_score": 0.7,
    },
]


# ============================================================================
# Service
# ============================================================================


class KnowledgeSimulationService:
    """Service for knowledge and simulation layer.

    Features:
    - Operational knowledge base
    - Incident pattern memory
    - What-if simulation
    - Policy conflict detection
    - Recommendation quality scoring
    - Training mode for operators
    """

    KNOWLEDGE_KEY = "knowledge:entries"
    PATTERNS_KEY = "knowledge:patterns"
    SIMULATIONS_KEY = "knowledge:simulations"
    RESULTS_KEY = "knowledge:results"
    CONFLICTS_KEY = "knowledge:conflicts"
    QUALITY_KEY = "knowledge:quality"
    SCENARIOS_KEY = "training:scenarios"
    SESSIONS_KEY = "training:sessions"
    PROFILES_KEY = "training:profiles"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Knowledge Base
    # ========================================================================

    async def initialize_knowledge(self) -> int:
        """Initialize default knowledge entries."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        created = 0

        for kb in DEFAULT_KNOWLEDGE:
            entry_id = hashlib.md5(kb["title"].encode()).hexdigest()[:8]

            existing = await redis.hget(self.KNOWLEDGE_KEY, entry_id)
            if existing:
                continue

            entry = KnowledgeEntry(
                id=entry_id,
                title=kb["title"],
                category=kb["category"],
                content=kb["content"],
                tags=kb["tags"],
                confidence=kb["confidence"],
                source="system",
                created_at=now,
                updated_at=now,
                created_by="system",
            )

            await redis.hset(
                self.KNOWLEDGE_KEY,
                entry_id,
                json.dumps(entry.to_dict()),
            )
            created += 1

        return created

    async def add_knowledge(
        self,
        title: str,
        category: KnowledgeCategory,
        content: str,
        tags: list[str],
        confidence: KnowledgeConfidence,
        source: str,
        created_by: str,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeEntry:
        """Add knowledge entry."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        entry = KnowledgeEntry(
            id=str(uuid.uuid4())[:8],
            title=title,
            category=category,
            content=content,
            tags=tags,
            confidence=confidence,
            source=source,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            metadata=metadata or {},
        )

        await redis.hset(
            self.KNOWLEDGE_KEY,
            entry.id,
            json.dumps(entry.to_dict()),
        )

        logger.info(f"[Knowledge] Added entry: {title}")
        return entry

    async def search_knowledge(
        self,
        query: str,
        category: KnowledgeCategory | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[KnowledgeEntry]:
        """Search knowledge base."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hgetall(self.KNOWLEDGE_KEY)

        query_lower = query.lower()
        query_words = set(query_lower.split())
        results = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)

                # Filter by category
                if category and data["category"] != category.value:
                    continue

                # Filter by tags
                if tags:
                    if not any(t in data["tags"] for t in tags):
                        continue

                # Score by relevance
                score = 0
                title_lower = data["title"].lower()
                content_lower = data["content"].lower()

                # Title match
                for word in query_words:
                    if word in title_lower:
                        score += 3
                    if word in content_lower:
                        score += 1

                # Tag match
                for tag in data["tags"]:
                    if tag.lower() in query_lower:
                        score += 2

                if score > 0:
                    entry = self._parse_knowledge_entry(data)
                    results.append((score, entry))
            except Exception:
                continue

        # Sort by score
        results.sort(key=lambda x: x[0], reverse=True)

        return [entry for _, entry in results[:limit]]

    async def get_knowledge(self, entry_id: str) -> KnowledgeEntry | None:
        """Get knowledge entry and increment views."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.KNOWLEDGE_KEY, entry_id)

        if not raw:
            return None

        data = json.loads(raw)
        data["views"] = data.get("views", 0) + 1

        await redis.hset(self.KNOWLEDGE_KEY, entry_id, json.dumps(data))

        return self._parse_knowledge_entry(data)

    async def vote_helpful(
        self,
        entry_id: str,
        helpful: bool,
    ) -> KnowledgeEntry | None:
        """Vote on knowledge entry helpfulness."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.KNOWLEDGE_KEY, entry_id)

        if not raw:
            return None

        data = json.loads(raw)
        if helpful:
            data["helpful_votes"] = data.get("helpful_votes", 0) + 1
        else:
            data["helpful_votes"] = max(0, data.get("helpful_votes", 0) - 1)

        await redis.hset(self.KNOWLEDGE_KEY, entry_id, json.dumps(data))

        return self._parse_knowledge_entry(data)

    def _parse_knowledge_entry(self, data: dict[str, Any]) -> KnowledgeEntry:
        """Parse knowledge entry from dict."""
        return KnowledgeEntry(
            id=data["id"],
            title=data["title"],
            category=KnowledgeCategory(data["category"]),
            content=data["content"],
            tags=data["tags"],
            confidence=KnowledgeConfidence(data["confidence"]),
            source=data["source"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            created_by=data["created_by"],
            views=data.get("views", 0),
            helpful_votes=data.get("helpful_votes", 0),
            related_entries=data.get("related_entries", []),
            metadata=data.get("metadata", {}),
        )

    # ========================================================================
    # Incident Pattern Memory
    # ========================================================================

    async def initialize_patterns(self) -> int:
        """Initialize default incident patterns."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        created = 0

        for p in DEFAULT_PATTERNS:
            pattern_id = hashlib.md5(p["name"].encode()).hexdigest()[:8]

            existing = await redis.hget(self.PATTERNS_KEY, pattern_id)
            if existing:
                continue

            pattern = IncidentPattern(
                id=pattern_id,
                pattern_type=p["pattern_type"],
                name=p["name"],
                description=p["description"],
                indicators=p["indicators"],
                regex_patterns=p["regex_patterns"],
                severity_correlation=p["severity_correlation"],
                category_correlation=p["category_correlation"],
                resolution_hints=p["resolution_hints"],
                avg_resolution_minutes=p["avg_resolution_minutes"],
                occurrence_count=0,
                last_seen=now,
                confidence=0.8,
                tags=[],
            )

            await redis.hset(
                self.PATTERNS_KEY,
                pattern_id,
                json.dumps(pattern.to_dict()),
            )
            created += 1

        return created

    async def record_pattern(
        self,
        pattern_type: PatternType,
        name: str,
        description: str,
        indicators: list[str],
        regex_patterns: list[str] | None = None,
        resolution_hints: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> IncidentPattern:
        """Record a new incident pattern."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        pattern = IncidentPattern(
            id=str(uuid.uuid4())[:8],
            pattern_type=pattern_type,
            name=name,
            description=description,
            indicators=indicators,
            regex_patterns=regex_patterns or [],
            severity_correlation={},
            category_correlation={},
            resolution_hints=resolution_hints or [],
            avg_resolution_minutes=30,
            occurrence_count=1,
            last_seen=now,
            confidence=0.5,
            tags=tags or [],
        )

        await redis.hset(
            self.PATTERNS_KEY,
            pattern.id,
            json.dumps(pattern.to_dict()),
        )

        logger.info(f"[Knowledge] Recorded pattern: {name}")
        return pattern

    async def match_patterns(
        self,
        incident_title: str,
        incident_description: str,
        limit: int = 5,
    ) -> list[PatternMatch]:
        """Match incident against known patterns."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hgetall(self.PATTERNS_KEY)

        text = f"{incident_title} {incident_description}".lower()
        matches = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)
                pattern = self._parse_pattern(data)

                # Check indicators
                matched_indicators = []
                for indicator in pattern.indicators:
                    if indicator.lower() in text:
                        matched_indicators.append(indicator)

                # Check regex patterns
                for regex in pattern.regex_patterns:
                    try:
                        if re.search(regex, text, re.IGNORECASE):
                            matched_indicators.append(f"regex:{regex}")
                    except Exception:
                        pass

                if matched_indicators:
                    # Calculate match score
                    indicator_score = len(matched_indicators) / max(len(pattern.indicators), 1)
                    confidence_weight = pattern.confidence
                    score = indicator_score * confidence_weight

                    reasoning = f"Matched {len(matched_indicators)} indicators with {pattern.confidence:.0%} confidence"

                    matches.append(PatternMatch(
                        pattern=pattern,
                        match_score=score,
                        matched_indicators=matched_indicators,
                        reasoning=reasoning,
                    ))
            except Exception:
                continue

        matches.sort(key=lambda m: m.match_score, reverse=True)
        return matches[:limit]

    async def update_pattern_stats(
        self,
        pattern_id: str,
        resolution_minutes: float,
        severity: str,
        category: str,
    ) -> IncidentPattern | None:
        """Update pattern statistics after incident resolution."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        raw = await redis.hget(self.PATTERNS_KEY, pattern_id)
        if not raw:
            return None

        data = json.loads(raw)

        # Update occurrence count
        data["occurrence_count"] = data.get("occurrence_count", 0) + 1

        # Update average resolution time
        old_avg = data.get("avg_resolution_minutes", 30)
        old_count = data["occurrence_count"] - 1
        new_avg = (old_avg * old_count + resolution_minutes) / data["occurrence_count"]
        data["avg_resolution_minutes"] = new_avg

        # Update severity correlation
        sev_corr = data.get("severity_correlation", {})
        sev_corr[severity] = sev_corr.get(severity, 0) + 0.1
        # Normalize
        total = sum(sev_corr.values())
        data["severity_correlation"] = {k: v / total for k, v in sev_corr.items()}

        # Update category correlation
        cat_corr = data.get("category_correlation", {})
        cat_corr[category] = cat_corr.get(category, 0) + 0.1
        total = sum(cat_corr.values())
        data["category_correlation"] = {k: v / total for k, v in cat_corr.items()}

        # Update confidence based on occurrences
        data["confidence"] = min(0.95, 0.5 + (data["occurrence_count"] * 0.05))

        data["last_seen"] = now.isoformat()

        await redis.hset(self.PATTERNS_KEY, pattern_id, json.dumps(data))

        return self._parse_pattern(data)

    def _parse_pattern(self, data: dict[str, Any]) -> IncidentPattern:
        """Parse pattern from dict."""
        return IncidentPattern(
            id=data["id"],
            pattern_type=PatternType(data["pattern_type"]),
            name=data["name"],
            description=data["description"],
            indicators=data["indicators"],
            regex_patterns=data.get("regex_patterns", []),
            severity_correlation=data.get("severity_correlation", {}),
            category_correlation=data.get("category_correlation", {}),
            resolution_hints=data.get("resolution_hints", []),
            avg_resolution_minutes=data.get("avg_resolution_minutes", 30),
            occurrence_count=data.get("occurrence_count", 0),
            last_seen=datetime.fromisoformat(data["last_seen"]),
            confidence=data.get("confidence", 0.5),
            tags=data.get("tags", []),
        )

    # ========================================================================
    # What-If Simulation
    # ========================================================================

    async def create_simulation(
        self,
        name: str,
        action_type: str,
        action_parameters: dict[str, Any],
        pre_conditions: dict[str, Any],
        created_by: str,
    ) -> SimulationScenario:
        """Create a what-if simulation scenario."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        scenario = SimulationScenario(
            id=str(uuid.uuid4())[:8],
            name=name,
            action_type=action_type,
            action_parameters=action_parameters,
            pre_conditions=pre_conditions,
            created_by=created_by,
            created_at=now,
        )

        await redis.hset(
            self.SIMULATIONS_KEY,
            scenario.id,
            json.dumps(scenario.to_dict()),
        )

        logger.info(f"[Simulation] Created scenario: {name}")
        return scenario

    async def run_simulation(
        self,
        scenario_id: str,
    ) -> SimulationResult:
        """Run a what-if simulation."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get scenario
        raw = await redis.hget(self.SIMULATIONS_KEY, scenario_id)
        if not raw:
            raise ValueError("Scenario not found")

        scenario_data = json.loads(raw)
        action_type = scenario_data["action_type"]
        params = scenario_data["action_parameters"]
        pre_conditions = scenario_data["pre_conditions"]

        # Simulate the action
        outcome, confidence = self._simulate_action(action_type, params, pre_conditions)

        # Predict impacts
        impacts = self._predict_impacts(action_type, params)

        # Identify risk factors
        risks = self._identify_risks(action_type, params, pre_conditions)

        # Generate mitigation suggestions
        mitigations = self._generate_mitigations(risks)

        # Estimate timing
        duration = self._estimate_duration(action_type)
        rollback_time = self._estimate_rollback_time(action_type)

        # Identify side effects
        side_effects = self._identify_side_effects(action_type, params)

        # Identify affected dependencies
        dependencies = self._identify_dependencies(action_type, params)

        result = SimulationResult(
            id=str(uuid.uuid4())[:8],
            scenario_id=scenario_id,
            status=SimulationStatus.COMPLETED,
            outcome=outcome,
            confidence=confidence,
            predicted_impacts=impacts,
            risk_factors=risks,
            mitigation_suggestions=mitigations,
            estimated_duration_minutes=duration,
            estimated_rollback_time_minutes=rollback_time,
            side_effects=side_effects,
            dependencies_affected=dependencies,
            executed_at=now,
            completed_at=datetime.now(UTC),
        )

        # Store result
        await redis.hset(
            self.RESULTS_KEY,
            result.id,
            json.dumps(result.to_dict()),
        )

        logger.info(f"[Simulation] Completed simulation {scenario_id}: {outcome.value}")
        return result

    def _simulate_action(
        self,
        action_type: str,
        params: dict[str, Any],
        pre_conditions: dict[str, Any],
    ) -> tuple[SimulationOutcome, float]:
        """Simulate an action and predict outcome."""
        # Base success probability by action type
        base_success = {
            "deploy": 0.85,
            "rollback": 0.95,
            "restart": 0.90,
            "scale": 0.92,
            "config_change": 0.88,
            "database_migration": 0.75,
            "cache_clear": 0.95,
            "failover": 0.80,
        }.get(action_type, 0.75)

        # Adjust based on pre-conditions
        if pre_conditions.get("error_rate", 0) > 10:
            base_success *= 0.9

        if pre_conditions.get("recent_deploy", False):
            base_success *= 0.95

        if pre_conditions.get("peak_hours", False):
            base_success *= 0.9

        # Determine outcome
        if base_success >= 0.9:
            return SimulationOutcome.SUCCESS, base_success
        elif base_success >= 0.7:
            return SimulationOutcome.PARTIAL_SUCCESS, base_success
        elif base_success >= 0.5:
            return SimulationOutcome.UNKNOWN, base_success
        else:
            return SimulationOutcome.FAILURE, base_success

    def _predict_impacts(
        self,
        action_type: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Predict impacts of action."""
        impacts = []

        if action_type == "deploy":
            impacts.append({
                "type": "availability",
                "description": "Brief service interruption during rollout",
                "severity": "low",
                "duration_seconds": 30,
            })
        elif action_type == "database_migration":
            impacts.append({
                "type": "performance",
                "description": "Temporary performance degradation",
                "severity": "medium",
                "duration_seconds": 300,
            })
            impacts.append({
                "type": "availability",
                "description": "Possible write lock during migration",
                "severity": "medium",
                "duration_seconds": 60,
            })
        elif action_type == "restart":
            impacts.append({
                "type": "availability",
                "description": "Service unavailable during restart",
                "severity": "medium",
                "duration_seconds": 30,
            })
        elif action_type == "failover":
            impacts.append({
                "type": "data",
                "description": "Possible brief data inconsistency",
                "severity": "low",
                "duration_seconds": 5,
            })

        return impacts

    def _identify_risks(
        self,
        action_type: str,
        params: dict[str, Any],
        pre_conditions: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Identify risk factors."""
        risks = []

        if action_type == "database_migration":
            risks.append({
                "factor": "data_loss",
                "probability": 0.05,
                "impact": "high",
                "mitigation": "Ensure backup exists",
            })

        if pre_conditions.get("peak_hours", False):
            risks.append({
                "factor": "user_impact",
                "probability": 0.8,
                "impact": "medium",
                "mitigation": "Consider off-peak execution",
            })

        if pre_conditions.get("error_rate", 0) > 5:
            risks.append({
                "factor": "cascading_failure",
                "probability": 0.3,
                "impact": "high",
                "mitigation": "Stabilize system first",
            })

        return risks

    def _generate_mitigations(
        self,
        risks: list[dict[str, Any]],
    ) -> list[str]:
        """Generate mitigation suggestions."""
        mitigations = []

        for risk in risks:
            if risk.get("mitigation"):
                mitigations.append(risk["mitigation"])

        mitigations.append("Have rollback plan ready")
        mitigations.append("Monitor closely after execution")

        return list(set(mitigations))

    def _estimate_duration(self, action_type: str) -> int:
        """Estimate action duration in minutes."""
        durations = {
            "deploy": 5,
            "rollback": 3,
            "restart": 2,
            "scale": 3,
            "config_change": 1,
            "database_migration": 15,
            "cache_clear": 1,
            "failover": 5,
        }
        return durations.get(action_type, 5)

    def _estimate_rollback_time(self, action_type: str) -> int:
        """Estimate rollback time in minutes."""
        times = {
            "deploy": 3,
            "rollback": 0,  # Already rolled back
            "restart": 0,
            "scale": 2,
            "config_change": 1,
            "database_migration": 30,
            "cache_clear": 0,
            "failover": 10,
        }
        return times.get(action_type, 5)

    def _identify_side_effects(
        self,
        action_type: str,
        params: dict[str, Any],
    ) -> list[str]:
        """Identify potential side effects."""
        effects = []

        if action_type == "restart":
            effects.append("Active connections will be dropped")
            effects.append("In-flight requests will fail")

        if action_type == "cache_clear":
            effects.append("Temporary increase in database load")
            effects.append("Higher latency until cache warms up")

        if action_type == "scale":
            effects.append("Resource usage will change")

        return effects

    def _identify_dependencies(
        self,
        action_type: str,
        params: dict[str, Any],
    ) -> list[str]:
        """Identify affected dependencies."""
        target = params.get("target", "unknown")
        dependencies = []

        if action_type in ["restart", "deploy"]:
            dependencies.append(f"Clients of {target}")

        if action_type == "database_migration":
            dependencies.append("All services using database")

        return dependencies

    # ========================================================================
    # Policy Conflict Detection
    # ========================================================================

    async def detect_policy_conflicts(
        self,
        policies: list[dict[str, Any]] | None = None,
    ) -> list[PolicyConflict]:
        """Detect conflicts between policies."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get policies if not provided
        if policies is None:
            try:
                from app.services.policy_engine import policy_engine
                active_policies = await policy_engine.list_policies(enabled_only=True)
                policies = [p.to_dict() for p in active_policies]
            except Exception:
                policies = []

        conflicts = []

        # Check each pair of policies
        for i, policy_a in enumerate(policies):
            for j, policy_b in enumerate(policies):
                if i >= j:
                    continue

                conflict = self._check_policy_pair(policy_a, policy_b, now)
                if conflict:
                    conflicts.append(conflict)

        # Store conflicts
        for conflict in conflicts:
            await redis.hset(
                self.CONFLICTS_KEY,
                conflict.id,
                json.dumps(conflict.to_dict()),
            )

        logger.info(f"[Knowledge] Detected {len(conflicts)} policy conflicts")
        return conflicts

    def _check_policy_pair(
        self,
        policy_a: dict[str, Any],
        policy_b: dict[str, Any],
        now: datetime,
    ) -> PolicyConflict | None:
        """Check for conflict between two policies."""
        # Check for contradicting actions
        action_a = policy_a.get("action", "")
        action_b = policy_b.get("action", "")

        rules_a = policy_a.get("rules", {})
        rules_b = policy_b.get("rules", {})

        # Check for direct contradiction
        if action_a == "allow" and action_b == "deny":
            # Check if they apply to similar scope
            scope_overlap = self._check_scope_overlap(rules_a, rules_b)
            if scope_overlap:
                return PolicyConflict(
                    id=str(uuid.uuid4())[:8],
                    policy_a_id=policy_a.get("id", ""),
                    policy_a_name=policy_a.get("name", ""),
                    policy_b_id=policy_b.get("id", ""),
                    policy_b_name=policy_b.get("name", ""),
                    conflict_type="contradicting_actions",
                    severity=ConflictSeverity.HIGH,
                    description=f"Policy '{policy_a.get('name')}' allows what '{policy_b.get('name')}' denies",
                    resolution_options=[
                        "Adjust policy priorities",
                        "Narrow scope of one policy",
                        "Disable one of the policies",
                    ],
                    detected_at=now,
                )

        # Check for overlapping conditions
        if self._check_overlapping_conditions(rules_a, rules_b):
            return PolicyConflict(
                id=str(uuid.uuid4())[:8],
                policy_a_id=policy_a.get("id", ""),
                policy_a_name=policy_a.get("name", ""),
                policy_b_id=policy_b.get("id", ""),
                policy_b_name=policy_b.get("name", ""),
                conflict_type="overlapping_conditions",
                severity=ConflictSeverity.MEDIUM,
                description=f"Policies '{policy_a.get('name')}' and '{policy_b.get('name')}' have overlapping conditions",
                resolution_options=[
                    "Make conditions mutually exclusive",
                    "Define clear priority order",
                ],
                detected_at=now,
            )

        return None

    def _check_scope_overlap(
        self,
        rules_a: dict[str, Any],
        rules_b: dict[str, Any],
    ) -> bool:
        """Check if rule scopes overlap."""
        # Simple overlap check
        for key in rules_a:
            if key in rules_b:
                return True
        return False

    def _check_overlapping_conditions(
        self,
        rules_a: dict[str, Any],
        rules_b: dict[str, Any],
    ) -> bool:
        """Check for overlapping conditions."""
        common_keys = set(rules_a.keys()) & set(rules_b.keys())
        return len(common_keys) > 1

    async def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
    ) -> PolicyConflict | None:
        """Mark a conflict as resolved."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.CONFLICTS_KEY, conflict_id)

        if not raw:
            return None

        data = json.loads(raw)
        data["resolved"] = True
        data["resolution"] = resolution

        await redis.hset(self.CONFLICTS_KEY, conflict_id, json.dumps(data))

        return PolicyConflict(
            id=data["id"],
            policy_a_id=data["policy_a_id"],
            policy_a_name=data["policy_a_name"],
            policy_b_id=data["policy_b_id"],
            policy_b_name=data["policy_b_name"],
            conflict_type=data["conflict_type"],
            severity=ConflictSeverity(data["severity"]),
            description=data["description"],
            resolution_options=data["resolution_options"],
            detected_at=datetime.fromisoformat(data["detected_at"]),
            resolved=True,
            resolution=resolution,
        )

    async def list_conflicts(
        self,
        include_resolved: bool = False,
    ) -> list[PolicyConflict]:
        """List policy conflicts."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hgetall(self.CONFLICTS_KEY)
        conflicts = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)

                if not include_resolved and data.get("resolved", False):
                    continue

                conflicts.append(PolicyConflict(
                    id=data["id"],
                    policy_a_id=data["policy_a_id"],
                    policy_a_name=data["policy_a_name"],
                    policy_b_id=data["policy_b_id"],
                    policy_b_name=data["policy_b_name"],
                    conflict_type=data["conflict_type"],
                    severity=ConflictSeverity(data["severity"]),
                    description=data["description"],
                    resolution_options=data["resolution_options"],
                    detected_at=datetime.fromisoformat(data["detected_at"]),
                    resolved=data.get("resolved", False),
                    resolution=data.get("resolution"),
                ))
            except Exception:
                continue

        return conflicts

    # ========================================================================
    # Recommendation Quality Scoring
    # ========================================================================

    async def score_recommendation(
        self,
        recommendation_id: str,
        recommendation_type: str,
        actual_outcome: dict[str, Any],
        predicted_outcome: dict[str, Any],
    ) -> RecommendationQuality:
        """Score recommendation quality based on outcome."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Calculate accuracy score
        accuracy = self._calculate_accuracy(actual_outcome, predicted_outcome)

        # Get existing quality data for context
        existing = await redis.hget(self.QUALITY_KEY, recommendation_id)
        feedback_count = 0
        positive = 0
        negative = 0

        if existing:
            data = json.loads(existing)
            feedback_count = data.get("feedback_count", 0)
            positive = data.get("positive_feedback", 0)
            negative = data.get("negative_feedback", 0)

        # Relevance (based on whether recommendation was used)
        relevance = 1.0 if actual_outcome.get("recommendation_used", False) else 0.5

        # Timeliness (based on response time)
        response_minutes = actual_outcome.get("response_time_minutes", 30)
        timeliness = max(0, 1 - (response_minutes / 60))

        # Completeness (based on missing steps)
        missing_steps = actual_outcome.get("missing_steps", 0)
        completeness = max(0, 1 - (missing_steps * 0.2))

        # Overall score
        overall = (accuracy * 0.4 + relevance * 0.3 + timeliness * 0.15 + completeness * 0.15)

        # Generate improvement suggestions
        suggestions = []
        if accuracy < 0.7:
            suggestions.append("Improve prediction accuracy with more historical data")
        if relevance < 0.7:
            suggestions.append("Make recommendations more actionable")
        if timeliness < 0.7:
            suggestions.append("Optimize recommendation generation time")
        if completeness < 0.7:
            suggestions.append("Include more comprehensive steps")

        quality = RecommendationQuality(
            recommendation_id=recommendation_id,
            recommendation_type=recommendation_type,
            accuracy_score=accuracy,
            relevance_score=relevance,
            timeliness_score=timeliness,
            completeness_score=completeness,
            overall_score=overall,
            feedback_count=feedback_count,
            positive_feedback=positive,
            negative_feedback=negative,
            improvement_suggestions=suggestions,
            scored_at=now,
        )

        await redis.hset(
            self.QUALITY_KEY,
            recommendation_id,
            json.dumps(quality.to_dict()),
        )

        logger.info(f"[Knowledge] Scored recommendation {recommendation_id}: {overall:.2f}")
        return quality

    def _calculate_accuracy(
        self,
        actual: dict[str, Any],
        predicted: dict[str, Any],
    ) -> float:
        """Calculate prediction accuracy."""
        matches = 0
        total = 0

        # Compare outcomes
        if "outcome" in actual and "outcome" in predicted:
            total += 1
            if actual["outcome"] == predicted["outcome"]:
                matches += 1

        # Compare duration
        if "duration_minutes" in actual and "estimated_duration" in predicted:
            total += 1
            actual_dur = actual["duration_minutes"]
            pred_dur = predicted["estimated_duration"]
            if abs(actual_dur - pred_dur) / max(pred_dur, 1) < 0.3:
                matches += 1

        # Compare severity
        if "severity" in actual and "predicted_severity" in predicted:
            total += 1
            if actual["severity"] == predicted["predicted_severity"]:
                matches += 1

        return matches / max(total, 1)

    async def submit_feedback(
        self,
        recommendation_id: str,
        helpful: bool,
        feedback_text: str | None = None,
    ) -> RecommendationQuality | None:
        """Submit feedback on a recommendation."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.QUALITY_KEY, recommendation_id)

        if not raw:
            return None

        data = json.loads(raw)
        data["feedback_count"] = data.get("feedback_count", 0) + 1

        if helpful:
            data["positive_feedback"] = data.get("positive_feedback", 0) + 1
        else:
            data["negative_feedback"] = data.get("negative_feedback", 0) + 1

        await redis.hset(self.QUALITY_KEY, recommendation_id, json.dumps(data))

        return RecommendationQuality(
            recommendation_id=data["recommendation_id"],
            recommendation_type=data["recommendation_type"],
            accuracy_score=data["accuracy_score"],
            relevance_score=data["relevance_score"],
            timeliness_score=data["timeliness_score"],
            completeness_score=data["completeness_score"],
            overall_score=data["overall_score"],
            feedback_count=data["feedback_count"],
            positive_feedback=data["positive_feedback"],
            negative_feedback=data["negative_feedback"],
            improvement_suggestions=data["improvement_suggestions"],
            scored_at=datetime.fromisoformat(data["scored_at"]),
        )

    # ========================================================================
    # Training Mode
    # ========================================================================

    async def initialize_training(self) -> int:
        """Initialize default training scenarios."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        created = 0

        for ts in DEFAULT_TRAINING_SCENARIOS:
            scenario_id = hashlib.md5(ts["name"].encode()).hexdigest()[:8]

            existing = await redis.hget(self.SCENARIOS_KEY, scenario_id)
            if existing:
                continue

            scenario = TrainingScenario(
                id=scenario_id,
                name=ts["name"],
                scenario_type=ts["scenario_type"],
                difficulty=ts["difficulty"],
                description=ts["description"],
                objectives=ts["objectives"],
                initial_state=ts["initial_state"],
                expected_actions=ts["expected_actions"],
                hints=ts["hints"],
                time_limit_minutes=ts["time_limit_minutes"],
                passing_score=ts["passing_score"],
                created_at=now,
            )

            await redis.hset(
                self.SCENARIOS_KEY,
                scenario_id,
                json.dumps(scenario.to_dict()),
            )
            created += 1

        return created

    async def list_training_scenarios(
        self,
        scenario_type: TrainingScenarioType | None = None,
        difficulty: TrainingDifficulty | None = None,
    ) -> list[TrainingScenario]:
        """List training scenarios."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hgetall(self.SCENARIOS_KEY)
        scenarios = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)

                if scenario_type and data["scenario_type"] != scenario_type.value:
                    continue

                if difficulty and data["difficulty"] != difficulty.value:
                    continue

                scenarios.append(TrainingScenario(
                    id=data["id"],
                    name=data["name"],
                    scenario_type=TrainingScenarioType(data["scenario_type"]),
                    difficulty=TrainingDifficulty(data["difficulty"]),
                    description=data["description"],
                    objectives=data["objectives"],
                    initial_state=data["initial_state"],
                    expected_actions=data["expected_actions"],
                    hints=data["hints"],
                    time_limit_minutes=data["time_limit_minutes"],
                    passing_score=data["passing_score"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                ))
            except Exception:
                continue

        return scenarios

    async def start_training_session(
        self,
        scenario_id: str,
        operator_id: str,
    ) -> TrainingSession:
        """Start a training session."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Verify scenario exists
        scenario_raw = await redis.hget(self.SCENARIOS_KEY, scenario_id)
        if not scenario_raw:
            raise ValueError("Scenario not found")

        session = TrainingSession(
            id=str(uuid.uuid4())[:8],
            scenario_id=scenario_id,
            operator_id=operator_id,
            started_at=now,
            completed_at=None,
            actions_taken=[],
            hints_used=0,
            score=None,
            passed=None,
            feedback="",
            time_spent_minutes=0,
        )

        await redis.hset(
            self.SESSIONS_KEY,
            session.id,
            json.dumps(session.to_dict()),
        )

        logger.info(f"[Training] Started session {session.id} for operator {operator_id}")
        return session

    async def record_training_action(
        self,
        session_id: str,
        action: dict[str, Any],
    ) -> TrainingSession:
        """Record an action in training session."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        raw = await redis.hget(self.SESSIONS_KEY, session_id)
        if not raw:
            raise ValueError("Session not found")

        data = json.loads(raw)
        data["actions_taken"].append({
            **action,
            "timestamp": now.isoformat(),
        })

        # Update time spent
        started = datetime.fromisoformat(data["started_at"])
        data["time_spent_minutes"] = (now - started).total_seconds() / 60

        await redis.hset(self.SESSIONS_KEY, session_id, json.dumps(data))

        return TrainingSession(
            id=data["id"],
            scenario_id=data["scenario_id"],
            operator_id=data["operator_id"],
            started_at=started,
            completed_at=None,
            actions_taken=data["actions_taken"],
            hints_used=data["hints_used"],
            score=None,
            passed=None,
            feedback="",
            time_spent_minutes=data["time_spent_minutes"],
        )

    async def use_hint(self, session_id: str) -> dict[str, Any]:
        """Use a hint in training session."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        raw = await redis.hget(self.SESSIONS_KEY, session_id)
        if not raw:
            raise ValueError("Session not found")

        data = json.loads(raw)
        scenario_raw = await redis.hget(self.SCENARIOS_KEY, data["scenario_id"])
        scenario = json.loads(scenario_raw)

        hints_used = data["hints_used"]
        available_hints = scenario["hints"]

        if hints_used >= len(available_hints):
            return {"hint": None, "message": "No more hints available"}

        hint = available_hints[hints_used]
        data["hints_used"] = hints_used + 1

        await redis.hset(self.SESSIONS_KEY, session_id, json.dumps(data))

        return {"hint": hint, "hints_remaining": len(available_hints) - hints_used - 1}

    async def complete_training_session(
        self,
        session_id: str,
    ) -> TrainingSession:
        """Complete and score a training session."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        raw = await redis.hget(self.SESSIONS_KEY, session_id)
        if not raw:
            raise ValueError("Session not found")

        data = json.loads(raw)
        scenario_raw = await redis.hget(self.SCENARIOS_KEY, data["scenario_id"])
        scenario = json.loads(scenario_raw)

        # Calculate score
        score, feedback = self._score_training_session(
            data["actions_taken"],
            scenario["expected_actions"],
            data["hints_used"],
        )

        passed = score >= scenario["passing_score"]

        # Update session
        data["completed_at"] = now.isoformat()
        data["score"] = score
        data["passed"] = passed
        data["feedback"] = feedback

        started = datetime.fromisoformat(data["started_at"])
        data["time_spent_minutes"] = (now - started).total_seconds() / 60

        await redis.hset(self.SESSIONS_KEY, session_id, json.dumps(data))

        # Update operator profile
        await self._update_operator_profile(
            data["operator_id"],
            scenario,
            score,
            passed,
            data["time_spent_minutes"],
        )

        logger.info(f"[Training] Completed session {session_id}: score={score:.2f}, passed={passed}")

        return TrainingSession(
            id=data["id"],
            scenario_id=data["scenario_id"],
            operator_id=data["operator_id"],
            started_at=started,
            completed_at=now,
            actions_taken=data["actions_taken"],
            hints_used=data["hints_used"],
            score=score,
            passed=passed,
            feedback=feedback,
            time_spent_minutes=data["time_spent_minutes"],
        )

    def _score_training_session(
        self,
        actions_taken: list[dict[str, Any]],
        expected_actions: list[dict[str, Any]],
        hints_used: int,
    ) -> tuple[float, str]:
        """Score a training session."""
        total_points = sum(e.get("points", 0) for e in expected_actions)
        earned_points = 0
        feedback_parts = []

        actions_by_type = {}
        for action in actions_taken:
            action_type = action.get("action")
            if action_type:
                actions_by_type[action_type] = action

        for expected in expected_actions:
            action_type = expected.get("action")
            points = expected.get("points", 0)

            if action_type in actions_by_type:
                earned_points += points
                feedback_parts.append(f"+ {action_type}: {points} points")
            else:
                feedback_parts.append(f"- {action_type}: missed ({points} points)")

        # Penalty for hints
        hint_penalty = hints_used * 0.05
        score = max(0, (earned_points / max(total_points, 1)) - hint_penalty)

        feedback = "\n".join(feedback_parts)
        if hints_used > 0:
            feedback += f"\n\nHint penalty: -{hint_penalty:.0%}"

        return score, feedback

    async def _update_operator_profile(
        self,
        operator_id: str,
        scenario: dict[str, Any],
        score: float,
        passed: bool,
        time_minutes: float,
    ) -> None:
        """Update operator skill profile."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        raw = await redis.hget(self.PROFILES_KEY, operator_id)

        if raw:
            profile = json.loads(raw)
        else:
            profile = {
                "operator_id": operator_id,
                "scenarios_completed": 0,
                "scenarios_passed": 0,
                "total_training_minutes": 0,
                "skill_scores": {},
                "certifications": [],
                "last_training": None,
                "strengths": [],
                "areas_for_improvement": [],
            }

        profile["scenarios_completed"] += 1
        if passed:
            profile["scenarios_passed"] += 1
        profile["total_training_minutes"] += time_minutes
        profile["last_training"] = now.isoformat()

        # Update skill score for this scenario type
        scenario_type = scenario["scenario_type"]
        old_score = profile["skill_scores"].get(scenario_type, 0.5)
        profile["skill_scores"][scenario_type] = (old_score + score) / 2

        # Update strengths and areas for improvement
        strengths = []
        improvements = []
        for skill, s in profile["skill_scores"].items():
            if s >= 0.8:
                strengths.append(skill)
            elif s < 0.6:
                improvements.append(skill)

        profile["strengths"] = strengths
        profile["areas_for_improvement"] = improvements

        await redis.hset(self.PROFILES_KEY, operator_id, json.dumps(profile))

    async def get_operator_profile(
        self,
        operator_id: str,
    ) -> OperatorSkillProfile | None:
        """Get operator skill profile."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.PROFILES_KEY, operator_id)

        if not raw:
            return None

        data = json.loads(raw)
        return OperatorSkillProfile(
            operator_id=data["operator_id"],
            scenarios_completed=data["scenarios_completed"],
            scenarios_passed=data["scenarios_passed"],
            total_training_minutes=data["total_training_minutes"],
            skill_scores=data["skill_scores"],
            certifications=data.get("certifications", []),
            last_training=datetime.fromisoformat(data["last_training"]) if data.get("last_training") else None,
            strengths=data.get("strengths", []),
            areas_for_improvement=data.get("areas_for_improvement", []),
        )

    async def get_training_session(self, session_id: str) -> TrainingSession | None:
        """Get training session."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        raw = await redis.hget(self.SESSIONS_KEY, session_id)

        if not raw:
            return None

        data = json.loads(raw)
        return TrainingSession(
            id=data["id"],
            scenario_id=data["scenario_id"],
            operator_id=data["operator_id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            actions_taken=data["actions_taken"],
            hints_used=data["hints_used"],
            score=data.get("score"),
            passed=data.get("passed"),
            feedback=data.get("feedback", ""),
            time_spent_minutes=data.get("time_spent_minutes", 0),
        )


# Singleton
knowledge_simulation = KnowledgeSimulationService()
