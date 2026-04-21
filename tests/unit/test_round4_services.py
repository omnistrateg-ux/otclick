"""Unit tests for Round 4 services.

Tests for:
1. Revenue Loop
2. Account Score
3. Forecasting
4. Manager Actions
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Patch path for redis
REDIS_PATCH = "app.storage.redis.get_redis"

UTC = timezone.utc


class TestRevenueLoop:
    """Tests for revenue loop service."""

    @pytest.fixture
    def service(self):
        from app.services.revenue_loop import RevenueLoopService
        return RevenueLoopService()

    @pytest.mark.asyncio
    async def test_create_deal(self, service):
        """Should create a new deal."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.sadd = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch(REDIS_PATCH, return_value=mock_redis):
            deal = await service.create_deal(
                lead_id="lead-123",
                account_id="acc-456",
                value=100000.0,
                manager_id="manager-1",
                campaign_id="camp-1",
            )

        assert deal.lead_id == "lead-123"
        assert deal.account_id == "acc-456"
        assert deal.value == 100000.0
        assert deal.stage.value == "handed_off"
        assert deal.probability == 0.10

    @pytest.mark.asyncio
    async def test_advance_stage(self, service):
        """Should advance deal to next stage."""
        from app.services.revenue_loop import DealStage
        import json

        deal_data = {
            "id": "deal-123",
            "lead_id": "lead-123",
            "account_id": "acc-456",
            "stage": "handed_off",
            "value": 100000.0,
            "probability": 0.10,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "stage_history": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(deal_data))
        mock_redis.set = AsyncMock(return_value=True)
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch(REDIS_PATCH, return_value=mock_redis):
            deal = await service.advance_stage(
                deal_id="deal-123",
                new_stage=DealStage.MEETING_SCHEDULED,
                actor="manager-1",
            )

        assert deal.stage == DealStage.MEETING_SCHEDULED
        assert deal.probability == 0.20
        assert len(deal.stage_history) == 1

    @pytest.mark.asyncio
    async def test_close_won(self, service):
        """Should close deal as won and record revenue."""
        from app.services.revenue_loop import DealStage
        import json

        deal_data = {
            "id": "deal-123",
            "lead_id": "lead-123",
            "account_id": "acc-456",
            "stage": "negotiation",
            "value": 100000.0,
            "probability": 0.70,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "stage_history": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(deal_data))
        mock_redis.set = AsyncMock(return_value=True)
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.incrbyfloat = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch(REDIS_PATCH, return_value=mock_redis):
            deal = await service.close_won(
                deal_id="deal-123",
                actual_revenue=95000.0,
                actor="manager-1",
            )

        assert deal.stage == DealStage.CLOSED_WON
        assert deal.won_revenue == 95000.0
        assert deal.actual_close_date is not None

    @pytest.mark.asyncio
    async def test_invalid_transition_raises_error(self, service):
        """Should raise error for invalid stage transition."""
        from app.services.revenue_loop import DealStage
        import json

        deal_data = {
            "id": "deal-123",
            "lead_id": "lead-123",
            "account_id": "acc-456",
            "stage": "handed_off",
            "value": 100000.0,
            "probability": 0.10,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "stage_history": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(deal_data))

        with patch(REDIS_PATCH, return_value=mock_redis):
            with pytest.raises(ValueError, match="Cannot transition"):
                await service.advance_stage(
                    deal_id="deal-123",
                    new_stage=DealStage.CONTRACT_SENT,  # Invalid jump
                    actor="manager-1",
                )


