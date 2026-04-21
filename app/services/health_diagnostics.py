"""Health Diagnostics Service.

Deep health checks, SLA monitoring, and alerting.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(str, Enum):
    """System component types."""

    DATABASE = "database"
    REDIS = "redis"
    CELERY = "celery"
    LLM = "llm"
    EMAIL = "email"
    EXTERNAL_API = "external_api"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of alerts."""

    SLA_BREACH = "sla_breach"
    SLA_WARNING = "sla_warning"
    COMPONENT_DOWN = "component_down"
    COMPONENT_DEGRADED = "component_degraded"
    HIGH_ERROR_RATE = "high_error_rate"
    QUEUE_BACKLOG = "queue_backlog"
    CAPACITY_WARNING = "capacity_warning"
    ANOMALY_DETECTED = "anomaly_detected"


@dataclass
class ComponentHealth:
    """Health of a system component."""

    component: ComponentType
    status: HealthStatus
    response_time_ms: float | None
    last_check: datetime
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component.value,
            "status": self.status.value,
            "response_time_ms": self.response_time_ms,
            "last_check": self.last_check.isoformat(),
            "message": self.message,
            "details": self.details,
        }


@dataclass
class SystemHealth:
    """Overall system health."""

    status: HealthStatus
    checked_at: datetime
    components: list[ComponentHealth]
    healthy_count: int
    degraded_count: int
    unhealthy_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "checked_at": self.checked_at.isoformat(),
            "components": [c.to_dict() for c in self.components],
            "healthy_count": self.healthy_count,
            "degraded_count": self.degraded_count,
            "unhealthy_count": self.unhealthy_count,
        }


@dataclass
class SLAMetric:
    """SLA metric definition and status."""

    name: str
    target_value: float
    current_value: float
    unit: str
    is_met: bool
    threshold_warning: float
    threshold_critical: float
    period_hours: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target_value": self.target_value,
            "current_value": self.current_value,
            "unit": self.unit,
            "is_met": self.is_met,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical,
            "period_hours": self.period_hours,
        }


@dataclass
class Alert:
    """System alert."""

    id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    created_at: datetime
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved: bool = False
    resolved_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
        }


# SLA Definitions
SLA_DEFINITIONS = [
    {
        "name": "handoff_response_time",
        "description": "Time to first action on handoff",
        "target_value": 4.0,
        "unit": "hours",
        "threshold_warning": 3.0,
        "threshold_critical": 4.0,
        "period_hours": 24,
    },
    {
        "name": "email_delivery_rate",
        "description": "Percentage of emails successfully delivered",
        "target_value": 95.0,
        "unit": "percent",
        "threshold_warning": 90.0,
        "threshold_critical": 85.0,
        "period_hours": 24,
    },
    {
        "name": "system_uptime",
        "description": "System availability",
        "target_value": 99.9,
        "unit": "percent",
        "threshold_warning": 99.5,
        "threshold_critical": 99.0,
        "period_hours": 24,
    },
    {
        "name": "api_response_time",
        "description": "Average API response time",
        "target_value": 500.0,
        "unit": "ms",
        "threshold_warning": 400.0,
        "threshold_critical": 500.0,
        "period_hours": 1,
    },
    {
        "name": "error_rate",
        "description": "Percentage of requests resulting in errors",
        "target_value": 1.0,
        "unit": "percent",
        "threshold_warning": 0.5,
        "threshold_critical": 1.0,
        "period_hours": 1,
    },
]


