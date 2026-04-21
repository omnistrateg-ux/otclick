"""Cohort Analytics and Anomaly Detection Service.

Cohort analysis and statistical anomaly detection.
"""

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class CohortType(str, Enum):
    """Types of cohorts."""

    WEEKLY = "weekly"  # By week of acquisition
    MONTHLY = "monthly"  # By month of acquisition
    SOURCE = "source"  # By lead source
    SEGMENT = "segment"  # By segment
    CAMPAIGN = "campaign"  # By campaign


class AnomalyType(str, Enum):
    """Types of anomalies."""

    SPIKE = "spike"  # Sudden increase
    DROP = "drop"  # Sudden decrease
    TREND_BREAK = "trend_break"  # Trend reversal
    OUTLIER = "outlier"  # Statistical outlier


class AnomalySeverity(str, Enum):
    """Anomaly severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CohortMetrics:
    """Metrics for a cohort."""

    cohort_id: str
    cohort_type: CohortType
    cohort_value: str
    period_start: datetime
    period_end: datetime
    size: int  # Number in cohort
    metrics: dict[str, float]  # Metric name -> value
    comparisons: dict[str, float] = field(default_factory=dict)  # vs previous

    def to_dict(self) -> dict[str, Any]:
        return {
            "cohort_id": self.cohort_id,
            "cohort_type": self.cohort_type.value,
            "cohort_value": self.cohort_value,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "size": self.size,
            "metrics": self.metrics,
            "comparisons": self.comparisons,
        }


@dataclass
class CohortComparison:
    """Comparison between cohorts."""

    cohort_a: str
    cohort_b: str
    metrics_diff: dict[str, float]  # Metric -> difference
    significant_changes: list[str]  # Metrics with significant change
    insights: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cohort_a": self.cohort_a,
            "cohort_b": self.cohort_b,
            "metrics_diff": self.metrics_diff,
            "significant_changes": self.significant_changes,
            "insights": self.insights,
        }


@dataclass
class Anomaly:
    """A detected anomaly."""

    id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    metric: str
    current_value: float
    expected_value: float
    deviation: float  # How far from expected (%)
    detected_at: datetime
    description: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "metric": self.metric,
            "current_value": self.current_value,
            "expected_value": self.expected_value,
            "deviation": self.deviation,
            "detected_at": self.detected_at.isoformat(),
            "description": self.description,
            "context": self.context,
        }


class CohortAnalyticsService:
    """Service for cohort analysis and anomaly detection.

    Features:
    - Cohort analysis by time, source, segment
    - Retention and conversion tracking
    - Anomaly detection
    - Trend analysis
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Cohort Analysis
    # ========================================================================

    async def get_cohort_metrics(
        self,
        cohort_type: CohortType,
        cohort_value: str,
        metrics: list[str] | None = None,
    ) -> CohortMetrics | None:
        """Get metrics for a specific cohort.

        Args:
            cohort_type: Type of cohort
            cohort_value: Cohort identifier (e.g., "2024-W01", "organic")
            metrics: Specific metrics to retrieve

        Returns:
            CohortMetrics or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        key = f"cohort:{cohort_type.value}:{cohort_value}"
        data = await redis.get(key)

        if not data:
            return None

        d = json.loads(data)

        return CohortMetrics(
            cohort_id=d["cohort_id"],
            cohort_type=CohortType(d["cohort_type"]),
            cohort_value=d["cohort_value"],
            period_start=datetime.fromisoformat(d["period_start"]),
            period_end=datetime.fromisoformat(d["period_end"]),
            size=d["size"],
            metrics=d["metrics"],
            comparisons=d.get("comparisons", {}),
        )

    async def get_weekly_cohorts(
        self,
        weeks: int = 12,
    ) -> list[CohortMetrics]:
        """Get weekly cohort analysis.

        Args:
            weeks: Number of weeks to analyze

        Returns:
            List of weekly cohort metrics
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)
        cohorts = []

        for i in range(weeks):
            week_start = now - timedelta(weeks=i)
            week_key = week_start.strftime("%Y-W%W")

            # Get or calculate cohort metrics
            key = f"cohort:weekly:{week_key}"
            data = await redis.get(key)

            if data:
                d = json.loads(data)
                cohort = CohortMetrics(
                    cohort_id=d["cohort_id"],
                    cohort_type=CohortType.WEEKLY,
                    cohort_value=week_key,
                    period_start=datetime.fromisoformat(d["period_start"]),
                    period_end=datetime.fromisoformat(d["period_end"]),
                    size=d["size"],
                    metrics=d["metrics"],
                    comparisons=d.get("comparisons", {}),
                )
            else:
                # Calculate from raw data
                cohort = await self._calculate_weekly_cohort(week_key, week_start)

            if cohort:
                cohorts.append(cohort)

        return cohorts

    async def _calculate_weekly_cohort(
        self,
        week_key: str,
        week_start: datetime,
    ) -> CohortMetrics:
        """Calculate metrics for a weekly cohort.

        Args:
            week_key: Week identifier
            week_start: Start of week

        Returns:
            CohortMetrics
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        week_end = week_start + timedelta(days=7)

        # Count leads acquired this week
        size = int(await redis.get(f"stats:weekly:{week_key}:leads_acquired") or 0)

        # Get conversion metrics
        enriched = int(await redis.get(f"stats:weekly:{week_key}:enriched") or 0)
        qualified = int(await redis.get(f"stats:weekly:{week_key}:qualified") or 0)
        handoffs = int(await redis.get(f"stats:weekly:{week_key}:handoffs") or 0)
        meetings = int(await redis.get(f"stats:weekly:{week_key}:meetings") or 0)
        conversions = int(await redis.get(f"stats:weekly:{week_key}:conversions") or 0)

        # Calculate rates
        metrics = {
            "leads_acquired": float(size),
            "enrichment_rate": enriched / size * 100 if size > 0 else 0,
            "qualification_rate": qualified / size * 100 if size > 0 else 0,
            "handoff_rate": handoffs / size * 100 if size > 0 else 0,
            "meeting_rate": meetings / size * 100 if size > 0 else 0,
            "conversion_rate": conversions / size * 100 if size > 0 else 0,
        }

        return CohortMetrics(
            cohort_id=f"weekly-{week_key}",
            cohort_type=CohortType.WEEKLY,
            cohort_value=week_key,
            period_start=week_start,
            period_end=week_end,
            size=size,
            metrics=metrics,
        )

    async def get_source_cohorts(self) -> list[CohortMetrics]:
        """Get cohort analysis by lead source.

        Returns:
            List of source cohort metrics
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        cohorts = []

        # Get all sources
        sources = await redis.smembers("cohort:sources:all")

        for source in sources:
            key = f"cohort:source:{source}"
            data = await redis.get(key)

            if data:
                d = json.loads(data)
                cohort = CohortMetrics(
                    cohort_id=d["cohort_id"],
                    cohort_type=CohortType.SOURCE,
                    cohort_value=source,
                    period_start=datetime.fromisoformat(d["period_start"]),
                    period_end=datetime.fromisoformat(d["period_end"]),
                    size=d["size"],
                    metrics=d["metrics"],
                    comparisons=d.get("comparisons", {}),
                )
                cohorts.append(cohort)

        return cohorts

    async def compare_cohorts(
        self,
        cohort_a_type: CohortType,
        cohort_a_value: str,
        cohort_b_type: CohortType,
        cohort_b_value: str,
    ) -> CohortComparison | None:
        """Compare two cohorts.

        Args:
            cohort_a_type: First cohort type
            cohort_a_value: First cohort value
            cohort_b_type: Second cohort type
            cohort_b_value: Second cohort value

        Returns:
            CohortComparison or None
        """
        cohort_a = await self.get_cohort_metrics(cohort_a_type, cohort_a_value)
        cohort_b = await self.get_cohort_metrics(cohort_b_type, cohort_b_value)

        if not cohort_a or not cohort_b:
            return None

        metrics_diff = {}
        significant_changes = []
        insights = []

        # Compare each metric
        for metric in cohort_a.metrics:
            if metric in cohort_b.metrics:
                val_a = cohort_a.metrics[metric]
                val_b = cohort_b.metrics[metric]

                if val_b != 0:
                    diff_pct = ((val_a - val_b) / val_b) * 100
                else:
                    diff_pct = 100 if val_a > 0 else 0

                metrics_diff[metric] = diff_pct

                # Check for significant change (>10%)
                if abs(diff_pct) > 10:
                    significant_changes.append(metric)
                    direction = "increased" if diff_pct > 0 else "decreased"
                    insights.append(
                        f"{metric} {direction} by {abs(diff_pct):.1f}%"
                    )

        return CohortComparison(
            cohort_a=cohort_a.cohort_id,
            cohort_b=cohort_b.cohort_id,
            metrics_diff=metrics_diff,
            significant_changes=significant_changes,
            insights=insights,
        )

    # ========================================================================
    # Retention Analysis
    # ========================================================================

    async def get_retention_matrix(
        self,
        weeks: int = 8,
    ) -> dict[str, Any]:
        """Get retention matrix showing cohort retention over time.

        Args:
            weeks: Number of weeks

        Returns:
            Retention matrix data
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        matrix = []

        for cohort_week in range(weeks):
            week_start = now - timedelta(weeks=cohort_week)
            cohort_key = week_start.strftime("%Y-W%W")

            # Get initial cohort size
            initial_size = int(await redis.get(f"stats:weekly:{cohort_key}:leads_acquired") or 0)

            if initial_size == 0:
                continue

            row = {
                "cohort": cohort_key,
                "initial_size": initial_size,
                "retention": [],
            }

            # Track retention for each subsequent week
            for retention_week in range(min(8, weeks - cohort_week)):
                key = f"retention:{cohort_key}:week_{retention_week}"
                active = int(await redis.get(key) or 0)
                retention_pct = (active / initial_size) * 100 if initial_size > 0 else 0
                row["retention"].append({
                    "week": retention_week,
                    "active": active,
                    "retention_pct": retention_pct,
                })

            matrix.append(row)

        return {
            "cohorts": matrix,
            "period_weeks": weeks,
            "generated_at": now.isoformat(),
        }

    # ========================================================================
    # Anomaly Detection
    # ========================================================================

    async def detect_anomalies(
        self,
        metric: str | None = None,
        lookback_days: int = 30,
    ) -> list[Anomaly]:
        """Detect anomalies in metrics.

        Args:
            metric: Specific metric to check, or all if None
            lookback_days: Days of history to analyze

        Returns:
            List of detected anomalies
        """
        from app.storage.redis import get_redis
        from uuid import uuid4

        redis = await get_redis()
        now = datetime.now(UTC)
        anomalies = []

        # Metrics to check
        metrics_to_check = [metric] if metric else [
            "leads_acquired",
            "emails_sent",
            "replies_received",
            "handoffs_created",
            "meetings_scheduled",
            "conversions",
            "bounce_rate",
            "response_time",
        ]

        for m in metrics_to_check:
            # Gather historical data
            values = []
            for i in range(lookback_days):
                day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
                val = float(await redis.get(f"stats:daily:{day}:{m}") or 0)
                values.append(val)

            if len(values) < 7:
                continue

            # Get current value (today)
            current = values[0]

            # Calculate statistics from history (excluding today)
            history = values[1:]
            if not history:
                continue

            mean = statistics.mean(history)
            if len(history) > 1:
                stdev = statistics.stdev(history)
            else:
                stdev = 0

            # Detect anomaly using z-score
            if stdev > 0:
                z_score = (current - mean) / stdev
            else:
                z_score = 0 if current == mean else (3 if current > mean else -3)

            # Check for anomaly
            if abs(z_score) >= 2:
                deviation = ((current - mean) / mean * 100) if mean != 0 else 0

                if z_score > 0:
                    anomaly_type = AnomalyType.SPIKE
                    description = f"{m} spiked to {current:.1f} (expected ~{mean:.1f})"
                else:
                    anomaly_type = AnomalyType.DROP
                    description = f"{m} dropped to {current:.1f} (expected ~{mean:.1f})"

                # Determine severity
                if abs(z_score) >= 3:
                    severity = AnomalySeverity.CRITICAL
                elif abs(z_score) >= 2.5:
                    severity = AnomalySeverity.HIGH
                else:
                    severity = AnomalySeverity.MEDIUM

                anomalies.append(
                    Anomaly(
                        id=str(uuid4()),
                        anomaly_type=anomaly_type,
                        severity=severity,
                        metric=m,
                        current_value=current,
                        expected_value=mean,
                        deviation=deviation,
                        detected_at=now,
                        description=description,
                        context={
                            "z_score": z_score,
                            "stdev": stdev,
                            "lookback_days": lookback_days,
                        },
                    )
                )

        # Check for trend breaks
        anomalies.extend(await self._detect_trend_breaks(lookback_days))

        return anomalies

    async def _detect_trend_breaks(
        self,
        lookback_days: int,
    ) -> list[Anomaly]:
        """Detect trend breaks in key metrics.

        Args:
            lookback_days: Days to analyze

        Returns:
            Trend break anomalies
        """
        from app.storage.redis import get_redis
        from uuid import uuid4

        redis = await get_redis()
        now = datetime.now(UTC)
        anomalies = []

        metrics = ["conversion_rate", "response_rate", "qualification_rate"]

        for metric in metrics:
            # Get daily values
            values = []
            for i in range(lookback_days):
                day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
                val = float(await redis.get(f"stats:daily:{day}:{metric}") or 0)
                values.append(val)

            if len(values) < 14:
                continue

            # Compare recent week to previous week
            recent_week = values[:7]
            prev_week = values[7:14]

            recent_avg = statistics.mean(recent_week) if recent_week else 0
            prev_avg = statistics.mean(prev_week) if prev_week else 0

            if prev_avg == 0:
                continue

            change_pct = ((recent_avg - prev_avg) / prev_avg) * 100

            # Detect significant trend change
            if abs(change_pct) >= 20:
                if change_pct > 0:
                    description = f"{metric} trending up {change_pct:.1f}% week-over-week"
                    severity = AnomalySeverity.LOW  # Good news
                else:
                    description = f"{metric} trending down {abs(change_pct):.1f}% week-over-week"
                    severity = AnomalySeverity.HIGH if abs(change_pct) >= 30 else AnomalySeverity.MEDIUM

                anomalies.append(
                    Anomaly(
                        id=str(uuid4()),
                        anomaly_type=AnomalyType.TREND_BREAK,
                        severity=severity,
                        metric=metric,
                        current_value=recent_avg,
                        expected_value=prev_avg,
                        deviation=change_pct,
                        detected_at=now,
                        description=description,
                        context={
                            "recent_week_avg": recent_avg,
                            "prev_week_avg": prev_avg,
                        },
                    )
                )

        return anomalies

    async def get_anomaly_history(
        self,
        days: int = 7,
        severity: AnomalySeverity | None = None,
    ) -> list[Anomaly]:
        """Get historical anomalies.

        Args:
            days: Days of history
            severity: Filter by severity

        Returns:
            List of past anomalies
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)
        anomalies = []

        # Get from stored anomalies
        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            key = f"anomalies:{day}"
            data = await redis.lrange(key, 0, -1)

            for item in data:
                d = json.loads(item)
                anomaly = Anomaly(
                    id=d["id"],
                    anomaly_type=AnomalyType(d["anomaly_type"]),
                    severity=AnomalySeverity(d["severity"]),
                    metric=d["metric"],
                    current_value=d["current_value"],
                    expected_value=d["expected_value"],
                    deviation=d["deviation"],
                    detected_at=datetime.fromisoformat(d["detected_at"]),
                    description=d["description"],
                    context=d.get("context", {}),
                )

                if severity and anomaly.severity != severity:
                    continue

                anomalies.append(anomaly)

        return anomalies

    async def record_anomaly(self, anomaly: Anomaly) -> None:
        """Record an anomaly for history.

        Args:
            anomaly: Anomaly to record
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        day = anomaly.detected_at.strftime("%Y-%m-%d")
        key = f"anomalies:{day}"

        await redis.rpush(key, json.dumps(anomaly.to_dict()))
        await redis.expire(key, 86400 * 90)  # 90 days retention

        logger.warning(
            f"[Anomaly] Detected | type={anomaly.anomaly_type.value} | "
            f"severity={anomaly.severity.value} | metric={anomaly.metric} | "
            f"deviation={anomaly.deviation:.1f}%"
        )

    # ========================================================================
    # Summary
    # ========================================================================

    async def get_analytics_summary(
        self,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get analytics summary with cohorts and anomalies.

        Args:
            days: Days to analyze

        Returns:
            Summary dict
        """
        weekly_cohorts = await self.get_weekly_cohorts(weeks=4)
        source_cohorts = await self.get_source_cohorts()
        anomalies = await self.detect_anomalies(lookback_days=days)

        critical_anomalies = [a for a in anomalies if a.severity == AnomalySeverity.CRITICAL]
        high_anomalies = [a for a in anomalies if a.severity == AnomalySeverity.HIGH]

        return {
            "period_days": days,
            "weekly_cohorts_count": len(weekly_cohorts),
            "source_cohorts_count": len(source_cohorts),
            "total_anomalies": len(anomalies),
            "critical_anomalies": len(critical_anomalies),
            "high_anomalies": len(high_anomalies),
            "anomalies": [a.to_dict() for a in anomalies[:10]],
            "top_cohort": weekly_cohorts[0].to_dict() if weekly_cohorts else None,
        }


# Singleton
cohort_analytics = CohortAnalyticsService()
