"""Analytics Service.

KPI, метрики, дашборд из ARCHITECTURE.md раздел 13.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import (
    DomainEventDB,
    EmailMessageDB,
    EmailSequenceDB,
    EmployerLeadDB,
    LeadScoreDB,
    LeadSignalDB,
    ManagerHandoffDB,
)
from app.models.enums import IndustrySegment, LeadStatus, ReplyIntent

logger = logging.getLogger(__name__)


@dataclass
class FunnelMetrics:
    """Funnel conversion metrics."""

    leads_found: int
    enriched: int
    scored: int
    email_ready: int
    outreach_sent: int
    replied: int
    interest_detected: int
    qualified: int
    handed_to_manager: int

    # Calculated rates
    enrichment_rate: float
    score_pass_rate: float
    outreach_rate: float
    reply_rate: float
    positive_reply_rate: float
    qualification_rate: float
    handoff_rate: float

    period_start: datetime
    period_end: datetime


@dataclass
class EmailPerformance:
    """Email performance metrics."""

    total_sent: int
    delivered: int
    bounced: int
    opened: int
    replied: int

    delivery_rate: float
    open_rate: float
    reply_rate: float
    bounce_rate: float

    by_segment: dict[str, dict[str, float]]
    by_email_type: dict[str, dict[str, float]]


@dataclass
class CostMetrics:
    """LLM cost metrics."""

    total_cost_usd: float
    cost_per_lead: float
    cost_per_qualified_lead: float
    cost_by_task_type: dict[str, float]
    cost_by_provider: dict[str, float]


class AnalyticsService:
    """Service for analytics and KPI tracking.

    Реализует метрики из ARCHITECTURE.md раздел 13.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_funnel_metrics(
        self,
        period_days: int = 7,
        campaign_id: UUID | None = None,
    ) -> FunnelMetrics:
        """Get funnel conversion metrics.

        Args:
            period_days: Number of days to analyze
            campaign_id: Filter by campaign (optional)

        Returns:
            Funnel metrics
        """
        period_start = datetime.now(UTC) - timedelta(days=period_days)
        period_end = datetime.now(UTC)

        # Base query
        base_filter = EmployerLeadDB.created_at >= period_start
        if campaign_id:
            base_filter = and_(base_filter, EmployerLeadDB.campaign_id == campaign_id)

        # Count by status
        status_counts = {}
        for status in LeadStatus:
            result = await self.db.execute(
                select(func.count(EmployerLeadDB.id)).where(
                    and_(base_filter, EmployerLeadDB.status == status.value)
                )
            )
            status_counts[status.value] = result.scalar_one() or 0

        # Get counts
        leads_found = await self._count_leads_created(period_start, campaign_id)
        enriched = status_counts.get(LeadStatus.ENRICHED.value, 0)
        scored = status_counts.get(LeadStatus.SCORED.value, 0)
        email_ready = status_counts.get(LeadStatus.EMAIL_READY.value, 0)
        outreach_sent = status_counts.get(LeadStatus.OUTREACH_SENT.value, 0)
        in_sequence = status_counts.get(LeadStatus.IN_SEQUENCE.value, 0)
        reply_received = status_counts.get(LeadStatus.REPLY_RECEIVED.value, 0)
        interest_detected = status_counts.get(LeadStatus.INTEREST_DETECTED.value, 0)
        qualified = status_counts.get(LeadStatus.QUALIFIED.value, 0)
        handed = status_counts.get(LeadStatus.HANDED_TO_MANAGER.value, 0)

        # Calculate total sent
        total_sent = outreach_sent + in_sequence + reply_received + interest_detected + qualified + handed

        # Calculate rates
        enrichment_rate = enriched / leads_found if leads_found > 0 else 0
        score_pass_rate = scored / enriched if enriched > 0 else 0
        outreach_rate = total_sent / scored if scored > 0 else 0
        reply_rate = (reply_received + interest_detected + qualified + handed) / total_sent if total_sent > 0 else 0
        positive_reply_rate = (interest_detected + qualified + handed) / (reply_received + interest_detected + qualified + handed) if (reply_received + interest_detected + qualified + handed) > 0 else 0
        qualification_rate = (qualified + handed) / interest_detected if interest_detected > 0 else 0
        handoff_rate = handed / qualified if qualified > 0 else 0

        return FunnelMetrics(
            leads_found=leads_found,
            enriched=enriched,
            scored=scored,
            email_ready=email_ready,
            outreach_sent=total_sent,
            replied=reply_received + interest_detected + qualified + handed,
            interest_detected=interest_detected,
            qualified=qualified,
            handed_to_manager=handed,
            enrichment_rate=enrichment_rate,
            score_pass_rate=score_pass_rate,
            outreach_rate=outreach_rate,
            reply_rate=reply_rate,
            positive_reply_rate=positive_reply_rate,
            qualification_rate=qualification_rate,
            handoff_rate=handoff_rate,
            period_start=period_start,
            period_end=period_end,
        )

    async def get_email_performance(
        self,
        period_days: int = 7,
        campaign_id: UUID | None = None,
    ) -> EmailPerformance:
        """Get email performance metrics.

        Args:
            period_days: Number of days to analyze
            campaign_id: Filter by campaign (optional)

        Returns:
            Email performance metrics
        """
        period_start = datetime.now(UTC) - timedelta(days=period_days)

        # Base filter
        base_filter = EmailMessageDB.sent_at >= period_start

        # Total sent
        result = await self.db.execute(
            select(func.count(EmailMessageDB.id)).where(
                and_(base_filter, EmailMessageDB.sent_at.isnot(None))
            )
        )
        total_sent = result.scalar_one() or 0

        # Delivered
        result = await self.db.execute(
            select(func.count(EmailMessageDB.id)).where(
                and_(base_filter, EmailMessageDB.delivered == True)  # noqa: E712
            )
        )
        delivered = result.scalar_one() or 0

        # Bounced
        result = await self.db.execute(
            select(func.count(EmailMessageDB.id)).where(
                and_(base_filter, EmailMessageDB.bounced == True)  # noqa: E712
            )
        )
        bounced = result.scalar_one() or 0

        # Opened
        result = await self.db.execute(
            select(func.count(EmailMessageDB.id)).where(
                and_(base_filter, EmailMessageDB.opened == True)  # noqa: E712
            )
        )
        opened = result.scalar_one() or 0

        # Replied
        result = await self.db.execute(
            select(func.count(EmailMessageDB.id)).where(
                and_(base_filter, EmailMessageDB.replied == True)  # noqa: E712
            )
        )
        replied = result.scalar_one() or 0

        # Calculate rates
        delivery_rate = delivered / total_sent if total_sent > 0 else 0
        open_rate = opened / delivered if delivered > 0 else 0
        reply_rate = replied / delivered if delivered > 0 else 0
        bounce_rate = bounced / total_sent if total_sent > 0 else 0

        return EmailPerformance(
            total_sent=total_sent,
            delivered=delivered,
            bounced=bounced,
            opened=opened,
            replied=replied,
            delivery_rate=delivery_rate,
            open_rate=open_rate,
            reply_rate=reply_rate,
            bounce_rate=bounce_rate,
            by_segment={},  # TODO: implement segment breakdown
            by_email_type={},  # TODO: implement email type breakdown
        )

    async def get_reply_intent_distribution(
        self,
        period_days: int = 7,
    ) -> dict[str, int]:
        """Get distribution of reply intents.

        Args:
            period_days: Number of days to analyze

        Returns:
            Dict of intent -> count
        """
        period_start = datetime.now(UTC) - timedelta(days=period_days)

        result = await self.db.execute(
            select(
                LeadSignalDB.intent,
                func.count(LeadSignalDB.id),
            )
            .where(LeadSignalDB.analyzed_at >= period_start)
            .group_by(LeadSignalDB.intent)
        )

        return dict(result.all())

    async def get_segment_performance(
        self,
        period_days: int = 30,
    ) -> dict[str, dict[str, Any]]:
        """Get performance breakdown by segment.

        Args:
            period_days: Number of days to analyze

        Returns:
            Dict of segment -> metrics
        """
        # TODO: Implement with proper joins
        return {}

    async def get_handoff_metrics(
        self,
        period_days: int = 7,
    ) -> dict[str, Any]:
        """Get handoff and conversion metrics.

        Args:
            period_days: Number of days to analyze

        Returns:
            Handoff metrics
        """
        period_start = datetime.now(UTC) - timedelta(days=period_days)

        # Total handoffs
        result = await self.db.execute(
            select(func.count(ManagerHandoffDB.id)).where(
                ManagerHandoffDB.notified_at >= period_start
            )
        )
        total_handoffs = result.scalar_one() or 0

        # Accepted
        result = await self.db.execute(
            select(func.count(ManagerHandoffDB.id)).where(
                and_(
                    ManagerHandoffDB.notified_at >= period_start,
                    ManagerHandoffDB.accepted_at.isnot(None),
                )
            )
        )
        accepted = result.scalar_one() or 0

        # Calls scheduled
        result = await self.db.execute(
            select(func.count(ManagerHandoffDB.id)).where(
                and_(
                    ManagerHandoffDB.notified_at >= period_start,
                    ManagerHandoffDB.call_scheduled_at.isnot(None),
                )
            )
        )
        calls_scheduled = result.scalar_one() or 0

        # Average score of handed leads
        result = await self.db.execute(
            select(func.avg(ManagerHandoffDB.lead_score)).where(
                ManagerHandoffDB.notified_at >= period_start
            )
        )
        avg_score = result.scalar_one() or 0

        return {
            "total_handoffs": total_handoffs,
            "accepted": accepted,
            "calls_scheduled": calls_scheduled,
            "acceptance_rate": accepted / total_handoffs if total_handoffs > 0 else 0,
            "call_rate": calls_scheduled / accepted if accepted > 0 else 0,
            "avg_lead_score": avg_score,
        }

    async def _count_leads_created(
        self,
        since: datetime,
        campaign_id: UUID | None = None,
    ) -> int:
        """Count leads created since date.

        Args:
            since: Start datetime
            campaign_id: Filter by campaign

        Returns:
            Count of leads
        """
        filters = [EmployerLeadDB.created_at >= since]
        if campaign_id:
            filters.append(EmployerLeadDB.campaign_id == campaign_id)

        result = await self.db.execute(
            select(func.count(EmployerLeadDB.id)).where(and_(*filters))
        )
        return result.scalar_one() or 0

    async def get_daily_stats(
        self,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Get daily statistics.

        Args:
            days: Number of days

        Returns:
            List of daily stats
        """
        stats = []

        for i in range(days):
            date = datetime.now(UTC).date() - timedelta(days=i)
            day_start = datetime.combine(date, datetime.min.time()).replace(tzinfo=UTC)
            day_end = day_start + timedelta(days=1)

            # Leads created
            result = await self.db.execute(
                select(func.count(EmployerLeadDB.id)).where(
                    and_(
                        EmployerLeadDB.created_at >= day_start,
                        EmployerLeadDB.created_at < day_end,
                    )
                )
            )
            leads_created = result.scalar_one() or 0

            # Emails sent
            result = await self.db.execute(
                select(func.count(EmailMessageDB.id)).where(
                    and_(
                        EmailMessageDB.sent_at >= day_start,
                        EmailMessageDB.sent_at < day_end,
                    )
                )
            )
            emails_sent = result.scalar_one() or 0

            # Replies
            result = await self.db.execute(
                select(func.count(LeadSignalDB.id)).where(
                    and_(
                        LeadSignalDB.analyzed_at >= day_start,
                        LeadSignalDB.analyzed_at < day_end,
                    )
                )
            )
            replies = result.scalar_one() or 0

            stats.append({
                "date": date.isoformat(),
                "leads_created": leads_created,
                "emails_sent": emails_sent,
                "replies": replies,
            })

        return list(reversed(stats))

    async def export_metrics_summary(self) -> dict[str, Any]:
        """Export full metrics summary for dashboard.

        Returns:
            Complete metrics summary
        """
        funnel = await self.get_funnel_metrics(period_days=7)
        email_perf = await self.get_email_performance(period_days=7)
        handoff = await self.get_handoff_metrics(period_days=7)
        daily = await self.get_daily_stats(days=7)
        intents = await self.get_reply_intent_distribution(period_days=7)

        return {
            "funnel": {
                "leads_found": funnel.leads_found,
                "enrichment_rate": f"{funnel.enrichment_rate:.1%}",
                "outreach_sent": funnel.outreach_sent,
                "reply_rate": f"{funnel.reply_rate:.1%}",
                "positive_reply_rate": f"{funnel.positive_reply_rate:.1%}",
                "qualified": funnel.qualified,
                "handed_to_manager": funnel.handed_to_manager,
            },
            "email": {
                "total_sent": email_perf.total_sent,
                "open_rate": f"{email_perf.open_rate:.1%}",
                "reply_rate": f"{email_perf.reply_rate:.1%}",
                "bounce_rate": f"{email_perf.bounce_rate:.1%}",
            },
            "handoff": handoff,
            "reply_intents": intents,
            "daily_stats": daily,
            "generated_at": datetime.now(UTC).isoformat(),
        }
