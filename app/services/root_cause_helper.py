"""Root Cause Helper Service.

Automated root cause analysis for incidents.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any
import uuid
import re

UTC = timezone.utc

logger = logging.getLogger(__name__)


class SymptomCategory(str, Enum):
    """Categories of symptoms."""

    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    AVAILABILITY = "availability"
    RESOURCE = "resource"
    DATA = "data"
    SECURITY = "security"
    INTEGRATION = "integration"


class RootCauseCategory(str, Enum):
    """Categories of root causes."""

    DATABASE = "database"
    CACHE = "cache"
    NETWORK = "network"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CODE_BUG = "code_bug"
    CONFIGURATION = "configuration"
    EXTERNAL_SERVICE = "external_service"
    SECURITY_INCIDENT = "security_incident"
    DEPLOYMENT = "deployment"
    DATA_CORRUPTION = "data_corruption"


class Confidence(str, Enum):
    """Confidence level in analysis."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Symptom:
    """Observed symptom."""

    id: str
    category: SymptomCategory
    description: str
    severity: str
    first_seen: datetime
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "description": self.description,
            "severity": self.severity,
            "first_seen": self.first_seen.isoformat(),
            "metrics": self.metrics,
        }


@dataclass
class Hypothesis:
    """Root cause hypothesis."""

    id: str
    category: RootCauseCategory
    description: str
    confidence: Confidence
    evidence: list[str]
    investigation_steps: list[str]
    remediation_steps: list[str]
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "description": self.description,
            "confidence": self.confidence.value,
            "evidence": self.evidence,
            "investigation_steps": self.investigation_steps,
            "remediation_steps": self.remediation_steps,
            "score": round(self.score, 2),
        }


@dataclass
class RootCauseAnalysis:
    """Root cause analysis result."""

    id: str
    analyzed_at: datetime
    symptoms: list[Symptom]
    hypotheses: list[Hypothesis]
    primary_hypothesis: Hypothesis | None
    summary: str
    recommended_actions: list[str]
    related_incidents: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "analyzed_at": self.analyzed_at.isoformat(),
            "symptoms": [s.to_dict() for s in self.symptoms],
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "primary_hypothesis": self.primary_hypothesis.to_dict() if self.primary_hypothesis else None,
            "summary": self.summary,
            "recommended_actions": self.recommended_actions,
            "related_incidents": self.related_incidents,
        }


