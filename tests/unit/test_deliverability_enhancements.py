"""Unit tests for deliverability enhancements.

Tests for:
1. Min sample size for auto-pause
2. Global suppression list
3. Sender/domain reputation score
4. A/B testing
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Patch path for redis
REDIS_PATCH = "app.storage.redis.get_redis"

from app.services.outbound_service import (
    OutboundService,
    CampaignHealth,
    ReputationScore,
    REPUTATION_EXCELLENT,
    REPUTATION_GOOD,
)
from app.services.ab_testing import (
    ABTestingService,
    ABTest,
    Variant,
    VariantType,
    VariantStats,
)


UTC = timezone.utc


class TestMinSampleSize:
    """Tests for minimum sample size for auto-pause."""

    @pytest.fixture
    def outbound_service(self):
        return OutboundService()

    @pytest.mark.asyncio
    async def test_no_pause_below_min_sample(self, outbound_service):
        """Campaign should not be paused if below min sample size."""
        mock_redis = AsyncMock()
        # 30 emails sent (below default 50 threshold)
        mock_redis.get = AsyncMock(side_effect=lambda k: {
            "throttle:campaign:test_camp:total_sent": "30",
            "deliverability:delivered:campaign:test_camp:total": "20",
            "deliverability:bounces:campaign:test_camp:total": "10",  # 33% bounce!
            "deliverability:complaints:campaign:test_camp:total": "5",
        }.get(k, None))

        with patch(REDIS_PATCH, return_value=mock_redis):
            health = await outbound_service.check_campaign_health("test_camp")

        # Should not recommend pause because sample size not met
        assert health.sample_size_met is False
        assert health.should_pause is False
        assert health.bounce_rate == 0.0  # Rate not calculated below min sample

    @pytest.mark.asyncio
    async def test_pause_when_sample_size_met(self, outbound_service):
        """Campaign should be paused if above min sample and high bounce rate."""
        mock_redis = AsyncMock()
        # 100 emails sent (above threshold)
        mock_redis.get = AsyncMock(side_effect=lambda k: {
            "throttle:campaign:test_camp:total_sent": "100",
            "deliverability:delivered:campaign:test_camp:total": "80",
            "deliverability:bounces:campaign:test_camp:total": "15",  # 15% bounce
            "deliverability:complaints:campaign:test_camp:total": "0",
        }.get(k, None))

        with patch(REDIS_PATCH, return_value=mock_redis):
            health = await outbound_service.check_campaign_health("test_camp")

        assert health.sample_size_met is True
        assert health.should_pause is True
        assert health.bounce_rate == 0.15


class TestSuppressionList:
    """Tests for global suppression list."""

    @pytest.fixture
    def outbound_service(self):
        return OutboundService()

    @pytest.mark.asyncio
    async def test_add_to_suppression(self, outbound_service):
        """Should add email to suppression list."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.sadd = AsyncMock(return_value=1)

        with patch(REDIS_PATCH, return_value=mock_redis):
            result = await outbound_service.add_to_suppression_list(
                "test@example.com", reason="bounce"
            )

        assert result is True
        mock_redis.set.assert_called_once()
        mock_redis.sadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_suppression_found(self, outbound_service):
        """Should detect suppressed email."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="bounce:2024-01-01T00:00:00")

        with patch(REDIS_PATCH, return_value=mock_redis):
            is_suppressed, reason = await outbound_service.check_suppression(
                "test@example.com"
            )

        assert is_suppressed is True
        assert reason == "bounce"

    @pytest.mark.asyncio
    async def test_check_suppression_not_found(self, outbound_service):
        """Should allow non-suppressed email."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch(REDIS_PATCH, return_value=mock_redis):
            is_suppressed, reason = await outbound_service.check_suppression(
                "test@example.com"
            )

        assert is_suppressed is False
        assert reason is None

    @pytest.mark.asyncio
    async def test_bulk_add_suppression(self, outbound_service):
        """Should bulk add emails to suppression."""
        mock_redis = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_pipeline.set = MagicMock()
        mock_pipeline.sadd = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        with patch(REDIS_PATCH, return_value=mock_redis):
            count = await outbound_service.bulk_add_suppression(
                ["a@test.com", "b@test.com", "c@test.com"],
                reason="import"
            )

        assert count == 3


class TestReputationScore:
    """Tests for sender/domain reputation scoring."""

    @pytest.fixture
    def outbound_service(self):
        return OutboundService()

    def test_calculate_reputation_excellent(self, outbound_service):
        """High delivery, low bounce/complaint = excellent."""
        rep = outbound_service._calculate_reputation(
            entity="sender@test.com",
            entity_type="sender",
            total_sent=1000,
            total_delivered=990,
            total_bounced=5,
            total_complained=0,
        )

        assert rep.rating == "excellent"
        assert rep.score >= REPUTATION_EXCELLENT
        assert rep.delivery_rate == 0.99

    def test_calculate_reputation_poor(self, outbound_service):
        """Low delivery, high bounce = poor."""
        rep = outbound_service._calculate_reputation(
            entity="sender@test.com",
            entity_type="sender",
            total_sent=100,
            total_delivered=50,
            total_bounced=40,
            total_complained=5,
        )

        assert rep.rating in ("poor", "critical")
        assert rep.score < REPUTATION_GOOD

    def test_calculate_reputation_unknown(self, outbound_service):
        """No data = unknown."""
        rep = outbound_service._calculate_reputation(
            entity="new@test.com",
            entity_type="sender",
            total_sent=0,
            total_delivered=0,
            total_bounced=0,
            total_complained=0,
        )

        assert rep.rating == "unknown"
        assert rep.score == 0.0


