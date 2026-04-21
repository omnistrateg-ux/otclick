"""Drift Detection Service.

Configuration and state drift detection.
"""

import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any
import uuid

UTC = timezone.utc

logger = logging.getLogger(__name__)


class DriftType(str, Enum):
    """Types of drift."""

    CONFIGURATION = "configuration"
    STATE = "state"
    SCHEMA = "schema"
    DEPENDENCY = "dependency"
    RESOURCE = "resource"


class DriftSeverity(str, Enum):
    """Severity of drift."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DriftStatus(str, Enum):
    """Status of drift detection."""

    DETECTED = "detected"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    IGNORED = "ignored"


@dataclass
class DriftSnapshot:
    """Snapshot of configuration/state at a point in time."""

    id: str
    drift_type: DriftType
    resource: str
    state_hash: str
    state_data: dict[str, Any]
    captured_at: datetime
    captured_by: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "drift_type": self.drift_type.value,
            "resource": self.resource,
            "state_hash": self.state_hash,
            "state_data": self.state_data,
            "captured_at": self.captured_at.isoformat(),
            "captured_by": self.captured_by,
        }


@dataclass
class DriftEvent:
    """Detected drift event."""

    id: str
    drift_type: DriftType
    resource: str
    severity: DriftSeverity
    status: DriftStatus
    detected_at: datetime
    previous_hash: str
    current_hash: str
    changes: list[dict[str, Any]]
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "drift_type": self.drift_type.value,
            "resource": self.resource,
            "severity": self.severity.value,
            "status": self.status.value,
            "detected_at": self.detected_at.isoformat(),
            "previous_hash": self.previous_hash,
            "current_hash": self.current_hash,
            "changes": self.changes,
            "acknowledged_by": self.acknowledged_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class DriftReport:
    """Summary drift report."""

    generated_at: datetime
    total_resources: int
    drifted_resources: int
    critical_drifts: int
    drift_rate: float
    recent_events: list[DriftEvent]
    resources_by_type: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "total_resources": self.total_resources,
            "drifted_resources": self.drifted_resources,
            "critical_drifts": self.critical_drifts,
            "drift_rate": round(self.drift_rate, 2),
            "recent_events": [e.to_dict() for e in self.recent_events],
            "resources_by_type": self.resources_by_type,
        }


# Resource definitions for monitoring
MONITORED_RESOURCES = [
    {
        "name": "settings",
        "type": DriftType.CONFIGURATION,
        "critical_keys": ["database_url", "redis_url", "secret_key"],
        "get_state": "get_settings_state",
    },
    {
        "name": "feature_flags",
        "type": DriftType.CONFIGURATION,
        "critical_keys": [],
        "get_state": "get_feature_flags_state",
    },
    {
        "name": "rate_limits",
        "type": DriftType.CONFIGURATION,
        "critical_keys": [],
        "get_state": "get_rate_limits_state",
    },
    {
        "name": "celery_workers",
        "type": DriftType.STATE,
        "critical_keys": ["worker_count"],
        "get_state": "get_workers_state",
    },
    {
        "name": "database_schema",
        "type": DriftType.SCHEMA,
        "critical_keys": ["tables", "columns"],
        "get_state": "get_schema_state",
    },
]


class DriftDetectionService:
    """Service for drift detection.

    Features:
    - Baseline snapshots
    - Periodic drift checks
    - Change tracking
    - Alert on critical drift
    """

    SNAPSHOTS_KEY = "drift:snapshots"
    EVENTS_KEY = "drift:events"
    BASELINES_KEY = "drift:baselines"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    def _compute_hash(self, data: dict[str, Any]) -> str:
        """Compute hash of state data."""
        import json
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def _diff_states(
        self,
        previous: dict[str, Any],
        current: dict[str, Any],
        path: str = "",
    ) -> list[dict[str, Any]]:
        """Compute differences between states."""
        changes = []

        all_keys = set(previous.keys()) | set(current.keys())

        for key in all_keys:
            full_path = f"{path}.{key}" if path else key
            prev_val = previous.get(key)
            curr_val = current.get(key)

            if key not in previous:
                changes.append({
                    "path": full_path,
                    "type": "added",
                    "new_value": curr_val,
                })
            elif key not in current:
                changes.append({
                    "path": full_path,
                    "type": "removed",
                    "old_value": prev_val,
                })
            elif isinstance(prev_val, dict) and isinstance(curr_val, dict):
                changes.extend(self._diff_states(prev_val, curr_val, full_path))
            elif prev_val != curr_val:
                changes.append({
                    "path": full_path,
                    "type": "changed",
                    "old_value": prev_val,
                    "new_value": curr_val,
                })

        return changes

    async def capture_baseline(
        self,
        resource: str,
        drift_type: DriftType,
        state_data: dict[str, Any],
        captured_by: str = "system",
    ) -> DriftSnapshot:
        """Capture baseline snapshot.

        Args:
            resource: Resource name
            drift_type: Type of drift
            state_data: Current state
            captured_by: Who captured

        Returns:
            Baseline snapshot
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        state_hash = self._compute_hash(state_data)

        snapshot = DriftSnapshot(
            id=str(uuid.uuid4())[:8],
            drift_type=drift_type,
            resource=resource,
            state_hash=state_hash,
            state_data=state_data,
            captured_at=now,
            captured_by=captured_by,
        )

        # Store as baseline
        await redis.hset(
            self.BASELINES_KEY,
            resource,
            json.dumps(snapshot.to_dict()),
        )

        # Also store in history
        await redis.lpush(
            f"{self.SNAPSHOTS_KEY}:{resource}",
            json.dumps(snapshot.to_dict()),
        )
        await redis.ltrim(f"{self.SNAPSHOTS_KEY}:{resource}", 0, 99)

        logger.info(f"[DriftDetection] Captured baseline for {resource}")

        return snapshot

    async def get_baseline(self, resource: str) -> DriftSnapshot | None:
        """Get baseline for resource.

        Args:
            resource: Resource name

        Returns:
            Baseline snapshot or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hget(self.BASELINES_KEY, resource)
        if not raw:
            return None

        data = json.loads(raw)

        return DriftSnapshot(
            id=data["id"],
            drift_type=DriftType(data["drift_type"]),
            resource=data["resource"],
            state_hash=data["state_hash"],
            state_data=data["state_data"],
            captured_at=datetime.fromisoformat(data["captured_at"]),
            captured_by=data["captured_by"],
        )

    async def check_drift(
        self,
        resource: str,
        current_state: dict[str, Any],
        critical_keys: list[str] | None = None,
    ) -> DriftEvent | None:
        """Check for drift against baseline.

        Args:
            resource: Resource name
            current_state: Current state
            critical_keys: Keys that trigger critical severity

        Returns:
            Drift event if drift detected, None otherwise
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        baseline = await self.get_baseline(resource)
        if not baseline:
            return None

        current_hash = self._compute_hash(current_state)

        # No drift
        if current_hash == baseline.state_hash:
            return None

        # Compute changes
        changes = self._diff_states(baseline.state_data, current_state)

        # Determine severity
        severity = DriftSeverity.WARNING
        if critical_keys:
            for change in changes:
                path = change["path"]
                if any(k in path for k in critical_keys):
                    severity = DriftSeverity.CRITICAL
                    break

        event = DriftEvent(
            id=str(uuid.uuid4())[:8],
            drift_type=baseline.drift_type,
            resource=resource,
            severity=severity,
            status=DriftStatus.DETECTED,
            detected_at=now,
            previous_hash=baseline.state_hash,
            current_hash=current_hash,
            changes=changes,
        )

        # Store event
        await redis.zadd(
            self.EVENTS_KEY,
            {json.dumps(event.to_dict()): now.timestamp()},
        )

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="drift_detected",
                actor="system",
                details={
                    "resource": resource,
                    "severity": severity.value,
                    "changes_count": len(changes),
                },
                severity="warning" if severity == DriftSeverity.CRITICAL else "info",
            )
        except Exception:
            pass

        logger.warning(f"[DriftDetection] Drift detected in {resource}: {len(changes)} changes")

        return event

    async def acknowledge_drift(
        self,
        event_id: str,
        acknowledged_by: str,
    ) -> DriftEvent | None:
        """Acknowledge a drift event.

        Args:
            event_id: Event ID
            acknowledged_by: Who acknowledged

        Returns:
            Updated event or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Find event
        events = await self.get_events(limit=100)
        event = None
        for e in events:
            if e.id == event_id:
                event = e
                break

        if not event:
            return None

        event.status = DriftStatus.ACKNOWLEDGED
        event.acknowledged_by = acknowledged_by

        # Update in storage (remove old, add new)
        # Simplified: just log acknowledgment
        logger.info(f"[DriftDetection] Event {event_id} acknowledged by {acknowledged_by}")

        return event

    async def resolve_drift(
        self,
        resource: str,
        current_state: dict[str, Any],
        resolved_by: str = "system",
    ) -> bool:
        """Resolve drift by updating baseline.

        Args:
            resource: Resource name
            current_state: Current (correct) state
            resolved_by: Who resolved

        Returns:
            True if resolved
        """
        # Update baseline to current state
        baseline = await self.get_baseline(resource)
        if not baseline:
            return False

        await self.capture_baseline(
            resource=resource,
            drift_type=baseline.drift_type,
            state_data=current_state,
            captured_by=resolved_by,
        )

        logger.info(f"[DriftDetection] Drift resolved for {resource} by {resolved_by}")

        return True

    async def get_events(
        self,
        limit: int = 50,
        severity: DriftSeverity | None = None,
        status: DriftStatus | None = None,
    ) -> list[DriftEvent]:
        """Get drift events.

        Args:
            limit: Max events
            severity: Filter by severity
            status: Filter by status

        Returns:
            List of events
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.zrevrange(self.EVENTS_KEY, 0, limit - 1)
        events = []

        for item in raw:
            try:
                data = json.loads(item)

                if severity and data["severity"] != severity.value:
                    continue

                if status and data["status"] != status.value:
                    continue

                events.append(DriftEvent(
                    id=data["id"],
                    drift_type=DriftType(data["drift_type"]),
                    resource=data["resource"],
                    severity=DriftSeverity(data["severity"]),
                    status=DriftStatus(data["status"]),
                    detected_at=datetime.fromisoformat(data["detected_at"]),
                    previous_hash=data["previous_hash"],
                    current_hash=data["current_hash"],
                    changes=data["changes"],
                    acknowledged_by=data.get("acknowledged_by"),
                    resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
                ))
            except Exception:
                continue

        return events

    async def generate_report(self) -> DriftReport:
        """Generate drift report.

        Returns:
            Drift report
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get all baselines
        baselines_raw = await redis.hgetall(self.BASELINES_KEY)
        total_resources = len(baselines_raw)

        # Get recent events
        events = await self.get_events(limit=100)
        recent_events = [e for e in events if e.detected_at >= now - timedelta(days=7)]

        # Count drifted resources
        drifted_resources = len({e.resource for e in recent_events})
        critical_drifts = sum(1 for e in recent_events if e.severity == DriftSeverity.CRITICAL)

        drift_rate = drifted_resources / total_resources if total_resources > 0 else 0

        # Resources by type
        resources_by_type: dict[str, int] = {}
        for e in recent_events:
            drift_type = e.drift_type.value
            resources_by_type[drift_type] = resources_by_type.get(drift_type, 0) + 1

        return DriftReport(
            generated_at=now,
            total_resources=total_resources,
            drifted_resources=drifted_resources,
            critical_drifts=critical_drifts,
            drift_rate=drift_rate,
            recent_events=recent_events[:10],
            resources_by_type=resources_by_type,
        )

    async def run_check_all(self) -> list[DriftEvent]:
        """Run drift check on all monitored resources.

        Returns:
            List of detected drift events
        """
        events = []

        for resource_def in MONITORED_RESOURCES:
            try:
                # Get current state (simplified - in production would call actual getters)
                current_state = await self._get_resource_state(resource_def["name"])

                event = await self.check_drift(
                    resource=resource_def["name"],
                    current_state=current_state,
                    critical_keys=resource_def.get("critical_keys", []),
                )

                if event:
                    events.append(event)

            except Exception as e:
                logger.error(f"[DriftDetection] Error checking {resource_def['name']}: {e}")

        return events

    async def _get_resource_state(self, resource: str) -> dict[str, Any]:
        """Get current state of a resource.

        Simplified implementation - in production would call actual services.
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        if resource == "settings":
            # Get settings-related state
            return {
                "environment": await redis.get("settings:environment") or "development",
                "debug": await redis.get("settings:debug") or "false",
            }

        elif resource == "feature_flags":
            from app.services.feature_flags import feature_flags
            flags = await feature_flags.list_flags()
            return {f.name: f.enabled for f in flags}

        elif resource == "rate_limits":
            limits = await redis.hgetall("control:rate_limits")
            return dict(limits)

        elif resource == "celery_workers":
            workers = await redis.get("control:workers:target") or "4"
            return {"worker_count": int(workers)}

        else:
            return {}


# Singleton
drift_detection = DriftDetectionService()
