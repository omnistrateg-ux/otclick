"""Manager Actions Service.

Actions managers can take on handoffs.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.config.settings import settings

UTC = timezone.utc

logger = logging.getLogger(__name__)


class HandoffAction(str, Enum):
    """Actions a manager can take on a handoff."""

    ACCEPT = "accept"
    REJECT = "reject"
    REASSIGN = "reassign"
    FOLLOW_UP = "follow_up"
    SCHEDULE_MEETING = "schedule_meeting"
    MARK_QUALIFIED = "mark_qualified"
    MARK_UNQUALIFIED = "mark_unqualified"
    REQUEST_INFO = "request_info"
    CLOSE = "close"


class HandoffStatus(str, Enum):
    """Handoff status."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    FOLLOW_UP_SCHEDULED = "follow_up_scheduled"
    MEETING_SCHEDULED = "meeting_scheduled"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    CLOSED = "closed"
    EXPIRED = "expired"


class RejectionReason(str, Enum):
    """Reasons for rejecting a handoff."""

    NOT_ICP = "not_icp"
    BAD_TIMING = "bad_timing"
    WRONG_CONTACT = "wrong_contact"
    ALREADY_IN_PIPELINE = "already_in_pipeline"
    COMPETITOR = "competitor"
    NO_BUDGET = "no_budget"
    DUPLICATE = "duplicate"
    OTHER = "other"


@dataclass
class Handoff:
    """A handoff from automation to manager."""

    id: str
    lead_id: str
    account_id: str
    contact_id: str | None

    # Status
    status: HandoffStatus
    assigned_to: str | None  # Manager ID
    created_by: str

    # Timing
    created_at: datetime
    updated_at: datetime
    sla_deadline: datetime | None  # When action is due
    accepted_at: datetime | None
    resolved_at: datetime | None

    # Context
    lead_score: float | None
    qualified_reason: str | None
    reply_summary: str | None
    interest_signals: list[str] = field(default_factory=list)

    # Actions
    action_history: list[dict[str, Any]] = field(default_factory=list)

    # Outcome
    rejection_reason: RejectionReason | None = None
    rejection_notes: str | None = None
    deal_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "account_id": self.account_id,
            "contact_id": self.contact_id,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "sla_deadline": self.sla_deadline.isoformat() if self.sla_deadline else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "lead_score": self.lead_score,
            "qualified_reason": self.qualified_reason,
            "reply_summary": self.reply_summary,
            "interest_signals": self.interest_signals,
            "action_history": self.action_history,
            "rejection_reason": self.rejection_reason.value if self.rejection_reason else None,
            "rejection_notes": self.rejection_notes,
            "deal_id": self.deal_id,
        }


@dataclass
class ManagerWorkload:
    """Manager workload summary."""

    manager_id: str
    pending_handoffs: int
    in_progress: int
    overdue: int
    accepted_today: int
    resolved_today: int
    avg_resolution_hours: float
    acceptance_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "manager_id": self.manager_id,
            "pending_handoffs": self.pending_handoffs,
            "in_progress": self.in_progress,
            "overdue": self.overdue,
            "accepted_today": self.accepted_today,
            "resolved_today": self.resolved_today,
            "avg_resolution_hours": round(self.avg_resolution_hours, 1),
            "acceptance_rate": round(self.acceptance_rate, 3),
        }


@dataclass
class ActionResult:
    """Result of a manager action."""

    success: bool
    handoff: Handoff
    message: str
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "handoff": self.handoff.to_dict(),
            "message": self.message,
            "next_actions": self.next_actions,
        }


# SLA configuration (hours)
SLA_HOURS = {
    "accept": 4,  # 4 hours to accept
    "follow_up": 24,  # 24 hours for follow-up
    "resolve": 72,  # 72 hours to resolve
}


