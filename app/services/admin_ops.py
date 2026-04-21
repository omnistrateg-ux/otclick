"""Admin Operations Service.

Manual overrides, admin actions, and data management.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class OverrideType(str, Enum):
    """Types of manual overrides."""

    STATUS_CHANGE = "status_change"
    SCORE_OVERRIDE = "score_override"
    ASSIGNMENT_CHANGE = "assignment_change"
    DATA_CORRECTION = "data_correction"
    FORCE_TRANSITION = "force_transition"
    UNBLOCK = "unblock"


class AdminActionType(str, Enum):
    """Types of admin actions."""

    OVERRIDE = "override"
    CLEANUP = "cleanup"
    PURGE = "purge"
    UNLOCK = "unlock"
    RESET = "reset"
    SYNC = "sync"
    BULK_UPDATE = "bulk_update"


@dataclass
class AdminAction:
    """Record of an admin action."""

    id: str
    action_type: AdminActionType
    override_type: OverrideType | None
    actor: str
    target_type: str
    target_id: str
    description: str
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    performed_at: datetime
    reason: str | None = None
    reversible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action_type": self.action_type.value,
            "override_type": self.override_type.value if self.override_type else None,
            "actor": self.actor,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "description": self.description,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "performed_at": self.performed_at.isoformat(),
            "reason": self.reason,
            "reversible": self.reversible,
            "metadata": self.metadata,
        }


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""

    operation: str
    records_processed: int
    records_deleted: int
    records_archived: int
    errors: list[str]
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "records_processed": self.records_processed,
            "records_deleted": self.records_deleted,
            "records_archived": self.records_archived,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
        }


class AdminOpsService:
    """Service for admin operations.

    Features:
    - Manual status overrides
    - Force state transitions
    - Data cleanup
    - Bulk operations
    - Action audit trail
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Manual Overrides
    # ========================================================================

    async def override_lead_status(
        self,
        lead_id: str,
        new_status: str,
        actor: str,
        reason: str,
    ) -> AdminAction:
        """Override lead status manually.

        Args:
            lead_id: Lead ID
            new_status: New status to set
            actor: Who performed the action
            reason: Reason for override

        Returns:
            AdminAction
        """
        from app.storage.redis import get_redis
        from uuid import uuid4
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get current lead
        lead_data = await redis.get(f"lead:{lead_id}")
        if not lead_data:
            raise ValueError(f"Lead {lead_id} not found")

        lead = json.loads(lead_data)
        old_status = lead.get("status")

        # Update lead
        lead["status"] = new_status
        lead["status_changed_at"] = now.isoformat()
        lead["last_override_at"] = now.isoformat()
        lead["last_override_by"] = actor

        # Add to history
        if "status_history" not in lead:
            lead["status_history"] = []
        lead["status_history"].append({
            "from": old_status,
            "to": new_status,
            "at": now.isoformat(),
            "by": actor,
            "reason": reason,
            "override": True,
        })

        await redis.set(f"lead:{lead_id}", json.dumps(lead), ex=86400 * 365)

        # Record action
        action = AdminAction(
            id=str(uuid4()),
            action_type=AdminActionType.OVERRIDE,
            override_type=OverrideType.STATUS_CHANGE,
            actor=actor,
            target_type="lead",
            target_id=lead_id,
            description=f"Status override: {old_status} -> {new_status}",
            before_state={"status": old_status},
            after_state={"status": new_status},
            performed_at=now,
            reason=reason,
        )

        await self._record_action(action)

        logger.warning(
            f"[Admin] Status override | lead={lead_id} | "
            f"{old_status} -> {new_status} | actor={actor}"
        )

        return action

    async def override_lead_score(
        self,
        lead_id: str,
        new_score: float,
        actor: str,
        reason: str,
    ) -> AdminAction:
        """Override lead score manually.

        Args:
            lead_id: Lead ID
            new_score: New score
            actor: Who performed the action
            reason: Reason for override

        Returns:
            AdminAction
        """
        from app.storage.redis import get_redis
        from uuid import uuid4
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get current lead
        lead_data = await redis.get(f"lead:{lead_id}")
        if not lead_data:
            raise ValueError(f"Lead {lead_id} not found")

        lead = json.loads(lead_data)
        old_score = lead.get("score", 0)

        # Update score
        lead["score"] = new_score
        lead["score_override"] = True
        lead["score_override_at"] = now.isoformat()
        lead["score_override_by"] = actor

        await redis.set(f"lead:{lead_id}", json.dumps(lead), ex=86400 * 365)

        # Record action
        action = AdminAction(
            id=str(uuid4()),
            action_type=AdminActionType.OVERRIDE,
            override_type=OverrideType.SCORE_OVERRIDE,
            actor=actor,
            target_type="lead",
            target_id=lead_id,
            description=f"Score override: {old_score} -> {new_score}",
            before_state={"score": old_score},
            after_state={"score": new_score},
            performed_at=now,
            reason=reason,
        )

        await self._record_action(action)

        logger.warning(
            f"[Admin] Score override | lead={lead_id} | "
            f"{old_score} -> {new_score} | actor={actor}"
        )

        return action

    async def force_handoff_assignment(
        self,
        handoff_id: str,
        new_assignee: str,
        actor: str,
        reason: str,
    ) -> AdminAction:
        """Force reassign a handoff.

        Args:
            handoff_id: Handoff ID
            new_assignee: New assignee
            actor: Who performed the action
            reason: Reason for override

        Returns:
            AdminAction
        """
        from app.storage.redis import get_redis
        from uuid import uuid4
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get current handoff
        handoff_data = await redis.get(f"handoff:{handoff_id}")
        if not handoff_data:
            raise ValueError(f"Handoff {handoff_id} not found")

        handoff = json.loads(handoff_data)
        old_assignee = handoff.get("assigned_to")

        # Update assignment
        handoff["assigned_to"] = new_assignee
        handoff["reassigned_at"] = now.isoformat()
        handoff["reassigned_by"] = actor

        await redis.set(f"handoff:{handoff_id}", json.dumps(handoff), ex=86400 * 90)

        # Update indices
        if old_assignee:
            await redis.srem(f"handoffs:assigned:{old_assignee}", handoff_id)
        await redis.sadd(f"handoffs:assigned:{new_assignee}", handoff_id)

        # Record action
        action = AdminAction(
            id=str(uuid4()),
            action_type=AdminActionType.OVERRIDE,
            override_type=OverrideType.ASSIGNMENT_CHANGE,
            actor=actor,
            target_type="handoff",
            target_id=handoff_id,
            description=f"Reassigned: {old_assignee} -> {new_assignee}",
            before_state={"assigned_to": old_assignee},
            after_state={"assigned_to": new_assignee},
            performed_at=now,
            reason=reason,
        )

        await self._record_action(action)

        logger.warning(
            f"[Admin] Handoff reassigned | handoff={handoff_id} | "
            f"{old_assignee} -> {new_assignee} | actor={actor}"
        )

        return action

    async def unblock_lead(
        self,
        lead_id: str,
        actor: str,
        reason: str,
    ) -> AdminAction:
        """Unblock a stuck lead.

        Args:
            lead_id: Lead ID
            actor: Who performed the action
            reason: Reason for unblock

        Returns:
            AdminAction
        """
        from app.storage.redis import get_redis
        from uuid import uuid4
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get current lead
        lead_data = await redis.get(f"lead:{lead_id}")
        if not lead_data:
            raise ValueError(f"Lead {lead_id} not found")

        lead = json.loads(lead_data)

        # Clear blocking flags
        before_state = {
            "locked": lead.get("locked"),
            "blocked_reason": lead.get("blocked_reason"),
            "cooldown_until": lead.get("cooldown_until"),
        }

        lead["locked"] = False
        lead["blocked_reason"] = None
        lead["cooldown_until"] = None
        lead["unblocked_at"] = now.isoformat()
        lead["unblocked_by"] = actor

        await redis.set(f"lead:{lead_id}", json.dumps(lead), ex=86400 * 365)

        # Record action
        action = AdminAction(
            id=str(uuid4()),
            action_type=AdminActionType.UNLOCK,
            override_type=OverrideType.UNBLOCK,
            actor=actor,
            target_type="lead",
            target_id=lead_id,
            description="Lead unblocked",
            before_state=before_state,
            after_state={"locked": False},
            performed_at=now,
            reason=reason,
        )

        await self._record_action(action)

        logger.warning(f"[Admin] Lead unblocked | lead={lead_id} | actor={actor}")

        return action

    # ========================================================================
    # Data Cleanup
    # ========================================================================

    async def cleanup_old_data(
        self,
        days_old: int = 90,
        dry_run: bool = True,
    ) -> CleanupResult:
        """Clean up old data.

        Args:
            days_old: Delete data older than this
            dry_run: If True, don't actually delete

        Returns:
            CleanupResult
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        start_time = datetime.now(UTC)
        cutoff = (start_time - timedelta(days=days_old)).timestamp()

        processed = 0
        deleted = 0
        archived = 0
        errors = []

        # Cleanup old audit entries
        try:
            old_audits = await redis.zrangebyscore("audit:timeline", "-inf", cutoff)
            processed += len(old_audits)

            if not dry_run:
                for audit_id in old_audits:
                    await redis.delete(f"audit:{audit_id}")
                    deleted += 1
                await redis.zremrangebyscore("audit:timeline", "-inf", cutoff)
        except Exception as e:
            errors.append(f"Audit cleanup error: {str(e)}")

        # Cleanup old security events
        try:
            old_events = await redis.zrangebyscore("security:timeline", "-inf", cutoff)
            processed += len(old_events)

            if not dry_run:
                for event_id in old_events:
                    await redis.delete(f"security:event:{event_id}")
                    deleted += 1
                await redis.zremrangebyscore("security:timeline", "-inf", cutoff)
        except Exception as e:
            errors.append(f"Security events cleanup error: {str(e)}")

        # Cleanup old alerts
        try:
            old_alerts = await redis.zrangebyscore("alerts:timeline", "-inf", cutoff)
            processed += len(old_alerts)

            if not dry_run:
                for alert_id in old_alerts:
                    await redis.delete(f"alert:{alert_id}")
                    deleted += 1
                await redis.zremrangebyscore("alerts:timeline", "-inf", cutoff)
        except Exception as e:
            errors.append(f"Alerts cleanup error: {str(e)}")

        duration = (datetime.now(UTC) - start_time).total_seconds()

        logger.info(
            f"[Admin] Cleanup completed | processed={processed} | "
            f"deleted={deleted} | dry_run={dry_run}"
        )

        return CleanupResult(
            operation="cleanup_old_data",
            records_processed=processed,
            records_deleted=deleted,
            records_archived=archived,
            errors=errors,
            duration_seconds=duration,
        )

    async def purge_lead(
        self,
        lead_id: str,
        actor: str,
        reason: str,
    ) -> AdminAction:
        """Permanently delete a lead.

        Args:
            lead_id: Lead ID
            actor: Who performed the action
            reason: Reason for purge

        Returns:
            AdminAction
        """
        from app.storage.redis import get_redis
        from uuid import uuid4
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get lead before delete
        lead_data = await redis.get(f"lead:{lead_id}")
        if not lead_data:
            raise ValueError(f"Lead {lead_id} not found")

        lead = json.loads(lead_data)

        # Delete lead and related data
        await redis.delete(f"lead:{lead_id}")
        await redis.delete(f"outreach:state:{lead_id}")
        await redis.zrem("leads:by_score", lead_id)

        # Record action
        action = AdminAction(
            id=str(uuid4()),
            action_type=AdminActionType.PURGE,
            override_type=None,
            actor=actor,
            target_type="lead",
            target_id=lead_id,
            description="Lead permanently deleted",
            before_state=lead,
            after_state={},
            performed_at=now,
            reason=reason,
            reversible=False,
        )

        await self._record_action(action)

        logger.warning(f"[Admin] Lead purged | lead={lead_id} | actor={actor}")

        return action

    # ========================================================================
    # Bulk Operations
    # ========================================================================

    async def bulk_status_update(
        self,
        lead_ids: list[str],
        new_status: str,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        """Update status for multiple leads.

        Args:
            lead_ids: Lead IDs
            new_status: New status
            actor: Who performed
            reason: Reason

        Returns:
            Summary
        """
        success = 0
        failed = 0
        errors = []

        for lead_id in lead_ids:
            try:
                await self.override_lead_status(lead_id, new_status, actor, reason)
                success += 1
            except Exception as e:
                failed += 1
                errors.append(f"{lead_id}: {str(e)}")

        logger.warning(
            f"[Admin] Bulk status update | total={len(lead_ids)} | "
            f"success={success} | failed={failed} | actor={actor}"
        )

        return {
            "total": len(lead_ids),
            "success": success,
            "failed": failed,
            "errors": errors[:10],
        }

    # ========================================================================
    # Action Recording
    # ========================================================================

    async def _record_action(self, action: AdminAction) -> None:
        """Record an admin action."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        await redis.set(
            f"admin_action:{action.id}",
            json.dumps(action.to_dict()),
            ex=86400 * 365,
        )

        await redis.zadd(
            "admin_actions:timeline",
            {action.id: action.performed_at.timestamp()},
        )
        await redis.expire("admin_actions:timeline", 86400 * 365)

        # Index by actor
        await redis.lpush(f"admin_actions:actor:{action.actor}", action.id)
        await redis.ltrim(f"admin_actions:actor:{action.actor}", 0, 999)
        await redis.expire(f"admin_actions:actor:{action.actor}", 86400 * 365)

    async def get_admin_action(self, action_id: str) -> AdminAction | None:
        """Get admin action by ID."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        data = await redis.get(f"admin_action:{action_id}")

        if not data:
            return None

        d = json.loads(data)
        return AdminAction(
            id=d["id"],
            action_type=AdminActionType(d["action_type"]),
            override_type=OverrideType(d["override_type"]) if d.get("override_type") else None,
            actor=d["actor"],
            target_type=d["target_type"],
            target_id=d["target_id"],
            description=d["description"],
            before_state=d["before_state"],
            after_state=d["after_state"],
            performed_at=datetime.fromisoformat(d["performed_at"]),
            reason=d.get("reason"),
            reversible=d.get("reversible", True),
            metadata=d.get("metadata", {}),
        )

    async def get_admin_actions(
        self,
        actor: str | None = None,
        hours: int = 24,
        limit: int = 50,
    ) -> list[AdminAction]:
        """Get admin actions.

        Args:
            actor: Filter by actor
            hours: Hours to look back
            limit: Max results

        Returns:
            List of actions
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        if actor:
            action_ids = await redis.lrange(f"admin_actions:actor:{actor}", 0, limit - 1)
        else:
            now = datetime.now(UTC)
            start_time = (now - timedelta(hours=hours)).timestamp()
            action_ids = await redis.zrevrangebyscore(
                "admin_actions:timeline",
                now.timestamp(),
                start_time,
                start=0,
                num=limit,
            )

        actions = []
        for action_id in action_ids:
            action = await self.get_admin_action(action_id)
            if action:
                actions.append(action)

        return actions

    # ========================================================================
    # System Dashboard
    # ========================================================================

    async def get_system_overview(self) -> dict[str, Any]:
        """Get system overview for admin dashboard.

        Returns:
            System overview
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Count leads by status
        lead_count = 0
        async for _ in redis.scan_iter("lead:*"):
            lead_count += 1

        # Count deals
        deal_count = 0
        async for _ in redis.scan_iter("deal:*"):
            deal_count += 1

        # Count handoffs
        handoff_count = 0
        async for _ in redis.scan_iter("handoff:*"):
            handoff_count += 1

        # Recent admin actions
        recent_actions = await self.get_admin_actions(hours=24, limit=10)

        # Memory usage
        try:
            info = await redis.info("memory")
            memory_mb = info.get("used_memory", 0) / 1024 / 1024
        except Exception as e:
            logger.debug(f"[Admin Ops] Failed to get Redis memory info: {e}")
            memory_mb = 0

        return {
            "timestamp": now.isoformat(),
            "counts": {
                "leads": lead_count,
                "deals": deal_count,
                "handoffs": handoff_count,
            },
            "recent_admin_actions": len(recent_actions),
            "redis_memory_mb": round(memory_mb, 2),
        }


# Singleton
admin_ops = AdminOpsService()
