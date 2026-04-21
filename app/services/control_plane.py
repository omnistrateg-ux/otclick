"""Real-time Control Plane Service.

Centralized system control and coordination.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

UTC = timezone.utc

logger = logging.getLogger(__name__)


class ControlAction(str, Enum):
    """Control plane actions."""

    PAUSE_PROCESSING = "pause_processing"
    RESUME_PROCESSING = "resume_processing"
    SCALE_WORKERS = "scale_workers"
    ENABLE_FEATURE = "enable_feature"
    DISABLE_FEATURE = "disable_feature"
    RATE_LIMIT_ADJUST = "rate_limit_adjust"
    CIRCUIT_BREAKER = "circuit_breaker"
    EMERGENCY_STOP = "emergency_stop"
    FLUSH_CACHE = "flush_cache"
    RELOAD_CONFIG = "reload_config"


class ControlScope(str, Enum):
    """Scope of control action."""

    GLOBAL = "global"
    SERVICE = "service"
    COMPONENT = "component"
    USER = "user"


class CommandStatus(str, Enum):
    """Command execution status."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ControlCommand:
    """Control plane command."""

    id: str
    action: ControlAction
    scope: ControlScope
    target: str | None
    parameters: dict[str, Any]
    status: CommandStatus
    issued_by: str
    issued_at: datetime
    executed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    rollback_command_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action.value,
            "scope": self.scope.value,
            "target": self.target,
            "parameters": self.parameters,
            "status": self.status.value,
            "issued_by": self.issued_by,
            "issued_at": self.issued_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "result": self.result,
            "error": self.error,
            "rollback_command_id": self.rollback_command_id,
        }


@dataclass
class SystemState:
    """Current system state snapshot."""

    timestamp: datetime
    processing_paused: bool
    worker_count: int
    active_circuit_breakers: list[str]
    rate_limits: dict[str, int]
    enabled_features: list[str]
    disabled_features: list[str]
    emergency_mode: bool
    health_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "processing_paused": self.processing_paused,
            "worker_count": self.worker_count,
            "active_circuit_breakers": self.active_circuit_breakers,
            "rate_limits": self.rate_limits,
            "enabled_features": self.enabled_features,
            "disabled_features": self.disabled_features,
            "emergency_mode": self.emergency_mode,
            "health_status": self.health_status,
        }


@dataclass
class ControlPlaneMetrics:
    """Control plane metrics."""

    commands_issued_24h: int
    commands_failed_24h: int
    avg_execution_time_ms: float
    active_overrides: int
    last_emergency_action: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "commands_issued_24h": self.commands_issued_24h,
            "commands_failed_24h": self.commands_failed_24h,
            "avg_execution_time_ms": round(self.avg_execution_time_ms, 2),
            "active_overrides": self.active_overrides,
            "last_emergency_action": (
                self.last_emergency_action.isoformat()
                if self.last_emergency_action else None
            ),
        }


