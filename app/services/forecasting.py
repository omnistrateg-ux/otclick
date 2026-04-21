"""Forecasting Service.

Predicts conversion rates and pipeline outcomes.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config.settings import settings

UTC = timezone.utc

logger = logging.getLogger(__name__)


@dataclass
class ConversionForecast:
    """Forecasted conversion rates."""

    metric: str  # reply_rate, qualified_rate, handoff_rate, win_rate
    current_value: float
    forecasted_value: float
    confidence: float  # 0-1
    trend: str  # "up", "down", "stable"
    change_percent: float
    sample_size: int
    forecast_period_days: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "current_value": round(self.current_value, 4),
            "forecasted_value": round(self.forecasted_value, 4),
            "confidence": round(self.confidence, 2),
            "trend": self.trend,
            "change_percent": round(self.change_percent, 2),
            "sample_size": self.sample_size,
            "forecast_period_days": self.forecast_period_days,
        }


@dataclass
class PipelineForecast:
    """Pipeline value forecast."""

    period_days: int
    current_pipeline_value: float
    forecasted_revenue: float
    win_probability: float
    expected_deals: int
    confidence: float
    by_stage: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "period_days": self.period_days,
            "current_pipeline_value": round(self.current_pipeline_value, 2),
            "forecasted_revenue": round(self.forecasted_revenue, 2),
            "win_probability": round(self.win_probability, 3),
            "expected_deals": self.expected_deals,
            "confidence": round(self.confidence, 2),
            "by_stage": {k: round(v, 2) for k, v in self.by_stage.items()},
        }


@dataclass
class SegmentForecast:
    """Forecast for a segment."""

    segment: str
    reply_rate: float
    qualified_rate: float
    handoff_rate: float
    expected_leads: int
    expected_qualified: int
    expected_handoffs: int
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment": self.segment,
            "reply_rate": round(self.reply_rate, 4),
            "qualified_rate": round(self.qualified_rate, 4),
            "handoff_rate": round(self.handoff_rate, 4),
            "expected_leads": self.expected_leads,
            "expected_qualified": self.expected_qualified,
            "expected_handoffs": self.expected_handoffs,
            "confidence": round(self.confidence, 2),
        }


@dataclass
class ForecastSummary:
    """Summary of all forecasts."""

    generated_at: datetime
    period_days: int
    conversion_forecasts: list[ConversionForecast]
    pipeline_forecast: PipelineForecast
    segment_forecasts: list[SegmentForecast]
    overall_health: str
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "period_days": self.period_days,
            "conversion_forecasts": [f.to_dict() for f in self.conversion_forecasts],
            "pipeline_forecast": self.pipeline_forecast.to_dict(),
            "segment_forecasts": [f.to_dict() for f in self.segment_forecasts],
            "overall_health": self.overall_health,
            "recommendations": self.recommendations,
        }


class ForecastingService:
    """Forecasts conversion rates and pipeline outcomes.

    Features:
    - Conversion rate forecasting
    - Pipeline value forecasting
    - Segment-level forecasting
    - Trend detection
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Conversion Rate Forecasting
    # ========================================================================

    async def forecast_conversion_rates(
        self,
        days: int = 30,
    ) -> list[ConversionForecast]:
        """Forecast conversion rates for next period.

        Args:
            days: Forecast period

        Returns:
            List of conversion forecasts
        """
        forecasts = []

        # Forecast each metric
        for metric in ["reply_rate", "qualified_rate", "handoff_rate", "win_rate"]:
            forecast = await self._forecast_metric(metric, days)
            forecasts.append(forecast)

        return forecasts

    async def _forecast_metric(
        self,
        metric: str,
        days: int,
    ) -> ConversionForecast:
        """Forecast a single metric.

        Uses simple moving average with trend detection.
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get historical data
        values = []
        for i in range(days * 2):  # Look back 2x period
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            key = f"metrics:{metric}:daily:{day}"
            data = await redis.hgetall(key)

            if data:
                numerator = int(data.get(b"numerator", data.get("numerator", 0)))
                denominator = int(data.get(b"denominator", data.get("denominator", 1)))
                if denominator > 0:
                    values.append(numerator / denominator)

        if not values:
            return ConversionForecast(
                metric=metric,
                current_value=0.0,
                forecasted_value=0.0,
                confidence=0.0,
                trend="stable",
                change_percent=0.0,
                sample_size=0,
                forecast_period_days=days,
            )

        # Current value = recent average
        recent_values = values[:min(7, len(values))]
        current_value = sum(recent_values) / len(recent_values)

        # Historical value = older average
        older_values = values[min(7, len(values)):]
        if older_values:
            historical_value = sum(older_values) / len(older_values)
        else:
            historical_value = current_value

        # Detect trend
        if current_value > historical_value * 1.05:
            trend = "up"
            # Project trend forward
            trend_factor = current_value / historical_value if historical_value > 0 else 1.0
            forecasted_value = current_value * (1 + (trend_factor - 1) * 0.5)
        elif current_value < historical_value * 0.95:
            trend = "down"
            trend_factor = current_value / historical_value if historical_value > 0 else 1.0
            forecasted_value = current_value * (1 - (1 - trend_factor) * 0.5)
        else:
            trend = "stable"
            forecasted_value = current_value

        # Calculate confidence based on sample size
        total_samples = sum(1 for v in values if v > 0)
        confidence = min(1.0, total_samples / 30)

        change_percent = ((forecasted_value - current_value) / current_value * 100) if current_value > 0 else 0

        return ConversionForecast(
            metric=metric,
            current_value=current_value,
            forecasted_value=forecasted_value,
            confidence=confidence,
            trend=trend,
            change_percent=change_percent,
            sample_size=total_samples,
            forecast_period_days=days,
        )

    # ========================================================================
    # Pipeline Forecasting
    # ========================================================================

    async def forecast_pipeline(
        self,
        days: int = 30,
    ) -> PipelineForecast:
        """Forecast pipeline revenue.

        Args:
            days: Forecast period

        Returns:
            PipelineForecast
        """
        from app.storage.redis import get_redis
        from app.services.revenue_loop import RevenueLoopService, DealStage, STAGE_PROBABILITIES
        import json

        redis = await get_redis()
        revenue_service = RevenueLoopService()

        # Get all active deals
        total_value = 0.0
        weighted_value = 0.0
        by_stage = {}
        deal_count = 0

        async for key in redis.scan_iter("deal:*"):
            if ":" in key[5:]:
                continue
            data = await redis.get(key)
            if data:
                deal = json.loads(data)
                stage = deal.get("stage")

                # Skip closed deals
                if stage in ("closed_won", "closed_lost"):
                    continue

                value = deal.get("value", 0)
                prob = STAGE_PROBABILITIES.get(DealStage(stage), 0.5) if stage else 0.5

                total_value += value
                weighted_value += value * prob
                deal_count += 1

                by_stage[stage] = by_stage.get(stage, 0) + value * prob

        # Get historical win rate for confidence
        metrics = await revenue_service.get_pipeline_metrics(days=90)
        historical_win_rate = metrics.win_rate if metrics.total_deals > 0 else 0.5

        # Adjust forecast by historical accuracy
        forecasted_revenue = weighted_value * (0.7 + historical_win_rate * 0.3)

        # Confidence based on deal count and history
        confidence = min(1.0, deal_count / 20) * min(1.0, metrics.total_deals / 50)

        return PipelineForecast(
            period_days=days,
            current_pipeline_value=total_value,
            forecasted_revenue=forecasted_revenue,
            win_probability=historical_win_rate,
            expected_deals=int(deal_count * historical_win_rate),
            confidence=confidence,
            by_stage=by_stage,
        )

    # ========================================================================
    # Segment Forecasting
    # ========================================================================

    async def forecast_by_segment(
        self,
        days: int = 30,
    ) -> list[SegmentForecast]:
        """Forecast by industry segment.

        Args:
            days: Forecast period

        Returns:
            List of segment forecasts
        """
        from app.storage.redis import get_redis
        from app.models.enums import IndustrySegment

        redis = await get_redis()
        forecasts = []

        for segment in IndustrySegment:
            segment_name = segment.value

            # Get segment metrics
            leads = int(await redis.get(f"segment:{segment_name}:leads:total") or 0)
            replies = int(await redis.get(f"segment:{segment_name}:replies:total") or 0)
            qualified = int(await redis.get(f"segment:{segment_name}:qualified:total") or 0)
            handoffs = int(await redis.get(f"segment:{segment_name}:handoffs:total") or 0)

            if leads == 0:
                continue

            reply_rate = replies / leads
            qualified_rate = qualified / leads
            handoff_rate = handoffs / leads

            # Estimate future leads (simple projection)
            daily_leads = int(await redis.get(f"segment:{segment_name}:leads:daily_avg") or 0)
            expected_leads = daily_leads * days if daily_leads > 0 else leads // 30 * days

            # Calculate confidence
            confidence = min(1.0, leads / 100)

            forecasts.append(SegmentForecast(
                segment=segment_name,
                reply_rate=reply_rate,
                qualified_rate=qualified_rate,
                handoff_rate=handoff_rate,
                expected_leads=expected_leads,
                expected_qualified=int(expected_leads * qualified_rate),
                expected_handoffs=int(expected_leads * handoff_rate),
                confidence=confidence,
            ))

        # Sort by expected handoffs
        forecasts.sort(key=lambda x: x.expected_handoffs, reverse=True)

        return forecasts

    # ========================================================================
    # Summary
    # ========================================================================

    async def get_forecast_summary(
        self,
        days: int = 30,
    ) -> ForecastSummary:
        """Get comprehensive forecast summary.

        Args:
            days: Forecast period

        Returns:
            ForecastSummary
        """
        conversion_forecasts = await self.forecast_conversion_rates(days)
        pipeline_forecast = await self.forecast_pipeline(days)
        segment_forecasts = await self.forecast_by_segment(days)

        recommendations = []

        # Analyze trends
        declining_metrics = [f for f in conversion_forecasts if f.trend == "down"]
        if declining_metrics:
            for f in declining_metrics:
                recommendations.append(f"Investigate declining {f.metric}")

        # Check pipeline health
        if pipeline_forecast.confidence < 0.3:
            recommendations.append("Increase deal volume for better forecasting")

        if pipeline_forecast.win_probability < 0.3:
            recommendations.append("Review deal qualification criteria")

        # Segment recommendations
        low_performing = [s for s in segment_forecasts if s.handoff_rate < 0.05 and s.confidence > 0.5]
        for seg in low_performing[:3]:
            recommendations.append(f"Review targeting for {seg.segment} segment")

        # Determine overall health
        avg_trend_score = sum(
            1 if f.trend == "up" else -1 if f.trend == "down" else 0
            for f in conversion_forecasts
        ) / len(conversion_forecasts) if conversion_forecasts else 0

        if avg_trend_score > 0.3:
            overall_health = "improving"
        elif avg_trend_score < -0.3:
            overall_health = "declining"
        else:
            overall_health = "stable"

        return ForecastSummary(
            generated_at=datetime.now(UTC),
            period_days=days,
            conversion_forecasts=conversion_forecasts,
            pipeline_forecast=pipeline_forecast,
            segment_forecasts=segment_forecasts,
            overall_health=overall_health,
            recommendations=recommendations,
        )

    # ========================================================================
    # Metrics Recording
    # ========================================================================

    async def record_metric_data(
        self,
        metric: str,
        numerator: int,
        denominator: int,
        segment: str | None = None,
    ) -> None:
        """Record metric data for forecasting.

        Args:
            metric: Metric name
            numerator: Metric numerator (e.g., replies)
            denominator: Metric denominator (e.g., sends)
            segment: Optional segment
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        # Store daily data
        key = f"metrics:{metric}:daily:{today}"
        await redis.hincrby(key, "numerator", numerator)
        await redis.hincrby(key, "denominator", denominator)
        await redis.expire(key, 86400 * 90)

        if segment:
            seg_key = f"metrics:{metric}:segment:{segment}:daily:{today}"
            await redis.hincrby(seg_key, "numerator", numerator)
            await redis.hincrby(seg_key, "denominator", denominator)
            await redis.expire(seg_key, 86400 * 90)

    async def get_historical_metrics(
        self,
        metric: str,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get historical metric data.

        Args:
            metric: Metric name
            days: Days to retrieve

        Returns:
            Historical data points
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        data = []

        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            key = f"metrics:{metric}:daily:{day}"
            values = await redis.hgetall(key)

            if values:
                num = int(values.get(b"numerator", values.get("numerator", 0)))
                denom = int(values.get(b"denominator", values.get("denominator", 1)))
                rate = num / denom if denom > 0 else 0

                data.append({
                    "date": day,
                    "numerator": num,
                    "denominator": denom,
                    "rate": round(rate, 4),
                })

        return data


# Singleton
forecasting = ForecastingService()
