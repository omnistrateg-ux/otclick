"""Unit tests for outbound enhancements v2.

Tests for:
1. Sender/domain warm-up
2. A/B winner by qualified/handoff rates
3. Holdout group
4. Send-time optimization
5. Deliverability trends
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.warmup_service import (
    WarmupService,
    WarmupConfig,
    WarmupPhase,
    WarmupStatus,
)
from app.services.ab_testing import (
    ABTestingService,
    VariantStats,
    WinnerMetric,
)
from app.services.send_time_optimizer import (
    SendTimeOptimizer,
    DEFAULT_SEND_WINDOWS,
)
from app.services.deliverability_trends import (
    DeliverabilityTrendsService,
    TrendAnalysis,
)


UTC = timezone.utc
REDIS_PATCH = "app.storage.redis.get_redis"


class TestWarmup:
    """Tests for sender/domain warm-up."""

    @pytest.fixture
    def warmup_service(self):
        config = WarmupConfig(
            initial_daily_limit=10,
            max_daily_limit=100,
            increment_percent=20,
            days_to_full=14,
        )
        return WarmupService(config)

    def test_calculate_daily_limit_day_1(self, warmup_service):
        """Day 1 should have initial limit."""
        limit = warmup_service._calculate_daily_limit(
            day=1, initial=10, maximum=100, increment_pct=20
        )
        assert limit == 10

    def test_calculate_daily_limit_day_5(self, warmup_service):
        """Day 5 should have increased limit."""
        limit = warmup_service._calculate_daily_limit(
            day=5, initial=10, maximum=100, increment_pct=20
        )
        # 10 * 1.2^4 = 20.7 -> 20
        assert limit == 20

    def test_calculate_daily_limit_capped_at_max(self, warmup_service):
        """Should not exceed maximum."""
        limit = warmup_service._calculate_daily_limit(
            day=30, initial=10, maximum=100, increment_pct=20
        )
        assert limit == 100

    @pytest.mark.asyncio
    async def test_start_warmup(self, warmup_service):
        """Should start warm-up for new sender."""
        mock_redis = AsyncMock()
        now = datetime.now(UTC)

        # First call to hgetall returns empty (no existing warmup)
        # Second call returns the newly created warmup data
        mock_redis.hgetall = AsyncMock(side_effect=[
            {},  # Initial check - not started
            {    # After save - return the new data
                "entity": "test@example.com",
                "entity_type": "sender",
                "phase": "warming",
                "started_at": now.isoformat(),
                "initial_daily_limit": "10",
                "max_daily_limit": "100",
                "increment_percent": "20",
                "days_to_full": "14",
            },
        ])
        mock_redis.hset = AsyncMock()
        mock_redis.expire = AsyncMock()
        mock_redis.get = AsyncMock(return_value="0")

        with patch(REDIS_PATCH, return_value=mock_redis):
            status = await warmup_service.start_warmup("test@example.com", "sender")

        assert status.phase == WarmupPhase.WARMING
        assert status.current_daily_limit == 10
        mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_can_send_during_warmup(self, warmup_service):
        """Should check if can send based on warm-up limits."""
        mock_redis = AsyncMock()
        now = datetime.now(UTC)
        mock_redis.hgetall = AsyncMock(return_value={
            "entity": "test@example.com",
            "entity_type": "sender",
            "phase": "warming",
            "started_at": now.isoformat(),
            "initial_daily_limit": "10",
            "max_daily_limit": "100",
            "increment_percent": "20",
            "days_to_full": "14",
        })
        mock_redis.get = AsyncMock(return_value="5")  # 5 sent today

        with patch(REDIS_PATCH, return_value=mock_redis):
            can_send, reason = await warmup_service.can_send("test@example.com", "sender")

        assert can_send is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_cannot_send_limit_reached(self, warmup_service):
        """Should block when daily limit reached."""
        mock_redis = AsyncMock()
        now = datetime.now(UTC)
        mock_redis.hgetall = AsyncMock(return_value={
            "entity": "test@example.com",
            "entity_type": "sender",
            "phase": "warming",
            "started_at": now.isoformat(),
            "initial_daily_limit": "10",
            "max_daily_limit": "100",
            "increment_percent": "20",
            "days_to_full": "14",
        })
        mock_redis.get = AsyncMock(return_value="10")  # Limit reached

        with patch(REDIS_PATCH, return_value=mock_redis):
            can_send, reason = await warmup_service.can_send("test@example.com", "sender")

        assert can_send is False
        assert "warmup_limit_reached" in reason


class TestABWinnerMetrics:
    """Tests for A/B winner calculation with new metrics."""

    @pytest.fixture
    def ab_service(self):
        return ABTestingService()

    def test_winner_by_qualified_rate(self, ab_service):
        """Should determine winner by qualified_rate."""
        stats = [
            VariantStats(
                variant_id="v1", variant_name="A",
                sent=200, delivered=180, opened=50, clicked=20, replied=20,
                qualified=5, handoffs=2, bounced=20,
                delivery_rate=0.9, open_rate=0.28, click_rate=0.11,
                reply_rate=0.11, qualified_rate=0.028, handoff_rate=0.011,
                bounce_rate=0.1, is_holdout=False
            ),
            VariantStats(
                variant_id="v2", variant_name="B",
                sent=200, delivered=190, opened=60, clicked=30, replied=25,
                qualified=15, handoffs=8, bounced=10,
                delivery_rate=0.95, open_rate=0.32, click_rate=0.16,
                reply_rate=0.13, qualified_rate=0.079, handoff_rate=0.042,
                bounce_rate=0.05, is_holdout=False
            ),
        ]

        # v2 has much better qualified_rate (7.9% vs 2.8%)
        can_declare, winner_id, confidence = ab_service._analyze_winner(
            stats, min_sample_size=100, winner_metric="qualified_rate"
        )

        assert can_declare is True
        assert winner_id == "v2"

    def test_winner_by_handoff_rate(self, ab_service):
        """Should determine winner by handoff_rate."""
        stats = [
            VariantStats(
                variant_id="v1", variant_name="A",
                sent=200, delivered=180, opened=50, clicked=20, replied=20,
                qualified=10, handoffs=2, bounced=20,
                delivery_rate=0.9, open_rate=0.28, click_rate=0.11,
                reply_rate=0.11, qualified_rate=0.056, handoff_rate=0.011,
                bounce_rate=0.1, is_holdout=False
            ),
            VariantStats(
                variant_id="v2", variant_name="B",
                sent=200, delivered=190, opened=60, clicked=30, replied=25,
                qualified=12, handoffs=10, bounced=10,
                delivery_rate=0.95, open_rate=0.32, click_rate=0.16,
                reply_rate=0.13, qualified_rate=0.063, handoff_rate=0.053,
                bounce_rate=0.05, is_holdout=False
            ),
        ]

        # v2 has much better handoff_rate (5.3% vs 1.1%)
        can_declare, winner_id, confidence = ab_service._analyze_winner(
            stats, min_sample_size=100, winner_metric="handoff_rate"
        )

        assert can_declare is True
        assert winner_id == "v2"

    def test_lift_calculation(self, ab_service):
        """Should calculate lift vs holdout."""
        treatment = VariantStats(
            variant_id="v1", variant_name="Treatment",
            sent=200, delivered=180, opened=50, clicked=20, replied=20,
            qualified=15, handoffs=8, bounced=20,
            delivery_rate=0.9, open_rate=0.28, click_rate=0.11,
            reply_rate=0.11, qualified_rate=0.083, handoff_rate=0.044,
            bounce_rate=0.1, is_holdout=False
        )

        holdout = VariantStats(
            variant_id="holdout", variant_name="Holdout",
            sent=50, delivered=45, opened=10, clicked=5, replied=5,
            qualified=3, handoffs=1, bounced=5,
            delivery_rate=0.9, open_rate=0.22, click_rate=0.11,
            reply_rate=0.11, qualified_rate=0.067, handoff_rate=0.022,
            bounce_rate=0.1, is_holdout=True
        )

        lift = ab_service._calculate_lift(treatment, holdout, "qualified_rate")

        # (0.083 - 0.067) / 0.067 * 100 = 23.9%
        assert lift is not None
        assert lift > 20


class TestSendTimeOptimizer:
    """Tests for send-time optimization."""

    @pytest.fixture
    def optimizer(self):
        return SendTimeOptimizer(timezone_offset=3)

    def test_default_windows_exist(self):
        """Should have default windows for segments."""
        assert "retail" in DEFAULT_SEND_WINDOWS
        assert "horeca" in DEFAULT_SEND_WINDOWS
        assert "it" in DEFAULT_SEND_WINDOWS
        assert "default" in DEFAULT_SEND_WINDOWS

    def test_optimal_time_for_segment(self, optimizer):
        """Should return optimal time for segment."""
        recommendation = optimizer.get_optimal_send_time("retail")

        assert recommendation.segment == "retail"
        assert recommendation.confidence > 0
        assert recommendation.recommended_time is not None
        assert 9 <= recommendation.window_start <= 16

    def test_optimal_time_uses_default_for_unknown(self, optimizer):
        """Should use default for unknown segment."""
        recommendation = optimizer.get_optimal_send_time("unknown_segment_xyz")

        assert recommendation.segment == "default"

    def test_skips_weekends(self, optimizer):
        """Should not recommend weekend times."""
        # Force earliest to be a Saturday
        saturday = datetime(2024, 1, 6, 10, 0, 0, tzinfo=UTC)  # A Saturday
        latest = saturday + timedelta(days=3)

        recommendation = optimizer.get_optimal_send_time(
            "retail",
            earliest=saturday,
            latest=latest,
        )

        # Should be Monday (day 0) not Saturday (day 5) or Sunday (day 6)
        assert recommendation.recommended_time.weekday() < 5


class TestDeliverabilityTrends:
    """Tests for deliverability trends."""

    @pytest.fixture
    def trends_service(self):
        return DeliverabilityTrendsService()

    def test_trend_improving(self, trends_service):
        """Should detect improving trend."""
        trend = trends_service._create_trend(
            metric="delivery_rate",
            current=0.95,
            previous=0.85,
            higher_is_better=True,
        )

        assert trend.trend == "improving"
        assert trend.is_healthy is True
        assert trend.change_percent > 0

    def test_trend_declining(self, trends_service):
        """Should detect declining trend."""
        trend = trends_service._create_trend(
            metric="delivery_rate",
            current=0.80,
            previous=0.95,
            higher_is_better=True,
        )

        assert trend.trend == "declining"
        assert trend.is_healthy is False

    def test_trend_stable(self, trends_service):
        """Should detect stable trend."""
        trend = trends_service._create_trend(
            metric="open_rate",
            current=0.25,
            previous=0.24,  # ~4% change
            higher_is_better=True,
        )

        assert trend.trend == "stable"

    def test_health_assessment_excellent(self, trends_service):
        """Should assess excellent health."""
        health, issues, recommendations = trends_service._assess_health(
            delivery_rate=0.98,
            bounce_rate=0.02,
            complaint_rate=0.0001,
            trends=[],
        )

        assert health == "excellent"
        assert len(issues) == 0

    def test_health_assessment_critical(self, trends_service):
        """Should assess critical health."""
        health, issues, recommendations = trends_service._assess_health(
            delivery_rate=0.70,
            bounce_rate=0.25,
            complaint_rate=0.01,
            trends=[],
        )

        assert health == "critical"
        assert len(issues) > 0
        assert any("URGENT" in r for r in recommendations)

    def test_health_with_declining_trends(self, trends_service):
        """Should factor in declining trends."""
        declining_trend = TrendAnalysis(
            metric="delivery_rate",
            current_value=0.90,
            previous_value=0.95,
            change_percent=-5.3,
            trend="declining",
            is_healthy=False,
        )

        health, issues, recommendations = trends_service._assess_health(
            delivery_rate=0.90,
            bounce_rate=0.05,
            complaint_rate=0.001,
            trends=[declining_trend],
        )

        assert any("declining" in issue for issue in issues)


class TestHoldoutGroup:
    """Tests for holdout group functionality."""

    @pytest.fixture
    def ab_service(self):
        return ABTestingService()

    def test_is_holdout_variant(self, ab_service):
        """Should identify holdout variant."""
        from app.services.ab_testing import Variant

        holdout = Variant(id="h1", name="Holdout", content="__HOLDOUT__", weight=0.1)
        treatment = Variant(id="v1", name="Treatment A", content="Subject A", weight=0.45)

        assert ab_service.is_holdout_variant(holdout) is True
        assert ab_service.is_holdout_variant(treatment) is False

    @pytest.mark.asyncio
    async def test_create_test_with_holdout(self, ab_service):
        """Should create test with holdout group."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.sadd = AsyncMock()

        with patch(REDIS_PATCH, return_value=mock_redis):
            from app.services.ab_testing import VariantType

            test = await ab_service.create_test(
                campaign_id="camp_1",
                variant_type=VariantType.SUBJECT,
                variants=[
                    {"name": "A", "content": "Subject A"},
                    {"name": "B", "content": "Subject B"},
                ],
                holdout_percent=0.1,
            )

        # Should have 3 variants: A, B, and Holdout
        assert len(test.variants) == 3
        assert test.holdout_percent == 0.1

        holdout_variants = [v for v in test.variants if v.content == "__HOLDOUT__"]
        assert len(holdout_variants) == 1
        assert holdout_variants[0].weight == 0.1