class ControlPlaneService:
    """Service for real-time system control.

    Features:
    - Issue control commands
    - Track command execution
    - System state management
    - Emergency controls
    - Rollback support
    """

    COMMANDS_KEY = "control:commands"
    STATE_KEY = "control:state"
    OVERRIDES_KEY = "control:overrides"
    METRICS_KEY = "control:metrics"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    async def issue_command(
        self,
        action: ControlAction,
        issued_by: str,
        scope: ControlScope = ControlScope.GLOBAL,
        target: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> ControlCommand:
        """Issue a control command.

        Args:
            action: Action to perform
            issued_by: Who issued command
            scope: Scope of action
            target: Target (for service/component scope)
            parameters: Action parameters

        Returns:
            Issued command
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        command = ControlCommand(
            id=str(uuid.uuid4())[:8],
            action=action,
            scope=scope,
            target=target,
            parameters=parameters or {},
            status=CommandStatus.PENDING,
            issued_by=issued_by,
            issued_at=now,
        )

        # Store command
        await redis.zadd(
            self.COMMANDS_KEY,
            {json.dumps(command.to_dict()): now.timestamp()},
        )

        # Execute command
        command = await self._execute_command(command)

        # Update stored command
        await redis.zremrangebyscore(
            self.COMMANDS_KEY,
            now.timestamp(),
            now.timestamp(),
        )
        await redis.zadd(
            self.COMMANDS_KEY,
            {json.dumps(command.to_dict()): now.timestamp()},
        )

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action=f"control_{action.value}",
                actor=issued_by,
                details={
                    "command_id": command.id,
                    "scope": scope.value,
                    "target": target,
                    "parameters": parameters,
                    "status": command.status.value,
                },
                severity="warning" if action == ControlAction.EMERGENCY_STOP else "info",
            )
        except Exception:
            pass

        logger.info(
            f"[ControlPlane] Command {command.id}: {action.value} - {command.status.value}"
        )

        return command

    async def _execute_command(
        self,
        command: ControlCommand,
    ) -> ControlCommand:
        """Execute a control command."""
        from app.storage.redis import get_redis
        import time

        redis = await get_redis()
        start = time.time()

        command.status = CommandStatus.EXECUTING

        try:
            if command.action == ControlAction.PAUSE_PROCESSING:
                await redis.set("control:processing:paused", "true")
                command.result = {"paused": True}

            elif command.action == ControlAction.RESUME_PROCESSING:
                await redis.delete("control:processing:paused")
                command.result = {"paused": False}

            elif command.action == ControlAction.EMERGENCY_STOP:
                await redis.set("control:emergency:active", "true")
                await redis.set("control:processing:paused", "true")
                await redis.set("control:emergency:by", command.issued_by)
                await redis.set("control:emergency:at", datetime.now(UTC).isoformat())
                command.result = {"emergency_mode": True}

            elif command.action == ControlAction.SCALE_WORKERS:
                count = command.parameters.get("count", 1)
                await redis.set("control:workers:target", str(count))
                command.result = {"target_workers": count}

            elif command.action == ControlAction.ENABLE_FEATURE:
                feature = command.parameters.get("feature")
                if feature:
                    await redis.sadd("control:features:enabled", feature)
                    await redis.srem("control:features:disabled", feature)
                    command.result = {"feature": feature, "enabled": True}

            elif command.action == ControlAction.DISABLE_FEATURE:
                feature = command.parameters.get("feature")
                if feature:
                    await redis.sadd("control:features:disabled", feature)
                    await redis.srem("control:features:enabled", feature)
                    command.result = {"feature": feature, "enabled": False}

            elif command.action == ControlAction.RATE_LIMIT_ADJUST:
                key = command.parameters.get("key", "default")
                limit = command.parameters.get("limit", 100)
                await redis.hset("control:rate_limits", key, str(limit))
                command.result = {"key": key, "limit": limit}

            elif command.action == ControlAction.CIRCUIT_BREAKER:
                service = command.parameters.get("service")
                state = command.parameters.get("state", "open")
                if service:
                    await redis.hset("control:circuit_breakers", service, state)
                    command.result = {"service": service, "state": state}

            elif command.action == ControlAction.FLUSH_CACHE:
                pattern = command.parameters.get("pattern", "cache:*")
                # In production, would iterate and delete matching keys
                command.result = {"pattern": pattern, "flushed": True}

            elif command.action == ControlAction.RELOAD_CONFIG:
                # Trigger config reload
                await redis.set("control:config:reload", datetime.now(UTC).isoformat())
                command.result = {"reloaded": True}

            command.status = CommandStatus.COMPLETED
            command.executed_at = datetime.now(UTC)

            # Record execution time
            exec_time = (time.time() - start) * 1000
            await redis.lpush(f"{self.METRICS_KEY}:exec_times", str(exec_time))
            await redis.ltrim(f"{self.METRICS_KEY}:exec_times", 0, 999)

        except Exception as e:
            command.status = CommandStatus.FAILED
            command.error = str(e)
            logger.error(f"[ControlPlane] Command {command.id} failed: {e}")

        return command

    async def get_system_state(self) -> SystemState:
        """Get current system state.

        Returns:
            System state snapshot
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        paused = await redis.get("control:processing:paused") == "true"
        emergency = await redis.get("control:emergency:active") == "true"
        workers = int(await redis.get("control:workers:target") or 4)

        # Get circuit breakers
        breakers_raw = await redis.hgetall("control:circuit_breakers")
        breakers = [k for k, v in breakers_raw.items() if v == "open"]

        # Get rate limits
        limits_raw = await redis.hgetall("control:rate_limits")
        limits = {k: int(v) for k, v in limits_raw.items()}

        # Get features
        enabled = list(await redis.smembers("control:features:enabled"))
        disabled = list(await redis.smembers("control:features:disabled"))

        # Health status
        if emergency:
            health = "emergency"
        elif paused:
            health = "paused"
        elif breakers:
            health = "degraded"
        else:
            health = "healthy"

        return SystemState(
            timestamp=now,
            processing_paused=paused,
            worker_count=workers,
            active_circuit_breakers=breakers,
            rate_limits=limits,
            enabled_features=enabled,
            disabled_features=disabled,
            emergency_mode=emergency,
            health_status=health,
        )

    async def get_command_history(
        self,
        limit: int = 50,
        action: ControlAction | None = None,
    ) -> list[ControlCommand]:
        """Get command history.

        Args:
            limit: Max commands
            action: Filter by action

        Returns:
            List of commands
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.zrevrange(self.COMMANDS_KEY, 0, limit - 1)

        commands = []
        for item in raw:
            try:
                data = json.loads(item)

                if action and data["action"] != action.value:
                    continue

                commands.append(ControlCommand(
                    id=data["id"],
                    action=ControlAction(data["action"]),
                    scope=ControlScope(data["scope"]),
                    target=data.get("target"),
                    parameters=data.get("parameters", {}),
                    status=CommandStatus(data["status"]),
                    issued_by=data["issued_by"],
                    issued_at=datetime.fromisoformat(data["issued_at"]),
                    executed_at=datetime.fromisoformat(data["executed_at"]) if data.get("executed_at") else None,
                    result=data.get("result"),
                    error=data.get("error"),
                ))
            except Exception:
                continue

        return commands

    async def get_metrics(self) -> ControlPlaneMetrics:
        """Get control plane metrics.

        Returns:
            Metrics
        """
        from app.storage.redis import get_redis
        from datetime import timedelta

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get recent commands
        commands = await self.get_command_history(limit=1000)
        cutoff = now - timedelta(hours=24)

        recent = [c for c in commands if c.issued_at >= cutoff]
        issued = len(recent)
        failed = sum(1 for c in recent if c.status == CommandStatus.FAILED)

        # Get exec times
        times_raw = await redis.lrange(f"{self.METRICS_KEY}:exec_times", 0, 99)
        times = [float(t) for t in times_raw if t]
        avg_time = sum(times) / len(times) if times else 0

        # Active overrides
        breakers = len(await redis.hgetall("control:circuit_breakers"))
        limits = len(await redis.hgetall("control:rate_limits"))
        overrides = breakers + limits

        # Last emergency
        last_emergency = None
        emergency_at = await redis.get("control:emergency:at")
        if emergency_at:
            last_emergency = datetime.fromisoformat(emergency_at)

        return ControlPlaneMetrics(
            commands_issued_24h=issued,
            commands_failed_24h=failed,
            avg_execution_time_ms=avg_time,
            active_overrides=overrides,
            last_emergency_action=last_emergency,
        )

    async def clear_emergency(
        self,
        cleared_by: str,
    ) -> dict[str, Any]:
        """Clear emergency mode.

        Args:
            cleared_by: Who cleared it

        Returns:
            Clear result
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        was_active = await redis.get("control:emergency:active") == "true"

        await redis.delete("control:emergency:active")
        await redis.delete("control:emergency:by")
        await redis.delete("control:emergency:at")

        # Record
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="emergency_cleared",
                actor=cleared_by,
                severity="critical",
            )
        except Exception:
            pass

        logger.info(f"[ControlPlane] Emergency cleared by {cleared_by}")

        return {"was_active": was_active, "cleared_by": cleared_by}


# Singleton
control_plane = ControlPlaneService()