# Pattern definitions for symptom-to-cause mapping
SYMPTOM_CAUSE_PATTERNS = [
    {
        "symptoms": [SymptomCategory.LATENCY, SymptomCategory.ERROR_RATE],
        "keywords": ["timeout", "connection", "slow"],
        "cause": RootCauseCategory.DATABASE,
        "description": "Database performance degradation",
        "evidence": ["Query timeouts", "Connection pool exhaustion", "Slow query logs"],
        "investigation": ["Check slow query log", "Monitor connection pool", "Analyze query plans"],
        "remediation": ["Optimize slow queries", "Increase connection pool", "Add indexes"],
    },
    {
        "symptoms": [SymptomCategory.LATENCY],
        "keywords": ["cache", "miss", "redis"],
        "cause": RootCauseCategory.CACHE,
        "description": "Cache miss rate spike",
        "evidence": ["High cache miss rate", "Increased database load"],
        "investigation": ["Check cache hit ratio", "Verify cache keys", "Monitor evictions"],
        "remediation": ["Warm up cache", "Increase cache size", "Review TTL settings"],
    },
    {
        "symptoms": [SymptomCategory.AVAILABILITY, SymptomCategory.ERROR_RATE],
        "keywords": ["connection", "refused", "network"],
        "cause": RootCauseCategory.NETWORK,
        "description": "Network connectivity issues",
        "evidence": ["Connection refused errors", "DNS resolution failures"],
        "investigation": ["Check network connectivity", "Verify DNS resolution", "Check firewall rules"],
        "remediation": ["Restart network services", "Update DNS entries", "Fix firewall rules"],
    },
    {
        "symptoms": [SymptomCategory.RESOURCE],
        "keywords": ["memory", "cpu", "disk", "oom"],
        "cause": RootCauseCategory.RESOURCE_EXHAUSTION,
        "description": "Resource exhaustion (CPU/Memory/Disk)",
        "evidence": ["High resource utilization", "OOM kills", "Throttling"],
        "investigation": ["Check resource metrics", "Identify heavy consumers", "Review recent changes"],
        "remediation": ["Scale resources", "Optimize memory usage", "Clean up disk space"],
    },
    {
        "symptoms": [SymptomCategory.ERROR_RATE],
        "keywords": ["exception", "error", "traceback", "500"],
        "cause": RootCauseCategory.CODE_BUG,
        "description": "Application code bug",
        "evidence": ["Unhandled exceptions", "Error spikes after deployment"],
        "investigation": ["Review error logs", "Check recent deployments", "Analyze stack traces"],
        "remediation": ["Rollback deployment", "Apply hotfix", "Add error handling"],
    },
    {
        "symptoms": [SymptomCategory.INTEGRATION],
        "keywords": ["api", "external", "third-party", "timeout"],
        "cause": RootCauseCategory.EXTERNAL_SERVICE,
        "description": "External service degradation",
        "evidence": ["API timeouts", "Rate limiting", "Service unavailable responses"],
        "investigation": ["Check external service status", "Review API logs", "Monitor rate limits"],
        "remediation": ["Enable circuit breaker", "Switch to fallback", "Contact provider"],
    },
    {
        "symptoms": [SymptomCategory.ERROR_RATE, SymptomCategory.AVAILABILITY],
        "keywords": ["deploy", "release", "rollout"],
        "cause": RootCauseCategory.DEPLOYMENT,
        "description": "Recent deployment issue",
        "evidence": ["Errors started after deployment", "Version mismatch"],
        "investigation": ["Check deployment logs", "Compare versions", "Review change log"],
        "remediation": ["Rollback to previous version", "Fix and redeploy", "Enable canary"],
    },
    {
        "symptoms": [SymptomCategory.DATA],
        "keywords": ["corrupt", "invalid", "inconsistent"],
        "cause": RootCauseCategory.DATA_CORRUPTION,
        "description": "Data corruption or inconsistency",
        "evidence": ["Invalid data format", "Constraint violations", "Data mismatch"],
        "investigation": ["Run data validation", "Check data pipelines", "Review data changes"],
        "remediation": ["Restore from backup", "Fix data pipeline", "Run data repair"],
    },
    {
        "symptoms": [SymptomCategory.SECURITY],
        "keywords": ["auth", "unauthorized", "access", "token"],
        "cause": RootCauseCategory.SECURITY_INCIDENT,
        "description": "Security-related issue",
        "evidence": ["Auth failures", "Unusual access patterns", "Token issues"],
        "investigation": ["Review auth logs", "Check access patterns", "Verify tokens"],
        "remediation": ["Rotate credentials", "Block suspicious IPs", "Review access policies"],
    },
]


