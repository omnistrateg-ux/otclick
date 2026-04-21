"""Audit Trail Service.

Comprehensive logging of all system actions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Audit action types."""

    # Lead actions
    LEAD_CREATED = "lead.created"
    LEAD_UPDATED = "lead.updated"
    LEAD_DELETED = "lead.deleted"
    LEAD_TRANSITIONED = "lead.transitioned"
    LEAD_ENRICHED = "lead.enriched"
    LEAD_SCORED = "lead.scored"

    # Deal actions
    DEAL_CREATED = "deal.created"
    DEAL_STAGE_CHANGED = "deal.stage_changed"
    DEAL_VALUE_CHANGED = "deal.value_changed"
    DEAL_ASSIGNED = "deal.assigned"
    DEAL_CLOSED_WON = "deal.closed_won"
    DEAL_CLOSED_LOST = "deal.closed_lost"

    # Handoff actions
    HANDOFF_CREATED = "handoff.created"
    HANDOFF_ACCEPTED = "handoff.accepted"
    HANDOFF_REJECTED = "handoff.rejected"
    HANDOFF_REASSIGNED = "handoff.reassigned"
    HANDOFF_QUALIFIED = "handoff.qualified"
    HANDOFF_CLOSED = "handoff.closed"

    # Campaign actions
    CAMPAIGN_CREATED = "campaign.created"
    CAMPAIGN_STARTED = "campaign.started"
    CAMPAIGN_PAUSED = "campaign.paused"
    CAMPAIGN_RESUMED = "campaign.resumed"
    CAMPAIGN_COMPLETED = "campaign.completed"

    # Email actions
    EMAIL_SENT = "email.sent"
    EMAIL_DELIVERED = "email.delivered"
    EMAIL_BOUNCED = "email.bounced"
    EMAIL_OPENED = "email.opened"
    EMAIL_CLICKED = "email.clicked"
    EMAIL_REPLIED = "email.replied"

    # User actions
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_ROLE_CHANGED = "user.role_changed"
    USER_DEACTIVATED = "user.deactivated"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"

    # Feedback actions
    FEEDBACK_SUBMITTED = "feedback.submitted"

    # System actions
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"
    CONFIG_CHANGED = "config.changed"


