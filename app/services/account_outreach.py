"""Account-Based Outreach Service.

Multi-contact touch strategy with stop rules for B2B outreach.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from app.config.settings import settings

UTC = timezone.utc

logger = logging.getLogger(__name__)


class AccountStatus(str, Enum):
    """Account outreach status."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    REPLIED = "replied"
    QUALIFIED = "qualified"
    STOPPED = "stopped"
    EXHAUSTED = "exhausted"  # All contacts/touches used


class ContactTouchStatus(str, Enum):
    """Status of a contact within account outreach."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    STOPPED = "stopped"
    BOUNCED = "bounced"


class StopReason(str, Enum):
    """Reason for stopping outreach."""

    REPLY_RECEIVED = "reply_received"
    POSITIVE_REPLY = "positive_reply"
    OPT_OUT = "opt_out"
    BOUNCE_LIMIT = "bounce_limit"
    COMPLAINT = "complaint"
    MANUAL = "manual"
    ALL_EXHAUSTED = "all_exhausted"


@dataclass
class ContactTouch:
    """Record of a touch to a contact."""

    contact_id: str
    touch_number: int
    sent_at: datetime
    email_id: str | None = None
    delivered: bool = False
    opened: bool = False
    replied: bool = False
    bounced: bool = False


@dataclass
class AccountOutreachState:
    """State of outreach for an account (company)."""

    lead_id: str
    status: AccountStatus
    contacts: list[dict[str, Any]]  # Contact states
    total_touches: int
    total_bounces: int
    has_reply: bool
    has_positive_reply: bool
    stop_reason: StopReason | None
    stopped_at: datetime | None
    started_at: datetime | None
    last_touch_at: datetime | None
    next_touch_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "lead_id": self.lead_id,
            "status": self.status.value,
            "contacts": self.contacts,
            "total_touches": self.total_touches,
            "total_bounces": self.total_bounces,
            "has_reply": self.has_reply,
            "has_positive_reply": self.has_positive_reply,
            "stop_reason": self.stop_reason.value if self.stop_reason else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_touch_at": self.last_touch_at.isoformat() if self.last_touch_at else None,
            "next_touch_at": self.next_touch_at.isoformat() if self.next_touch_at else None,
        }


@dataclass
class NextTouchRecommendation:
    """Recommendation for next touch."""

    should_touch: bool
    contact_id: str | None
    touch_number: int
    recommended_time: datetime | None
    reason: str
    days_until: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_touch": self.should_touch,
            "contact_id": self.contact_id,
            "touch_number": self.touch_number,
            "recommended_time": self.recommended_time.isoformat() if self.recommended_time else None,
            "reason": self.reason,
            "days_until": self.days_until,
        }


class AccountOutreachService:
    """Manages multi-contact outreach for accounts.

    Features:
    - Priority-ordered contact touching
    - Configurable touch cadence
    - Stop rules (reply, bounce, opt-out)
    - Account-level state tracking
    """

    def __init__(self) -> None:
        """Initialize service."""
        self.max_contacts = settings.abo_max_contacts_per_account
        self.days_between_contacts = settings.abo_days_between_contacts
        self.max_touches_per_contact = settings.abo_max_touches_per_contact
        self.stop_on_any_reply = settings.abo_stop_on_any_reply
        self.bounce_stop_count = settings.abo_stop_on_bounce_count

    # ========================================================================
    # Account State Management
    # ========================================================================

    async def get_account_state(self, lead_id: str) -> AccountOutreachState:
        """Get current outreach state for an account.

        Args:
            lead_id: Lead/account ID

        Returns:
            AccountOutreachState
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        key = f"abo:state:{lead_id}"

        data = await redis.get(key)
        if not data:
            return AccountOutreachState(
                lead_id=lead_id,
                status=AccountStatus.NOT_STARTED,
                contacts=[],
                total_touches=0,
                total_bounces=0,
                has_reply=False,
                has_positive_reply=False,
                stop_reason=None,
                stopped_at=None,
                started_at=None,
                last_touch_at=None,
                next_touch_at=None,
            )

        state_data = json.loads(data)
        return AccountOutreachState(
            lead_id=state_data["lead_id"],
            status=AccountStatus(state_data["status"]),
            contacts=state_data.get("contacts", []),
            total_touches=state_data.get("total_touches", 0),
            total_bounces=state_data.get("total_bounces", 0),
            has_reply=state_data.get("has_reply", False),
            has_positive_reply=state_data.get("has_positive_reply", False),
            stop_reason=StopReason(state_data["stop_reason"]) if state_data.get("stop_reason") else None,
            stopped_at=datetime.fromisoformat(state_data["stopped_at"]) if state_data.get("stopped_at") else None,
            started_at=datetime.fromisoformat(state_data["started_at"]) if state_data.get("started_at") else None,
            last_touch_at=datetime.fromisoformat(state_data["last_touch_at"]) if state_data.get("last_touch_at") else None,
            next_touch_at=datetime.fromisoformat(state_data["next_touch_at"]) if state_data.get("next_touch_at") else None,
        )

    async def _save_account_state(self, state: AccountOutreachState) -> None:
        """Save account state to Redis."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        key = f"abo:state:{state.lead_id}"

        await redis.set(key, json.dumps(state.to_dict()), ex=86400 * 90)  # 90 days

    async def initialize_account(
        self,
        lead_id: str,
        contact_ids: list[str],
        contact_priorities: dict[str, int] | None = None,
    ) -> AccountOutreachState:
        """Initialize outreach for an account with contacts.

        Args:
            lead_id: Lead/account ID
            contact_ids: List of contact IDs to reach
            contact_priorities: Optional priority scores {contact_id: priority}

        Returns:
            Initialized AccountOutreachState
        """
        # Sort contacts by priority (higher first)
        if contact_priorities:
            sorted_contacts = sorted(
                contact_ids,
                key=lambda c: contact_priorities.get(c, 0),
                reverse=True
            )
        else:
            sorted_contacts = contact_ids

        # Limit to max contacts
        selected_contacts = sorted_contacts[:self.max_contacts]

        contacts = [
            {
                "contact_id": cid,
                "status": ContactTouchStatus.PENDING.value,
                "touches": 0,
                "bounces": 0,
                "last_touch_at": None,
                "priority": contact_priorities.get(cid, 0) if contact_priorities else i,
            }
            for i, cid in enumerate(selected_contacts)
        ]

        state = AccountOutreachState(
            lead_id=lead_id,
            status=AccountStatus.IN_PROGRESS,
            contacts=contacts,
            total_touches=0,
            total_bounces=0,
            has_reply=False,
            has_positive_reply=False,
            stop_reason=None,
            stopped_at=None,
            started_at=datetime.now(UTC),
            last_touch_at=None,
            next_touch_at=datetime.now(UTC),
        )

        await self._save_account_state(state)

        logger.info(
            f"[ABO] Initialized account | lead={lead_id} | "
            f"contacts={len(selected_contacts)}"
        )

        return state

    # ========================================================================
    # Touch Management
    # ========================================================================

    async def get_next_touch(self, lead_id: str) -> NextTouchRecommendation:
        """Get recommendation for next touch.

        Args:
            lead_id: Lead/account ID

        Returns:
            NextTouchRecommendation
        """
        state = await self.get_account_state(lead_id)

        # Check if stopped
        if state.status in (AccountStatus.STOPPED, AccountStatus.REPLIED, AccountStatus.QUALIFIED):
            return NextTouchRecommendation(
                should_touch=False,
                contact_id=None,
                touch_number=0,
                recommended_time=None,
                reason=f"account_{state.status.value}",
            )

        if state.status == AccountStatus.EXHAUSTED:
            return NextTouchRecommendation(
                should_touch=False,
                contact_id=None,
                touch_number=0,
                recommended_time=None,
                reason="all_contacts_exhausted",
            )

        now = datetime.now(UTC)

        # Find next contact to touch
        for contact in state.contacts:
            if contact["status"] in (ContactTouchStatus.COMPLETED.value, ContactTouchStatus.STOPPED.value, ContactTouchStatus.BOUNCED.value):
                continue

            touches = contact["touches"]

            # Check if this contact has remaining touches
            if touches >= self.max_touches_per_contact:
                continue

            # Check timing
            last_touch = contact.get("last_touch_at")
            if last_touch and touches > 0:
                last_touch_dt = datetime.fromisoformat(last_touch)
                days_since = (now - last_touch_dt).days
                if days_since < self.days_between_contacts:
                    days_until = self.days_between_contacts - days_since
                    recommended_time = last_touch_dt + timedelta(days=self.days_between_contacts)
                    return NextTouchRecommendation(
                        should_touch=False,
                        contact_id=contact["contact_id"],
                        touch_number=touches + 1,
                        recommended_time=recommended_time,
                        reason=f"waiting_{days_until}_days",
                        days_until=days_until,
                    )

            # This contact is ready
            return NextTouchRecommendation(
                should_touch=True,
                contact_id=contact["contact_id"],
                touch_number=touches + 1,
                recommended_time=now,
                reason="contact_ready",
            )

        # All contacts exhausted
        return NextTouchRecommendation(
            should_touch=False,
            contact_id=None,
            touch_number=0,
            recommended_time=None,
            reason="all_contacts_exhausted",
        )

    async def record_touch(
        self,
        lead_id: str,
        contact_id: str,
        email_id: str | None = None,
    ) -> AccountOutreachState:
        """Record a touch to a contact.

        Args:
            lead_id: Lead/account ID
            contact_id: Contact ID
            email_id: Email message ID

        Returns:
            Updated AccountOutreachState
        """
        state = await self.get_account_state(lead_id)
        now = datetime.now(UTC)

        for contact in state.contacts:
            if contact["contact_id"] == contact_id:
                contact["touches"] += 1
                contact["last_touch_at"] = now.isoformat()
                contact["status"] = ContactTouchStatus.ACTIVE.value
                if email_id:
                    if "email_ids" not in contact:
                        contact["email_ids"] = []
                    contact["email_ids"].append(email_id)
                break

        state.total_touches += 1
        state.last_touch_at = now
        state.next_touch_at = now + timedelta(days=self.days_between_contacts)

        # Check if all contacts exhausted
        all_exhausted = all(
            c["touches"] >= self.max_touches_per_contact or
            c["status"] in (ContactTouchStatus.STOPPED.value, ContactTouchStatus.BOUNCED.value)
            for c in state.contacts
        )
        if all_exhausted:
            state.status = AccountStatus.EXHAUSTED

        await self._save_account_state(state)

        logger.info(
            f"[ABO] Touch recorded | lead={lead_id} | contact={contact_id} | "
            f"total_touches={state.total_touches}"
        )

        return state

    # ========================================================================
    # Event Handling
    # ========================================================================

    async def handle_reply(
        self,
        lead_id: str,
        contact_id: str,
        is_positive: bool = False,
    ) -> AccountOutreachState:
        """Handle a reply from a contact.

        Args:
            lead_id: Lead/account ID
            contact_id: Contact ID that replied
            is_positive: Whether reply indicates interest

        Returns:
            Updated AccountOutreachState
        """
        state = await self.get_account_state(lead_id)
        now = datetime.now(UTC)

        state.has_reply = True
        if is_positive:
            state.has_positive_reply = True

        # Update contact status
        for contact in state.contacts:
            if contact["contact_id"] == contact_id:
                contact["status"] = ContactTouchStatus.COMPLETED.value
                contact["replied"] = True
                contact["replied_at"] = now.isoformat()

        # Apply stop rule
        if self.stop_on_any_reply:
            state.status = AccountStatus.REPLIED if not is_positive else AccountStatus.QUALIFIED
            state.stop_reason = StopReason.POSITIVE_REPLY if is_positive else StopReason.REPLY_RECEIVED
            state.stopped_at = now

            # Stop all other contacts
            for contact in state.contacts:
                if contact["status"] == ContactTouchStatus.ACTIVE.value:
                    contact["status"] = ContactTouchStatus.STOPPED.value

        await self._save_account_state(state)

        logger.info(
            f"[ABO] Reply received | lead={lead_id} | contact={contact_id} | "
            f"positive={is_positive} | stopped={self.stop_on_any_reply}"
        )

        return state

    async def handle_bounce(
        self,
        lead_id: str,
        contact_id: str,
        is_hard_bounce: bool = False,
    ) -> AccountOutreachState:
        """Handle a bounce for a contact.

        Args:
            lead_id: Lead/account ID
            contact_id: Contact ID that bounced
            is_hard_bounce: Whether it's a hard bounce

        Returns:
            Updated AccountOutreachState
        """
        state = await self.get_account_state(lead_id)
        now = datetime.now(UTC)

        state.total_bounces += 1

        # Update contact
        for contact in state.contacts:
            if contact["contact_id"] == contact_id:
                contact["bounces"] = contact.get("bounces", 0) + 1
                if is_hard_bounce or contact["bounces"] >= 2:
                    contact["status"] = ContactTouchStatus.BOUNCED.value

        # Check account-level bounce stop rule
        if state.total_bounces >= self.bounce_stop_count:
            state.status = AccountStatus.STOPPED
            state.stop_reason = StopReason.BOUNCE_LIMIT
            state.stopped_at = now

            logger.warning(
                f"[ABO] Account stopped due to bounces | lead={lead_id} | "
                f"bounces={state.total_bounces}"
            )

        await self._save_account_state(state)

        return state

    async def handle_opt_out(
        self,
        lead_id: str,
        contact_id: str | None = None,
    ) -> AccountOutreachState:
        """Handle an opt-out (stops entire account).

        Args:
            lead_id: Lead/account ID
            contact_id: Contact ID that opted out (optional)

        Returns:
            Updated AccountOutreachState
        """
        state = await self.get_account_state(lead_id)
        now = datetime.now(UTC)

        state.status = AccountStatus.STOPPED
        state.stop_reason = StopReason.OPT_OUT
        state.stopped_at = now

        # Stop all contacts
        for contact in state.contacts:
            contact["status"] = ContactTouchStatus.STOPPED.value

        await self._save_account_state(state)

        logger.warning(
            f"[ABO] Account opt-out | lead={lead_id} | contact={contact_id}"
        )

        return state

    async def stop_account(
        self,
        lead_id: str,
        reason: StopReason = StopReason.MANUAL,
    ) -> AccountOutreachState:
        """Manually stop outreach for an account.

        Args:
            lead_id: Lead/account ID
            reason: Stop reason

        Returns:
            Updated AccountOutreachState
        """
        state = await self.get_account_state(lead_id)

        state.status = AccountStatus.STOPPED
        state.stop_reason = reason
        state.stopped_at = datetime.now(UTC)

        for contact in state.contacts:
            if contact["status"] == ContactTouchStatus.ACTIVE.value:
                contact["status"] = ContactTouchStatus.STOPPED.value

        await self._save_account_state(state)

        logger.info(f"[ABO] Account stopped | lead={lead_id} | reason={reason.value}")

        return state

    # ========================================================================
    # Bulk Operations
    # ========================================================================

    async def get_accounts_ready_for_touch(
        self,
        limit: int = 100,
    ) -> list[NextTouchRecommendation]:
        """Get accounts ready for next touch.

        Args:
            limit: Maximum accounts to return

        Returns:
            List of touch recommendations
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        ready = []

        async for key in redis.scan_iter("abo:state:*"):
            if len(ready) >= limit:
                break

            lead_id = key.split(":")[-1]
            recommendation = await self.get_next_touch(lead_id)

            if recommendation.should_touch:
                ready.append(recommendation)

        return ready

    async def get_account_stats(self) -> dict[str, Any]:
        """Get aggregate account outreach statistics.

        Returns:
            Statistics dict
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        stats = {
            "total_accounts": 0,
            "by_status": {},
            "total_touches": 0,
            "total_replies": 0,
            "total_positive_replies": 0,
        }

        async for key in redis.scan_iter("abo:state:*"):
            data = await redis.get(key)
            if data:
                state = json.loads(data)
                stats["total_accounts"] += 1

                status = state.get("status", "unknown")
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

                stats["total_touches"] += state.get("total_touches", 0)
                if state.get("has_reply"):
                    stats["total_replies"] += 1
                if state.get("has_positive_reply"):
                    stats["total_positive_replies"] += 1

        return stats

    async def get_contact_statuses(
        self,
        lead_id: str,
    ) -> list[dict[str, Any]]:
        """Get contact statuses for an account.

        Args:
            lead_id: Lead/account ID

        Returns:
            List of contact status dicts
        """
        state = await self.get_account_state(lead_id)
        return state.contacts

    async def get_active_accounts(
        self,
        campaign_id: str | None = None,
        limit: int = 100,
    ) -> list[AccountOutreachState]:
        """Get all active account outreach campaigns.

        Args:
            campaign_id: Filter by campaign
            limit: Maximum to return

        Returns:
            List of active AccountOutreachState
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        accounts = []

        async for key in redis.scan_iter("abo:state:*"):
            if len(accounts) >= limit:
                break

            data = await redis.get(key)
            if data:
                state_data = json.loads(data)

                # Filter by active status
                status = state_data.get("status")
                if status not in (AccountStatus.IN_PROGRESS.value,):
                    continue

                # Filter by campaign if specified
                if campaign_id and state_data.get("campaign_id") != campaign_id:
                    continue

                accounts.append(AccountOutreachState(
                    lead_id=state_data["lead_id"],
                    status=AccountStatus(state_data["status"]),
                    contacts=state_data.get("contacts", []),
                    total_touches=state_data.get("total_touches", 0),
                    total_bounces=state_data.get("total_bounces", 0),
                    has_reply=state_data.get("has_reply", False),
                    has_positive_reply=state_data.get("has_positive_reply", False),
                    stop_reason=StopReason(state_data["stop_reason"]) if state_data.get("stop_reason") else None,
                    stopped_at=datetime.fromisoformat(state_data["stopped_at"]) if state_data.get("stopped_at") else None,
                    started_at=datetime.fromisoformat(state_data["started_at"]) if state_data.get("started_at") else None,
                    last_touch_at=datetime.fromisoformat(state_data["last_touch_at"]) if state_data.get("last_touch_at") else None,
                    next_touch_at=datetime.fromisoformat(state_data["next_touch_at"]) if state_data.get("next_touch_at") else None,
                ))

        return accounts

    async def get_outreach_stats(
        self,
        campaign_id: str | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get account-based outreach statistics.

        Args:
            campaign_id: Filter by campaign
            days: Days to analyze

        Returns:
            Statistics dict
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        stats = {
            "period_days": days,
            "campaign_id": campaign_id,
            "total_accounts": 0,
            "active_accounts": 0,
            "completed_accounts": 0,
            "stopped_accounts": 0,
            "total_touches": 0,
            "total_bounces": 0,
            "reply_rate": 0.0,
            "positive_rate": 0.0,
            "by_status": {},
            "by_stop_reason": {},
        }

        accounts_with_reply = 0
        accounts_with_positive = 0

        async for key in redis.scan_iter("abo:state:*"):
            data = await redis.get(key)
            if data:
                state = json.loads(data)

                # Filter by campaign if specified
                if campaign_id and state.get("campaign_id") != campaign_id:
                    continue

                stats["total_accounts"] += 1

                status = state.get("status", "unknown")
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

                if status == AccountStatus.IN_PROGRESS.value:
                    stats["active_accounts"] += 1
                elif status in (AccountStatus.REPLIED.value, AccountStatus.QUALIFIED.value, AccountStatus.EXHAUSTED.value):
                    stats["completed_accounts"] += 1
                elif status == AccountStatus.STOPPED.value:
                    stats["stopped_accounts"] += 1

                stop_reason = state.get("stop_reason")
                if stop_reason:
                    stats["by_stop_reason"][stop_reason] = stats["by_stop_reason"].get(stop_reason, 0) + 1

                stats["total_touches"] += state.get("total_touches", 0)
                stats["total_bounces"] += state.get("total_bounces", 0)

                if state.get("has_reply"):
                    accounts_with_reply += 1
                if state.get("has_positive_reply"):
                    accounts_with_positive += 1

        if stats["total_accounts"] > 0:
            stats["reply_rate"] = round(accounts_with_reply / stats["total_accounts"], 3)
            stats["positive_rate"] = round(accounts_with_positive / stats["total_accounts"], 3)

        return stats


# Singleton
account_outreach = AccountOutreachService()
