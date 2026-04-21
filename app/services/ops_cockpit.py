"""Unified Operational Cockpit Service.

Single pane of glass for all operational data.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class OverallStatus(str, Enum):
    """Overall system status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    AT_RISK = "at_risk"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class ActionPriority(str, Enum):
    """Priority of recommended action."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionCategory(str, Enum):
    """Category of recommended action."""

    INCIDENT = "incident"
    APPROVAL = "approval"
    COST = "cost"
    SLO = "slo"
    DRIFT = "drift"
    QUEUE = "queue"
    HEALTH = "health"
    SECURITY = "security"


@dataclass
class RecommendedAction:
    """Recommended action for operators."""

    id: str
    title: str
    description: str
    category: ActionCategory
    priority: ActionPriority
    source_service: str
    source_id: str | None
    action_url: str | None
    created_at: datetime
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "priority": self.priority.value,
            "source_service": self.source_service,
            "source_id": self.source_id,
            "action_url": self.action_url,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }


@dataclass
class HealthSummary:
    """Health summary across all services."""

    status: OverallStatus
    services_total: int
    services_healthy: int
    services_degraded: int
    services_unhealthy: int
    active_circuit_breakers: list[str]
    processing_paused: bool
    emergency_mode: bool
    last_check: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "services_total": self.services_total,
            "services_healthy": self.services_healthy,
            "services_degraded": self.services_degraded,
            "services_unhealthy": self.services_unhealthy,
            "active_circuit_breakers": self.active_circuit_breakers,
            "processing_paused": self.processing_paused,
            "emergency_mode": self.emergency_mode,
            "last_check": self.last_check.isoformat(),
        }


@dataclass
class IncidentSummary:
    """Incident summary."""

    active_count: int
    critical_count: int
    high_count: int
    oldest_active_hours: float | None
    mttr_hours_30d: float | None
    recent_incidents: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_count": self.active_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "oldest_active_hours": round(self.oldest_active_hours, 1) if self.oldest_active_hours else None,
            "mttr_hours_30d": round(self.mttr_hours_30d, 2) if self.mttr_hours_30d else None,
            "recent_incidents": self.recent_incidents,
        }


@dataclass
class QueueSummary:
    """Queue health summary."""

    total_queues: int
    total_pending: int
    total_processing: int
    queues_backed_up: int
    oldest_task_minutes: float | None
    queue_details: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_queues": self.total_queues,
            "total_pending": self.total_pending,
            "total_processing": self.total_processing,
            "queues_backed_up": self.queues_backed_up,
            "oldest_task_minutes": round(self.oldest_task_minutes, 1) if self.oldest_task_minutes else None,
            "queue_details": self.queue_details,
        }


@dataclass
class SLOSummary:
    """SLO/error budget summary."""

    total_slos: int
    slos_at_risk: int
    slos_breached: int
    lowest_budget_percent: float | None
    lowest_budget_slo: str | None
    budget_details: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_slos": self.total_slos,
            "slos_at_risk": self.slos_at_risk,
            "slos_breached": self.slos_breached,
            "lowest_budget_percent": round(self.lowest_budget_percent, 1) if self.lowest_budget_percent is not None else None,
            "lowest_budget_slo": self.lowest_budget_slo,
            "budget_details": self.budget_details,
        }


@dataclass
class CostSummary:
    """Cost summary."""

    daily_total_usd: float
    daily_budget_usd: float
    daily_utilization_percent: float
    monthly_total_usd: float
    monthly_budget_usd: float
    monthly_utilization_percent: float
    top_cost_drivers: list[dict[str, Any]]
    alerts_active: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "daily_total_usd": round(self.daily_total_usd, 2),
            "daily_budget_usd": round(self.daily_budget_usd, 2),
            "daily_utilization_percent": round(self.daily_utilization_percent, 1),
            "monthly_total_usd": round(self.monthly_total_usd, 2),
            "monthly_budget_usd": round(self.monthly_budget_usd, 2),
            "monthly_utilization_percent": round(self.monthly_utilization_percent, 1),
            "top_cost_drivers": self.top_cost_drivers,
            "alerts_active": self.alerts_active,
        }


@dataclass
class DriftSummary:
    """Drift detection summary."""

    total_monitored: int
    drifted_count: int
    critical_drifts: int
    drift_rate_percent: float
    recent_drifts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_monitored": self.total_monitored,
            "drifted_count": self.drifted_count,
            "critical_drifts": self.critical_drifts,
            "drift_rate_percent": round(self.drift_rate_percent, 1),
            "recent_drifts": self.recent_drifts,
        }


@dataclass
class ApprovalSummary:
    """Pending approvals summary."""

    pending_count: int
    critical_pending: int
    high_pending: int
    oldest_pending_hours: float | None
    expiring_soon: int
    pending_details: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pending_count": self.pending_count,
            "critical_pending": self.critical_pending,
            "high_pending": self.high_pending,
            "oldest_pending_hours": round(self.oldest_pending_hours, 1) if self.oldest_pending_hours else None,
            "expiring_soon": self.expiring_soon,
            "pending_details": self.pending_details,
        }


@dataclass
class RiskyActionsSummary:
    """Recent risky actions summary."""

    last_24h_count: int
    emergency_actions: int
    policy_violations: int
    recent_actions: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_24h_count": self.last_24h_count,
            "emergency_actions": self.emergency_actions,
            "policy_violations": self.policy_violations,
            "recent_actions": self.recent_actions,
        }


@dataclass
class OperationalCockpit:
    """Complete operational cockpit view."""

    generated_at: datetime
    overall_status: OverallStatus
    status_reason: str
    health: HealthSummary
    incidents: IncidentSummary
    queues: QueueSummary
    slos: SLOSummary
    costs: CostSummary
    drift: DriftSummary
    approvals: ApprovalSummary
    risky_actions: RiskyActionsSummary
    recommended_actions: list[RecommendedAction]
    alerts_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "overall_status": self.overall_status.value,
            "status_reason": self.status_reason,
            "health": self.health.to_dict(),
            "incidents": self.incidents.to_dict(),
            "queues": self.queues.to_dict(),
            "slos": self.slos.to_dict(),
            "costs": self.costs.to_dict(),
            "drift": self.drift.to_dict(),
            "approvals": self.approvals.to_dict(),
            "risky_actions": self.risky_actions.to_dict(),
            "recommended_actions": [a.to_dict() for a in self.recommended_actions],
            "alerts_count": self.alerts_count,
        }


class OpsCockpitService:
    """Service for unified operational cockpit.

    Aggregates data from all operational services into
    a single coherent view with recommended actions.
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    async def get_cockpit(self) -> OperationalCockpit:
        """Get complete operational cockpit.

        Returns:
            Full cockpit data
        """
        now = datetime.now(UTC)

        # Gather all summaries in parallel-ish
        health = await self._get_health_summary()
        incidents = await self._get_incident_summary()
        queues = await self._get_queue_summary()
        slos = await self._get_slo_summary()
        costs = await self._get_cost_summary()
        drift = await self._get_drift_summary()
        approvals = await self._get_approval_summary()
        risky_actions = await self._get_risky_actions_summary()

        # Generate recommended actions
        recommended = await self._generate_recommendations(
            health, incidents, queues, slos, costs, drift, approvals
        )

        # Determine overall status
        overall_status, status_reason = self._determine_overall_status(
            health, incidents, slos, costs, drift, approvals
        )

        # Count total alerts
        alerts_count = (
            incidents.critical_count +
            slos.slos_breached +
            drift.critical_drifts +
            approvals.critical_pending +
            costs.alerts_active
        )

        return OperationalCockpit(
            generated_at=now,
            overall_status=overall_status,
            status_reason=status_reason,
            health=health,
            incidents=incidents,
            queues=queues,
            slos=slos,
            costs=costs,
            drift=drift,
            approvals=approvals,
            risky_actions=risky_actions,
            recommended_actions=recommended,
            alerts_count=alerts_count,
        )

    async def _get_health_summary(self) -> HealthSummary:
        """Get health summary from control plane and dependency graph."""
        now = datetime.now(UTC)

        try:
            from app.services.control_plane import control_plane
            state = await control_plane.get_system_state()

            processing_paused = state.processing_paused
            emergency_mode = state.emergency_mode
            circuit_breakers = state.active_circuit_breakers
        except Exception:
            processing_paused = False
            emergency_mode = False
            circuit_breakers = []

        try:
            from app.services.dependency_graph import dependency_graph
            health_map = await dependency_graph.check_health_propagation()

            total = len(health_map)
            healthy = sum(1 for h in health_map.values() if h == "healthy")
            degraded = sum(1 for h in health_map.values() if h == "degraded")
            unhealthy = sum(1 for h in health_map.values() if h == "unhealthy")
        except Exception:
            total = healthy = degraded = unhealthy = 0

        # Determine status
        if emergency_mode:
            status = OverallStatus.EMERGENCY
        elif unhealthy > 0 or len(circuit_breakers) > 2:
            status = OverallStatus.CRITICAL
        elif degraded > 0 or processing_paused or circuit_breakers:
            status = OverallStatus.DEGRADED
        else:
            status = OverallStatus.HEALTHY

        return HealthSummary(
            status=status,
            services_total=total,
            services_healthy=healthy,
            services_degraded=degraded,
            services_unhealthy=unhealthy,
            active_circuit_breakers=circuit_breakers,
            processing_paused=processing_paused,
            emergency_mode=emergency_mode,
            last_check=now,
        )

    async def _get_incident_summary(self) -> IncidentSummary:
        """Get incident summary."""
        now = datetime.now(UTC)

        try:
            from app.services.incident_timeline import incident_timeline, IncidentSeverity

            active = await incident_timeline.get_active_incidents()
            stats = await incident_timeline.get_stats(days=30)

            active_count = len(active)
            critical_count = sum(1 for i in active if i.severity == IncidentSeverity.CRITICAL)
            high_count = sum(1 for i in active if i.severity == IncidentSeverity.HIGH)

            # Oldest active
            oldest_hours = None
            if active:
                oldest = min(i.created_at for i in active)
                oldest_hours = (now - oldest).total_seconds() / 3600

            recent = [
                {
                    "id": i.id,
                    "title": i.title,
                    "severity": i.severity.value,
                    "status": i.status.value,
                    "created_at": i.created_at.isoformat(),
                }
                for i in active[:5]
            ]

            mttr = stats.mttr_minutes / 60 if stats.mttr_minutes else None

        except Exception:
            active_count = critical_count = high_count = 0
            oldest_hours = mttr = None
            recent = []

        return IncidentSummary(
            active_count=active_count,
            critical_count=critical_count,
            high_count=high_count,
            oldest_active_hours=oldest_hours,
            mttr_hours_30d=mttr,
            recent_incidents=recent,
        )

    async def _get_queue_summary(self) -> QueueSummary:
        """Get queue health summary."""
        try:
            from app.services.worker_health import worker_health

            queue_stats = await worker_health.get_queue_stats()

            total_queues = len(queue_stats)
            total_pending = sum(q.length for q in queue_stats)
            total_processing = sum(q.processing for q in queue_stats)
            backed_up = sum(1 for q in queue_stats if q.length > 100)

            # Oldest task estimate (simplified)
            oldest = None
            if queue_stats:
                max_len = max(q.length for q in queue_stats)
                if max_len > 0:
                    oldest = max_len * 0.5  # Rough estimate

            details = [
                {
                    "name": q.name,
                    "pending": q.length,
                    "processing": q.processing,
                }
                for q in queue_stats[:5]
            ]

        except Exception:
            total_queues = total_pending = total_processing = backed_up = 0
            oldest = None
            details = []

        return QueueSummary(
            total_queues=total_queues,
            total_pending=total_pending,
            total_processing=total_processing,
            queues_backed_up=backed_up,
            oldest_task_minutes=oldest,
            queue_details=details,
        )

    async def _get_slo_summary(self) -> SLOSummary:
        """Get SLO/error budget summary."""
        try:
            from app.services.slo_budgets import slo_budgets

            budgets = await slo_budgets.get_all_budgets()

            total = len(budgets)
            at_risk = sum(1 for b in budgets if 0 < b.remaining_percent <= 20)
            breached = sum(1 for b in budgets if b.remaining_percent <= 0)

            lowest_budget = None
            lowest_slo = None
            if budgets:
                sorted_budgets = sorted(budgets, key=lambda b: b.remaining_percent)
                lowest_budget = sorted_budgets[0].remaining_percent
                lowest_slo = sorted_budgets[0].slo_id

            details = [
                {
                    "slo_id": b.slo_id,
                    "remaining_percent": round(b.remaining_percent, 1),
                    "burn_rate": round(b.burn_rate, 2),
                    "status": "breached" if b.remaining_percent <= 0 else "at_risk" if b.remaining_percent <= 20 else "ok",
                }
                for b in budgets[:5]
            ]

        except Exception:
            total = at_risk = breached = 0
            lowest_budget = lowest_slo = None
            details = []

        return SLOSummary(
            total_slos=total,
            slos_at_risk=at_risk,
            slos_breached=breached,
            lowest_budget_percent=lowest_budget,
            lowest_budget_slo=lowest_slo,
            budget_details=details,
        )

    async def _get_cost_summary(self) -> CostSummary:
        """Get cost summary."""
        try:
            from app.services.cost_observability import cost_observability, CostPeriod

            daily = await cost_observability.get_summary(CostPeriod.DAILY)
            monthly = await cost_observability.get_summary(CostPeriod.MONTHLY)

            budget_status = await cost_observability.get_budget_status()
            alerts = sum(1 for b in budget_status if b.utilization_percent >= b.alert_threshold_percent)

            top_drivers = [
                {
                    "category": cat,
                    "amount_usd": round(amount, 2),
                }
                for cat, amount in sorted(
                    daily.by_category.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:3]
            ]

            daily_budget = sum(b.budget_usd for b in budget_status if b.period.value == "daily")
            monthly_budget = sum(b.budget_usd for b in budget_status if b.period.value == "monthly")

            daily_util = (daily.total_usd / daily_budget * 100) if daily_budget > 0 else 0
            monthly_util = (monthly.total_usd / monthly_budget * 100) if monthly_budget > 0 else 0

        except Exception:
            daily_util = monthly_util = 0
            daily_budget = monthly_budget = 0
            top_drivers = []
            alerts = 0
            daily = monthly = None

        return CostSummary(
            daily_total_usd=daily.total_usd if daily else 0,
            daily_budget_usd=daily_budget or 100,
            daily_utilization_percent=daily_util,
            monthly_total_usd=monthly.total_usd if monthly else 0,
            monthly_budget_usd=monthly_budget or 3000,
            monthly_utilization_percent=monthly_util,
            top_cost_drivers=top_drivers,
            alerts_active=alerts,
        )

    async def _get_drift_summary(self) -> DriftSummary:
        """Get drift detection summary."""
        try:
            from app.services.drift_detection import drift_detection, DriftSeverity

            report = await drift_detection.generate_report()
            events = await drift_detection.get_events(limit=10)

            critical = sum(1 for e in events if e.severity == DriftSeverity.CRITICAL)

            recent = [
                {
                    "resource": e.resource,
                    "severity": e.severity.value,
                    "detected_at": e.detected_at.isoformat(),
                    "changes_count": len(e.changes),
                }
                for e in events[:5]
            ]

        except Exception:
            report = None
            critical = 0
            recent = []

        return DriftSummary(
            total_monitored=report.total_resources if report else 0,
            drifted_count=report.drifted_resources if report else 0,
            critical_drifts=critical,
            drift_rate_percent=report.drift_rate * 100 if report else 0,
            recent_drifts=recent,
        )

    async def _get_approval_summary(self) -> ApprovalSummary:
        """Get pending approvals summary."""
        now = datetime.now(UTC)

        try:
            from app.services.approval_gates import approval_gates, RiskLevel

            pending = await approval_gates.list_pending()

            pending_count = len(pending)
            critical = sum(1 for p in pending if p.risk_level == RiskLevel.CRITICAL)
            high = sum(1 for p in pending if p.risk_level == RiskLevel.HIGH)

            # Oldest pending
            oldest_hours = None
            if pending:
                oldest = min(p.created_at for p in pending)
                oldest_hours = (now - oldest).total_seconds() / 3600

            # Expiring within 4 hours
            expiring_soon = sum(
                1 for p in pending
                if (p.expires_at - now).total_seconds() < 4 * 3600
            )

            details = [
                {
                    "id": p.id,
                    "action": p.action[:50],
                    "risk_level": p.risk_level.value,
                    "requester": p.requester,
                    "expires_at": p.expires_at.isoformat(),
                }
                for p in pending[:5]
            ]

        except Exception:
            pending_count = critical = high = 0
            oldest_hours = None
            expiring_soon = 0
            details = []

        return ApprovalSummary(
            pending_count=pending_count,
            critical_pending=critical,
            high_pending=high,
            oldest_pending_hours=oldest_hours,
            expiring_soon=expiring_soon,
            pending_details=details,
        )

    async def _get_risky_actions_summary(self) -> RiskyActionsSummary:
        """Get risky actions summary."""
        try:
            from app.services.control_plane import control_plane, ControlAction
            from app.services.policy_engine import policy_engine

            commands = await control_plane.get_command_history(limit=100)
            violations = await policy_engine.get_violations(limit=50)

            now = datetime.now(UTC)
            cutoff = now - timedelta(hours=24)

            recent_commands = [c for c in commands if c.issued_at >= cutoff]
            count_24h = len(recent_commands)

            emergency_count = sum(
                1 for c in recent_commands
                if c.action == ControlAction.EMERGENCY_STOP
            )

            violation_count = sum(
                1 for v in violations
                if v.violated_at >= cutoff
            )

            recent = [
                {
                    "action": c.action.value,
                    "issued_by": c.issued_by,
                    "issued_at": c.issued_at.isoformat(),
                    "status": c.status.value,
                }
                for c in recent_commands[:5]
            ]

        except Exception:
            count_24h = emergency_count = violation_count = 0
            recent = []

        return RiskyActionsSummary(
            last_24h_count=count_24h,
            emergency_actions=emergency_count,
            policy_violations=violation_count,
            recent_actions=recent,
        )

    async def _generate_recommendations(
        self,
        health: HealthSummary,
        incidents: IncidentSummary,
        queues: QueueSummary,
        slos: SLOSummary,
        costs: CostSummary,
        drift: DriftSummary,
        approvals: ApprovalSummary,
    ) -> list[RecommendedAction]:
        """Generate recommended actions based on current state."""
        import uuid
        now = datetime.now(UTC)
        actions = []

        # Emergency mode
        if health.emergency_mode:
            actions.append(RecommendedAction(
                id=str(uuid.uuid4())[:8],
                title="Clear Emergency Mode",
                description="System is in emergency mode. Review and clear when safe.",
                category=ActionCategory.HEALTH,
                priority=ActionPriority.CRITICAL,
                source_service="control_plane",
                source_id=None,
                action_url="/api/v1/platform/control/emergency/clear",
                created_at=now,
            ))

        # Processing paused
        if health.processing_paused and not health.emergency_mode:
            actions.append(RecommendedAction(
                id=str(uuid.uuid4())[:8],
                title="Resume Processing",
                description="Processing is paused. Resume when ready.",
                category=ActionCategory.HEALTH,
                priority=ActionPriority.HIGH,
                source_service="control_plane",
                source_id=None,
                action_url="/api/v1/platform/control/command",
                created_at=now,
            ))

        # Critical incidents
        if incidents.critical_count > 0:
            actions.append(RecommendedAction(
                id=str(uuid.uuid4())[:8],
                title=f"Resolve {incidents.critical_count} Critical Incident(s)",
                description="Critical incidents require immediate attention.",
                category=ActionCategory.INCIDENT,
                priority=ActionPriority.CRITICAL,
                source_service="incident_timeline",
                source_id=None,
                action_url="/api/v1/platform/incidents/active",
                created_at=now,
            ))

        # Pending critical approvals
        if approvals.critical_pending > 0:
            actions.append(RecommendedAction(
                id=str(uuid.uuid4())[:8],
                title=f"Review {approvals.critical_pending} Critical Approval(s)",
                description="Critical approval requests awaiting decision.",
                category=ActionCategory.APPROVAL,
                priority=ActionPriority.CRITICAL,
                source_service="approval_gates",
                source_id=None,
                action_url="/api/v1/platform/approvals/pending",
                created_at=now,
            ))

        # Expiring approvals
        if approvals.expiring_soon > 0:
            actions.append(RecommendedAction(
                id=str(uuid.uuid4())[:8],
                title=f"{approvals.expiring_soon} Approval(s) Expiring Soon",
                description="Some approval requests will expire within 4 hours.",
                category=ActionCategory.APPROVAL,
                priority=ActionPriority.HIGH,
                source_service="approval_gates",
                source_id=None,
                action_url="/api/v1/platform/approvals/pending",
                created_at=now,
            ))

        # SLO breaches
        if slos.slos_breached > 0:
            actions.append(RecommendedAction(
                id=str(uuid.uuid4())[:8],
                title=f"{slos.slos_breached} SLO(s) Breached",
                description="Error budget exhausted for some SLOs.",
                category=ActionCategory.SLO,
                priority=ActionPriority.CRITICAL,
                source_service="slo_budgets",
                source_id=slos.lowest_budget_slo,
                action_url="/api/v1/platform/slos/budgets",
                created_at=now,
            ))

        # SLOs at risk
        if slos.slos_at_risk > 0:
            actions.append(RecommendedAction(
                id=str(uuid.uuid4())[:8],
                title=f"{slos.slos_at_risk} SLO(s) at Risk",
                description=f"Error budget below 20%. Lowest: {slos.lowest_budget_percent:.1f}%",
                category=ActionCategory.SLO,
                priority=ActionPriority.HIGH,
                source_service="slo_budgets",
                source_id=slos.lowest_budget_slo,
                action_url="/api/v1/platform/slos/budgets",
                created_at=now,
            ))

        # Cost alerts
        if costs.alerts_active > 0:
            actions.append(RecommendedAction(
                id=str(uuid.uuid4())[:8],
                title=f"{costs.alerts_active} Cost Alert(s) Active",
                description=f"Cost utilization at {costs.daily_utilization_percent:.0f}% of daily budget.",
                category=ActionCategory.COST,
                priority=ActionPriority.HIGH,
                source_service="cost_observability",
                source_id=None,
                action_url="/api/v1/platform/costs/budgets",
                created_at=now,
            ))

        # Critical drifts
        if drift.critical_drifts > 0:
            actions.append(RecommendedAction(
                id=str(uuid.uuid4())[:8],
                title=f"{drift.critical_drifts} Critical Drift(s) Detected",
                description="Configuration drift requires attention.",
                category=ActionCategory.DRIFT,
                priority=ActionPriority.HIGH,
                source_service="drift_detection",
                source_id=None,
                action_url="/api/v1/platform/drift/events",
                created_at=now,
            ))

        # Queue backlog
        if queues.queues_backed_up > 0:
            actions.append(RecommendedAction(
                id=str(uuid.uuid4())[:8],
                title=f"{queues.queues_backed_up} Queue(s) Backed Up",
                description=f"Total pending: {queues.total_pending} tasks.",
                category=ActionCategory.QUEUE,
                priority=ActionPriority.MEDIUM,
                source_service="worker_health",
                source_id=None,
                action_url="/api/v1/ops/queues",
                created_at=now,
            ))

        # Circuit breakers
        if health.active_circuit_breakers:
            actions.append(RecommendedAction(
                id=str(uuid.uuid4())[:8],
                title=f"{len(health.active_circuit_breakers)} Circuit Breaker(s) Open",
                description=f"Services: {', '.join(health.active_circuit_breakers[:3])}",
                category=ActionCategory.HEALTH,
                priority=ActionPriority.MEDIUM,
                source_service="control_plane",
                source_id=None,
                action_url="/api/v1/platform/control/state",
                created_at=now,
            ))

        # Sort by priority
        priority_order = {
            ActionPriority.CRITICAL: 0,
            ActionPriority.HIGH: 1,
            ActionPriority.MEDIUM: 2,
            ActionPriority.LOW: 3,
        }
        actions.sort(key=lambda a: priority_order[a.priority])

        return actions

    def _determine_overall_status(
        self,
        health: HealthSummary,
        incidents: IncidentSummary,
        slos: SLOSummary,
        costs: CostSummary,
        drift: DriftSummary,
        approvals: ApprovalSummary,
    ) -> tuple[OverallStatus, str]:
        """Determine overall system status."""

        # Emergency
        if health.emergency_mode:
            return OverallStatus.EMERGENCY, "System in emergency mode"

        # Critical
        critical_reasons = []
        if incidents.critical_count > 0:
            critical_reasons.append(f"{incidents.critical_count} critical incident(s)")
        if slos.slos_breached > 0:
            critical_reasons.append(f"{slos.slos_breached} SLO(s) breached")
        if health.services_unhealthy > 0:
            critical_reasons.append(f"{health.services_unhealthy} unhealthy service(s)")

        if critical_reasons:
            return OverallStatus.CRITICAL, "; ".join(critical_reasons)

        # At Risk
        risk_reasons = []
        if incidents.high_count > 0:
            risk_reasons.append(f"{incidents.high_count} high severity incident(s)")
        if slos.slos_at_risk > 0:
            risk_reasons.append(f"{slos.slos_at_risk} SLO(s) at risk")
        if approvals.critical_pending > 0:
            risk_reasons.append(f"{approvals.critical_pending} critical approval(s) pending")
        if costs.daily_utilization_percent >= 90:
            risk_reasons.append("Daily cost at 90%+ of budget")

        if risk_reasons:
            return OverallStatus.AT_RISK, "; ".join(risk_reasons)

        # Degraded
        degraded_reasons = []
        if health.processing_paused:
            degraded_reasons.append("Processing paused")
        if health.services_degraded > 0:
            degraded_reasons.append(f"{health.services_degraded} degraded service(s)")
        if health.active_circuit_breakers:
            degraded_reasons.append(f"{len(health.active_circuit_breakers)} circuit breaker(s) open")
        if drift.critical_drifts > 0:
            degraded_reasons.append(f"{drift.critical_drifts} critical drift(s)")

        if degraded_reasons:
            return OverallStatus.DEGRADED, "; ".join(degraded_reasons)

        return OverallStatus.HEALTHY, "All systems operational"

    async def get_quick_status(self) -> dict[str, Any]:
        """Get quick status overview.

        Lighter weight than full cockpit.
        """
        now = datetime.now(UTC)

        health = await self._get_health_summary()
        incidents = await self._get_incident_summary()
        slos = await self._get_slo_summary()
        approvals = await self._get_approval_summary()

        overall, reason = self._determine_overall_status(
            health, incidents, slos,
            CostSummary(0, 100, 0, 0, 3000, 0, [], 0),
            DriftSummary(0, 0, 0, 0, []),
            approvals,
        )

        return {
            "timestamp": now.isoformat(),
            "status": overall.value,
            "status_reason": reason,
            "critical_items": {
                "incidents": incidents.critical_count,
                "slos_breached": slos.slos_breached,
                "approvals_pending": approvals.critical_pending,
                "emergency_mode": health.emergency_mode,
            },
            "processing_paused": health.processing_paused,
        }

    async def get_actions_only(
        self,
        priority: ActionPriority | None = None,
        category: ActionCategory | None = None,
        limit: int = 20,
    ) -> list[RecommendedAction]:
        """Get only recommended actions.

        Args:
            priority: Filter by priority
            category: Filter by category
            limit: Max actions

        Returns:
            List of actions
        """
        cockpit = await self.get_cockpit()

        actions = cockpit.recommended_actions

        if priority:
            actions = [a for a in actions if a.priority == priority]

        if category:
            actions = [a for a in actions if a.category == category]

        return actions[:limit]


# Singleton
ops_cockpit = OpsCockpitService()
