"""Deliverability Trends Service.

Tracks and analyzes deliverability metrics over time for dashboard/reporting.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


@dataclass
class DailyMetrics:
    """Daily deliverability metrics."""

    date: str
    sent: int
    delivered: int
    bounced: int
    complained: int
    opened: int
    clicked: int
    replied: int
    delivery_rate: float
    bounce_rate: float
    open_rate: float
    reply_rate: float


@dataclass
class TrendAnalysis:
    """Trend analysis results."""

    metric: str
    current_value: float
    previous_value: float
    change_percent: float
    trend: str  # "improving", "stable", "declining"
    is_healthy: bool


@dataclass
class DeliverabilityDashboard:
    """Complete deliverability dashboard data."""

    period_days: int
    generated_at: datetime

    # Summary metrics
    total_sent: int
    total_delivered: int
    total_bounced: int
    total_complained: int
    total_opened: int
    total_replied: int

    # Rates
    delivery_rate: float
    bounce_rate: float
    complaint_rate: float
    open_rate: float
    reply_rate: float

    # Daily breakdown
    daily_metrics: list[DailyMetrics]

    # Trends
    trends: list[TrendAnalysis]

    # Top performing
    top_senders: list[dict[str, Any]]
    top_domains: list[dict[str, Any]]
    problem_domains: list[dict[str, Any]]

    # Health status
    overall_health: str  # "excellent", "good", "warning", "critical"
    health_issues: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "period_days": self.period_days,
            "generated_at": self.generated_at.isoformat(),
            "summary": {
                "total_sent": self.total_sent,
                "total_delivered": self.total_delivered,
                "total_bounced": self.total_bounced,
                "total_complained": self.total_complained,
                "total_opened": self.total_opened,
                "total_replied": self.total_replied,
            },
            "rates": {
                "delivery_rate": self.delivery_rate,
                "bounce_rate": self.bounce_rate,
                "complaint_rate": self.complaint_rate,
                "open_rate": self.open_rate,
                "reply_rate": self.reply_rate,
            },
            "daily_metrics": [
                {
                    "date": d.date,
                    "sent": d.sent,
                    "delivered": d.delivered,
                    "bounced": d.bounced,
                    "complained": d.complained,
                    "opened": d.opened,
                    "clicked": d.clicked,
                    "replied": d.replied,
                    "delivery_rate": d.delivery_rate,
                    "bounce_rate": d.bounce_rate,
                    "open_rate": d.open_rate,
                    "reply_rate": d.reply_rate,
                }
                for d in self.daily_metrics
            ],
            "trends": [
                {
                    "metric": t.metric,
                    "current_value": t.current_value,
                    "previous_value": t.previous_value,
                    "change_percent": t.change_percent,
                    "trend": t.trend,
                    "is_healthy": t.is_healthy,
                }
                for t in self.trends
            ],
            "top_senders": self.top_senders,
            "top_domains": self.top_domains,
            "problem_domains": self.problem_domains,
            "health": {
                "overall": self.overall_health,
                "issues": self.health_issues,
                "recommendations": self.recommendations,
            },
        }


class DeliverabilityTrendsService:
    """Analyzes deliverability trends for dashboard and reporting.

    Features:
    - Daily/weekly/monthly metrics
    - Trend analysis with change detection
    - Top/bottom performers
    - Health scoring and recommendations
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    async def get_dashboard(
        self,
        days: int = 30,
        compare_previous: bool = True,
    ) -> DeliverabilityDashboard:
        """Get complete deliverability dashboard.

        Args:
            days: Number of days to analyze
            compare_previous: Whether to compare with previous period

        Returns:
            DeliverabilityDashboard
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Collect daily metrics
        daily_metrics = []
        total_sent = 0
        total_delivered = 0
        total_bounced = 0
        total_complained = 0
        total_opened = 0
        total_clicked = 0
        total_replied = 0

        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            metrics = await self._get_day_metrics(redis, day)
            daily_metrics.append(metrics)

            total_sent += metrics.sent
            total_delivered += metrics.delivered
            total_bounced += metrics.bounced
            total_complained += metrics.complained
            total_opened += metrics.opened
            total_clicked += metrics.clicked
            total_replied += metrics.replied

        # Calculate rates
        delivery_rate = total_delivered / total_sent if total_sent > 0 else 0
        bounce_rate = total_bounced / total_sent if total_sent > 0 else 0
        complaint_rate = total_complained / total_sent if total_sent > 0 else 0
        open_rate = total_opened / total_delivered if total_delivered > 0 else 0
        reply_rate = total_replied / total_delivered if total_delivered > 0 else 0

        # Analyze trends
        trends = []
        if compare_previous and days >= 7:
            trends = await self._analyze_trends(redis, days)

        # Get top performers
        top_senders = await self._get_top_senders(redis, days, limit=5)
        top_domains = await self._get_top_domains(redis, days, limit=5)
        problem_domains = await self._get_problem_domains(redis, days, limit=5)

        # Determine health
        health, issues, recommendations = self._assess_health(
            delivery_rate, bounce_rate, complaint_rate, trends
        )

        return DeliverabilityDashboard(
            period_days=days,
            generated_at=now,
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_bounced=total_bounced,
            total_complained=total_complained,
            total_opened=total_opened,
            total_replied=total_replied,
            delivery_rate=round(delivery_rate, 4),
            bounce_rate=round(bounce_rate, 4),
            complaint_rate=round(complaint_rate, 4),
            open_rate=round(open_rate, 4),
            reply_rate=round(reply_rate, 4),
            daily_metrics=daily_metrics,
            trends=trends,
            top_senders=top_senders,
            top_domains=top_domains,
            problem_domains=problem_domains,
            overall_health=health,
            health_issues=issues,
            recommendations=recommendations,
        )

    async def _get_day_metrics(self, redis: Any, day: str) -> DailyMetrics:
        """Get metrics for a specific day."""
        sent = int(await redis.get(f"deliverability:global:sent:{day}") or 0)
        delivered = int(await redis.get(f"deliverability:delivered:global:{day}") or 0)
        bounced = int(await redis.get(f"deliverability:bounces:global:{day}") or 0)
        complained = int(await redis.get(f"deliverability:complaints:global:{day}") or 0)
        opened = int(await redis.get(f"deliverability:opened:global:{day}") or 0)
        clicked = int(await redis.get(f"deliverability:clicked:global:{day}") or 0)
        replied = int(await redis.get(f"deliverability:replied:global:{day}") or 0)

        return DailyMetrics(
            date=day,
            sent=sent,
            delivered=delivered,
            bounced=bounced,
            complained=complained,
            opened=opened,
            clicked=clicked,
            replied=replied,
            delivery_rate=delivered / sent if sent > 0 else 0,
            bounce_rate=bounced / sent if sent > 0 else 0,
            open_rate=opened / delivered if delivered > 0 else 0,
            reply_rate=replied / delivered if delivered > 0 else 0,
        )

    async def _analyze_trends(
        self,
        redis: Any,
        days: int,
    ) -> list[TrendAnalysis]:
        """Analyze metric trends comparing current vs previous period."""
        now = datetime.now(UTC)
        half_days = days // 2

        # Current period totals
        current_sent = 0
        current_delivered = 0
        current_bounced = 0
        current_opened = 0
        current_replied = 0

        for i in range(half_days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            current_sent += int(await redis.get(f"deliverability:global:sent:{day}") or 0)
            current_delivered += int(await redis.get(f"deliverability:delivered:global:{day}") or 0)
            current_bounced += int(await redis.get(f"deliverability:bounces:global:{day}") or 0)
            current_opened += int(await redis.get(f"deliverability:opened:global:{day}") or 0)
            current_replied += int(await redis.get(f"deliverability:replied:global:{day}") or 0)

        # Previous period totals
        prev_sent = 0
        prev_delivered = 0
        prev_bounced = 0
        prev_opened = 0
        prev_replied = 0

        for i in range(half_days, days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            prev_sent += int(await redis.get(f"deliverability:global:sent:{day}") or 0)
            prev_delivered += int(await redis.get(f"deliverability:delivered:global:{day}") or 0)
            prev_bounced += int(await redis.get(f"deliverability:bounces:global:{day}") or 0)
            prev_opened += int(await redis.get(f"deliverability:opened:global:{day}") or 0)
            prev_replied += int(await redis.get(f"deliverability:replied:global:{day}") or 0)

        trends = []

        # Delivery rate trend
        current_delivery_rate = current_delivered / current_sent if current_sent > 0 else 0
        prev_delivery_rate = prev_delivered / prev_sent if prev_sent > 0 else 0
        trends.append(self._create_trend(
            "delivery_rate", current_delivery_rate, prev_delivery_rate, higher_is_better=True
        ))

        # Bounce rate trend
        current_bounce_rate = current_bounced / current_sent if current_sent > 0 else 0
        prev_bounce_rate = prev_bounced / prev_sent if prev_sent > 0 else 0
        trends.append(self._create_trend(
            "bounce_rate", current_bounce_rate, prev_bounce_rate, higher_is_better=False
        ))

        # Open rate trend
        current_open_rate = current_opened / current_delivered if current_delivered > 0 else 0
        prev_open_rate = prev_opened / prev_delivered if prev_delivered > 0 else 0
        trends.append(self._create_trend(
            "open_rate", current_open_rate, prev_open_rate, higher_is_better=True
        ))

        # Reply rate trend
        current_reply_rate = current_replied / current_delivered if current_delivered > 0 else 0
        prev_reply_rate = prev_replied / prev_delivered if prev_delivered > 0 else 0
        trends.append(self._create_trend(
            "reply_rate", current_reply_rate, prev_reply_rate, higher_is_better=True
        ))

        return trends

    def _create_trend(
        self,
        metric: str,
        current: float,
        previous: float,
        higher_is_better: bool = True,
    ) -> TrendAnalysis:
        """Create trend analysis for a metric."""
        if previous == 0:
            change_percent = 100.0 if current > 0 else 0.0
        else:
            change_percent = ((current - previous) / previous) * 100

        # Determine trend direction
        if abs(change_percent) < 5:
            trend = "stable"
        elif change_percent > 0:
            trend = "improving" if higher_is_better else "declining"
        else:
            trend = "declining" if higher_is_better else "improving"

        # Determine if healthy
        is_healthy = trend != "declining"

        return TrendAnalysis(
            metric=metric,
            current_value=round(current, 4),
            previous_value=round(previous, 4),
            change_percent=round(change_percent, 1),
            trend=trend,
            is_healthy=is_healthy,
        )

    async def _get_top_senders(
        self,
        redis: Any,
        days: int,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Get top performing senders."""
        now = datetime.now(UTC)
        senders: dict[str, dict[str, int]] = {}

        # Scan for sender keys
        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            pattern = f"throttle:sender:*:{day}"

            async for key in redis.scan_iter(pattern):
                parts = key.split(":")
                if len(parts) >= 4:
                    sender = parts[2]
                    if sender not in senders:
                        senders[sender] = {"sent": 0, "delivered": 0, "bounced": 0}

                    senders[sender]["sent"] += int(await redis.get(key) or 0)

                    # Get delivered count
                    delivered_key = f"deliverability:delivered:sender:{sender}:{day}"
                    senders[sender]["delivered"] += int(await redis.get(delivered_key) or 0)

                    # Get bounce count
                    bounce_key = f"deliverability:bounces:sender:{sender}:{day}"
                    senders[sender]["bounced"] += int(await redis.get(bounce_key) or 0)

        # Calculate rates and sort
        results = []
        for sender, stats in senders.items():
            if stats["sent"] >= 10:  # Minimum sample
                delivery_rate = stats["delivered"] / stats["sent"]
                results.append({
                    "sender": sender,
                    "sent": stats["sent"],
                    "delivered": stats["delivered"],
                    "delivery_rate": round(delivery_rate, 3),
                })

        results.sort(key=lambda x: x["delivery_rate"], reverse=True)
        return results[:limit]

    async def _get_top_domains(
        self,
        redis: Any,
        days: int,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Get top performing recipient domains."""
        now = datetime.now(UTC)
        domains: dict[str, dict[str, int]] = {}

        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            pattern = f"throttle:domain:*:{day}"

            async for key in redis.scan_iter(pattern):
                parts = key.split(":")
                if len(parts) >= 4:
                    domain = parts[2]
                    if domain not in domains:
                        domains[domain] = {"sent": 0, "delivered": 0, "bounced": 0}

                    domains[domain]["sent"] += int(await redis.get(key) or 0)

                    delivered_key = f"deliverability:delivered:domain:{domain}:{day}"
                    domains[domain]["delivered"] += int(await redis.get(delivered_key) or 0)

                    bounce_key = f"deliverability:bounces:domain:{domain}:{day}"
                    domains[domain]["bounced"] += int(await redis.get(bounce_key) or 0)

        results = []
        for domain, stats in domains.items():
            if stats["sent"] >= 5:
                delivery_rate = stats["delivered"] / stats["sent"]
                results.append({
                    "domain": domain,
                    "sent": stats["sent"],
                    "delivered": stats["delivered"],
                    "delivery_rate": round(delivery_rate, 3),
                })

        results.sort(key=lambda x: x["delivery_rate"], reverse=True)
        return results[:limit]

    async def _get_problem_domains(
        self,
        redis: Any,
        days: int,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Get domains with high bounce rates."""
        now = datetime.now(UTC)
        domains: dict[str, dict[str, int]] = {}

        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            pattern = f"deliverability:bounces:domain:*:{day}"

            async for key in redis.scan_iter(pattern):
                parts = key.split(":")
                if len(parts) >= 5:
                    domain = parts[3]
                    if domain not in domains:
                        domains[domain] = {"sent": 0, "bounced": 0}

                    domains[domain]["bounced"] += int(await redis.get(key) or 0)

                    sent_key = f"throttle:domain:{domain}:{day}"
                    domains[domain]["sent"] += int(await redis.get(sent_key) or 0)

        results = []
        for domain, stats in domains.items():
            if stats["sent"] >= 3 and stats["bounced"] > 0:
                bounce_rate = stats["bounced"] / stats["sent"]
                if bounce_rate > 0.1:  # Only domains with >10% bounce rate
                    results.append({
                        "domain": domain,
                        "sent": stats["sent"],
                        "bounced": stats["bounced"],
                        "bounce_rate": round(bounce_rate, 3),
                    })

        results.sort(key=lambda x: x["bounce_rate"], reverse=True)
        return results[:limit]

    def _assess_health(
        self,
        delivery_rate: float,
        bounce_rate: float,
        complaint_rate: float,
        trends: list[TrendAnalysis],
    ) -> tuple[str, list[str], list[str]]:
        """Assess overall deliverability health.

        Returns:
            Tuple of (health_status, issues, recommendations)
        """
        issues = []
        recommendations = []
        score = 100

        # Check delivery rate
        if delivery_rate < 0.90:
            issues.append(f"Delivery rate below 90%: {delivery_rate:.1%}")
            recommendations.append("Review email content for spam triggers")
            score -= 20
        elif delivery_rate < 0.95:
            issues.append(f"Delivery rate could be improved: {delivery_rate:.1%}")
            score -= 10

        # Check bounce rate
        if bounce_rate > 0.10:
            issues.append(f"High bounce rate: {bounce_rate:.1%}")
            recommendations.append("Clean email list and verify addresses before sending")
            score -= 25
        elif bounce_rate > 0.05:
            issues.append(f"Elevated bounce rate: {bounce_rate:.1%}")
            recommendations.append("Monitor bounce patterns by domain")
            score -= 10

        # Check complaint rate
        if complaint_rate > 0.005:
            issues.append(f"High complaint rate: {complaint_rate:.2%}")
            recommendations.append("Review targeting and add clear unsubscribe links")
            score -= 30
        elif complaint_rate > 0.001:
            issues.append(f"Elevated complaint rate: {complaint_rate:.2%}")
            score -= 15

        # Check trends
        for trend in trends:
            if trend.trend == "declining" and trend.metric in ("delivery_rate", "open_rate"):
                issues.append(f"{trend.metric} declining by {abs(trend.change_percent):.1f}%")
                score -= 10

        # Determine overall health
        if score >= 85:
            health = "excellent"
        elif score >= 70:
            health = "good"
        elif score >= 50:
            health = "warning"
            if not recommendations:
                recommendations.append("Monitor metrics closely and investigate issues")
        else:
            health = "critical"
            recommendations.insert(0, "URGENT: Pause campaigns and investigate issues")

        return health, issues, recommendations

    async def record_global_event(
        self,
        event_type: str,
        count: int = 1,
    ) -> None:
        """Record a global deliverability event.

        Args:
            event_type: Event type (sent, delivered, bounced, complained, opened, clicked, replied)
            count: Number of events
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        key = f"deliverability:{event_type}:global:{today}"
        await redis.incrby(key, count)
        await redis.expire(key, 86400 * 90)  # 90 days TTL


# Singleton
deliverability_trends = DeliverabilityTrendsService()
