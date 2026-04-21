"""Maintenance Mode Service.

Readiness and maintenance mode management for graceful operations.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class SystemState(str, Enum):
    """System operational states."""

    RUNNING = "running"
    MAINTENANCE = "maintenance"
    DEGRADED = "degraded"
    STARTING = "starting"
    STOPPING = "stopping"


class ReadinessState(str, Enum):
    """Readiness probe states."""

    READY = "ready"
    NOT_READY = "not_ready"
    DRAINING = "draining"


@dataclass
class MaintenanceWindow:
    """Scheduled maintenance window."""

    id: str
    reason: str
    scheduled_by: str
    scheduled_at: datetime
    start_time: datetime
    end_time: datetime | None
    affected_services: list[str]
    notify_users: bool
    auto_recover: bool
    is_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "reason": self.reason,
            "scheduled_by": self.scheduled_by,
            "scheduled_at": self.scheduled_at.isoformat(),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "affected_services": self.affected_services,
            "notify_users": self.notify_users,
            "auto_recover": self.auto_recover,
            "is_active": self.is_active,
        }


@dataclass
class SystemStatus:
    """Current system status."""

    state: SystemState
    readiness: ReadinessState
    maintenance_mode: bool
    maintenance_reason: str | None
    maintenance_started_at: datetime | None
    maintenance_by: str | None
    services_healthy: dict[str, bool]
    active_connections: int
    pending_requests: int
    checked_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "readiness": self.readiness.value,
            "maintenance_mode": self.maintenance_mode,
            "maintenance_reason": self.maintenance_reason,
            "maintenance_started_at": (
                self.maintenance_started_at.isoformat()
                if self.maintenance_started_at
                else None
            ),
            "maintenance_by": self.maintenance_by,
            "services_healthy": self.services_healthy,
            "active_connections": self.active_connections,
            "pending_requests": self.pending_requests,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass
class DrainStatus:
    """Connection drain status during maintenance."""

    is_draining: bool
    drain_started_at: datetime | None
    initial_connections: int
    current_connections: int
    drain_timeout_seconds: int
    estimated_completion: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_draining": self.is_draining,
            "drain_started_at": (
                self.drain_started_at.isoformat() if self.drain_started_at else None
            ),
            "initial_connections": self.initial_connections,
            "current_connections": self.current_connections,
            "drain_timeout_seconds": self.drain_timeout_seconds,
            "estimated_completion": (
                self.estimated_completion.isoformat()
                if self.estimated_completion
                else None
            ),
        }


class MaintenanceModeService:
    """Service for maintenance mode and readiness management.

    Features:
    - Maintenance mode toggle
    - Graceful connection draining
    - Readiness probes for k8s
    - Scheduled maintenance windows
    - Service health tracking
    """

    # Redis keys
    MAINTENANCE_KEY = "system:maintenance:active"
    MAINTENANCE_REASON_KEY = "system:maintenance:reason"
    MAINTENANCE_BY_KEY = "system:maintenance:by"
    MAINTENANCE_START_KEY = "system:maintenance:started_at"
    DRAIN_KEY = "system:drain:active"
    DRAIN_START_KEY = "system:drain:started_at"
    DRAIN_INITIAL_KEY = "system:drain:initial_connections"
    WINDOWS_KEY = "system:maintenance:windows"
    SERVICE_HEALTH_PREFIX = "system:service:health:"

    def __init__(self) -> None:
        """Initialize service."""
        self._drain_timeout = 300  # 5 minutes

    async def enter_maintenance_mode(
        self,
        reason: str,
        actor: str,
        drain_connections: bool = True,
        notify: bool = True,
    ) -> dict[str, Any]:
        """Enter maintenance mode.

        Args:
            reason: Why entering maintenance
            actor: Who initiated maintenance
            drain_connections: Whether to drain existing connections
            notify: Whether to notify about maintenance

        Returns:
            Maintenance status
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Set maintenance flags
        await redis.set(self.MAINTENANCE_KEY, "true")
        await redis.set(self.MAINTENANCE_REASON_KEY, reason)
        await redis.set(self.MAINTENANCE_BY_KEY, actor)
        await redis.set(self.MAINTENANCE_START_KEY, now.isoformat())

        if drain_connections:
            # Start draining
            connections = int(await redis.get("system:active_connections") or 0)
            await redis.set(self.DRAIN_KEY, "true")
            await redis.set(self.DRAIN_START_KEY, now.isoformat())
            await redis.set(self.DRAIN_INITIAL_KEY, str(connections))

        logger.warning(
            f"[Maintenance] Entered maintenance mode: {reason} by {actor}"
        )

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="enter_maintenance",
                actor=actor,
                details={
                    "reason": reason,
                    "drain_connections": drain_connections,
                    "notify": notify,
                },
                severity="critical",
            )
        except Exception:
            pass  # Journal not critical

        return {
            "status": "maintenance_mode_active",
            "reason": reason,
            "started_at": now.isoformat(),
            "draining": drain_connections,
        }

    async def exit_maintenance_mode(
        self,
        actor: str,
    ) -> dict[str, Any]:
        """Exit maintenance mode.

        Args:
            actor: Who is exiting maintenance

        Returns:
            Exit status
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Get maintenance info before clearing
        reason = await redis.get(self.MAINTENANCE_REASON_KEY)
        started = await redis.get(self.MAINTENANCE_START_KEY)

        # Clear all maintenance flags
        await redis.delete(self.MAINTENANCE_KEY)
        await redis.delete(self.MAINTENANCE_REASON_KEY)
        await redis.delete(self.MAINTENANCE_BY_KEY)
        await redis.delete(self.MAINTENANCE_START_KEY)
        await redis.delete(self.DRAIN_KEY)
        await redis.delete(self.DRAIN_START_KEY)
        await redis.delete(self.DRAIN_INITIAL_KEY)

        duration_seconds = None
        if started:
            try:
                start_dt = datetime.fromisoformat(started)
                duration_seconds = (datetime.now(UTC) - start_dt).total_seconds()
            except Exception:
                pass

        logger.info(f"[Maintenance] Exited maintenance mode by {actor}")

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="exit_maintenance",
                actor=actor,
                details={
                    "previous_reason": reason,
                    "duration_seconds": duration_seconds,
                },
                severity="critical",
            )
        except Exception:
            pass

        return {
            "status": "running",
            "previous_reason": reason,
            "duration_seconds": duration_seconds,
        }

    async def get_status(self) -> SystemStatus:
        """Get current system status.

        Returns:
            SystemStatus
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Check maintenance mode
        maintenance = await redis.get(self.MAINTENANCE_KEY) == "true"
        reason = await redis.get(self.MAINTENANCE_REASON_KEY)
        by = await redis.get(self.MAINTENANCE_BY_KEY)
        started_str = await redis.get(self.MAINTENANCE_START_KEY)
        started = None
        if started_str:
            try:
                started = datetime.fromisoformat(started_str)
            except Exception:
                pass

        # Check draining
        draining = await redis.get(self.DRAIN_KEY) == "true"

        # Determine state and readiness
        if maintenance:
            state = SystemState.MAINTENANCE
            readiness = ReadinessState.DRAINING if draining else ReadinessState.NOT_READY
        else:
            state = SystemState.RUNNING
            readiness = ReadinessState.READY

        # Get service health
        services_healthy = {}
        for service in ["redis", "postgres", "celery", "api"]:
            health = await redis.get(f"{self.SERVICE_HEALTH_PREFIX}{service}")
            services_healthy[service] = health != "false"

        # Get connection counts
        active = int(await redis.get("system:active_connections") or 0)
        pending = int(await redis.get("system:pending_requests") or 0)

        return SystemStatus(
            state=state,
            readiness=readiness,
            maintenance_mode=maintenance,
            maintenance_reason=reason,
            maintenance_started_at=started,
            maintenance_by=by,
            services_healthy=services_healthy,
            active_connections=active,
            pending_requests=pending,
            checked_at=now,
        )

    async def get_drain_status(self) -> DrainStatus:
        """Get connection drain status.

        Returns:
            DrainStatus
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        draining = await redis.get(self.DRAIN_KEY) == "true"
        started_str = await redis.get(self.DRAIN_START_KEY)
        initial = int(await redis.get(self.DRAIN_INITIAL_KEY) or 0)
        current = int(await redis.get("system:active_connections") or 0)

        started = None
        estimated = None
        if started_str:
            try:
                started = datetime.fromisoformat(started_str)
                # Estimate completion based on drain rate
                if initial > 0 and current < initial:
                    elapsed = (datetime.now(UTC) - started).total_seconds()
                    drained = initial - current
                    rate = drained / elapsed if elapsed > 0 else 1
                    remaining = current / rate if rate > 0 else self._drain_timeout
                    estimated = datetime.now(UTC) + __import__("datetime").timedelta(
                        seconds=min(remaining, self._drain_timeout)
                    )
            except Exception:
                pass

        return DrainStatus(
            is_draining=draining,
            drain_started_at=started,
            initial_connections=initial,
            current_connections=current,
            drain_timeout_seconds=self._drain_timeout,
            estimated_completion=estimated,
        )

    async def is_ready(self) -> bool:
        """Check if system is ready (for k8s readiness probe).

        Returns:
            True if ready
        """
        status = await self.get_status()
        return status.readiness == ReadinessState.READY

    async def is_live(self) -> bool:
        """Check if system is alive (for k8s liveness probe).

        Returns:
            True if alive
        """
        from app.storage.redis import get_redis

        try:
            redis = await get_redis()
            await redis.ping()
            return True
        except Exception:
            return False

    async def set_service_health(
        self,
        service: str,
        healthy: bool,
    ) -> None:
        """Set service health status.

        Args:
            service: Service name
            healthy: Whether healthy
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        await redis.set(
            f"{self.SERVICE_HEALTH_PREFIX}{service}",
            "true" if healthy else "false",
            ex=60,  # 1 min TTL
        )

    async def schedule_maintenance(
        self,
        window: MaintenanceWindow,
    ) -> str:
        """Schedule a maintenance window.

        Args:
            window: Maintenance window details

        Returns:
            Window ID
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Store window
        await redis.zadd(
            self.WINDOWS_KEY,
            {json.dumps(window.to_dict()): window.start_time.timestamp()},
        )

        logger.info(
            f"[Maintenance] Scheduled window {window.id}: "
            f"{window.reason} at {window.start_time}"
        )

        return window.id

    async def get_scheduled_windows(
        self,
        include_past: bool = False,
    ) -> list[MaintenanceWindow]:
        """Get scheduled maintenance windows.

        Args:
            include_past: Whether to include past windows

        Returns:
            List of maintenance windows
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        now = datetime.now(UTC)
        if include_past:
            min_score = "-inf"
        else:
            min_score = now.timestamp()

        raw = await redis.zrangebyscore(
            self.WINDOWS_KEY,
            min_score,
            "+inf",
        )

        windows = []
        for item in raw:
            try:
                data = json.loads(item)
                windows.append(
                    MaintenanceWindow(
                        id=data["id"],
                        reason=data["reason"],
                        scheduled_by=data["scheduled_by"],
                        scheduled_at=datetime.fromisoformat(data["scheduled_at"]),
                        start_time=datetime.fromisoformat(data["start_time"]),
                        end_time=(
                            datetime.fromisoformat(data["end_time"])
                            if data.get("end_time")
                            else None
                        ),
                        affected_services=data["affected_services"],
                        notify_users=data["notify_users"],
                        auto_recover=data["auto_recover"],
                        is_active=data.get("is_active", False),
                    )
                )
            except Exception as e:
                logger.error(f"[Maintenance] Failed to parse window: {e}")

        return windows


# Singleton
maintenance_mode = MaintenanceModeService()
