"""Change Impact Analysis Service.

Pre-change impact analysis and risk assessment.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

UTC = timezone.utc

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Types of changes."""

    CODE_DEPLOY = "code_deploy"
    CONFIG_UPDATE = "config_update"
    DATABASE_MIGRATION = "database_migration"
    DEPENDENCY_UPDATE = "dependency_update"
    INFRASTRUCTURE = "infrastructure"
    FEATURE_FLAG = "feature_flag"
    ROLLBACK = "rollback"


class RiskLevel(str, Enum):
    """Risk level assessment."""

    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactArea(str, Enum):
    """Areas potentially impacted."""

    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    DATA_INTEGRITY = "data_integrity"
    SECURITY = "security"
    USER_EXPERIENCE = "user_experience"
    COST = "cost"
    COMPLIANCE = "compliance"


@dataclass
class ChangeRequest:
    """Change request for analysis."""

    id: str
    change_type: ChangeType
    title: str
    description: str
    requested_by: str
    requested_at: datetime
    target_components: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "change_type": self.change_type.value,
            "title": self.title,
            "description": self.description,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at.isoformat(),
            "target_components": self.target_components,
            "metadata": self.metadata,
        }


@dataclass
class ImpactAssessment:
    """Assessment of impact on a specific area."""

    area: ImpactArea
    risk_level: RiskLevel
    description: str
    affected_components: list[str]
    mitigation_steps: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "area": self.area.value,
            "risk_level": self.risk_level.value,
            "description": self.description,
            "affected_components": self.affected_components,
            "mitigation_steps": self.mitigation_steps,
        }


@dataclass
class ChangeImpactReport:
    """Full change impact analysis report."""

    id: str
    change_request: ChangeRequest
    analyzed_at: datetime
    overall_risk: RiskLevel
    impact_assessments: list[ImpactAssessment]
    affected_services: list[str]
    dependencies_affected: list[str]
    rollback_plan: list[str]
    recommended_actions: list[str]
    approval_required: bool
    estimated_downtime_minutes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "change_request": self.change_request.to_dict(),
            "analyzed_at": self.analyzed_at.isoformat(),
            "overall_risk": self.overall_risk.value,
            "impact_assessments": [a.to_dict() for a in self.impact_assessments],
            "affected_services": self.affected_services,
            "dependencies_affected": self.dependencies_affected,
            "rollback_plan": self.rollback_plan,
            "recommended_actions": self.recommended_actions,
            "approval_required": self.approval_required,
            "estimated_downtime_minutes": self.estimated_downtime_minutes,
        }


# Impact patterns for different change types
IMPACT_PATTERNS = {
    ChangeType.CODE_DEPLOY: {
        "default_risk": RiskLevel.MEDIUM,
        "impact_areas": [ImpactArea.AVAILABILITY, ImpactArea.PERFORMANCE, ImpactArea.USER_EXPERIENCE],
        "downtime_minutes": 5,
        "rollback_steps": [
            "Identify failing deployment",
            "Trigger rollback to previous version",
            "Verify service health",
            "Notify stakeholders",
        ],
    },
    ChangeType.CONFIG_UPDATE: {
        "default_risk": RiskLevel.LOW,
        "impact_areas": [ImpactArea.AVAILABILITY, ImpactArea.SECURITY],
        "downtime_minutes": 0,
        "rollback_steps": [
            "Identify incorrect config",
            "Revert to previous config values",
            "Restart affected services",
        ],
    },
    ChangeType.DATABASE_MIGRATION: {
        "default_risk": RiskLevel.HIGH,
        "impact_areas": [ImpactArea.DATA_INTEGRITY, ImpactArea.AVAILABILITY, ImpactArea.PERFORMANCE],
        "downtime_minutes": 30,
        "rollback_steps": [
            "Stop application writes",
            "Run reverse migration",
            "Verify data integrity",
            "Resume normal operations",
        ],
    },
    ChangeType.DEPENDENCY_UPDATE: {
        "default_risk": RiskLevel.MEDIUM,
        "impact_areas": [ImpactArea.SECURITY, ImpactArea.PERFORMANCE, ImpactArea.AVAILABILITY],
        "downtime_minutes": 10,
        "rollback_steps": [
            "Identify breaking dependency",
            "Revert to previous version",
            "Clear caches if needed",
            "Redeploy with old dependencies",
        ],
    },
    ChangeType.INFRASTRUCTURE: {
        "default_risk": RiskLevel.HIGH,
        "impact_areas": [ImpactArea.AVAILABILITY, ImpactArea.PERFORMANCE, ImpactArea.COST],
        "downtime_minutes": 60,
        "rollback_steps": [
            "Failover to backup infrastructure",
            "Revert infrastructure changes",
            "Verify connectivity",
            "Update DNS if needed",
        ],
    },
    ChangeType.FEATURE_FLAG: {
        "default_risk": RiskLevel.LOW,
        "impact_areas": [ImpactArea.USER_EXPERIENCE],
        "downtime_minutes": 0,
        "rollback_steps": [
            "Disable feature flag",
            "Clear feature cache",
            "Verify rollback complete",
        ],
    },
    ChangeType.ROLLBACK: {
        "default_risk": RiskLevel.MEDIUM,
        "impact_areas": [ImpactArea.AVAILABILITY, ImpactArea.DATA_INTEGRITY],
        "downtime_minutes": 15,
        "rollback_steps": [
            "This is already a rollback",
            "If further issues, escalate to incident",
        ],
    },
}

