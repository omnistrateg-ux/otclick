"""SLO and Error Budgets Service.

Service Level Objectives and error budget tracking.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class SLOType(str, Enum):
    """SLO types."""

    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    FRESHNESS = "freshness"


class SLOStatus(str, Enum):
    """SLO status."""

    HEALTHY = "healthy"
    WARNING = "warning"  # Budget depleting
    CRITICAL = "critical"  # Budget exhausted
    UNKNOWN = "unknown"


@dataclass
class SLO:
    """Service Level Objective."""

    id: str
    name: str
    description: str
    slo_type: SLOType
    target_percent: float  # e.g., 99.9
    window_days: int  # Rolling window
    measurement_query: str  # How to measure
    service: str
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "slo_type": self.slo_type.value,
            "target_percent": self.target_percent,
            "window_days": self.window_days,
            "measurement_query": self.measurement_query,
            "service": self.service,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }


@dataclass
class ErrorBudget:
    """Error budget status."""

    slo_id: str
    slo_name: str
    target_percent: float
    current_percent: float
    budget_total_minutes: float
    budget_consumed_minutes: float
    budget_remaining_minutes: float
    budget_remaining_percent: float
    burn_rate: float  # Budget consumption rate
    time_to_exhaustion_hours: float | None
    status: SLOStatus
    window_start: datetime
    window_end: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "slo_id": self.slo_id,
            "slo_name": self.slo_name,
            "target_percent": self.target_percent,
            "current_percent": round(self.current_percent, 4),
            "budget_total_minutes": round(self.budget_total_minutes, 2),
            "budget_consumed_minutes": round(self.budget_consumed_minutes, 2),
            "budget_remaining_minutes": round(self.budget_remaining_minutes, 2),
            "budget_remaining_percent": round(self.budget_remaining_percent, 2),
            "burn_rate": round(self.burn_rate, 4),
            "time_to_exhaustion_hours": (
                round(self.time_to_exhaustion_hours, 1)
                if self.time_to_exhaustion_hours
                else None
            ),
            "status": self.status.value,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
        }


@dataclass
class SLOEvent:
    """SLO-related event."""

    slo_id: str
    event_type: str  # violation, recovery, budget_warning
    timestamp: datetime
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "slo_id": self.slo_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class SLOReport:
    """SLO report summary."""

    generated_at: datetime
    period_days: int
    slos: list[dict[str, Any]]
    overall_health: SLOStatus
    slos_meeting_target: int
    slos_at_risk: int
    slos_breached: int
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "period_days": self.period_days,
            "slos": self.slos,
            "overall_health": self.overall_health.value,
            "slos_meeting_target": self.slos_meeting_target,
            "slos_at_risk": self.slos_at_risk,
            "slos_breached": self.slos_breached,
            "recommendations": self.recommendations,
        }


# Default SLOs
DEFAULT_SLOS = [
    SLO(
        id="api_availability",
        name="API Availability",
        description="API endpoint availability",
        slo_type=SLOType.AVAILABILITY,
        target_percent=99.9,
        window_days=30,
        measurement_query="api:availability:percent",
        service="api",
    ),
    SLO(
        id="api_latency_p99",
        name="API P99 Latency",
        description="99th percentile API latency < 500ms",
        slo_type=SLOType.LATENCY,
        target_percent=99.0,
        window_days=30,
        measurement_query="api:latency:p99_under_500ms",
        service="api",
    ),
    SLO(
        id="email_delivery",
        name="Email Delivery Rate",
        description="Email delivery success rate",
        slo_type=SLOType.AVAILABILITY,
        target_percent=98.0,
        window_days=7,
        measurement_query="email:delivery:percent",
        service="email",
    ),
    SLO(
        id="enrichment_success",
        name="Enrichment Success Rate",
        description="Lead enrichment success rate",
        slo_type=SLOType.AVAILABILITY,
        target_percent=95.0,
        window_days=7,
        measurement_query="enrichment:success:percent",
        service="enrichment",
    ),
    SLO(
        id="queue_processing",
        name="Queue Processing Time",
        description="Queue tasks processed within SLA",
        slo_type=SLOType.LATENCY,
        target_percent=99.0,
        window_days=7,
        measurement_query="queue:processing:within_sla",
        service="workers",
    ),
    SLO(
        id="error_rate",
        name="System Error Rate",
        description="Overall system error rate < 1%",
        slo_type=SLOType.ERROR_RATE,
        target_percent=99.0,
        window_days=30,
        measurement_query="system:errors:percent_ok",
        service="system",
    ),
]


class SLOBudgetsService:
    """Service for SLO and error budget management.

    Features:
    - SLO definition and tracking
    - Error budget calculation
    - Burn rate monitoring
    - SLO violation alerts
    - Historical reporting
    """

    SLOS_KEY = "slo:definitions"
    METRICS_PREFIX = "slo:metrics:"
    EVENTS_KEY = "slo:events"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    async def get_slo(self, slo_id: str) -> SLO | None:
        """Get SLO by ID.

        Args:
            slo_id: SLO ID

        Returns:
            SLO if found
        """
        slos = await self.list_slos()
        for slo in slos:
            if slo.id == slo_id:
                return slo
        return None

    async def list_slos(
        self,
        service: str | None = None,
    ) -> list[SLO]:
        """List all SLOs.

        Args:
            service: Filter by service

        Returns:
            List of SLOs
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        raw = await redis.hgetall(self.SLOS_KEY)

        slos = []
        existing_ids = set()

        for key, data in raw.items():
            try:
                d = json.loads(data)
                slo = SLO(
                    id=d["id"],
                    name=d["name"],
                    description=d["description"],
                    slo_type=SLOType(d["slo_type"]),
                    target_percent=d["target_percent"],
                    window_days=d["window_days"],
                    measurement_query=d["measurement_query"],
                    service=d["service"],
                    enabled=d.get("enabled", True),
                    metadata=d.get("metadata", {}),
                )

                if service and slo.service != service:
                    continue

                slos.append(slo)
                existing_ids.add(slo.id)
            except Exception:
                continue

        # Add missing defaults
        for default in DEFAULT_SLOS:
            if default.id not in existing_ids:
                if service and default.service != service:
                    continue
                slos.append(default)

        return slos

    async def create_slo(self, slo: SLO) -> SLO:
        """Create a new SLO.

        Args:
            slo: SLO to create

        Returns:
            Created SLO
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        await redis.hset(self.SLOS_KEY, slo.id, json.dumps(slo.to_dict()))

        logger.info(f"[SLO] Created: {slo.id} ({slo.name})")

        return slo

    async def record_metric(
        self,
        slo_id: str,
        good_events: int,
        total_events: int,
        timestamp: datetime | None = None,
    ) -> None:
        """Record SLO metric data.

        Args:
            slo_id: SLO ID
            good_events: Number of good events
            total_events: Total events
            timestamp: Metric timestamp
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        ts = timestamp or datetime.now(UTC)

        # Store by hour
        hour_key = f"{self.METRICS_PREFIX}{slo_id}:{ts.strftime('%Y-%m-%d-%H')}"

        await redis.hincrby(hour_key, "good", good_events)
        await redis.hincrby(hour_key, "total", total_events)
        await redis.expire(hour_key, 86400 * 35)  # 35 days

    async def get_error_budget(self, slo_id: str) -> ErrorBudget | None:
        """Calculate error budget for an SLO.

        Args:
            slo_id: SLO ID

        Returns:
            Error budget status
        """
        slo = await self.get_slo(slo_id)
        if not slo:
            return None

        now = datetime.now(UTC)
        window_start = now - timedelta(days=slo.window_days)

        # Get metrics for window
        good_total, events_total = await self._get_window_metrics(slo_id, window_start, now)

        if events_total == 0:
            # No data - assume healthy
            return ErrorBudget(
                slo_id=slo.id,
                slo_name=slo.name,
                target_percent=slo.target_percent,
                current_percent=100.0,
                budget_total_minutes=self._calculate_budget_minutes(slo.target_percent, slo.window_days),
                budget_consumed_minutes=0,
                budget_remaining_minutes=self._calculate_budget_minutes(slo.target_percent, slo.window_days),
                budget_remaining_percent=100.0,
                burn_rate=0,
                time_to_exhaustion_hours=None,
                status=SLOStatus.UNKNOWN,
                window_start=window_start,
                window_end=now,
            )

        current_percent = (good_total / events_total) * 100
        budget_total = self._calculate_budget_minutes(slo.target_percent, slo.window_days)

        # Calculate consumed budget
        error_percent = 100 - current_percent
        allowed_error = 100 - slo.target_percent

        if allowed_error > 0:
            budget_consumed_ratio = error_percent / allowed_error
        else:
            budget_consumed_ratio = 1.0 if error_percent > 0 else 0

        budget_consumed = min(budget_total, budget_total * budget_consumed_ratio)
        budget_remaining = max(0, budget_total - budget_consumed)
        budget_remaining_percent = (budget_remaining / budget_total * 100) if budget_total > 0 else 0

        # Calculate burn rate (budget consumed per hour)
        hours_elapsed = (now - window_start).total_seconds() / 3600
        burn_rate = budget_consumed / hours_elapsed if hours_elapsed > 0 else 0

        # Time to exhaustion
        time_to_exhaustion = None
        if burn_rate > 0 and budget_remaining > 0:
            time_to_exhaustion = budget_remaining / burn_rate

        # Determine status
        if budget_remaining_percent <= 0:
            status = SLOStatus.CRITICAL
        elif budget_remaining_percent <= 20:
            status = SLOStatus.WARNING
        else:
            status = SLOStatus.HEALTHY

        # Record event if status changed
        await self._check_status_change(slo_id, status)

        return ErrorBudget(
            slo_id=slo.id,
            slo_name=slo.name,
            target_percent=slo.target_percent,
            current_percent=current_percent,
            budget_total_minutes=budget_total,
            budget_consumed_minutes=budget_consumed,
            budget_remaining_minutes=budget_remaining,
            budget_remaining_percent=budget_remaining_percent,
            burn_rate=burn_rate,
            time_to_exhaustion_hours=time_to_exhaustion,
            status=status,
            window_start=window_start,
            window_end=now,
        )

    async def _get_window_metrics(
        self,
        slo_id: str,
        start: datetime,
        end: datetime,
    ) -> tuple[int, int]:
        """Get aggregated metrics for a time window."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        good_total = 0
        events_total = 0

        current = start
        while current <= end:
            hour_key = f"{self.METRICS_PREFIX}{slo_id}:{current.strftime('%Y-%m-%d-%H')}"
            data = await redis.hgetall(hour_key)

            good_total += int(data.get("good", 0))
            events_total += int(data.get("total", 0))

            current += timedelta(hours=1)

        return good_total, events_total

    def _calculate_budget_minutes(
        self,
        target_percent: float,
        window_days: int,
    ) -> float:
        """Calculate total error budget in minutes."""
        total_minutes = window_days * 24 * 60
        allowed_error_percent = 100 - target_percent
        return total_minutes * (allowed_error_percent / 100)

    async def _check_status_change(
        self,
        slo_id: str,
        new_status: SLOStatus,
    ) -> None:
        """Check if status changed and record event."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        status_key = f"slo:status:{slo_id}"

        old_status = await redis.get(status_key)

        if old_status != new_status.value:
            await redis.set(status_key, new_status.value, ex=86400)

            if old_status:
                event_type = "violation" if new_status == SLOStatus.CRITICAL else "status_change"

                event = SLOEvent(
                    slo_id=slo_id,
                    event_type=event_type,
                    timestamp=datetime.now(UTC),
                    details={
                        "previous_status": old_status,
                        "new_status": new_status.value,
                    },
                )

                await redis.zadd(
                    self.EVENTS_KEY,
                    {json.dumps(event.to_dict()): event.timestamp.timestamp()},
                )

                logger.warning(
                    f"[SLO] Status change: {slo_id} {old_status} -> {new_status.value}"
                )

    async def get_all_budgets(self) -> list[ErrorBudget]:
        """Get error budgets for all SLOs.

        Returns:
            List of error budgets
        """
        slos = await self.list_slos()
        budgets = []

        for slo in slos:
            if slo.enabled:
                budget = await self.get_error_budget(slo.id)
                if budget:
                    budgets.append(budget)

        return budgets

    async def generate_report(
        self,
        period_days: int = 30,
    ) -> SLOReport:
        """Generate SLO report.

        Args:
            period_days: Report period

        Returns:
            SLO report
        """
        now = datetime.now(UTC)
        budgets = await self.get_all_budgets()

        slos = []
        meeting_target = 0
        at_risk = 0
        breached = 0

        for budget in budgets:
            slos.append(budget.to_dict())

            if budget.status == SLOStatus.HEALTHY:
                meeting_target += 1
            elif budget.status == SLOStatus.WARNING:
                at_risk += 1
            elif budget.status == SLOStatus.CRITICAL:
                breached += 1

        # Determine overall health
        if breached > 0:
            overall = SLOStatus.CRITICAL
        elif at_risk > 0:
            overall = SLOStatus.WARNING
        elif meeting_target > 0:
            overall = SLOStatus.HEALTHY
        else:
            overall = SLOStatus.UNKNOWN

        # Generate recommendations
        recommendations = []
        for budget in budgets:
            if budget.status == SLOStatus.CRITICAL:
                recommendations.append(
                    f"CRITICAL: {budget.slo_name} budget exhausted. "
                    "Consider feature freezes."
                )
            elif budget.status == SLOStatus.WARNING:
                if budget.time_to_exhaustion_hours:
                    recommendations.append(
                        f"WARNING: {budget.slo_name} budget depleting. "
                        f"~{budget.time_to_exhaustion_hours:.0f}h remaining."
                    )
            if budget.burn_rate > 1.0:
                recommendations.append(
                    f"High burn rate on {budget.slo_name}: "
                    f"{budget.burn_rate:.2f} min/hour"
                )

        return SLOReport(
            generated_at=now,
            period_days=period_days,
            slos=slos,
            overall_health=overall,
            slos_meeting_target=meeting_target,
            slos_at_risk=at_risk,
            slos_breached=breached,
            recommendations=recommendations,
        )

    async def get_events(
        self,
        slo_id: str | None = None,
        hours: int = 24,
        limit: int = 100,
    ) -> list[SLOEvent]:
        """Get SLO events.

        Args:
            slo_id: Filter by SLO
            hours: Hours to look back
            limit: Max events

        Returns:
            List of events
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)
        min_ts = (now - timedelta(hours=hours)).timestamp()

        raw = await redis.zrevrangebyscore(
            self.EVENTS_KEY,
            "+inf",
            min_ts,
            start=0,
            num=limit,
        )

        events = []
        for item in raw:
            try:
                data = json.loads(item)

                if slo_id and data["slo_id"] != slo_id:
                    continue

                events.append(SLOEvent(
                    slo_id=data["slo_id"],
                    event_type=data["event_type"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    details=data["details"],
                ))
            except Exception:
                continue

        return events


# Singleton
slo_budgets = SLOBudgetsService()
