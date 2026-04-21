"""Unit tests for Operational Cockpit service."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import json

UTC = timezone.utc

REDIS_PATCH = "app.storage.redis.get_redis"


class TestOpsCockpitService:
    """Tests for OpsCockpitService."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock()
        mock.hgetall = AsyncMock(return_value={})
        mock.hget = AsyncMock(return_value=None)
        mock.smembers = AsyncMock(return_value=set())
        mock.lrange = AsyncMock(return_value=[])
        mock.zrevrange = AsyncMock(return_value=[])
        mock.zrangebyscore = AsyncMock(return_value=[])
        return mock

    @pytest.mark.asyncio
    async def test_get_quick_status(self, mock_redis):
        """Test getting quick status."""
        from app.services.ops_cockpit import OpsCockpitService

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            status = await service.get_quick_status()

            assert "status" in status
            assert "timestamp" in status
            assert "critical_items" in status

    @pytest.mark.asyncio
    async def test_get_cockpit(self, mock_redis):
        """Test getting full cockpit."""
        from app.services.ops_cockpit import OpsCockpitService, OverallStatus

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            cockpit = await service.get_cockpit()

            assert cockpit.overall_status in [s for s in OverallStatus]
            assert cockpit.health is not None
            assert cockpit.incidents is not None
            assert cockpit.queues is not None
            assert cockpit.slos is not None
            assert cockpit.costs is not None
            assert cockpit.drift is not None
            assert cockpit.approvals is not None
            assert cockpit.risky_actions is not None
            assert isinstance(cockpit.recommended_actions, list)

    @pytest.mark.asyncio
    async def test_cockpit_to_dict(self, mock_redis):
        """Test cockpit serialization."""
        from app.services.ops_cockpit import OpsCockpitService

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            cockpit = await service.get_cockpit()
            data = cockpit.to_dict()

            assert "generated_at" in data
            assert "overall_status" in data
            assert "health" in data
            assert "incidents" in data
            assert "queues" in data
            assert "slos" in data
            assert "costs" in data
            assert "drift" in data
            assert "approvals" in data
            assert "risky_actions" in data
            assert "recommended_actions" in data

    @pytest.mark.asyncio
    async def test_health_summary(self, mock_redis):
        """Test health summary generation."""
        from app.services.ops_cockpit import OpsCockpitService, OverallStatus

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            health = await service._get_health_summary()

            assert health.status in [s for s in OverallStatus]
            assert isinstance(health.services_total, int)
            assert isinstance(health.active_circuit_breakers, list)

    @pytest.mark.asyncio
    async def test_incident_summary(self, mock_redis):
        """Test incident summary generation."""
        from app.services.ops_cockpit import OpsCockpitService

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            incidents = await service._get_incident_summary()

            assert isinstance(incidents.active_count, int)
            assert isinstance(incidents.critical_count, int)
            assert isinstance(incidents.recent_incidents, list)

    @pytest.mark.asyncio
    async def test_queue_summary(self, mock_redis):
        """Test queue summary generation."""
        from app.services.ops_cockpit import OpsCockpitService

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            queues = await service._get_queue_summary()

            assert isinstance(queues.total_queues, int)
            assert isinstance(queues.total_pending, int)
            assert isinstance(queues.queue_details, list)

    @pytest.mark.asyncio
    async def test_slo_summary(self, mock_redis):
        """Test SLO summary generation."""
        from app.services.ops_cockpit import OpsCockpitService

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            slos = await service._get_slo_summary()

            assert isinstance(slos.total_slos, int)
            assert isinstance(slos.slos_at_risk, int)
            assert isinstance(slos.slos_breached, int)

    @pytest.mark.asyncio
    async def test_cost_summary(self, mock_redis):
        """Test cost summary generation."""
        from app.services.ops_cockpit import OpsCockpitService

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            costs = await service._get_cost_summary()

            assert isinstance(costs.daily_total_usd, (int, float))
            assert isinstance(costs.daily_budget_usd, (int, float))
            assert isinstance(costs.top_cost_drivers, list)

    @pytest.mark.asyncio
    async def test_drift_summary(self, mock_redis):
        """Test drift summary generation."""
        from app.services.ops_cockpit import OpsCockpitService

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            drift = await service._get_drift_summary()

            assert isinstance(drift.total_monitored, int)
            assert isinstance(drift.drifted_count, int)
            assert isinstance(drift.recent_drifts, list)

    @pytest.mark.asyncio
    async def test_approval_summary(self, mock_redis):
        """Test approval summary generation."""
        from app.services.ops_cockpit import OpsCockpitService

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            approvals = await service._get_approval_summary()

            assert isinstance(approvals.pending_count, int)
            assert isinstance(approvals.critical_pending, int)
            assert isinstance(approvals.pending_details, list)

    @pytest.mark.asyncio
    async def test_risky_actions_summary(self, mock_redis):
        """Test risky actions summary generation."""
        from app.services.ops_cockpit import OpsCockpitService

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            risky = await service._get_risky_actions_summary()

            assert isinstance(risky.last_24h_count, int)
            assert isinstance(risky.emergency_actions, int)
            assert isinstance(risky.recent_actions, list)

    @pytest.mark.asyncio
    async def test_get_actions_only(self, mock_redis):
        """Test getting only recommended actions."""
        from app.services.ops_cockpit import OpsCockpitService

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            actions = await service.get_actions_only()

            assert isinstance(actions, list)

    @pytest.mark.asyncio
    async def test_get_actions_filtered_by_priority(self, mock_redis):
        """Test filtering actions by priority."""
        from app.services.ops_cockpit import OpsCockpitService, ActionPriority

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            actions = await service.get_actions_only(priority=ActionPriority.CRITICAL)

            # All actions should be critical
            for action in actions:
                assert action.priority == ActionPriority.CRITICAL

    @pytest.mark.asyncio
    async def test_get_actions_filtered_by_category(self, mock_redis):
        """Test filtering actions by category."""
        from app.services.ops_cockpit import OpsCockpitService, ActionCategory

        with patch(REDIS_PATCH, return_value=mock_redis):
            service = OpsCockpitService()
            actions = await service.get_actions_only(category=ActionCategory.INCIDENT)

            # All actions should be incident category
            for action in actions:
                assert action.category == ActionCategory.INCIDENT


