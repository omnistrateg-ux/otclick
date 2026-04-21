"""Revenue Loop Service.

Tracks deal stages from meeting to revenue.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.config.settings import settings

UTC = timezone.utc

logger = logging.getLogger(__name__)


class DealStage(str, Enum):
    """Deal pipeline stages."""

    # Pre-deal stages (from lead)
    HANDED_OFF = "handed_off"
    MEETING_SCHEDULED = "meeting_scheduled"
    MEETING_COMPLETED = "meeting_completed"

    # Deal stages
    PROPOSAL_SENT = "proposal_sent"
    NEGOTIATION = "negotiation"
    CONTRACT_SENT = "contract_sent"

    # Terminal stages
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    STALLED = "stalled"


class LostReason(str, Enum):
    """Reasons for lost deals."""

    PRICE = "price"
    COMPETITOR = "competitor"
    NO_BUDGET = "no_budget"
    NO_DECISION = "no_decision"
    TIMING = "timing"
    PRODUCT_FIT = "product_fit"
    UNRESPONSIVE = "unresponsive"
    OTHER = "other"


# Stage transition rules
STAGE_TRANSITIONS = {
    DealStage.HANDED_OFF: [DealStage.MEETING_SCHEDULED, DealStage.CLOSED_LOST, DealStage.STALLED],
    DealStage.MEETING_SCHEDULED: [DealStage.MEETING_COMPLETED, DealStage.CLOSED_LOST, DealStage.STALLED],
    DealStage.MEETING_COMPLETED: [DealStage.PROPOSAL_SENT, DealStage.CLOSED_LOST, DealStage.STALLED],
    DealStage.PROPOSAL_SENT: [DealStage.NEGOTIATION, DealStage.CLOSED_WON, DealStage.CLOSED_LOST, DealStage.STALLED],
    DealStage.NEGOTIATION: [DealStage.CONTRACT_SENT, DealStage.CLOSED_WON, DealStage.CLOSED_LOST, DealStage.STALLED],
    DealStage.CONTRACT_SENT: [DealStage.CLOSED_WON, DealStage.CLOSED_LOST, DealStage.NEGOTIATION],
    DealStage.CLOSED_WON: [],  # Terminal
    DealStage.CLOSED_LOST: [],  # Terminal
    DealStage.STALLED: [DealStage.MEETING_SCHEDULED, DealStage.CLOSED_LOST],  # Can reactivate
}


@dataclass
class Deal:
    """A deal in the revenue pipeline."""

    id: str
    lead_id: str
    account_id: str  # Company ID
    stage: DealStage
    value: float  # Expected revenue
    currency: str = "RUB"
    probability: float = 0.0  # Win probability (0-1)

    # Attribution
    campaign_id: str | None = None
    source: str | None = None

    # Ownership
    manager_id: str | None = None
    created_by: str | None = None

    # Timing
    created_at: datetime | None = None
    updated_at: datetime | None = None
    expected_close_date: datetime | None = None
    actual_close_date: datetime | None = None

    # Stage history
    stage_history: list[dict[str, Any]] = field(default_factory=list)

    # Outcome
    lost_reason: LostReason | None = None
    lost_notes: str | None = None
    won_revenue: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "account_id": self.account_id,
            "stage": self.stage.value,
            "value": self.value,
            "currency": self.currency,
            "probability": round(self.probability, 2),
            "campaign_id": self.campaign_id,
            "source": self.source,
            "manager_id": self.manager_id,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "expected_close_date": self.expected_close_date.isoformat() if self.expected_close_date else None,
            "actual_close_date": self.actual_close_date.isoformat() if self.actual_close_date else None,
            "stage_history": self.stage_history,
            "lost_reason": self.lost_reason.value if self.lost_reason else None,
            "lost_notes": self.lost_notes,
            "won_revenue": self.won_revenue,
        }


@dataclass
class StageConversionRates:
    """Conversion rates between stages."""

    from_stage: str
    to_stage: str
    conversion_rate: float
    avg_days: float
    sample_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "conversion_rate": round(self.conversion_rate, 3),
            "avg_days": round(self.avg_days, 1),
            "sample_size": self.sample_size,
        }


@dataclass
class RevenueMetrics:
    """Revenue pipeline metrics."""

    period_days: int
    total_deals: int
    total_value: float
    won_deals: int
    won_revenue: float
    lost_deals: int
    lost_value: float
    win_rate: float
    avg_deal_value: float
    avg_cycle_days: float
    by_stage: dict[str, int]
    by_source: dict[str, float]
    by_campaign: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "period_days": self.period_days,
            "total_deals": self.total_deals,
            "total_value": round(self.total_value, 2),
            "won_deals": self.won_deals,
            "won_revenue": round(self.won_revenue, 2),
            "lost_deals": self.lost_deals,
            "lost_value": round(self.lost_value, 2),
            "win_rate": round(self.win_rate, 3),
            "avg_deal_value": round(self.avg_deal_value, 2),
            "avg_cycle_days": round(self.avg_cycle_days, 1),
            "by_stage": self.by_stage,
            "by_source": self.by_source,
            "by_campaign": self.by_campaign,
        }


# Stage probability defaults
STAGE_PROBABILITIES = {
    DealStage.HANDED_OFF: 0.10,
    DealStage.MEETING_SCHEDULED: 0.20,
    DealStage.MEETING_COMPLETED: 0.35,
    DealStage.PROPOSAL_SENT: 0.50,
    DealStage.NEGOTIATION: 0.70,
    DealStage.CONTRACT_SENT: 0.85,
    DealStage.CLOSED_WON: 1.0,
    DealStage.CLOSED_LOST: 0.0,
    DealStage.STALLED: 0.05,
}


class RevenueLoopService:
    """Manages revenue pipeline and deal tracking.

    Features:
    - Deal stage management
    - Revenue attribution to leads/campaigns
    - Conversion rate tracking
    - Pipeline metrics
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Deal Management
    # ========================================================================

    async def create_deal(
        self,
        lead_id: str,
        account_id: str,
        value: float,
        manager_id: str | None = None,
        campaign_id: str | None = None,
        source: str | None = None,
        expected_close_date: datetime | None = None,
    ) -> Deal:
        """Create a new deal from a handoff.

        Args:
            lead_id: Lead ID
            account_id: Account/company ID
            value: Expected deal value
            manager_id: Assigned manager
            campaign_id: Source campaign
            source: Lead source
            expected_close_date: Expected close date

        Returns:
            Created Deal
        """
        from app.storage.redis import get_redis
        from uuid import uuid4
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        deal = Deal(
            id=str(uuid4()),
            lead_id=lead_id,
            account_id=account_id,
            stage=DealStage.HANDED_OFF,
            value=value,
            probability=STAGE_PROBABILITIES[DealStage.HANDED_OFF],
            campaign_id=campaign_id,
            source=source,
            manager_id=manager_id,
            created_by=manager_id,
            created_at=now,
            updated_at=now,
            expected_close_date=expected_close_date or (now + timedelta(days=30)),
            stage_history=[{
                "stage": DealStage.HANDED_OFF.value,
                "entered_at": now.isoformat(),
                "actor": manager_id,
            }],
        )

        # Store deal
        key = f"deal:{deal.id}"
        await redis.set(key, json.dumps(deal.to_dict()), ex=86400 * 365)

        # Index by lead
        await redis.sadd(f"deals:lead:{lead_id}", deal.id)
        await redis.expire(f"deals:lead:{lead_id}", 86400 * 365)

        # Index by account
        await redis.sadd(f"deals:account:{account_id}", deal.id)
        await redis.expire(f"deals:account:{account_id}", 86400 * 365)

        # Index by manager
        if manager_id:
            await redis.sadd(f"deals:manager:{manager_id}", deal.id)
            await redis.expire(f"deals:manager:{manager_id}", 86400 * 365)

        # Track metrics
        await self._record_stage_entry(deal.stage, campaign_id, source)

        logger.info(
            f"[REVENUE] Deal created | deal={deal.id} | lead={lead_id} | "
            f"value={value} | manager={manager_id}"
        )

        return deal

    async def get_deal(self, deal_id: str) -> Deal | None:
        """Get deal by ID.

        Args:
            deal_id: Deal ID

        Returns:
            Deal or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        data = await redis.get(f"deal:{deal_id}")

        if not data:
            return None

        d = json.loads(data)
        return Deal(
            id=d["id"],
            lead_id=d["lead_id"],
            account_id=d["account_id"],
            stage=DealStage(d["stage"]),
            value=d["value"],
            currency=d.get("currency", "RUB"),
            probability=d.get("probability", 0),
            campaign_id=d.get("campaign_id"),
            source=d.get("source"),
            manager_id=d.get("manager_id"),
            created_by=d.get("created_by"),
            created_at=datetime.fromisoformat(d["created_at"]) if d.get("created_at") else None,
            updated_at=datetime.fromisoformat(d["updated_at"]) if d.get("updated_at") else None,
            expected_close_date=datetime.fromisoformat(d["expected_close_date"]) if d.get("expected_close_date") else None,
            actual_close_date=datetime.fromisoformat(d["actual_close_date"]) if d.get("actual_close_date") else None,
            stage_history=d.get("stage_history", []),
            lost_reason=LostReason(d["lost_reason"]) if d.get("lost_reason") else None,
            lost_notes=d.get("lost_notes"),
            won_revenue=d.get("won_revenue"),
        )

    async def advance_stage(
        self,
        deal_id: str,
        new_stage: DealStage,
        actor: str,
        notes: str | None = None,
    ) -> Deal:
        """Advance deal to next stage.

        Args:
            deal_id: Deal ID
            new_stage: Target stage
            actor: Who made the change
            notes: Optional notes

        Returns:
            Updated Deal

        Raises:
            ValueError: If transition not allowed
        """
        from app.storage.redis import get_redis
        import json

        deal = await self.get_deal(deal_id)
        if not deal:
            raise ValueError(f"Deal {deal_id} not found")

        # Validate transition
        allowed = STAGE_TRANSITIONS.get(deal.stage, [])
        if new_stage not in allowed:
            raise ValueError(
                f"Cannot transition from {deal.stage.value} to {new_stage.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        old_stage = deal.stage
        now = datetime.now(UTC)

        # Update deal
        deal.stage = new_stage
        deal.probability = STAGE_PROBABILITIES.get(new_stage, 0.5)
        deal.updated_at = now

        # Add to history
        deal.stage_history.append({
            "stage": new_stage.value,
            "from_stage": old_stage.value,
            "entered_at": now.isoformat(),
            "actor": actor,
            "notes": notes,
        })

        # Handle terminal stages
        if new_stage == DealStage.CLOSED_WON:
            deal.actual_close_date = now
            deal.won_revenue = deal.value

        elif new_stage == DealStage.CLOSED_LOST:
            deal.actual_close_date = now

        # Save
        redis = await get_redis()
        await redis.set(f"deal:{deal_id}", json.dumps(deal.to_dict()), ex=86400 * 365)

        # Track metrics
        await self._record_stage_transition(old_stage, new_stage, deal.campaign_id, deal.source)

        logger.info(
            f"[REVENUE] Stage advanced | deal={deal_id} | "
            f"{old_stage.value} -> {new_stage.value} | actor={actor}"
        )

        return deal

    async def close_lost(
        self,
        deal_id: str,
        reason: LostReason,
        actor: str,
        notes: str | None = None,
    ) -> Deal:
        """Close deal as lost.

        Args:
            deal_id: Deal ID
            reason: Lost reason
            actor: Who closed it
            notes: Optional notes

        Returns:
            Updated Deal
        """
        deal = await self.advance_stage(deal_id, DealStage.CLOSED_LOST, actor, notes)

        # Update lost reason
        from app.storage.redis import get_redis
        import json

        deal.lost_reason = reason
        deal.lost_notes = notes

        redis = await get_redis()
        await redis.set(f"deal:{deal_id}", json.dumps(deal.to_dict()), ex=86400 * 365)

        # Track lost reason
        await self._record_lost_reason(reason, deal.campaign_id, deal.source)

        return deal

    async def close_won(
        self,
        deal_id: str,
        actual_revenue: float,
        actor: str,
        notes: str | None = None,
    ) -> Deal:
        """Close deal as won.

        Args:
            deal_id: Deal ID
            actual_revenue: Actual revenue (may differ from estimate)
            actor: Who closed it
            notes: Optional notes

        Returns:
            Updated Deal
        """
        deal = await self.advance_stage(deal_id, DealStage.CLOSED_WON, actor, notes)

        # Update revenue
        from app.storage.redis import get_redis
        import json

        deal.won_revenue = actual_revenue

        redis = await get_redis()
        await redis.set(f"deal:{deal_id}", json.dumps(deal.to_dict()), ex=86400 * 365)

        # Track revenue
        await self._record_revenue(actual_revenue, deal.campaign_id, deal.source)

        logger.info(
            f"[REVENUE] Deal won! | deal={deal_id} | revenue={actual_revenue} | "
            f"campaign={deal.campaign_id}"
        )

        return deal

    # ========================================================================
    # Metrics
    # ========================================================================

    async def _record_stage_entry(
        self,
        stage: DealStage,
        campaign_id: str | None,
        source: str | None,
    ) -> None:
        """Record stage entry for metrics."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        pipe = redis.pipeline()
        pipe.incr(f"revenue:stage:{stage.value}:total")
        pipe.incr(f"revenue:stage:{stage.value}:daily:{today}")

        if campaign_id:
            pipe.incr(f"revenue:campaign:{campaign_id}:stage:{stage.value}")
        if source:
            pipe.incr(f"revenue:source:{source}:stage:{stage.value}")

        await pipe.execute()

    async def _record_stage_transition(
        self,
        from_stage: DealStage,
        to_stage: DealStage,
        campaign_id: str | None,
        source: str | None,
    ) -> None:
        """Record stage transition for conversion tracking."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        pipe = redis.pipeline()
        pipe.incr(f"revenue:transition:{from_stage.value}:{to_stage.value}:total")

        if campaign_id:
            pipe.incr(f"revenue:campaign:{campaign_id}:transition:{from_stage.value}:{to_stage.value}")

        await pipe.execute()

    async def _record_lost_reason(
        self,
        reason: LostReason,
        campaign_id: str | None,
        source: str | None,
    ) -> None:
        """Record lost reason."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        pipe = redis.pipeline()
        pipe.incr(f"revenue:lost_reason:{reason.value}:total")

        if campaign_id:
            pipe.incr(f"revenue:campaign:{campaign_id}:lost_reason:{reason.value}")

        await pipe.execute()

    async def _record_revenue(
        self,
        amount: float,
        campaign_id: str | None,
        source: str | None,
    ) -> None:
        """Record revenue."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        pipe = redis.pipeline()
        pipe.incrbyfloat("revenue:total", amount)
        pipe.incrbyfloat(f"revenue:daily:{today}", amount)

        if campaign_id:
            pipe.incrbyfloat(f"revenue:campaign:{campaign_id}:total", amount)
        if source:
            pipe.incrbyfloat(f"revenue:source:{source}:total", amount)

        await pipe.execute()

    async def get_conversion_rates(self) -> list[StageConversionRates]:
        """Get stage conversion rates.

        Returns:
            List of stage conversion rates
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        rates = []

        for from_stage in DealStage:
            allowed = STAGE_TRANSITIONS.get(from_stage, [])
            total_from = int(await redis.get(f"revenue:stage:{from_stage.value}:total") or 0)

            for to_stage in allowed:
                count = int(await redis.get(
                    f"revenue:transition:{from_stage.value}:{to_stage.value}:total"
                ) or 0)

                if total_from > 0:
                    rate = count / total_from
                else:
                    rate = 0.0

                rates.append(StageConversionRates(
                    from_stage=from_stage.value,
                    to_stage=to_stage.value,
                    conversion_rate=rate,
                    avg_days=0.0,  # TODO: Calculate from stage history
                    sample_size=count,
                ))

        return rates

    async def get_pipeline_metrics(
        self,
        days: int = 30,
        campaign_id: str | None = None,
    ) -> RevenueMetrics:
        """Get pipeline metrics.

        Args:
            days: Days to analyze
            campaign_id: Filter by campaign

        Returns:
            RevenueMetrics
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Scan all deals
        deals = []
        async for key in redis.scan_iter("deal:*"):
            if not key.startswith("deal:") or ":" in key[5:]:
                continue
            data = await redis.get(key)
            if data:
                d = json.loads(data)
                if campaign_id and d.get("campaign_id") != campaign_id:
                    continue
                deals.append(d)

        # Calculate metrics
        total_deals = len(deals)
        total_value = sum(d["value"] for d in deals)
        won_deals = [d for d in deals if d["stage"] == DealStage.CLOSED_WON.value]
        won_revenue = sum(d.get("won_revenue", 0) or 0 for d in won_deals)
        lost_deals = [d for d in deals if d["stage"] == DealStage.CLOSED_LOST.value]
        lost_value = sum(d["value"] for d in lost_deals)

        by_stage = {}
        for d in deals:
            stage = d["stage"]
            by_stage[stage] = by_stage.get(stage, 0) + 1

        by_source = {}
        for d in deals:
            source = d.get("source", "unknown")
            by_source[source] = by_source.get(source, 0) + d["value"]

        by_campaign = {}
        for d in deals:
            camp = d.get("campaign_id", "unknown")
            by_campaign[camp] = by_campaign.get(camp, 0) + d["value"]

        closed_deals = len(won_deals) + len(lost_deals)
        win_rate = len(won_deals) / closed_deals if closed_deals > 0 else 0.0
        avg_deal_value = total_value / total_deals if total_deals > 0 else 0.0

        return RevenueMetrics(
            period_days=days,
            total_deals=total_deals,
            total_value=total_value,
            won_deals=len(won_deals),
            won_revenue=won_revenue,
            lost_deals=len(lost_deals),
            lost_value=lost_value,
            win_rate=win_rate,
            avg_deal_value=avg_deal_value,
            avg_cycle_days=0.0,  # TODO: Calculate from close dates
            by_stage=by_stage,
            by_source=by_source,
            by_campaign=by_campaign,
        )

    async def get_deals_by_manager(
        self,
        manager_id: str,
        active_only: bool = True,
    ) -> list[Deal]:
        """Get deals for a manager.

        Args:
            manager_id: Manager ID
            active_only: Only return active deals

        Returns:
            List of deals
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        deal_ids = await redis.smembers(f"deals:manager:{manager_id}")

        deals = []
        for deal_id in deal_ids:
            deal = await self.get_deal(deal_id)
            if deal:
                if active_only and deal.stage in (DealStage.CLOSED_WON, DealStage.CLOSED_LOST):
                    continue
                deals.append(deal)

        return deals


# Singleton
revenue_loop = RevenueLoopService()