class ManagerActionsService:
    """Manages handoff actions for sales managers.

    Features:
    - Handoff acceptance/rejection
    - Action tracking
    - SLA management
    - Workload balancing
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Handoff Management
    # ========================================================================

    async def create_handoff(
        self,
        lead_id: str,
        account_id: str,
        contact_id: str | None = None,
        assigned_to: str | None = None,
        lead_score: float | None = None,
        qualified_reason: str | None = None,
        reply_summary: str | None = None,
        interest_signals: list[str] | None = None,
    ) -> Handoff:
        """Create a new handoff.

        Args:
            lead_id: Lead ID
            account_id: Account ID
            contact_id: Contact ID
            assigned_to: Manager to assign to
            lead_score: Lead score
            qualified_reason: Why lead is qualified
            reply_summary: Summary of reply
            interest_signals: Interest signals detected

        Returns:
            Created Handoff
        """
        from app.storage.redis import get_redis
        from uuid import uuid4
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        handoff = Handoff(
            id=str(uuid4()),
            lead_id=lead_id,
            account_id=account_id,
            contact_id=contact_id,
            status=HandoffStatus.PENDING,
            assigned_to=assigned_to,
            created_by="system",
            created_at=now,
            updated_at=now,
            sla_deadline=now + timedelta(hours=SLA_HOURS["accept"]),
            accepted_at=None,
            resolved_at=None,
            lead_score=lead_score,
            qualified_reason=qualified_reason,
            reply_summary=reply_summary,
            interest_signals=interest_signals or [],
            action_history=[{
                "action": "created",
                "actor": "system",
                "timestamp": now.isoformat(),
            }],
        )

        # Store handoff
        key = f"handoff:{handoff.id}"
        await redis.set(key, json.dumps(handoff.to_dict()), ex=86400 * 90)

        # Index by lead
        await redis.sadd(f"handoffs:lead:{lead_id}", handoff.id)
        await redis.expire(f"handoffs:lead:{lead_id}", 86400 * 90)

        # Index by manager
        if assigned_to:
            await redis.sadd(f"handoffs:manager:{assigned_to}:pending", handoff.id)
            await redis.expire(f"handoffs:manager:{assigned_to}:pending", 86400 * 90)

        # Add to pending queue
        await redis.zadd("handoffs:pending", {handoff.id: now.timestamp()})

        logger.info(
            f"[HANDOFF] Created | id={handoff.id} | lead={lead_id} | "
            f"assigned_to={assigned_to}"
        )

        return handoff

    async def get_handoff(self, handoff_id: str) -> Handoff | None:
        """Get handoff by ID.

        Args:
            handoff_id: Handoff ID

        Returns:
            Handoff or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        data = await redis.get(f"handoff:{handoff_id}")

        if not data:
            return None

        d = json.loads(data)
        return Handoff(
            id=d["id"],
            lead_id=d["lead_id"],
            account_id=d["account_id"],
            contact_id=d.get("contact_id"),
            status=HandoffStatus(d["status"]),
            assigned_to=d.get("assigned_to"),
            created_by=d["created_by"],
            created_at=datetime.fromisoformat(d["created_at"]),
            updated_at=datetime.fromisoformat(d["updated_at"]),
            sla_deadline=datetime.fromisoformat(d["sla_deadline"]) if d.get("sla_deadline") else None,
            accepted_at=datetime.fromisoformat(d["accepted_at"]) if d.get("accepted_at") else None,
            resolved_at=datetime.fromisoformat(d["resolved_at"]) if d.get("resolved_at") else None,
            lead_score=d.get("lead_score"),
            qualified_reason=d.get("qualified_reason"),
            reply_summary=d.get("reply_summary"),
            interest_signals=d.get("interest_signals", []),
            action_history=d.get("action_history", []),
            rejection_reason=RejectionReason(d["rejection_reason"]) if d.get("rejection_reason") else None,
            rejection_notes=d.get("rejection_notes"),
            deal_id=d.get("deal_id"),
        )

    async def _save_handoff(self, handoff: Handoff) -> None:
        """Save handoff to Redis."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        key = f"handoff:{handoff.id}"
        await redis.set(key, json.dumps(handoff.to_dict()), ex=86400 * 90)

    # ========================================================================
    # Actions
    # ========================================================================

    async def take_action(
        self,
        handoff_id: str,
        action: HandoffAction,
        actor: str,
        notes: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ActionResult:
        """Take an action on a handoff.

        Args:
            handoff_id: Handoff ID
            action: Action to take
            actor: Manager taking action
            notes: Optional notes
            metadata: Additional metadata

        Returns:
            ActionResult
        """
        handoff = await self.get_handoff(handoff_id)
        if not handoff:
            raise ValueError(f"Handoff {handoff_id} not found")

        now = datetime.now(UTC)
        next_actions = []

        # Record action
        handoff.action_history.append({
            "action": action.value,
            "actor": actor,
            "timestamp": now.isoformat(),
            "notes": notes,
            "metadata": metadata,
        })
        handoff.updated_at = now

        # Handle action
        if action == HandoffAction.ACCEPT:
            handoff.status = HandoffStatus.ACCEPTED
            handoff.assigned_to = actor
            handoff.accepted_at = now
            handoff.sla_deadline = now + timedelta(hours=SLA_HOURS["resolve"])
            next_actions = ["follow_up", "schedule_meeting", "mark_qualified"]
            message = "Handoff accepted"

        elif action == HandoffAction.REJECT:
            handoff.status = HandoffStatus.REJECTED
            handoff.resolved_at = now
            if metadata and metadata.get("reason"):
                try:
                    handoff.rejection_reason = RejectionReason(metadata["reason"])
                except ValueError:
                    pass
            handoff.rejection_notes = notes
            message = "Handoff rejected"

        elif action == HandoffAction.REASSIGN:
            new_manager = metadata.get("new_manager") if metadata else None
            if not new_manager:
                raise ValueError("new_manager required for reassign")

            old_manager = handoff.assigned_to
            handoff.assigned_to = new_manager

            # Update indices
            from app.storage.redis import get_redis
            redis = await get_redis()
            if old_manager:
                await redis.srem(f"handoffs:manager:{old_manager}:pending", handoff_id)
            await redis.sadd(f"handoffs:manager:{new_manager}:pending", handoff_id)

            next_actions = ["accept", "reject"]
            message = f"Reassigned to {new_manager}"

        elif action == HandoffAction.FOLLOW_UP:
            handoff.status = HandoffStatus.FOLLOW_UP_SCHEDULED
            follow_up_date = metadata.get("follow_up_date") if metadata else None
            if follow_up_date:
                handoff.sla_deadline = datetime.fromisoformat(follow_up_date)
            else:
                handoff.sla_deadline = now + timedelta(hours=SLA_HOURS["follow_up"])
            next_actions = ["schedule_meeting", "mark_qualified", "close"]
            message = "Follow-up scheduled"

        elif action == HandoffAction.SCHEDULE_MEETING:
            handoff.status = HandoffStatus.MEETING_SCHEDULED
            meeting_date = metadata.get("meeting_date") if metadata else None
            next_actions = ["mark_qualified", "mark_unqualified", "close"]
            message = f"Meeting scheduled for {meeting_date}"

        elif action == HandoffAction.MARK_QUALIFIED:
            handoff.status = HandoffStatus.QUALIFIED
            handoff.resolved_at = now

            # Create deal if value provided
            if metadata and metadata.get("deal_value"):
                from app.services.revenue_loop import RevenueLoopService
                revenue = RevenueLoopService()
                deal = await revenue.create_deal(
                    lead_id=handoff.lead_id,
                    account_id=handoff.account_id,
                    value=metadata["deal_value"],
                    manager_id=actor,
                )
                handoff.deal_id = deal.id

            message = "Marked as qualified"
            next_actions = []

        elif action == HandoffAction.MARK_UNQUALIFIED:
            handoff.status = HandoffStatus.REJECTED
            handoff.resolved_at = now
            handoff.rejection_reason = RejectionReason.NOT_ICP
            message = "Marked as unqualified"

        elif action == HandoffAction.REQUEST_INFO:
            handoff.status = HandoffStatus.IN_PROGRESS
            next_actions = ["follow_up", "schedule_meeting", "mark_qualified"]
            message = "Additional info requested"

        elif action == HandoffAction.CLOSE:
            handoff.status = HandoffStatus.CLOSED
            handoff.resolved_at = now
            message = "Handoff closed"

        else:
            message = f"Action {action.value} recorded"

        # Save
        await self._save_handoff(handoff)

        # Update indices
        await self._update_indices(handoff)

        # Track metrics
        await self._track_action(action, actor, handoff)

        logger.info(
            f"[HANDOFF] Action taken | id={handoff_id} | action={action.value} | "
            f"actor={actor} | status={handoff.status.value}"
        )

        return ActionResult(
            success=True,
            handoff=handoff,
            message=message,
            next_actions=next_actions,
        )

    async def _update_indices(self, handoff: Handoff) -> None:
        """Update Redis indices for handoff."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Remove from pending if resolved
        if handoff.status in (HandoffStatus.QUALIFIED, HandoffStatus.REJECTED, HandoffStatus.CLOSED):
            await redis.zrem("handoffs:pending", handoff.id)
            if handoff.assigned_to:
                await redis.srem(f"handoffs:manager:{handoff.assigned_to}:pending", handoff.id)

    async def _track_action(
        self,
        action: HandoffAction,
        actor: str,
        handoff: Handoff,
    ) -> None:
        """Track action metrics."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        pipe = redis.pipeline()
        pipe.incr(f"handoff:action:{action.value}:total")
        pipe.incr(f"handoff:action:{action.value}:daily:{today}")
        pipe.incr(f"handoff:manager:{actor}:action:{action.value}")
        await pipe.execute()

    # ========================================================================
    # Workload Management
    # ========================================================================

    async def get_manager_workload(
        self,
        manager_id: str,
    ) -> ManagerWorkload:
        """Get workload for a manager.

        Args:
            manager_id: Manager ID

        Returns:
            ManagerWorkload
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)
        today = now.strftime("%Y-%m-%d")

        # Get pending handoffs
        pending_ids = await redis.smembers(f"handoffs:manager:{manager_id}:pending")
        pending = 0
        in_progress = 0
        overdue = 0

        for hid in pending_ids:
            handoff = await self.get_handoff(hid)
            if handoff:
                if handoff.status == HandoffStatus.PENDING:
                    pending += 1
                elif handoff.status in (HandoffStatus.ACCEPTED, HandoffStatus.IN_PROGRESS, HandoffStatus.FOLLOW_UP_SCHEDULED):
                    in_progress += 1

                if handoff.sla_deadline and handoff.sla_deadline < now:
                    overdue += 1

        # Get today's metrics
        accepted_today = int(await redis.get(f"handoff:manager:{manager_id}:action:accept:daily:{today}") or 0)
        resolved_today = int(await redis.get(f"handoff:manager:{manager_id}:resolved:daily:{today}") or 0)

        # Calculate average resolution time
        total_accepted = int(await redis.get(f"handoff:manager:{manager_id}:action:accept") or 0)
        total_qualified = int(await redis.get(f"handoff:manager:{manager_id}:action:mark_qualified") or 0)
        total_rejected = int(await redis.get(f"handoff:manager:{manager_id}:action:reject") or 0)

        total_resolved = total_qualified + total_rejected
        acceptance_rate = total_qualified / total_resolved if total_resolved > 0 else 0.5

        # Get avg resolution hours from stored metric
        avg_hours = float(await redis.get(f"handoff:manager:{manager_id}:avg_resolution_hours") or 24)

        return ManagerWorkload(
            manager_id=manager_id,
            pending_handoffs=pending,
            in_progress=in_progress,
            overdue=overdue,
            accepted_today=accepted_today,
            resolved_today=resolved_today,
            avg_resolution_hours=avg_hours,
            acceptance_rate=acceptance_rate,
        )

    async def get_best_assignee(
        self,
        exclude_managers: list[str] | None = None,
    ) -> str | None:
        """Get best manager to assign handoff to based on workload.

        Args:
            exclude_managers: Managers to exclude

        Returns:
            Manager ID or None
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        exclude = set(exclude_managers or [])

        # Get all managers with handoffs
        manager_ids = set()
        async for key in redis.scan_iter("handoffs:manager:*:pending"):
            manager_id = key.split(":")[2]
            if manager_id not in exclude:
                manager_ids.add(manager_id)

        if not manager_ids:
            return None

        # Get workloads and find lightest
        workloads = []
        for manager_id in manager_ids:
            workload = await self.get_manager_workload(manager_id)
            workloads.append((manager_id, workload))

        # Sort by pending + in_progress (ascending)
        workloads.sort(key=lambda x: x[1].pending_handoffs + x[1].in_progress)

        return workloads[0][0] if workloads else None

    # ========================================================================
    # Queries
    # ========================================================================

    async def get_pending_handoffs(
        self,
        manager_id: str | None = None,
        limit: int = 50,
    ) -> list[Handoff]:
        """Get pending handoffs.

        Args:
            manager_id: Filter by manager
            limit: Max results

        Returns:
            List of handoffs
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        handoffs = []

        if manager_id:
            ids = await redis.smembers(f"handoffs:manager:{manager_id}:pending")
        else:
            ids = await redis.zrange("handoffs:pending", 0, limit - 1)

        for hid in ids[:limit]:
            handoff = await self.get_handoff(hid)
            if handoff and handoff.status == HandoffStatus.PENDING:
                handoffs.append(handoff)

        return handoffs

    async def get_overdue_handoffs(
        self,
        limit: int = 50,
    ) -> list[Handoff]:
        """Get overdue handoffs.

        Args:
            limit: Max results

        Returns:
            List of overdue handoffs
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        overdue = []

        ids = await redis.zrange("handoffs:pending", 0, -1)

        for hid in ids:
            handoff = await self.get_handoff(hid)
            if handoff and handoff.sla_deadline and handoff.sla_deadline < now:
                overdue.append(handoff)
                if len(overdue) >= limit:
                    break

        return overdue

    async def get_handoff_stats(
        self,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get handoff statistics.

        Args:
            days: Days to analyze

        Returns:
            Statistics dict
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        stats = {
            "period_days": days,
            "total_created": 0,
            "total_accepted": 0,
            "total_rejected": 0,
            "total_qualified": 0,
            "acceptance_rate": 0.0,
            "qualification_rate": 0.0,
            "by_action": {},
            "by_rejection_reason": {},
        }

        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")

            for action in HandoffAction:
                count = int(await redis.get(f"handoff:action:{action.value}:daily:{day}") or 0)
                stats["by_action"][action.value] = stats["by_action"].get(action.value, 0) + count

                if action == HandoffAction.ACCEPT:
                    stats["total_accepted"] += count
                elif action == HandoffAction.REJECT:
                    stats["total_rejected"] += count
                elif action == HandoffAction.MARK_QUALIFIED:
                    stats["total_qualified"] += count

        # Calculate rates
        total_resolved = stats["total_accepted"] + stats["total_rejected"]
        if total_resolved > 0:
            stats["acceptance_rate"] = stats["total_accepted"] / total_resolved
            stats["qualification_rate"] = stats["total_qualified"] / total_resolved

        return stats


# Singleton
manager_actions = ManagerActionsService()