class AuditSeverity(str, Enum):
    """Audit event severity."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEntry:
    """An audit log entry."""

    id: str
    timestamp: datetime
    action: AuditAction
    severity: AuditSeverity
    actor_id: str
    actor_type: str  # "user", "system", "api"
    resource_type: str  # "lead", "deal", "handoff", etc.
    resource_id: str
    description: str
    changes: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "severity": self.severity.value,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "description": self.description,
            "changes": self.changes,
            "metadata": self.metadata,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


@dataclass
class AuditSummary:
    """Summary of audit activity."""

    period_days: int
    total_events: int
    by_action: dict[str, int]
    by_actor: dict[str, int]
    by_resource_type: dict[str, int]
    by_severity: dict[str, int]
    top_actors: list[dict[str, Any]]
    recent_errors: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "period_days": self.period_days,
            "total_events": self.total_events,
            "by_action": self.by_action,
            "by_actor": self.by_actor,
            "by_resource_type": self.by_resource_type,
            "by_severity": self.by_severity,
            "top_actors": self.top_actors,
            "recent_errors": self.recent_errors,
        }


class AuditTrailService:
    """Audit trail service for action logging.

    Features:
    - Action logging
    - Change tracking
    - Search and filtering
    - Summary reports
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Logging
    # ========================================================================

    async def log(
        self,
        action: AuditAction,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        description: str,
        actor_type: str = "user",
        severity: AuditSeverity = AuditSeverity.INFO,
        changes: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEntry:
        """Log an audit event.

        Args:
            action: Action type
            actor_id: Who performed the action
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            description: Human-readable description
            actor_type: Type of actor
            severity: Event severity
            changes: Before/after changes
            metadata: Additional metadata
            ip_address: Client IP
            user_agent: Client user agent

        Returns:
            Created AuditEntry
        """
        from app.storage.redis import get_redis
        from uuid import uuid4
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        entry = AuditEntry(
            id=str(uuid4()),
            timestamp=now,
            action=action,
            severity=severity,
            actor_id=actor_id,
            actor_type=actor_type,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            changes=changes or {},
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Store entry
        key = f"audit:{entry.id}"
        await redis.set(key, json.dumps(entry.to_dict()), ex=86400 * 365)

        # Add to time-sorted index
        await redis.zadd("audit:timeline", {entry.id: now.timestamp()})
        await redis.expire("audit:timeline", 86400 * 365)

        # Add to resource index
        await redis.lpush(f"audit:resource:{resource_type}:{resource_id}", entry.id)
        await redis.ltrim(f"audit:resource:{resource_type}:{resource_id}", 0, 999)
        await redis.expire(f"audit:resource:{resource_type}:{resource_id}", 86400 * 365)

        # Add to actor index
        await redis.lpush(f"audit:actor:{actor_id}", entry.id)
        await redis.ltrim(f"audit:actor:{actor_id}", 0, 999)
        await redis.expire(f"audit:actor:{actor_id}", 86400 * 365)

        # Add to action index
        await redis.lpush(f"audit:action:{action.value}", entry.id)
        await redis.ltrim(f"audit:action:{action.value}", 0, 999)
        await redis.expire(f"audit:action:{action.value}", 86400 * 365)

        # Track daily stats
        today = now.strftime("%Y-%m-%d")
        pipe = redis.pipeline()
        pipe.incr(f"audit:stats:daily:{today}:total")
        pipe.incr(f"audit:stats:daily:{today}:action:{action.value}")
        pipe.incr(f"audit:stats:daily:{today}:severity:{severity.value}")
        pipe.incr(f"audit:stats:actor:{actor_id}:total")
        await pipe.execute()

        # Log to standard logger for critical/error
        if severity == AuditSeverity.CRITICAL:
            logger.critical(f"[AUDIT] {action.value}: {description}")
        elif severity == AuditSeverity.ERROR:
            logger.error(f"[AUDIT] {action.value}: {description}")

        return entry

    async def log_change(
        self,
        action: AuditAction,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        field: str,
        old_value: Any,
        new_value: Any,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Log a field change with before/after values.

        Args:
            action: Action type
            actor_id: Who made the change
            resource_type: Type of resource
            resource_id: Resource ID
            field: Field that changed
            old_value: Previous value
            new_value: New value
            metadata: Additional metadata

        Returns:
            Created AuditEntry
        """
        changes = {
            field: {
                "old": old_value,
                "new": new_value,
            }
        }

        description = f"Changed {field} from '{old_value}' to '{new_value}'"

        return await self.log(
            action=action,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            changes=changes,
            metadata=metadata,
        )

    # ========================================================================
    # Retrieval
    # ========================================================================

    async def get_entry(self, entry_id: str) -> AuditEntry | None:
        """Get audit entry by ID.

        Args:
            entry_id: Entry ID

        Returns:
            AuditEntry or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        data = await redis.get(f"audit:{entry_id}")

        if not data:
            return None

        d = json.loads(data)
        return AuditEntry(
            id=d["id"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            action=AuditAction(d["action"]),
            severity=AuditSeverity(d["severity"]),
            actor_id=d["actor_id"],
            actor_type=d["actor_type"],
            resource_type=d["resource_type"],
            resource_id=d["resource_id"],
            description=d["description"],
            changes=d.get("changes", {}),
            metadata=d.get("metadata", {}),
            ip_address=d.get("ip_address"),
            user_agent=d.get("user_agent"),
        )

    async def get_resource_history(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 50,
    ) -> list[AuditEntry]:
        """Get audit history for a resource.

        Args:
            resource_type: Resource type
            resource_id: Resource ID
            limit: Max entries

        Returns:
            List of audit entries
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        key = f"audit:resource:{resource_type}:{resource_id}"

        entry_ids = await redis.lrange(key, 0, limit - 1)

        entries = []
        for entry_id in entry_ids:
            entry = await self.get_entry(entry_id)
            if entry:
                entries.append(entry)

        return entries

    async def get_actor_history(
        self,
        actor_id: str,
        limit: int = 50,
    ) -> list[AuditEntry]:
        """Get audit history for an actor.

        Args:
            actor_id: Actor ID
            limit: Max entries

        Returns:
            List of audit entries
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        key = f"audit:actor:{actor_id}"

        entry_ids = await redis.lrange(key, 0, limit - 1)

        entries = []
        for entry_id in entry_ids:
            entry = await self.get_entry(entry_id)
            if entry:
                entries.append(entry)

        return entries

    async def search(
        self,
        action: AuditAction | None = None,
        actor_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        severity: AuditSeverity | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Search audit entries.

        Args:
            action: Filter by action
            actor_id: Filter by actor
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            severity: Filter by severity
            start_time: Start time
            end_time: End time
            limit: Max results

        Returns:
            Matching audit entries
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Get entry IDs from most specific index
        if resource_type and resource_id:
            entry_ids = await redis.lrange(
                f"audit:resource:{resource_type}:{resource_id}", 0, limit * 2
            )
        elif actor_id:
            entry_ids = await redis.lrange(f"audit:actor:{actor_id}", 0, limit * 2)
        elif action:
            entry_ids = await redis.lrange(f"audit:action:{action.value}", 0, limit * 2)
        else:
            # Use timeline
            if start_time and end_time:
                entry_ids = await redis.zrangebyscore(
                    "audit:timeline",
                    start_time.timestamp(),
                    end_time.timestamp(),
                    start=0,
                    num=limit * 2,
                )
            else:
                entry_ids = await redis.zrevrange("audit:timeline", 0, limit * 2)

        # Filter and retrieve entries
        entries = []
        for entry_id in entry_ids:
            if len(entries) >= limit:
                break

            entry = await self.get_entry(entry_id)
            if not entry:
                continue

            # Apply filters
            if action and entry.action != action:
                continue
            if actor_id and entry.actor_id != actor_id:
                continue
            if resource_type and entry.resource_type != resource_type:
                continue
            if severity and entry.severity != severity:
                continue
            if start_time and entry.timestamp < start_time:
                continue
            if end_time and entry.timestamp > end_time:
                continue

            entries.append(entry)

        return entries

    # ========================================================================
    # Summary
    # ========================================================================

    async def get_summary(
        self,
        days: int = 7,
    ) -> AuditSummary:
        """Get audit summary.

        Args:
            days: Days to analyze

        Returns:
            AuditSummary
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        total_events = 0
        by_action: dict[str, int] = {}
        by_severity: dict[str, int] = {}

        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")

            daily_total = int(await redis.get(f"audit:stats:daily:{day}:total") or 0)
            total_events += daily_total

            for action in AuditAction:
                count = int(await redis.get(f"audit:stats:daily:{day}:action:{action.value}") or 0)
                if count > 0:
                    by_action[action.value] = by_action.get(action.value, 0) + count

            for sev in AuditSeverity:
                count = int(await redis.get(f"audit:stats:daily:{day}:severity:{sev.value}") or 0)
                if count > 0:
                    by_severity[sev.value] = by_severity.get(sev.value, 0) + count

        # Get top actors
        top_actors = []
        async for key in redis.scan_iter("audit:stats:actor:*:total"):
            actor_id = key.split(":")[3]
            count = int(await redis.get(key) or 0)
            if count > 0:
                top_actors.append({"actor_id": actor_id, "count": count})

        top_actors.sort(key=lambda x: x["count"], reverse=True)
        top_actors = top_actors[:10]

        # Get recent errors
        recent_errors = []
        for entry in await self.search(severity=AuditSeverity.ERROR, limit=10):
            recent_errors.append({
                "id": entry.id,
                "timestamp": entry.timestamp.isoformat(),
                "action": entry.action.value,
                "description": entry.description,
            })

        return AuditSummary(
            period_days=days,
            total_events=total_events,
            by_action=by_action,
            by_actor={},  # Simplified
            by_resource_type={},  # Simplified
            by_severity=by_severity,
            top_actors=top_actors,
            recent_errors=recent_errors,
        )


# Singleton
audit_trail = AuditTrailService()