class TestAccountScore:
    """Tests for account score service."""

    @pytest.fixture
    def service(self):
        from app.services.account_score import AccountScoreService
        return AccountScoreService()

    @pytest.mark.asyncio
    async def test_calculate_account_score(self, service):
        """Should calculate composite account score."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.smembers = AsyncMock(return_value=set())
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.lrange = AsyncMock(return_value=[])

        with patch(REDIS_PATCH, return_value=mock_redis):
            score = await service.calculate_account_score(
                account_id="acc-123",
                lead_id="lead-123",
            )

        assert score.account_id == "acc-123"
        assert 0 <= score.overall_score <= 100
        assert score.tier is not None
        assert score.engagement_level is not None
        assert score.last_calculated is not None

    @pytest.mark.asyncio
    async def test_tier_classification(self, service):
        """Should classify accounts into correct tiers."""
        from app.services.account_score import AccountTier

        assert service._determine_tier(85) == AccountTier.ENTERPRISE
        assert service._determine_tier(65) == AccountTier.MID_MARKET
        assert service._determine_tier(45) == AccountTier.SMB
        assert service._determine_tier(25) == AccountTier.STARTUP
        assert service._determine_tier(10) == AccountTier.UNQUALIFIED

    @pytest.mark.asyncio
    async def test_engagement_level_classification(self, service):
        """Should classify engagement levels correctly."""
        from app.services.account_score import EngagementLevel

        assert service._determine_engagement_level(80) == EngagementLevel.HOT
        assert service._determine_engagement_level(50) == EngagementLevel.WARM
        assert service._determine_engagement_level(20) == EngagementLevel.COLD
        assert service._determine_engagement_level(5) == EngagementLevel.DORMANT

    @pytest.mark.asyncio
    async def test_record_engagement(self, service):
        """Should record engagement event."""
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock(return_value=1)

        with patch(REDIS_PATCH, return_value=mock_redis):
            await service.record_engagement(
                account_id="acc-123",
                engagement_type="reply",
            )

        assert mock_redis.incr.called


class TestForecasting:
    """Tests for forecasting service."""

    @pytest.fixture
    def service(self):
        from app.services.forecasting import ForecastingService
        return ForecastingService()

    @pytest.mark.asyncio
    async def test_forecast_conversion_rates(self, service):
        """Should forecast conversion rates."""
        mock_redis = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={
            b"numerator": b"10",
            b"denominator": b"100",
        })

        with patch(REDIS_PATCH, return_value=mock_redis):
            forecasts = await service.forecast_conversion_rates(days=30)

        assert len(forecasts) == 4  # 4 metrics
        for forecast in forecasts:
            assert forecast.metric in ["reply_rate", "qualified_rate", "handoff_rate", "win_rate"]
            assert 0 <= forecast.confidence <= 1
            assert forecast.trend in ["up", "down", "stable"]

    @pytest.mark.asyncio
    async def test_forecast_pipeline(self, service):
        """Should forecast pipeline revenue."""
        import json

        deal_data = {
            "id": "deal-1",
            "lead_id": "lead-1",
            "account_id": "acc-1",
            "stage": "proposal_sent",
            "value": 100000.0,
            "probability": 0.50,
        }

        mock_redis = AsyncMock()

        async def mock_scan_iter(pattern):
            yield "deal:deal-1"

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get = AsyncMock(return_value=json.dumps(deal_data))

        # Also mock the RevenueLoopService
        with patch(REDIS_PATCH, return_value=mock_redis):
            forecast = await service.forecast_pipeline(days=30)

        assert forecast.period_days == 30
        assert forecast.current_pipeline_value >= 0
        assert 0 <= forecast.win_probability <= 1

    @pytest.mark.asyncio
    async def test_record_metric_data(self, service):
        """Should record metric data."""
        mock_redis = AsyncMock()
        mock_redis.hincrby = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)

        with patch(REDIS_PATCH, return_value=mock_redis):
            await service.record_metric_data(
                metric="reply_rate",
                numerator=10,
                denominator=100,
                segment="retail",
            )

        assert mock_redis.hincrby.called


class TestManagerActions:
    """Tests for manager actions service."""

    @pytest.fixture
    def service(self):
        from app.services.manager_actions import ManagerActionsService
        return ManagerActionsService()

    @pytest.mark.asyncio
    async def test_create_handoff(self, service):
        """Should create a new handoff."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.sadd = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.zadd = AsyncMock(return_value=1)

        with patch(REDIS_PATCH, return_value=mock_redis):
            handoff = await service.create_handoff(
                lead_id="lead-123",
                account_id="acc-456",
                contact_id="contact-789",
                assigned_to="manager-1",
                lead_score=85.0,
            )

        assert handoff.lead_id == "lead-123"
        assert handoff.account_id == "acc-456"
        assert handoff.status.value == "pending"
        assert handoff.assigned_to == "manager-1"
        assert handoff.sla_deadline is not None

    @pytest.mark.asyncio
    async def test_accept_handoff(self, service):
        """Should accept a handoff."""
        from app.services.manager_actions import HandoffAction, HandoffStatus
        import json

        handoff_data = {
            "id": "handoff-123",
            "lead_id": "lead-123",
            "account_id": "acc-456",
            "contact_id": None,
            "status": "pending",
            "assigned_to": "manager-1",
            "created_by": "system",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "sla_deadline": (datetime.now(UTC) + timedelta(hours=4)).isoformat(),
            "action_history": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(handoff_data))
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.zrem = AsyncMock(return_value=1)
        mock_redis.srem = AsyncMock(return_value=1)
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch(REDIS_PATCH, return_value=mock_redis):
            result = await service.take_action(
                handoff_id="handoff-123",
                action=HandoffAction.ACCEPT,
                actor="manager-1",
            )

        assert result.success is True
        assert result.handoff.status == HandoffStatus.ACCEPTED
        assert result.handoff.accepted_at is not None
        assert "follow_up" in result.next_actions

    @pytest.mark.asyncio
    async def test_reject_handoff(self, service):
        """Should reject a handoff with reason."""
        from app.services.manager_actions import HandoffAction, HandoffStatus, RejectionReason
        import json

        handoff_data = {
            "id": "handoff-123",
            "lead_id": "lead-123",
            "account_id": "acc-456",
            "contact_id": None,
            "status": "pending",
            "assigned_to": "manager-1",
            "created_by": "system",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "sla_deadline": (datetime.now(UTC) + timedelta(hours=4)).isoformat(),
            "action_history": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(handoff_data))
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.zrem = AsyncMock(return_value=1)
        mock_redis.srem = AsyncMock(return_value=1)
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch(REDIS_PATCH, return_value=mock_redis):
            result = await service.take_action(
                handoff_id="handoff-123",
                action=HandoffAction.REJECT,
                actor="manager-1",
                notes="Not a good fit",
                metadata={"reason": "not_icp"},
            )

        assert result.success is True
        assert result.handoff.status == HandoffStatus.REJECTED
        assert result.handoff.rejection_reason == RejectionReason.NOT_ICP

    @pytest.mark.asyncio
    async def test_reassign_handoff(self, service):
        """Should reassign handoff to another manager."""
        from app.services.manager_actions import HandoffAction
        import json

        handoff_data = {
            "id": "handoff-123",
            "lead_id": "lead-123",
            "account_id": "acc-456",
            "contact_id": None,
            "status": "pending",
            "assigned_to": "manager-1",
            "created_by": "system",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "sla_deadline": (datetime.now(UTC) + timedelta(hours=4)).isoformat(),
            "action_history": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(handoff_data))
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.srem = AsyncMock(return_value=1)
        mock_redis.sadd = AsyncMock(return_value=1)
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch(REDIS_PATCH, return_value=mock_redis):
            result = await service.take_action(
                handoff_id="handoff-123",
                action=HandoffAction.REASSIGN,
                actor="manager-1",
                metadata={"new_manager": "manager-2"},
            )

        assert result.success is True
        assert result.handoff.assigned_to == "manager-2"

    @pytest.mark.asyncio
    async def test_get_manager_workload(self, service):
        """Should get manager workload."""
        mock_redis = AsyncMock()
        mock_redis.smembers = AsyncMock(return_value=set())
        mock_redis.get = AsyncMock(return_value=None)

        with patch(REDIS_PATCH, return_value=mock_redis):
            workload = await service.get_manager_workload("manager-1")

        assert workload.manager_id == "manager-1"
        assert workload.pending_handoffs >= 0
        assert workload.in_progress >= 0
        assert 0 <= workload.acceptance_rate <= 1