class TestABTesting:
    """Tests for A/B testing service."""

    @pytest.fixture
    def ab_service(self):
        return ABTestingService()

    @pytest.mark.asyncio
    async def test_create_subject_test(self, ab_service):
        """Should create subject A/B test."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.sadd = AsyncMock()

        with patch(REDIS_PATCH, return_value=mock_redis):
            test = await ab_service.create_subject_test(
                campaign_id="campaign_1",
                subject_a="Subject A version",
                subject_b="Subject B version",
            )

        assert test.campaign_id == "campaign_1"
        assert test.variant_type == VariantType.SUBJECT
        # 2 variants + 1 holdout (10% default from settings)
        assert len(test.variants) >= 2
        assert test.is_active is True

    @pytest.mark.asyncio
    async def test_deterministic_variant_assignment(self, ab_service):
        """Same lead should always get same variant."""
        test = ABTest(
            test_id="test_1",
            campaign_id="camp_1",
            variant_type=VariantType.SUBJECT,
            variants=[
                Variant(id="v1", name="A", content="Subject A", weight=0.5),
                Variant(id="v2", name="B", content="Subject B", weight=0.5),
            ],
            created_at=datetime.now(UTC),
            is_active=True,
        )

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        import json
        test_data = {
            "test_id": test.test_id,
            "campaign_id": test.campaign_id,
            "variant_type": test.variant_type.value,
            "variants": [
                {"id": v.id, "name": v.name, "content": v.content, "weight": v.weight}
                for v in test.variants
            ],
            "created_at": test.created_at.isoformat(),
            "is_active": True,
        }

        async def mock_get(key):
            if key == "abtest:test_1":
                return json.dumps(test_data)
            return None

        mock_redis.get = AsyncMock(side_effect=mock_get)

        with patch(REDIS_PATCH, return_value=mock_redis):
            # Same lead_id should always get same variant
            v1 = await ab_service.assign_variant("test_1", "lead_123")
            v2 = await ab_service.assign_variant("test_1", "lead_123")
            v3 = await ab_service.assign_variant("test_1", "lead_123")

        assert v1.id == v2.id == v3.id

    def test_winner_analysis_not_enough_data(self, ab_service):
        """Should not declare winner with insufficient data."""
        stats = [
            VariantStats(
                variant_id="v1", variant_name="A",
                sent=50, delivered=45, opened=10, clicked=5, replied=2,
                qualified=1, handoffs=0, bounced=5,
                delivery_rate=0.9, open_rate=0.22, click_rate=0.11, reply_rate=0.044,
                qualified_rate=0.022, handoff_rate=0.0, bounce_rate=0.1
            ),
            VariantStats(
                variant_id="v2", variant_name="B",
                sent=50, delivered=48, opened=15, clicked=8, replied=4,
                qualified=2, handoffs=1, bounced=2,
                delivery_rate=0.96, open_rate=0.31, click_rate=0.17, reply_rate=0.083,
                qualified_rate=0.042, handoff_rate=0.021, bounce_rate=0.04
            ),
        ]

        can_declare, winner_id, confidence = ab_service._analyze_winner(
            stats, min_sample_size=100
        )

        assert can_declare is False
        assert winner_id is None

    def test_winner_analysis_with_clear_winner(self, ab_service):
        """Should declare winner with clear difference."""
        stats = [
            VariantStats(
                variant_id="v1", variant_name="A",
                sent=200, delivered=180, opened=20, clicked=10, replied=5,
                qualified=2, handoffs=1, bounced=20,
                delivery_rate=0.9, open_rate=0.11, click_rate=0.06, reply_rate=0.028,
                qualified_rate=0.011, handoff_rate=0.006, bounce_rate=0.1
            ),
            VariantStats(
                variant_id="v2", variant_name="B",
                sent=200, delivered=190, opened=50, clicked=30, replied=20,
                qualified=15, handoffs=8, bounced=10,
                delivery_rate=0.95, open_rate=0.26, click_rate=0.16, reply_rate=0.105,
                qualified_rate=0.079, handoff_rate=0.042, bounce_rate=0.05
            ),
        ]

        can_declare, winner_id, confidence = ab_service._analyze_winner(
            stats, min_sample_size=100
        )

        # v2 has much higher qualified rate (7.9% vs 1.1%)
        assert can_declare is True
        assert winner_id == "v2"
        assert confidence is not None