class RootCauseHelperService:
    """Service for automated root cause analysis.

    Features:
    - Symptom collection
    - Pattern matching
    - Hypothesis generation
    - Investigation guidance
    """

    ANALYSES_KEY = "rootcause:analyses"
    SYMPTOMS_KEY = "rootcause:symptoms"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    async def record_symptom(
        self,
        category: SymptomCategory,
        description: str,
        severity: str = "medium",
        metrics: dict[str, Any] | None = None,
    ) -> Symptom:
        """Record an observed symptom.

        Args:
            category: Symptom category
            description: What was observed
            severity: low/medium/high/critical
            metrics: Associated metrics

        Returns:
            Recorded symptom
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        symptom = Symptom(
            id=str(uuid.uuid4())[:8],
            category=category,
            description=description,
            severity=severity,
            first_seen=now,
            metrics=metrics or {},
        )

        await redis.zadd(
            self.SYMPTOMS_KEY,
            {json.dumps(symptom.to_dict()): now.timestamp()},
        )

        # Keep last 1000 symptoms
        await redis.zremrangebyrank(self.SYMPTOMS_KEY, 0, -1001)

        logger.info(f"[RootCause] Recorded symptom: {description}")
        return symptom

    async def get_recent_symptoms(
        self,
        hours: int = 24,
        category: SymptomCategory | None = None,
    ) -> list[Symptom]:
        """Get recent symptoms.

        Args:
            hours: Look back window
            category: Filter by category

        Returns:
            List of symptoms
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=hours)

        raw = await redis.zrangebyscore(
            self.SYMPTOMS_KEY,
            cutoff.timestamp(),
            now.timestamp(),
        )

        symptoms = []
        for item in raw:
            try:
                data = json.loads(item)

                if category and data["category"] != category.value:
                    continue

                symptoms.append(Symptom(
                    id=data["id"],
                    category=SymptomCategory(data["category"]),
                    description=data["description"],
                    severity=data["severity"],
                    first_seen=datetime.fromisoformat(data["first_seen"]),
                    metrics=data.get("metrics", {}),
                ))
            except Exception:
                continue

        return symptoms

    def _generate_hypotheses(
        self,
        symptoms: list[Symptom],
    ) -> list[Hypothesis]:
        """Generate root cause hypotheses based on symptoms.

        Args:
            symptoms: Observed symptoms

        Returns:
            List of hypotheses ranked by score
        """
        symptom_categories = {s.category for s in symptoms}
        all_descriptions = " ".join(s.description.lower() for s in symptoms)

        hypotheses = []

        for pattern in SYMPTOM_CAUSE_PATTERNS:
            # Check category match
            pattern_symptoms = set(pattern["symptoms"])
            category_overlap = len(symptom_categories & pattern_symptoms)

            if category_overlap == 0:
                continue

            # Check keyword match
            keywords = pattern["keywords"]
            keyword_matches = sum(1 for k in keywords if k in all_descriptions)

            # Calculate score
            category_score = category_overlap / len(pattern_symptoms)
            keyword_score = keyword_matches / len(keywords) if keywords else 0
            total_score = (category_score * 0.6) + (keyword_score * 0.4)

            if total_score < 0.2:
                continue

            # Determine confidence
            if total_score >= 0.7:
                confidence = Confidence.HIGH
            elif total_score >= 0.4:
                confidence = Confidence.MEDIUM
            else:
                confidence = Confidence.LOW

            hypothesis = Hypothesis(
                id=str(uuid.uuid4())[:8],
                category=pattern["cause"],
                description=pattern["description"],
                confidence=confidence,
                evidence=pattern["evidence"],
                investigation_steps=pattern["investigation"],
                remediation_steps=pattern["remediation"],
                score=total_score,
            )
            hypotheses.append(hypothesis)

        # Sort by score
        hypotheses.sort(key=lambda h: h.score, reverse=True)
        return hypotheses

    async def analyze(
        self,
        symptoms: list[Symptom] | None = None,
        hours: int = 24,
    ) -> RootCauseAnalysis:
        """Perform root cause analysis.

        Args:
            symptoms: Specific symptoms (or get recent)
            hours: Look back window if getting recent

        Returns:
            Root cause analysis
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get symptoms
        if symptoms is None:
            symptoms = await self.get_recent_symptoms(hours=hours)

        if not symptoms:
            return RootCauseAnalysis(
                id=str(uuid.uuid4())[:8],
                analyzed_at=now,
                symptoms=[],
                hypotheses=[],
                primary_hypothesis=None,
                summary="No symptoms to analyze",
                recommended_actions=["Monitor system health"],
                related_incidents=[],
            )

        # Generate hypotheses
        hypotheses = self._generate_hypotheses(symptoms)

        # Primary hypothesis
        primary = hypotheses[0] if hypotheses else None

        # Generate summary
        if primary:
            summary = f"Most likely cause: {primary.description} ({primary.confidence.value} confidence)"
        else:
            summary = "Unable to determine root cause from available symptoms"

        # Recommended actions
        actions = []
        if primary:
            actions.extend(primary.investigation_steps[:2])
            actions.extend(primary.remediation_steps[:2])
        else:
            actions = ["Gather more diagnostic data", "Review recent changes", "Monitor metrics"]

        # Find related incidents
        related = await self._find_related_incidents(symptoms)

        analysis = RootCauseAnalysis(
            id=str(uuid.uuid4())[:8],
            analyzed_at=now,
            symptoms=symptoms,
            hypotheses=hypotheses,
            primary_hypothesis=primary,
            summary=summary,
            recommended_actions=actions,
            related_incidents=related,
        )

        # Store analysis
        await redis.lpush(
            self.ANALYSES_KEY,
            json.dumps(analysis.to_dict()),
        )
        await redis.ltrim(self.ANALYSES_KEY, 0, 99)

        logger.info(f"[RootCause] Analysis {analysis.id}: {summary}")

        return analysis

    async def _find_related_incidents(
        self,
        symptoms: list[Symptom],
    ) -> list[str]:
        """Find related past incidents.

        Args:
            symptoms: Current symptoms

        Returns:
            List of related incident IDs
        """
        try:
            from app.services.incident_timeline import incident_timeline

            recent = await incident_timeline.list_incidents(limit=50)

            related = []
            symptom_categories = {s.category.value for s in symptoms}

            for incident in recent:
                # Check for similar symptoms in incident title/description
                incident_data = incident.to_dict()
                title = incident_data.get("title", "").lower()

                for category in symptom_categories:
                    if category in title:
                        related.append(incident.id)
                        break

                if len(related) >= 5:
                    break

            return related
        except Exception:
            return []

    async def analyze_error(
        self,
        error_message: str,
        stack_trace: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> RootCauseAnalysis:
        """Analyze a specific error.

        Args:
            error_message: Error message
            stack_trace: Optional stack trace
            context: Additional context

        Returns:
            Root cause analysis
        """
        # Create symptom from error
        severity = "high" if "critical" in error_message.lower() else "medium"

        symptom = await self.record_symptom(
            category=SymptomCategory.ERROR_RATE,
            description=error_message[:500],
            severity=severity,
            metrics={
                "stack_trace": stack_trace[:1000] if stack_trace else None,
                "context": context,
            },
        )

        # Analyze with this symptom
        return await self.analyze(symptoms=[symptom])

    async def get_analysis_history(
        self,
        limit: int = 20,
    ) -> list[RootCauseAnalysis]:
        """Get past analyses.

        Args:
            limit: Max results

        Returns:
            List of analyses
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.lrange(self.ANALYSES_KEY, 0, limit - 1)
        analyses = []

        for item in raw:
            try:
                data = json.loads(item)

                symptoms = [
                    Symptom(
                        id=s["id"],
                        category=SymptomCategory(s["category"]),
                        description=s["description"],
                        severity=s["severity"],
                        first_seen=datetime.fromisoformat(s["first_seen"]),
                        metrics=s.get("metrics", {}),
                    )
                    for s in data.get("symptoms", [])
                ]

                hypotheses = [
                    Hypothesis(
                        id=h["id"],
                        category=RootCauseCategory(h["category"]),
                        description=h["description"],
                        confidence=Confidence(h["confidence"]),
                        evidence=h["evidence"],
                        investigation_steps=h["investigation_steps"],
                        remediation_steps=h["remediation_steps"],
                        score=h["score"],
                    )
                    for h in data.get("hypotheses", [])
                ]

                primary = None
                if data.get("primary_hypothesis"):
                    ph = data["primary_hypothesis"]
                    primary = Hypothesis(
                        id=ph["id"],
                        category=RootCauseCategory(ph["category"]),
                        description=ph["description"],
                        confidence=Confidence(ph["confidence"]),
                        evidence=ph["evidence"],
                        investigation_steps=ph["investigation_steps"],
                        remediation_steps=ph["remediation_steps"],
                        score=ph["score"],
                    )

                analyses.append(RootCauseAnalysis(
                    id=data["id"],
                    analyzed_at=datetime.fromisoformat(data["analyzed_at"]),
                    symptoms=symptoms,
                    hypotheses=hypotheses,
                    primary_hypothesis=primary,
                    summary=data["summary"],
                    recommended_actions=data["recommended_actions"],
                    related_incidents=data.get("related_incidents", []),
                ))
            except Exception:
                continue

        return analyses

    async def get_common_causes(
        self,
        days: int = 30,
    ) -> dict[str, int]:
        """Get most common root causes.

        Args:
            days: Look back window

        Returns:
            Map of cause category to count
        """
        analyses = await self.get_analysis_history(limit=100)
        cutoff = datetime.now(UTC) - timedelta(days=days)

        cause_counts: dict[str, int] = {}

        for analysis in analyses:
            if analysis.analyzed_at < cutoff:
                continue

            if analysis.primary_hypothesis:
                cause = analysis.primary_hypothesis.category.value
                cause_counts[cause] = cause_counts.get(cause, 0) + 1

        return dict(sorted(cause_counts.items(), key=lambda x: x[1], reverse=True))


# Singleton
root_cause_helper = RootCauseHelperService()