class TestDealStageTransitions:
    """Tests for deal stage transitions."""

    def test_valid_transitions(self):
        """Test valid stage transitions."""
        from app.services.revenue_loop import STAGE_TRANSITIONS, DealStage

        # handed_off can go to meeting_scheduled
        assert DealStage.MEETING_SCHEDULED in STAGE_TRANSITIONS[DealStage.HANDED_OFF]

        # meeting_completed can go to proposal_sent
        assert DealStage.PROPOSAL_SENT in STAGE_TRANSITIONS[DealStage.MEETING_COMPLETED]

        # terminal states have no transitions
        assert len(STAGE_TRANSITIONS[DealStage.CLOSED_WON]) == 0
        assert len(STAGE_TRANSITIONS[DealStage.CLOSED_LOST]) == 0

    def test_stage_probabilities(self):
        """Test stage probability values."""
        from app.services.revenue_loop import STAGE_PROBABILITIES, DealStage

        # Probabilities should increase through pipeline
        assert STAGE_PROBABILITIES[DealStage.HANDED_OFF] < STAGE_PROBABILITIES[DealStage.MEETING_SCHEDULED]
        assert STAGE_PROBABILITIES[DealStage.MEETING_SCHEDULED] < STAGE_PROBABILITIES[DealStage.PROPOSAL_SENT]
        assert STAGE_PROBABILITIES[DealStage.PROPOSAL_SENT] < STAGE_PROBABILITIES[DealStage.NEGOTIATION]

        # Terminal states
        assert STAGE_PROBABILITIES[DealStage.CLOSED_WON] == 1.0
        assert STAGE_PROBABILITIES[DealStage.CLOSED_LOST] == 0.0