class HealthDiagnosticsService:
    """Service for health diagnostics and alerting.

    Features:
    - Component health checks
    - SLA monitoring
    - Alert management
    - System diagnostics
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Health Checks
    # ========================================================================

    async def check_system_health(self) -> SystemHealth:
        """Check health of all system components.

        Returns:
            SystemHealth
        """
        now = datetime.now(UTC)
        components = []

        # Check Redis
        components.append(await self._check_redis())

        # Check Celery
        components.append(await self._check_celery())

        # Calculate overall status
        healthy = sum(1 for c in components if c.status == HealthStatus.HEALTHY)
        degraded = sum(1 for c in components if c.status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for c in components if c.status == HealthStatus.UNHEALTHY)

        if unhealthy > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        return SystemHealth(
            status=overall_status,
            checked_at=now,
            components=components,
            healthy_count=healthy,
            degraded_count=degraded,
            unhealthy_count=unhealthy,
        )

    async def _check_redis(self) -> ComponentHealth:
        """Check Redis health."""
        import time

        now = datetime.now(UTC)

        try:
            from app.storage.redis import get_redis

            start = time.time()
            redis = await get_redis()
            await redis.ping()
            response_time = (time.time() - start) * 1000

            # Check memory usage
            info = await redis.info("memory")
            used_memory = info.get("used_memory", 0)
            max_memory = info.get("maxmemory", 0)

            if max_memory > 0:
                memory_usage = (used_memory / max_memory) * 100
                if memory_usage > 90:
                    return ComponentHealth(
                        component=ComponentType.REDIS,
                        status=HealthStatus.DEGRADED,
                        response_time_ms=response_time,
                        last_check=now,
                        message=f"High memory usage: {memory_usage:.1f}%",
                        details={"memory_usage_percent": memory_usage},
                    )

            return ComponentHealth(
                component=ComponentType.REDIS,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                last_check=now,
                message="Redis is healthy",
                details={"used_memory_mb": used_memory / 1024 / 1024},
            )

        except Exception as e:
            return ComponentHealth(
                component=ComponentType.REDIS,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=None,
                last_check=now,
                message=f"Redis check failed: {str(e)}",
            )

    async def _check_celery(self) -> ComponentHealth:
        """Check Celery health."""
        now = datetime.now(UTC)

        try:
            from app.storage.redis import get_redis

            redis = await get_redis()

            # Check queue lengths
            queues = ["celery", "high_priority", "low_priority"]
            total_tasks = 0

            for queue in queues:
                length = await redis.llen(queue)
                total_tasks += length

            if total_tasks > 1000:
                return ComponentHealth(
                    component=ComponentType.CELERY,
                    status=HealthStatus.DEGRADED,
                    response_time_ms=None,
                    last_check=now,
                    message=f"High queue backlog: {total_tasks} tasks",
                    details={"total_queued_tasks": total_tasks},
                )

            return ComponentHealth(
                component=ComponentType.CELERY,
                status=HealthStatus.HEALTHY,
                response_time_ms=None,
                last_check=now,
                message="Celery queues healthy",
                details={"total_queued_tasks": total_tasks},
            )

        except Exception as e:
            return ComponentHealth(
                component=ComponentType.CELERY,
                status=HealthStatus.UNKNOWN,
                response_time_ms=None,
                last_check=now,
                message=f"Celery check failed: {str(e)}",
            )

    async def check_component(
        self,
        component: ComponentType,
    ) -> ComponentHealth:
        """Check specific component health.

        Args:
            component: Component to check

        Returns:
            ComponentHealth
        """
        if component == ComponentType.REDIS:
            return await self._check_redis()
        elif component == ComponentType.CELERY:
            return await self._check_celery()
        else:
            return ComponentHealth(
                component=component,
                status=HealthStatus.UNKNOWN,
                response_time_ms=None,
                last_check=datetime.now(UTC),
                message="Component check not implemented",
            )

    # ========================================================================
    # SLA Monitoring
    # ========================================================================

    async def get_sla_status(self) -> list[SLAMetric]:
        """Get status of all SLA metrics.

        Returns:
            List of SLA metrics
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        metrics = []

        for sla in SLA_DEFINITIONS:
            name = sla["name"]
            target = sla["target_value"]
            warning = sla["threshold_warning"]
            critical = sla["threshold_critical"]
            period = sla["period_hours"]
            unit = sla["unit"]

            # Get current value from Redis
            current = float(await redis.get(f"sla:current:{name}") or 0)

            # Determine if SLA is met (depends on direction)
            if unit == "percent" and "rate" in name.lower():
                # Higher is better (delivery rate, uptime)
                is_met = current >= target
            elif unit == "percent" and "error" in name.lower():
                # Lower is better (error rate)
                is_met = current <= target
            elif unit in ("ms", "hours"):
                # Lower is better (response time)
                is_met = current <= target
            else:
                is_met = current >= target

            metrics.append(SLAMetric(
                name=name,
                target_value=target,
                current_value=current,
                unit=unit,
                is_met=is_met,
                threshold_warning=warning,
                threshold_critical=critical,
                period_hours=period,
            ))

        return metrics

    async def update_sla_metric(
        self,
        name: str,
        value: float,
    ) -> None:
        """Update an SLA metric value.

        Args:
            name: Metric name
            value: Current value
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        await redis.set(f"sla:current:{name}", str(value), ex=86400)

        # Track history
        now = datetime.now(UTC)
        await redis.zadd(
            f"sla:history:{name}",
            {f"{now.timestamp()}:{value}": now.timestamp()},
        )
        await redis.expire(f"sla:history:{name}", 86400 * 7)

    async def check_sla_breaches(self) -> list[Alert]:
        """Check for SLA breaches and create alerts.

        Returns:
            List of breach alerts
        """
        from uuid import uuid4

        metrics = await self.get_sla_status()
        alerts = []
        now = datetime.now(UTC)

        for metric in metrics:
            if not metric.is_met:
                # Determine severity
                if metric.unit in ("ms", "hours"):
                    # Lower is better
                    if metric.current_value >= metric.threshold_critical:
                        severity = AlertSeverity.CRITICAL
                    elif metric.current_value >= metric.threshold_warning:
                        severity = AlertSeverity.WARNING
                    else:
                        continue
                else:
                    # Higher is better
                    if metric.current_value <= metric.threshold_critical:
                        severity = AlertSeverity.CRITICAL
                    elif metric.current_value <= metric.threshold_warning:
                        severity = AlertSeverity.WARNING
                    else:
                        continue

                alert = Alert(
                    id=str(uuid4()),
                    alert_type=AlertType.SLA_BREACH if severity == AlertSeverity.CRITICAL else AlertType.SLA_WARNING,
                    severity=severity,
                    title=f"SLA Breach: {metric.name}",
                    message=f"{metric.name} is {metric.current_value}{metric.unit} (target: {metric.target_value}{metric.unit})",
                    created_at=now,
                    metadata={
                        "metric_name": metric.name,
                        "current_value": metric.current_value,
                        "target_value": metric.target_value,
                    },
                )
                alerts.append(alert)

                await self._store_alert(alert)

        return alerts

    # ========================================================================
    # Alert Management
    # ========================================================================

    async def create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> Alert:
        """Create a new alert.

        Args:
            alert_type: Type of alert
            severity: Alert severity
            title: Alert title
            message: Alert message
            metadata: Additional metadata

        Returns:
            Created alert
        """
        from uuid import uuid4

        now = datetime.now(UTC)

        alert = Alert(
            id=str(uuid4()),
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            created_at=now,
            metadata=metadata or {},
        )

        await self._store_alert(alert)

        logger.warning(
            f"[Alert] Created | type={alert_type.value} | "
            f"severity={severity.value} | {title}"
        )

        return alert

    async def _store_alert(self, alert: Alert) -> None:
        """Store alert in Redis."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        await redis.set(
            f"alert:{alert.id}",
            json.dumps(alert.to_dict()),
            ex=86400 * 7,
        )

        await redis.zadd(
            "alerts:timeline",
            {alert.id: alert.created_at.timestamp()},
        )
        await redis.expire("alerts:timeline", 86400 * 7)

        if not alert.acknowledged:
            await redis.sadd("alerts:unacknowledged", alert.id)
            await redis.expire("alerts:unacknowledged", 86400 * 7)

    async def get_alert(self, alert_id: str) -> Alert | None:
        """Get alert by ID."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        data = await redis.get(f"alert:{alert_id}")

        if not data:
            return None

        d = json.loads(data)
        return Alert(
            id=d["id"],
            alert_type=AlertType(d["alert_type"]),
            severity=AlertSeverity(d["severity"]),
            title=d["title"],
            message=d["message"],
            created_at=datetime.fromisoformat(d["created_at"]),
            acknowledged=d.get("acknowledged", False),
            acknowledged_by=d.get("acknowledged_by"),
            acknowledged_at=datetime.fromisoformat(d["acknowledged_at"]) if d.get("acknowledged_at") else None,
            resolved=d.get("resolved", False),
            resolved_at=datetime.fromisoformat(d["resolved_at"]) if d.get("resolved_at") else None,
            metadata=d.get("metadata", {}),
        )

    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
    ) -> Alert | None:
        """Acknowledge an alert.

        Args:
            alert_id: Alert ID
            acknowledged_by: User who acknowledged

        Returns:
            Updated alert
        """
        from app.storage.redis import get_redis
        import json

        alert = await self.get_alert(alert_id)
        if not alert:
            return None

        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.now(UTC)

        redis = await get_redis()
        await redis.set(
            f"alert:{alert_id}",
            json.dumps(alert.to_dict()),
            ex=86400 * 7,
        )
        await redis.srem("alerts:unacknowledged", alert_id)

        logger.info(f"[Alert] Acknowledged | id={alert_id} | by={acknowledged_by}")

        return alert

    async def resolve_alert(self, alert_id: str) -> Alert | None:
        """Resolve an alert.

        Args:
            alert_id: Alert ID

        Returns:
            Updated alert
        """
        from app.storage.redis import get_redis
        import json

        alert = await self.get_alert(alert_id)
        if not alert:
            return None

        alert.resolved = True
        alert.resolved_at = datetime.now(UTC)

        redis = await get_redis()
        await redis.set(
            f"alert:{alert_id}",
            json.dumps(alert.to_dict()),
            ex=86400 * 7,
        )

        logger.info(f"[Alert] Resolved | id={alert_id}")

        return alert

    async def get_active_alerts(
        self,
        severity: AlertSeverity | None = None,
        limit: int = 50,
    ) -> list[Alert]:
        """Get active (unresolved) alerts.

        Args:
            severity: Filter by severity
            limit: Max results

        Returns:
            List of alerts
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        alert_ids = await redis.zrevrange("alerts:timeline", 0, limit * 2)

        alerts = []
        for alert_id in alert_ids:
            if len(alerts) >= limit:
                break

            alert = await self.get_alert(alert_id)
            if not alert or alert.resolved:
                continue

            if severity and alert.severity != severity:
                continue

            alerts.append(alert)

        return alerts

    async def get_unacknowledged_count(self) -> int:
        """Get count of unacknowledged alerts."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        return await redis.scard("alerts:unacknowledged") or 0


# Singleton
health_service = HealthDiagnosticsService()