class TestOverallStatusDetermination:
    """Tests for overall status determination logic."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.hgetall = AsyncMock(return_value={})
        mock.smembers = AsyncMock(return_value=set())
        mock.lrange = AsyncMock(return_value=[])
        mock.zrevrange = AsyncMock(return_value=[])
        return mock

    @pytest.mark.asyncio
    async def test_status_emergency_when_emergency_mode(self, mock_redis):
        """Test emergency status when emergency mode active."""
        from app.services.ops_cockpit import (
            OpsCockpitService, OverallStatus,
            HealthSummary, IncidentSummary, SLOSummary,
            CostSummary, DriftSummary, ApprovalSummary,
        )

        service = OpsCockpitService()

        health = HealthSummary(
            status=OverallStatus.EMERGENCY,
            services_total=5,
            services_healthy=5,
            services_degraded=0,
            services_unhealthy=0,
            active_circuit_breakers=[],
            processing_paused=False,
            emergency_mode=True,
            last_check=datetime.now(UTC),
        )
        incidents = IncidentSummary(0, 0, 0, None, None, [])
        slos = SLOSummary(0, 0, 0, None, None, [])
        costs = CostSummary(0, 100, 0, 0, 3000, 0, [], 0)
        drift = DriftSummary(0, 0, 0, 0, [])
        approvals = ApprovalSummary(0, 0, 0, None, 0, [])

        status, reason = service._determine_overall_status(
            health, incidents, slos, costs, drift, approvals
        )

        assert status == OverallStatus.EMERGENCY
        assert "emergency" in reason.lower()

    @pytest.mark.asyncio
    async def test_status_critical_with_incidents(self, mock_redis):
        """Test critical status with critical incidents."""
        from app.services.ops_cockpit import (
            OpsCockpitService, OverallStatus,
            HealthSummary, IncidentSummary, SLOSummary,
            CostSummary, DriftSummary, ApprovalSummary,
        )

        service = OpsCockpitService()

        health = HealthSummary(
            status=OverallStatus.HEALTHY,
            services_total=5,
            services_healthy=5,
            services_degraded=0,
            services_unhealthy=0,
            active_circuit_breakers=[],
            processing_paused=False,
            emergency_mode=False,
            last_check=datetime.now(UTC),
        )
        incidents = IncidentSummary(2, 2, 0, 1.5, 2.0, [])  # 2 critical
        slos = SLOSummary(0, 0, 0, None, None, [])
        costs = CostSummary(0, 100, 0, 0, 3000, 0, [], 0)
        drift = DriftSummary(0, 0, 0, 0, [])
        approvals = ApprovalSummary(0, 0, 0, None, 0, [])

        status, reason = service._determine_overall_status(
            health, incidents, slos, costs, drift, approvals
        )

        assert status == OverallStatus.CRITICAL
        assert "incident" in reason.lower()

    @pytest.mark.asyncio
    async def test_status_at_risk_with_slos(self, mock_redis):
        """Test at-risk status with SLOs at risk."""
        from app.services.ops_cockpit import (
            OpsCockpitService, OverallStatus,
            HealthSummary, IncidentSummary, SLOSummary,
            CostSummary, DriftSummary, ApprovalSummary,
        )

        service = OpsCockpitService()

        health = HealthSummary(
            status=OverallStatus.HEALTHY,
            services_total=5,
            services_healthy=5,
            services_degraded=0,
            services_unhealthy=0,
            active_circuit_breakers=[],
            processing_paused=False,
            emergency_mode=False,
            last_check=datetime.now(UTC),
        )
        incidents = IncidentSummary(0, 0, 0, None, None, [])
        slos = SLOSummary(3, 2, 0, 15.0, "api_latency", [])  # 2 at risk
        costs = CostSummary(0, 100, 0, 0, 3000, 0, [], 0)
        drift = DriftSummary(0, 0, 0, 0, [])
        approvals = ApprovalSummary(0, 0, 0, None, 0, [])

        status, reason = service._determine_overall_status(
            health, incidents, slos, costs, drift, approvals
        )

        assert status == OverallStatus.AT_RISK
        assert "slo" in reason.lower()

    @pytest.mark.asyncio
    async def test_status_degraded_with_circuit_breakers(self, mock_redis):
        """Test degraded status with circuit breakers."""
        from app.services.ops_cockpit import (
            OpsCockpitService, OverallStatus,
            HealthSummary, IncidentSummary, SLOSummary,
            CostSummary, DriftSummary, ApprovalSummary,
        )

        service = OpsCockpitService()

        health = HealthSummary(
            status=OverallStatus.DEGRADED,
            services_total=5,
            services_healthy=4,
            services_degraded=1,
            services_unhealthy=0,
            active_circuit_breakers=["openai"],
            processing_paused=False,
            emergency_mode=False,
            last_check=datetime.now(UTC),
        )
        incidents = IncidentSummary(0, 0, 0, None, None, [])
        slos = SLOSummary(3, 0, 0, 80.0, None, [])
        costs = CostSummary(50, 100, 50, 500, 3000, 16.7, [], 0)
        drift = DriftSummary(0, 0, 0, 0, [])
        approvals = ApprovalSummary(0, 0, 0, None, 0, [])

        status, reason = service._determine_overall_status(
            health, incidents, slos, costs, drift, approvals
        )

        assert status == OverallStatus.DEGRADED
        assert "circuit" in reason.lower() or "degraded" in reason.lower()

    @pytest.mark.asyncio
    async def test_status_healthy_when_all_good(self, mock_redis):
        """Test healthy status when everything is good."""
        from app.services.ops_cockpit import (
            OpsCockpitService, OverallStatus,
            HealthSummary, IncidentSummary, SLOSummary,
            CostSummary, DriftSummary, ApprovalSummary,
        )

        service = OpsCockpitService()

        health = HealthSummary(
            status=OverallStatus.HEALTHY,
            services_total=5,
            services_healthy=5,
            services_degraded=0,
            services_unhealthy=0,
            active_circuit_breakers=[],
            processing_paused=False,
            emergency_mode=False,
            last_check=datetime.now(UTC),
        )
        incidents = IncidentSummary(0, 0, 0, None, None, [])
        slos = SLOSummary(3, 0, 0, 80.0, None, [])
        costs = CostSummary(50, 100, 50, 500, 3000, 16.7, [], 0)
        drift = DriftSummary(5, 0, 0, 0, [])
        approvals = ApprovalSummary(0, 0, 0, None, 0, [])

        status, reason = service._determine_overall_status(
            health, incidents, slos, costs, drift, approvals
        )

        assert status == OverallStatus.HEALTHY
        assert "operational" in reason.lower()


class TestRecommendedActions:
    """Tests for recommended actions generation."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.hgetall = AsyncMock(return_value={})
        mock.smembers = AsyncMock(return_value=set())
        return mock

    @pytest.mark.asyncio
    async def test_generates_emergency_action(self, mock_redis):
        """Test generating emergency action when in emergency mode."""
        from app.services.ops_cockpit import (
            OpsCockpitService, ActionPriority, ActionCategory,
            HealthSummary, IncidentSummary, QueueSummary, SLOSummary,
            CostSummary, DriftSummary, ApprovalSummary, OverallStatus,
        )

        service = OpsCockpitService()

        health = HealthSummary(
            status=OverallStatus.EMERGENCY,
            services_total=5,
            services_healthy=5,
            services_degraded=0,
            services_unhealthy=0,
            active_circuit_breakers=[],
            processing_paused=True,
            emergency_mode=True,
            last_check=datetime.now(UTC),
        )
        incidents = IncidentSummary(0, 0, 0, None, None, [])
        queues = QueueSummary(3, 10, 2, 0, None, [])
        slos = SLOSummary(3, 0, 0, 80.0, None, [])
        costs = CostSummary(50, 100, 50, 500, 3000, 16.7, [], 0)
        drift = DriftSummary(5, 0, 0, 0, [])
        approvals = ApprovalSummary(0, 0, 0, None, 0, [])

        actions = await service._generate_recommendations(
            health, incidents, queues, slos, costs, drift, approvals
        )

        emergency_actions = [a for a in actions if "emergency" in a.title.lower()]
        assert len(emergency_actions) > 0
        assert emergency_actions[0].priority == ActionPriority.CRITICAL

    @pytest.mark.asyncio
    async def test_generates_incident_action(self, mock_redis):
        """Test generating action for critical incidents."""
        from app.services.ops_cockpit import (
            OpsCockpitService, ActionPriority, ActionCategory,
            HealthSummary, IncidentSummary, QueueSummary, SLOSummary,
            CostSummary, DriftSummary, ApprovalSummary, OverallStatus,
        )

        service = OpsCockpitService()

        health = HealthSummary(
            status=OverallStatus.HEALTHY,
            services_total=5,
            services_healthy=5,
            services_degraded=0,
            services_unhealthy=0,
            active_circuit_breakers=[],
            processing_paused=False,
            emergency_mode=False,
            last_check=datetime.now(UTC),
        )
        incidents = IncidentSummary(2, 2, 0, 1.5, None, [])  # 2 critical
        queues = QueueSummary(3, 10, 2, 0, None, [])
        slos = SLOSummary(3, 0, 0, 80.0, None, [])
        costs = CostSummary(50, 100, 50, 500, 3000, 16.7, [], 0)
        drift = DriftSummary(5, 0, 0, 0, [])
        approvals = ApprovalSummary(0, 0, 0, None, 0, [])

        actions = await service._generate_recommendations(
            health, incidents, queues, slos, costs, drift, approvals
        )

        incident_actions = [a for a in actions if a.category == ActionCategory.INCIDENT]
        assert len(incident_actions) > 0
        assert incident_actions[0].priority == ActionPriority.CRITICAL

    @pytest.mark.asyncio
    async def test_actions_sorted_by_priority(self, mock_redis):
        """Test that actions are sorted by priority."""
        from app.services.ops_cockpit import (
            OpsCockpitService, ActionPriority,
            HealthSummary, IncidentSummary, QueueSummary, SLOSummary,
            CostSummary, DriftSummary, ApprovalSummary, OverallStatus,
        )

        service = OpsCockpitService()

        health = HealthSummary(
            status=OverallStatus.DEGRADED,
            services_total=5,
            services_healthy=3,
            services_degraded=2,
            services_unhealthy=0,
            active_circuit_breakers=["redis"],
            processing_paused=False,
            emergency_mode=False,
            last_check=datetime.now(UTC),
        )
        incidents = IncidentSummary(1, 1, 0, 1.0, None, [])
        queues = QueueSummary(3, 200, 10, 2, 30.0, [])
        slos = SLOSummary(3, 1, 0, 15.0, "api_latency", [])
        costs = CostSummary(95, 100, 95, 2800, 3000, 93.3, [], 1)
        drift = DriftSummary(5, 1, 1, 20, [])
        approvals = ApprovalSummary(2, 1, 1, 2.0, 1, [])

        actions = await service._generate_recommendations(
            health, incidents, queues, slos, costs, drift, approvals
        )

        # Check that critical comes before high, high before medium
        priorities_seen = [a.priority for a in actions]
        priority_order = [ActionPriority.CRITICAL, ActionPriority.HIGH, ActionPriority.MEDIUM, ActionPriority.LOW]

        last_idx = -1
        for priority in priorities_seen:
            idx = priority_order.index(priority)
            assert idx >= last_idx, "Actions not sorted by priority"
            last_idx = idx


class TestRecommendedActionModel:
    """Tests for RecommendedAction dataclass."""

    def test_recommended_action_to_dict(self):
        """Test RecommendedAction serialization."""
        from app.services.ops_cockpit import (
            RecommendedAction, ActionPriority, ActionCategory
        )

        now = datetime.now(UTC)
        action = RecommendedAction(
            id="test123",
            title="Test Action",
            description="Test description",
            category=ActionCategory.INCIDENT,
            priority=ActionPriority.HIGH,
            source_service="test_service",
            source_id="src123",
            action_url="/api/test",
            created_at=now,
            expires_at=now + timedelta(hours=1),
            metadata={"key": "value"},
        )

        data = action.to_dict()

        assert data["id"] == "test123"
        assert data["title"] == "Test Action"
        assert data["category"] == "incident"
        assert data["priority"] == "high"
        assert data["source_service"] == "test_service"
        assert data["action_url"] == "/api/test"
        assert data["metadata"] == {"key": "value"}