class TestHandoffSLA:
    """Tests for handoff SLA management."""

    @pytest.fixture
    def service(self):
        from app.services.manager_actions import ManagerActionsService
        return ManagerActionsService()

    @pytest.mark.asyncio
    async def test_sla_deadline_set_on_create(self, service):
        """SLA deadline should be set when handoff is created."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.sadd = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.zadd = AsyncMock(return_value=1)

        with patch(REDIS_PATCH, return_value=mock_redis):
            handoff = await service.create_handoff(
                lead_id="lead-123",
                account_id="acc-456",
            )

        assert handoff.sla_deadline is not None
        # SLA should be in the future
        assert handoff.sla_deadline > handoff.created_at

    @pytest.mark.asyncio
    async def test_sla_extended_on_accept(self, service):
        """SLA should be extended when handoff is accepted."""
        from app.services.manager_actions import HandoffAction, SLA_HOURS
        import json

        now = datetime.now(UTC)
        initial_sla = now + timedelta(hours=SLA_HOURS["accept"])

        handoff_data = {
            "id": "handoff-123",
            "lead_id": "lead-123",
            "account_id": "acc-456",
            "contact_id": None,
            "status": "pending",
            "assigned_to": "manager-1",
            "created_by": "system",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "sla_deadline": initial_sla.isoformat(),
            "action_history": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(handoff_data))
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.zrem = AsyncMock(return_value=1)
        mock_redis.srem = AsyncMock(return_value=1)
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch(REDIS_PATCH, return_value=mock_redis):
            result = await service.take_action(
                handoff_id="handoff-123",
                action=HandoffAction.ACCEPT,
                actor="manager-1",
            )

        # SLA should be extended for resolve
        assert result.handoff.sla_deadline > initial_sla
