"""Analytics Service.

KPI, метрики, дашборд из ARCHITECTURE.md раздел 13.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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

# Python 3.10 compatibility
UTC = timezone.utc

logger = logging.getLogger(__name__)


@dataclass
class FunnelMetrics:
    """Funnel conversion metrics."""

    discovered: int
    enriched: int
    scored: int
    qualified: int
    outreach_started: int
    replied: int
    interested: int
    handed_off: int
    converted: int
    lost: int

    period_start: datetime
    period_end: datetime


@dataclass
class EmailPerformance:
    """Email performance metrics."""

    total_sent: int
    total_delivered: int
    total_opened: int
    total_clicked: int
    total_replied: int
    total_bounced: int

    open_rate: float
    click_rate: float
    reply_rate: float
    bounce_rate: float

    by_type: dict[str, dict[str, float]] | None = None


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
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        segment: str | None = None,
        period_days: int = 7,
        campaign_id: UUID | None = None,
    ) -> FunnelMetrics:
        """Get funnel conversion metrics.

        Args:
            start_date: Start of date range (optional)
            end_date: End of date range (optional)
            segment: Filter by segment (optional)
            period_days: Number of days to analyze (used if start_date not provided)
            campaign_id: Filter by campaign (optional)

        Returns:
            Funnel metrics
        """
        if end_date is None:
            period_end = datetime.now(UTC)
        else:
            period_end = end_date

        if start_date is None:
            period_start = period_end - timedelta(days=period_days)
        else:
            period_start = start_date

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

        # Get counts - map old status names to new
        discovered = await self._count_leads_created(period_start, campaign_id)
        enriched = status_counts.get(LeadStatus.ENRICHED.value, 0)
        scored = status_counts.get(LeadStatus.SCORED.value, 0)
        qualified = status_counts.get(LeadStatus.QUALIFIED.value, 0)
        outreach_sent = status_counts.get(LeadStatus.OUTREACH_SENT.value, 0)
        in_sequence = status_counts.get(LeadStatus.IN_SEQUENCE.value, 0)
        reply_received = status_counts.get(LeadStatus.REPLY_RECEIVED.value, 0)
        interest_detected = status_counts.get(LeadStatus.INTEREST_DETECTED.value, 0)
        handed = status_counts.get(LeadStatus.HANDED_TO_MANAGER.value, 0)
        converted = status_counts.get(LeadStatus.CONVERTED.value, 0)
        archived = status_counts.get(LeadStatus.ARCHIVED.value, 0)
        opted_out = status_counts.get(LeadStatus.OPTED_OUT.value, 0)

        # Calculate total outreach
        outreach_started = outreach_sent + in_sequence + reply_received + interest_detected + qualified + handed + converted

        return FunnelMetrics(
            discovered=discovered,
            enriched=enriched,
            scored=scored,
            qualified=qualified,
            outreach_started=outreach_started,
            replied=reply_received + interest_detected,
            interested=interest_detected,
            handed_off=handed,
            converted=converted,
            lost=archived + opted_out,
            period_start=period_start,
            period_end=period_end,
        )

    async def get_email_performance(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        period_days: int = 7,
        campaign_id: UUID | None = None,
    ) -> EmailPerformance:
        """Get email performance metrics.

        Args:
            start_date: Start of date range (optional)
            end_date: End of date range (optional)
            period_days: Number of days to analyze (used if start_date not provided)
            campaign_id: Filter by campaign (optional)

        Returns:
            Email performance metrics
        """
        if end_date is None:
            period_end = datetime.now(UTC)
        else:
            period_end = end_date

        if start_date is None:
            period_start = period_end - timedelta(days=period_days)
        else:
            period_start = start_date

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
        total_delivered = result.scalar_one() or 0

        # Bounced
        result = await self.db.execute(
            select(func.count(EmailMessageDB.id)).where(
                and_(base_filter, EmailMessageDB.bounced == True)  # noqa: E712
            )
        )
        total_bounced = result.scalar_one() or 0

        # Opened
        result = await self.db.execute(
            select(func.count(EmailMessageDB.id)).where(
                and_(base_filter, EmailMessageDB.opened == True)  # noqa: E712
            )
        )
        total_opened = result.scalar_one() or 0

        # Clicked (assuming there's a clicked field, else use 0)
        total_clicked = 0
        try:
            result = await self.db.execute(
                select(func.count(EmailMessageDB.id)).where(
                    and_(base_filter, EmailMessageDB.clicked == True)  # noqa: E712
                )
            )
            total_clicked = result.scalar_one() or 0
        except Exception:
            pass

        # Replied
        result = await self.db.execute(
            select(func.count(EmailMessageDB.id)).where(
                and_(base_filter, EmailMessageDB.replied == True)  # noqa: E712
            )
        )
        total_replied = result.scalar_one() or 0

        # Calculate rates
        open_rate = total_opened / total_delivered if total_delivered > 0 else 0
        click_rate = total_clicked / total_delivered if total_delivered > 0 else 0
        reply_rate = total_replied / total_delivered if total_delivered > 0 else 0
        bounce_rate = total_bounced / total_sent if total_sent > 0 else 0

        return EmailPerformance(
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_opened=total_opened,
            total_clicked=total_clicked,
            total_replied=total_replied,
            total_bounced=total_bounced,
            open_rate=open_rate,
            click_rate=click_rate,
            reply_rate=reply_rate,
            bounce_rate=bounce_rate,
            by_type={},
        )

    async def get_time_series(
        self,
        metric: str,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "day",
    ) -> list[dict[str, Any]]:
        """Get time series data for a metric.

        Args:
            metric: Metric name
            start_date: Start date
            end_date: End date
            granularity: Time granularity (hour, day, week, month)

        Returns:
            List of data points
        """
        data = []
        current = start_date

        if granularity == "hour":
            delta = timedelta(hours=1)
        elif granularity == "week":
            delta = timedelta(weeks=1)
        elif granularity == "month":
            delta = timedelta(days=30)
        else:
            delta = timedelta(days=1)

        while current < end_date:
            next_date = current + delta

            if metric == "discovered":
                result = await self.db.execute(
                    select(func.count(EmployerLeadDB.id)).where(
                        and_(
                            EmployerLeadDB.created_at >= current,
                            EmployerLeadDB.created_at < next_date,
                        )
                    )
                )
                value = result.scalar_one() or 0
            elif metric == "sent":
                result = await self.db.execute(
                    select(func.count(EmailMessageDB.id)).where(
                        and_(
                            EmailMessageDB.sent_at >= current,
                            EmailMessageDB.sent_at < next_date,
                        )
                    )
                )
                value = result.scalar_one() or 0
            elif metric == "opened":
                result = await self.db.execute(
                    select(func.count(EmailMessageDB.id)).where(
                        and_(
                            EmailMessageDB.opened == True,  # noqa: E712
                            EmailMessageDB.sent_at >= current,
                            EmailMessageDB.sent_at < next_date,
                        )
                    )
                )
                value = result.scalar_one() or 0
            elif metric == "replied":
                result = await self.db.execute(
                    select(func.count(EmailMessageDB.id)).where(
                        and_(
                            EmailMessageDB.replied == True,  # noqa: E712
                            EmailMessageDB.sent_at >= current,
                            EmailMessageDB.sent_at < next_date,
                        )
                    )
                )
                value = result.scalar_one() or 0
            elif metric == "converted":
                result = await self.db.execute(
                    select(func.count(EmployerLeadDB.id)).where(
                        and_(
                            EmployerLeadDB.status == LeadStatus.CONVERTED.value,
                            EmployerLeadDB.updated_at >= current,
                            EmployerLeadDB.updated_at < next_date,
                        )
                    )
                )
                value = result.scalar_one() or 0
            else:
                value = 0

            data.append({
                "date": current.isoformat(),
                "value": value,
            })

            current = next_date

        return data

    async def get_segment_performance(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        period_days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get performance breakdown by segment.

        Args:
            start_date: Start of date range
            end_date: End of date range
            period_days: Number of days to analyze

        Returns:
            List of segment metrics
        """
        # TODO: Implement with proper segment data
        return []

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

    async def export_data(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Export analytics data.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Export data
        """
        funnel = await self.get_funnel_metrics(start_date=start_date, end_date=end_date)
        email_perf = await self.get_email_performance(start_date=start_date, end_date=end_date)
        handoff = await self.get_handoff_metrics(period_days=7)
        daily = await self.get_daily_stats(days=7)
        intents = await self.get_reply_intent_distribution(period_days=7)

        return {
            "funnel": {
                "discovered": funnel.discovered,
                "enriched": funnel.enriched,
                "scored": funnel.scored,
                "qualified": funnel.qualified,
                "outreach_started": funnel.outreach_started,
                "replied": funnel.replied,
                "interested": funnel.interested,
                "handed_off": funnel.handed_off,
                "converted": funnel.converted,
                "lost": funnel.lost,
            },
            "email": {
                "total_sent": email_perf.total_sent,
                "open_rate": email_perf.open_rate,
                "reply_rate": email_perf.reply_rate,
                "bounce_rate": email_perf.bounce_rate,
            },
            "handoff": handoff,
            "reply_intents": intents,
            "daily_stats": daily,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    async def export_metrics_summary(self) -> dict[str, Any]:
        """Export full metrics summary for dashboard.

        Returns:
            Complete metrics summary
        """
        return await self.export_data()