# Component risk multipliers
COMPONENT_RISK = {
    "api": 1.5,
    "database": 2.0,
    "redis": 1.5,
    "celery": 1.0,
    "auth": 2.0,
    "payments": 2.5,
    "email": 1.0,
    "llm": 1.0,
}


class ChangeImpactService:
    """Service for change impact analysis.

    Features:
    - Pre-change risk assessment
    - Dependency impact mapping
    - Rollback planning
    - Approval recommendations
    """

    REPORTS_KEY = "impact:reports"
    HISTORY_KEY = "impact:history"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    async def analyze(
        self,
        change_type: ChangeType,
        title: str,
        description: str,
        requested_by: str,
        target_components: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChangeImpactReport:
        """Analyze impact of proposed change.

        Args:
            change_type: Type of change
            title: Change title
            description: Change description
            requested_by: Who requested
            target_components: Components affected
            metadata: Additional metadata

        Returns:
            Impact analysis report
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        # Create change request
        request = ChangeRequest(
            id=str(uuid.uuid4())[:8],
            change_type=change_type,
            title=title,
            description=description,
            requested_by=requested_by,
            requested_at=now,
            target_components=target_components or [],
            metadata=metadata or {},
        )

        # Get pattern for change type
        pattern = IMPACT_PATTERNS.get(change_type, IMPACT_PATTERNS[ChangeType.CODE_DEPLOY])

        # Calculate risk
        base_risk = pattern["default_risk"]
        risk_score = self._risk_to_score(base_risk)

        # Adjust for components
        for component in target_components or []:
            multiplier = COMPONENT_RISK.get(component.lower(), 1.0)
            risk_score *= multiplier

        overall_risk = self._score_to_risk(risk_score)

        # Generate impact assessments
        assessments = self._generate_assessments(
            pattern["impact_areas"],
            target_components or [],
            overall_risk,
        )

        # Get affected services via dependency graph
        affected_services = await self._get_affected_services(target_components or [])
        dependencies = await self._get_dependencies(target_components or [])

        # Generate rollback plan
        rollback_plan = pattern["rollback_steps"].copy()

        # Generate recommendations
        recommendations = self._generate_recommendations(
            change_type,
            overall_risk,
            target_components or [],
        )

        # Determine if approval required
        approval_required = overall_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]

        # Estimate downtime
        downtime = pattern["downtime_minutes"]
        if overall_risk == RiskLevel.CRITICAL:
            downtime = int(downtime * 1.5)

        report = ChangeImpactReport(
            id=str(uuid.uuid4())[:8],
            change_request=request,
            analyzed_at=now,
            overall_risk=overall_risk,
            impact_assessments=assessments,
            affected_services=affected_services,
            dependencies_affected=dependencies,
            rollback_plan=rollback_plan,
            recommended_actions=recommendations,
            approval_required=approval_required,
            estimated_downtime_minutes=downtime,
        )

        # Store report
        await redis.hset(
            self.REPORTS_KEY,
            report.id,
            json.dumps(report.to_dict()),
        )

        # Store in history
        await redis.lpush(
            self.HISTORY_KEY,
            json.dumps(report.to_dict()),
        )
        await redis.ltrim(self.HISTORY_KEY, 0, 99)

        logger.info(f"[ChangeImpact] Analyzed change {report.id}: {overall_risk.value} risk")

        return report

    def _risk_to_score(self, risk: RiskLevel) -> float:
        """Convert risk level to numeric score."""
        mapping = {
            RiskLevel.MINIMAL: 0.2,
            RiskLevel.LOW: 0.4,
            RiskLevel.MEDIUM: 0.6,
            RiskLevel.HIGH: 0.8,
            RiskLevel.CRITICAL: 1.0,
        }
        return mapping.get(risk, 0.6)

    def _score_to_risk(self, score: float) -> RiskLevel:
        """Convert numeric score to risk level."""
        if score >= 1.5:
            return RiskLevel.CRITICAL
        elif score >= 1.0:
            return RiskLevel.HIGH
        elif score >= 0.6:
            return RiskLevel.MEDIUM
        elif score >= 0.3:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL

    def _generate_assessments(
        self,
        impact_areas: list[ImpactArea],
        components: list[str],
        overall_risk: RiskLevel,
    ) -> list[ImpactAssessment]:
        """Generate impact assessments for each area."""
        assessments = []

        for area in impact_areas:
            assessment = self._assess_area(area, components, overall_risk)
            assessments.append(assessment)

        return assessments

    def _assess_area(
        self,
        area: ImpactArea,
        components: list[str],
        overall_risk: RiskLevel,
    ) -> ImpactAssessment:
        """Assess impact on specific area."""
        descriptions = {
            ImpactArea.PERFORMANCE: "May affect response times and throughput",
            ImpactArea.AVAILABILITY: "May cause temporary service interruption",
            ImpactArea.DATA_INTEGRITY: "May affect data consistency",
            ImpactArea.SECURITY: "May affect security posture",
            ImpactArea.USER_EXPERIENCE: "May affect user-facing features",
            ImpactArea.COST: "May affect operational costs",
            ImpactArea.COMPLIANCE: "May affect compliance status",
        }

        mitigations = {
            ImpactArea.PERFORMANCE: [
                "Enable performance monitoring",
                "Set up auto-scaling",
                "Prepare rollback trigger",
            ],
            ImpactArea.AVAILABILITY: [
                "Use blue-green deployment",
                "Enable health checks",
                "Prepare failover",
            ],
            ImpactArea.DATA_INTEGRITY: [
                "Take database backup",
                "Validate data before/after",
                "Enable audit logging",
            ],
            ImpactArea.SECURITY: [
                "Review security implications",
                "Scan for vulnerabilities",
                "Update access controls if needed",
            ],
            ImpactArea.USER_EXPERIENCE: [
                "Test in staging first",
                "Use feature flags",
                "Prepare user communication",
            ],
            ImpactArea.COST: [
                "Review resource usage",
                "Set budget alerts",
                "Monitor spending",
            ],
            ImpactArea.COMPLIANCE: [
                "Review compliance requirements",
                "Document changes",
                "Verify audit trail",
            ],
        }

        return ImpactAssessment(
            area=area,
            risk_level=overall_risk,
            description=descriptions.get(area, "Potential impact on this area"),
            affected_components=components,
            mitigation_steps=mitigations.get(area, ["Monitor closely"]),
        )

    async def _get_affected_services(
        self,
        components: list[str],
    ) -> list[str]:
        """Get services affected by component changes."""
        try:
            from app.services.dependency_graph import dependency_graph

            affected = set()
            for component in components:
                impact = await dependency_graph.analyze_impact(component)
                affected.update(impact.directly_affected)
                affected.update(impact.transitively_affected)

            return list(affected)
        except Exception:
            # Fallback
            return components

    async def _get_dependencies(
        self,
        components: list[str],
    ) -> list[str]:
        """Get dependencies of affected components."""
        try:
            from app.services.dependency_graph import dependency_graph

            deps = set()
            for component in components:
                edges = await dependency_graph.get_dependencies(component)
                deps.update(e.target_id for e in edges)

            return list(deps)
        except Exception:
            return []

    def _generate_recommendations(
        self,
        change_type: ChangeType,
        risk: RiskLevel,
        components: list[str],
    ) -> list[str]:
        """Generate recommendations for the change."""
        recommendations = []

        # General recommendations
        recommendations.append("Review change in staging environment first")
        recommendations.append("Ensure monitoring is active")

        if risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recommendations.append("Schedule change during low-traffic window")
            recommendations.append("Have incident response team on standby")
            recommendations.append("Get explicit approval from tech lead")

        if change_type == ChangeType.DATABASE_MIGRATION:
            recommendations.append("Take database backup before migration")
            recommendations.append("Test migration on copy of production data")

        if change_type == ChangeType.DEPENDENCY_UPDATE:
            recommendations.append("Review changelog for breaking changes")
            recommendations.append("Run full test suite")

        if "database" in [c.lower() for c in components]:
            recommendations.append("Enable database connection pooling")

        if "auth" in [c.lower() for c in components]:
            recommendations.append("Test authentication flows thoroughly")

        return recommendations

    async def get_report(self, report_id: str) -> ChangeImpactReport | None:
        """Get impact report by ID.

        Args:
            report_id: Report ID

        Returns:
            Report or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hget(self.REPORTS_KEY, report_id)
        if not raw:
            return None

        data = json.loads(raw)
        return self._parse_report(data)

    async def get_history(
        self,
        limit: int = 20,
        change_type: ChangeType | None = None,
    ) -> list[ChangeImpactReport]:
        """Get report history.

        Args:
            limit: Max results
            change_type: Filter by type

        Returns:
            List of reports
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.lrange(self.HISTORY_KEY, 0, limit - 1)
        reports = []

        for item in raw:
            try:
                data = json.loads(item)

                if change_type and data["change_request"]["change_type"] != change_type.value:
                    continue

                reports.append(self._parse_report(data))
            except Exception:
                continue

        return reports

    def _parse_report(self, data: dict[str, Any]) -> ChangeImpactReport:
        """Parse report from stored data."""
        req_data = data["change_request"]
        request = ChangeRequest(
            id=req_data["id"],
            change_type=ChangeType(req_data["change_type"]),
            title=req_data["title"],
            description=req_data["description"],
            requested_by=req_data["requested_by"],
            requested_at=datetime.fromisoformat(req_data["requested_at"]),
            target_components=req_data["target_components"],
            metadata=req_data.get("metadata", {}),
        )

        assessments = [
            ImpactAssessment(
                area=ImpactArea(a["area"]),
                risk_level=RiskLevel(a["risk_level"]),
                description=a["description"],
                affected_components=a["affected_components"],
                mitigation_steps=a["mitigation_steps"],
            )
            for a in data.get("impact_assessments", [])
        ]

        return ChangeImpactReport(
            id=data["id"],
            change_request=request,
            analyzed_at=datetime.fromisoformat(data["analyzed_at"]),
            overall_risk=RiskLevel(data["overall_risk"]),
            impact_assessments=assessments,
            affected_services=data.get("affected_services", []),
            dependencies_affected=data.get("dependencies_affected", []),
            rollback_plan=data.get("rollback_plan", []),
            recommended_actions=data.get("recommended_actions", []),
            approval_required=data.get("approval_required", False),
            estimated_downtime_minutes=data.get("estimated_downtime_minutes", 0),
        )

    async def quick_assess(
        self,
        change_type: ChangeType,
        components: list[str] | None = None,
    ) -> dict[str, Any]:
        """Quick risk assessment without full analysis.

        Args:
            change_type: Type of change
            components: Target components

        Returns:
            Quick assessment dict
        """
        pattern = IMPACT_PATTERNS.get(change_type, IMPACT_PATTERNS[ChangeType.CODE_DEPLOY])

        base_risk = pattern["default_risk"]
        risk_score = self._risk_to_score(base_risk)

        for component in components or []:
            multiplier = COMPONENT_RISK.get(component.lower(), 1.0)
            risk_score *= multiplier

        overall_risk = self._score_to_risk(risk_score)

        return {
            "change_type": change_type.value,
            "components": components or [],
            "risk_level": overall_risk.value,
            "approval_required": overall_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL],
            "estimated_downtime_minutes": pattern["downtime_minutes"],
            "impact_areas": [a.value for a in pattern["impact_areas"]],
        }


# Singleton
change_impact = ChangeImpactService()
