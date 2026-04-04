"""Analytics API endpoints.

Метрики, отчёты и аналитика.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

UTC = timezone.utc

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.storage.database import async_session_factory

router = APIRouter(prefix="/analytics", tags=["analytics"])


# Response models
class FunnelMetricsResponse(BaseModel):
    """Funnel metrics response."""

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

    # Conversion rates
    enrichment_rate: float
    qualification_rate: float
    reply_rate: float
    conversion_rate: float


class EmailPerformanceResponse(BaseModel):
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

    # By email type
    by_type: dict[str, dict[str, Any]]


class TimeSeriesDataPoint(BaseModel):
    """Time series data point."""

    date: str
    value: float


class TimeSeriesResponse(BaseModel):
    """Time series response."""

    metric: str
    data: list[TimeSeriesDataPoint]
    total: float
    average: float


class SegmentPerformanceResponse(BaseModel):
    """Segment performance metrics."""

    segment: str
    leads_count: int
    qualified_count: int
    converted_count: int
    qualification_rate: float
    conversion_rate: float
    avg_score: float


class DashboardResponse(BaseModel):
    """Dashboard summary response."""

    period: str
    funnel: FunnelMetricsResponse
    email_performance: EmailPerformanceResponse
    top_segments: list[SegmentPerformanceResponse]
    recent_handoffs: int
    conversion_value: float


@router.get("/funnel", response_model=FunnelMetricsResponse)
async def get_funnel_metrics(
    start_date: datetime | None = Query(None, description="Start date"),
    end_date: datetime | None = Query(None, description="End date"),
    segment: str | None = Query(None, description="Filter by segment"),
) -> FunnelMetricsResponse:
    """Get funnel metrics.

    Args:
        start_date: Start of date range
        end_date: End of date range
        segment: Optional segment filter

    Returns:
        Funnel metrics
    """
    from app.services.analytics_service import AnalyticsService

    async with async_session_factory() as db:
        analytics = AnalyticsService(db=db)

        metrics = await analytics.get_funnel_metrics(
            start_date=start_date,
            end_date=end_date,
            segment=segment,
        )

        # Calculate rates
        discovered = metrics.discovered or 1
        outreach = metrics.outreach_started or 1
        handed_off = metrics.handed_off or 1

        return FunnelMetricsResponse(
            discovered=metrics.discovered,
            enriched=metrics.enriched,
            scored=metrics.scored,
            qualified=metrics.qualified,
            outreach_started=metrics.outreach_started,
            replied=metrics.replied,
            interested=metrics.interested,
            handed_off=metrics.handed_off,
            converted=metrics.converted,
            lost=metrics.lost,
            enrichment_rate=metrics.enriched / discovered,
            qualification_rate=metrics.qualified / discovered,
            reply_rate=metrics.replied / outreach if outreach else 0,
            conversion_rate=metrics.converted / handed_off if handed_off else 0,
        )


@router.get("/email-performance", response_model=EmailPerformanceResponse)
async def get_email_performance(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> EmailPerformanceResponse:
    """Get email performance metrics.

    Args:
        start_date: Start of date range
        end_date: End of date range

    Returns:
        Email performance metrics
    """
    from app.services.analytics_service import AnalyticsService

    async with async_session_factory() as db:
        analytics = AnalyticsService(db=db)

        perf = await analytics.get_email_performance(
            start_date=start_date,
            end_date=end_date,
        )

        return EmailPerformanceResponse(
            total_sent=perf.total_sent,
            total_delivered=perf.total_delivered,
            total_opened=perf.total_opened,
            total_clicked=perf.total_clicked,
            total_replied=perf.total_replied,
            total_bounced=perf.total_bounced,
            open_rate=perf.open_rate,
            click_rate=perf.click_rate,
            reply_rate=perf.reply_rate,
            bounce_rate=perf.bounce_rate,
            by_type=perf.by_type or {},
        )


@router.get("/time-series/{metric}", response_model=TimeSeriesResponse)
async def get_time_series(
    metric: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    granularity: str = Query("day", pattern="^(hour|day|week|month)$"),
) -> TimeSeriesResponse:
    """Get time series data for a metric.

    Args:
        metric: Metric name (discovered, sent, opened, converted, etc.)
        start_date: Start of date range
        end_date: End of date range
        granularity: Time granularity

    Returns:
        Time series data
    """
    # Default to last 30 days
    if not end_date:
        end_date = datetime.now(UTC)
    if not start_date:
        start_date = end_date - timedelta(days=30)

    from app.services.analytics_service import AnalyticsService

    async with async_session_factory() as db:
        analytics = AnalyticsService(db=db)

        data = await analytics.get_time_series(
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
        )

        values = [d.get("value", 0) for d in data]

        return TimeSeriesResponse(
            metric=metric,
            data=[
                TimeSeriesDataPoint(
                    date=d.get("date", ""),
                    value=d.get("value", 0),
                )
                for d in data
            ],
            total=sum(values),
            average=sum(values) / len(values) if values else 0,
        )


@router.get("/segments", response_model=list[SegmentPerformanceResponse])
async def get_segment_performance(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[SegmentPerformanceResponse]:
    """Get performance by segment.

    Args:
        start_date: Start of date range
        end_date: End of date range

    Returns:
        Segment performance metrics
    """
    from app.services.analytics_service import AnalyticsService

    async with async_session_factory() as db:
        analytics = AnalyticsService(db=db)

        segments = await analytics.get_segment_performance(
            start_date=start_date,
            end_date=end_date,
        )

        return [
            SegmentPerformanceResponse(
                segment=s.get("segment", "unknown"),
                leads_count=s.get("leads_count", 0),
                qualified_count=s.get("qualified_count", 0),
                converted_count=s.get("converted_count", 0),
                qualification_rate=s.get("qualification_rate", 0),
                conversion_rate=s.get("conversion_rate", 0),
                avg_score=s.get("avg_score", 0),
            )
            for s in segments
        ]


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    period: str = Query("week", pattern="^(day|week|month|quarter)$"),
) -> DashboardResponse:
    """Get dashboard summary.

    Args:
        period: Time period

    Returns:
        Dashboard data
    """
    from app.services.analytics_service import AnalyticsService

    # Calculate date range
    end_date = datetime.now(UTC)
    period_days = {
        "day": 1,
        "week": 7,
        "month": 30,
        "quarter": 90,
    }
    start_date = end_date - timedelta(days=period_days.get(period, 7))

    async with async_session_factory() as db:
        analytics = AnalyticsService(db=db)

        # Get all metrics
        funnel = await analytics.get_funnel_metrics(
            start_date=start_date,
            end_date=end_date,
        )

        email_perf = await analytics.get_email_performance(
            start_date=start_date,
            end_date=end_date,
        )

        segments = await analytics.get_segment_performance(
            start_date=start_date,
            end_date=end_date,
        )

        # Calculate rates
        discovered = funnel.discovered or 1
        outreach = funnel.outreach_started or 1
        handed_off = funnel.handed_off or 1

        funnel_response = FunnelMetricsResponse(
            discovered=funnel.discovered,
            enriched=funnel.enriched,
            scored=funnel.scored,
            qualified=funnel.qualified,
            outreach_started=funnel.outreach_started,
            replied=funnel.replied,
            interested=funnel.interested,
            handed_off=funnel.handed_off,
            converted=funnel.converted,
            lost=funnel.lost,
            enrichment_rate=funnel.enriched / discovered,
            qualification_rate=funnel.qualified / discovered,
            reply_rate=funnel.replied / outreach if outreach else 0,
            conversion_rate=funnel.converted / handed_off if handed_off else 0,
        )

        email_response = EmailPerformanceResponse(
            total_sent=email_perf.total_sent,
            total_delivered=email_perf.total_delivered,
            total_opened=email_perf.total_opened,
            total_clicked=email_perf.total_clicked,
            total_replied=email_perf.total_replied,
            total_bounced=email_perf.total_bounced,
            open_rate=email_perf.open_rate,
            click_rate=email_perf.click_rate,
            reply_rate=email_perf.reply_rate,
            bounce_rate=email_perf.bounce_rate,
            by_type=email_perf.by_type or {},
        )

        top_segments = [
            SegmentPerformanceResponse(
                segment=s.get("segment", "unknown"),
                leads_count=s.get("leads_count", 0),
                qualified_count=s.get("qualified_count", 0),
                converted_count=s.get("converted_count", 0),
                qualification_rate=s.get("qualification_rate", 0),
                conversion_rate=s.get("conversion_rate", 0),
                avg_score=s.get("avg_score", 0),
            )
            for s in segments[:5]  # Top 5 segments
        ]

        return DashboardResponse(
            period=period,
            funnel=funnel_response,
            email_performance=email_response,
            top_segments=top_segments,
            recent_handoffs=funnel.handed_off,
            conversion_value=0.0,  # Would calculate from actual deal values
        )


@router.get("/export")
async def export_analytics(
    format: str = Query("json", pattern="^(json|csv)$"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict[str, Any]:
    """Export analytics data.

    Args:
        format: Export format (json or csv)
        start_date: Start of date range
        end_date: End of date range

    Returns:
        Export data or download URL
    """
    from app.services.analytics_service import AnalyticsService

    async with async_session_factory() as db:
        analytics = AnalyticsService(db=db)

        data = await analytics.export_data(
            start_date=start_date,
            end_date=end_date,
        )

        if format == "csv":
            # In production, would generate CSV file and return download URL
            return {
                "format": "csv",
                "status": "generating",
                "message": "CSV export would be generated asynchronously",
            }

        return {
            "format": "json",
            "data": data,
            "generated_at": datetime.now(UTC).isoformat(),
        }
