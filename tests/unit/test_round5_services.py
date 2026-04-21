"""Tests for Round 5 Services.

RBAC, Audit Trail, Playbooks, Next Best Action, Capacity Planning, Cohort Analytics.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

UTC = timezone.utc


# ============================================================================
# RBAC Tests
# ============================================================================


class TestRBACService:
    """Tests for RBACService."""

    def test_role_enum_values(self):
        """Test Role enum has expected values."""
        from app.services.rbac import Role

        assert Role.ADMIN.value == "admin"
        assert Role.MANAGER.value == "manager"
        assert Role.SALES_REP.value == "sales_rep"
        assert Role.MARKETING.value == "marketing"
        assert Role.VIEWER.value == "viewer"
        assert Role.SYSTEM.value == "system"

    def test_permission_enum_values(self):
        """Test Permission enum has expected values."""
        from app.services.rbac import Permission

        assert Permission.LEAD_VIEW.value == "lead:view"
        assert Permission.DEAL_CLOSE.value == "deal:close"
        assert Permission.HANDOFF_ACCEPT.value == "handoff:accept"
        assert Permission.USER_MANAGE.value == "user:manage"
        assert Permission.AUDIT_VIEW.value == "audit:view"

    def test_role_permissions_mapping(self):
        """Test role permissions are defined."""
        from app.services.rbac import ROLE_PERMISSIONS, Role, Permission

        # Admin has all permissions
        assert ROLE_PERMISSIONS[Role.ADMIN] == set(Permission)

        # Manager has expected permissions
        assert Permission.LEAD_VIEW in ROLE_PERMISSIONS[Role.MANAGER]
        assert Permission.DEAL_CLOSE in ROLE_PERMISSIONS[Role.MANAGER]
        assert Permission.HANDOFF_ACCEPT in ROLE_PERMISSIONS[Role.MANAGER]

        # Viewer has limited permissions
        assert Permission.LEAD_VIEW in ROLE_PERMISSIONS[Role.VIEWER]
        assert Permission.LEAD_CREATE not in ROLE_PERMISSIONS[Role.VIEWER]

    def test_user_to_dict(self):
        """Test User.to_dict() method."""
        from app.services.rbac import User, Role

        user = User(
            id="user-1",
            email="test@example.com",
            name="Test User",
            role=Role.MANAGER,
            is_active=True,
        )

        d = user.to_dict()

        assert d["id"] == "user-1"
        assert d["email"] == "test@example.com"
        assert d["role"] == "manager"
        assert d["is_active"] is True

    def test_access_check_result_to_dict(self):
        """Test AccessCheckResult.to_dict() method."""
        from app.services.rbac import AccessCheckResult

        result = AccessCheckResult(
            allowed=True,
            user_id="user-1",
            permission="lead:view",
            role="manager",
            reason="role_permission",
        )

        d = result.to_dict()

        assert d["allowed"] is True
        assert d["permission"] == "lead:view"
        assert d["reason"] == "role_permission"

    @pytest.mark.asyncio
    async def test_create_user(self):
        """Test creating a user."""
        from app.services.rbac import RBACService, Role

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = RBACService()
            user = await service.create_user(
                user_id="user-1",
                email="test@example.com",
                name="Test User",
                role=Role.MANAGER,
            )

        assert user.id == "user-1"
        assert user.email == "test@example.com"
        assert user.role == Role.MANAGER
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_check_permission_allowed(self):
        """Test permission check when allowed."""
        from app.services.rbac import RBACService, Role, Permission

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value='{"id":"user-1","email":"test@example.com","name":"Test","role":"manager","is_active":true}')

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = RBACService()
            result = await service.check_permission("user-1", Permission.LEAD_VIEW)

        assert result.allowed is True
        assert result.reason == "role_permission"

    @pytest.mark.asyncio
    async def test_check_permission_denied(self):
        """Test permission check when denied."""
        from app.services.rbac import RBACService, Role, Permission

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value='{"id":"user-1","email":"test@example.com","name":"Test","role":"viewer","is_active":true}')

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = RBACService()
            result = await service.check_permission("user-1", Permission.LEAD_CREATE)

        assert result.allowed is False
        assert result.reason == "no_permission"


# ============================================================================
# Audit Trail Tests
# ============================================================================


class TestAuditTrailService:
    """Tests for AuditTrailService."""

    def test_audit_action_enum_values(self):
        """Test AuditAction enum has expected values."""
        from app.services.audit_trail import AuditAction

        assert AuditAction.LEAD_CREATED.value == "lead.created"
        assert AuditAction.DEAL_STAGE_CHANGED.value == "deal.stage_changed"
        assert AuditAction.HANDOFF_ACCEPTED.value == "handoff.accepted"
        assert AuditAction.USER_LOGIN.value == "user.login"

    def test_audit_severity_enum_values(self):
        """Test AuditSeverity enum has expected values."""
        from app.services.audit_trail import AuditSeverity

        assert AuditSeverity.INFO.value == "info"
        assert AuditSeverity.WARNING.value == "warning"
        assert AuditSeverity.ERROR.value == "error"
        assert AuditSeverity.CRITICAL.value == "critical"

    def test_audit_entry_to_dict(self):
        """Test AuditEntry.to_dict() method."""
        from app.services.audit_trail import AuditEntry, AuditAction, AuditSeverity

        now = datetime.now(UTC)
        entry = AuditEntry(
            id="entry-1",
            timestamp=now,
            action=AuditAction.LEAD_CREATED,
            severity=AuditSeverity.INFO,
            actor_id="user-1",
            actor_type="user",
            resource_type="lead",
            resource_id="lead-1",
            description="Created lead",
        )

        d = entry.to_dict()

        assert d["id"] == "entry-1"
        assert d["action"] == "lead.created"
        assert d["severity"] == "info"
        assert d["resource_type"] == "lead"

    @pytest.mark.asyncio
    async def test_log_audit_event(self):
        """Test logging an audit event."""
        from app.services.audit_trail import AuditTrailService, AuditAction

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.zadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        mock_redis.lpush = AsyncMock()
        mock_redis.ltrim = AsyncMock()
        mock_redis.pipeline = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock()
        mock_pipe.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipe

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = AuditTrailService()
            entry = await service.log(
                action=AuditAction.LEAD_CREATED,
                actor_id="user-1",
                resource_type="lead",
                resource_id="lead-1",
                description="Created lead",
            )

        assert entry.action == AuditAction.LEAD_CREATED
        assert entry.actor_id == "user-1"
        assert entry.resource_id == "lead-1"

    @pytest.mark.asyncio
    async def test_log_change(self):
        """Test logging a field change."""
        from app.services.audit_trail import AuditTrailService, AuditAction

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.zadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        mock_redis.lpush = AsyncMock()
        mock_redis.ltrim = AsyncMock()
        mock_redis.pipeline = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock()
        mock_pipe.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipe

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = AuditTrailService()
            entry = await service.log_change(
                action=AuditAction.LEAD_UPDATED,
                actor_id="user-1",
                resource_type="lead",
                resource_id="lead-1",
                field="status",
                old_value="new",
                new_value="qualified",
            )

        assert "status" in entry.changes
        assert entry.changes["status"]["old"] == "new"
        assert entry.changes["status"]["new"] == "qualified"


# ============================================================================
# Playbooks Tests
# ============================================================================


class TestPlaybookService:
    """Tests for PlaybookService."""

    def test_playbook_stage_enum_values(self):
        """Test PlaybookStage enum has expected values."""
        from app.services.playbooks import PlaybookStage

        assert PlaybookStage.LEAD_FOUND.value == "lead_found"
        assert PlaybookStage.OUTREACH.value == "outreach"
        assert PlaybookStage.MEETING.value == "meeting"

    def test_segment_enum_values(self):
        """Test Segment enum has expected values."""
        from app.services.playbooks import Segment

        assert Segment.ENTERPRISE.value == "enterprise"
        assert Segment.SMB.value == "smb"
        assert Segment.STARTUP.value == "startup"

    def test_action_type_enum_values(self):
        """Test ActionType enum has expected values."""
        from app.services.playbooks import ActionType

        assert ActionType.EMAIL.value == "email"
        assert ActionType.CALL.value == "call"
        assert ActionType.MEETING.value == "meeting"

    def test_playbook_action_to_dict(self):
        """Test PlaybookAction.to_dict() method."""
        from app.services.playbooks import PlaybookAction, ActionType

        action = PlaybookAction(
            id="action-1",
            action_type=ActionType.EMAIL,
            name="Send Email",
            description="Send intro email",
            delay_hours=24,
        )

        d = action.to_dict()

        assert d["id"] == "action-1"
        assert d["action_type"] == "email"
        assert d["delay_hours"] == 24

    def test_default_playbooks_loaded(self):
        """Test default playbooks are loaded."""
        from app.services.playbooks import PlaybookService, PlaybookStage

        service = PlaybookService()

        # Should have enterprise outreach playbook
        assert "outreach-enterprise" in service._playbooks

        # Should have SMB outreach playbook
        assert "outreach-smb" in service._playbooks

    @pytest.mark.asyncio
    async def test_get_playbook(self):
        """Test getting a playbook."""
        from app.services.playbooks import PlaybookService

        service = PlaybookService()
        playbook = await service.get_playbook("outreach-enterprise")

        assert playbook is not None
        assert playbook.name == "Enterprise Outreach Sequence"
        assert len(playbook.actions) > 0

    @pytest.mark.asyncio
    async def test_get_playbooks_for_stage(self):
        """Test getting playbooks for a stage."""
        from app.services.playbooks import PlaybookService, PlaybookStage

        service = PlaybookService()
        playbooks = await service.get_playbooks_for_stage(PlaybookStage.OUTREACH)

        assert len(playbooks) >= 2  # Enterprise and SMB

    @pytest.mark.asyncio
    async def test_start_playbook(self):
        """Test starting a playbook."""
        from app.services.playbooks import PlaybookService

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = PlaybookService()
            progress = await service.start_playbook(
                playbook_id="outreach-enterprise",
                resource_type="lead",
                resource_id="lead-1",
            )

        assert progress.playbook_id == "outreach-enterprise"
        assert progress.status == "in_progress"
        assert progress.current_action_index == 0


# ============================================================================
# Next Best Action Tests
# ============================================================================


class TestNextBestActionEngine:
    """Tests for NextBestActionEngine."""

    def test_action_priority_enum_values(self):
        """Test ActionPriority enum has expected values."""
        from app.services.next_best_action import ActionPriority

        assert ActionPriority.CRITICAL.value == "critical"
        assert ActionPriority.HIGH.value == "high"
        assert ActionPriority.MEDIUM.value == "medium"
        assert ActionPriority.LOW.value == "low"

    def test_action_category_enum_values(self):
        """Test ActionCategory enum has expected values."""
        from app.services.next_best_action import ActionCategory

        assert ActionCategory.OUTREACH.value == "outreach"
        assert ActionCategory.HANDOFF.value == "handoff"
        assert ActionCategory.DEAL.value == "deal"

    def test_recommended_action_to_dict(self):
        """Test RecommendedAction.to_dict() method."""
        from app.services.next_best_action import (
            RecommendedAction,
            ActionCategory,
            ActionPriority,
        )

        action = RecommendedAction(
            id="action-1",
            action_type="review_handoff",
            category=ActionCategory.HANDOFF,
            priority=ActionPriority.HIGH,
            title="Review Handoff",
            description="Review pending handoff",
            resource_type="handoff",
            resource_id="handoff-1",
            score=85,
            reasoning="SLA deadline approaching",
        )

        d = action.to_dict()

        assert d["id"] == "action-1"
        assert d["category"] == "handoff"
        assert d["priority"] == "high"
        assert d["score"] == 85

    @pytest.mark.asyncio
    async def test_get_recommendations(self):
        """Test getting recommendations."""
        from app.services.next_best_action import NextBestActionEngine

        mock_redis = AsyncMock()
        mock_redis.lrange = AsyncMock(return_value=[])
        mock_redis.zrangebyscore = AsyncMock(return_value=[])
        mock_redis.smembers = AsyncMock(return_value=set())

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            engine = NextBestActionEngine()
            recommendations = await engine.get_recommendations(
                user_id="user-1",
                role="sales_rep",
                limit=10,
            )

        # Should return empty list when no data
        assert isinstance(recommendations, list)

    def test_get_time_of_day(self):
        """Test time of day classification."""
        from app.services.next_best_action import NextBestActionEngine

        engine = NextBestActionEngine()

        morning = datetime(2024, 1, 1, 9, 0, tzinfo=UTC)
        assert engine._get_time_of_day(morning) == "morning"

        afternoon = datetime(2024, 1, 1, 14, 0, tzinfo=UTC)
        assert engine._get_time_of_day(afternoon) == "afternoon"

        evening = datetime(2024, 1, 1, 19, 0, tzinfo=UTC)
        assert engine._get_time_of_day(evening) == "evening"


# ============================================================================
# Capacity Planning Tests
# ============================================================================


class TestCapacityPlanningService:
    """Tests for CapacityPlanningService."""

    def test_capacity_status_enum_values(self):
        """Test CapacityStatus enum has expected values."""
        from app.services.capacity_planning import CapacityStatus

        assert CapacityStatus.AVAILABLE.value == "available"
        assert CapacityStatus.BUSY.value == "busy"
        assert CapacityStatus.OVERLOADED.value == "overloaded"
        assert CapacityStatus.UNAVAILABLE.value == "unavailable"

    def test_manager_capacity_to_dict(self):
        """Test ManagerCapacity.to_dict() method."""
        from app.services.capacity_planning import ManagerCapacity, CapacityStatus

        capacity = ManagerCapacity(
            manager_id="mgr-1",
            name="Manager One",
            status=CapacityStatus.AVAILABLE,
            max_handoffs=15,
            current_handoffs=5,
            max_deals=25,
            current_deals=10,
            capacity_percent=37.5,
            available_slots=10,
        )

        d = capacity.to_dict()

        assert d["manager_id"] == "mgr-1"
        assert d["status"] == "available"
        assert d["available_slots"] == 10

    def test_team_capacity_to_dict(self):
        """Test TeamCapacity.to_dict() method."""
        from app.services.capacity_planning import TeamCapacity

        team = TeamCapacity(
            total_managers=5,
            active_managers=4,
            total_capacity=60,
            used_capacity=30,
            available_capacity=30,
            utilization_percent=50.0,
            by_status={"available": 3, "busy": 1},
            bottlenecks=[],
        )

        d = team.to_dict()

        assert d["total_managers"] == 5
        assert d["utilization_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_get_manager_capacity(self):
        """Test getting manager capacity."""
        from app.services.capacity_planning import CapacityPlanningService

        config_json = '{"name":"Test Manager","max_handoffs":15,"max_deals":25,"skills":[],"segments":[],"is_active":true}'

        async def mock_get(key):
            if "manager:config:" in key:
                return config_json
            return None  # For metrics keys

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=mock_get)
        mock_redis.scard = AsyncMock(return_value=5)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = CapacityPlanningService()
            capacity = await service.get_manager_capacity("mgr-1")

        assert capacity.manager_id == "mgr-1"
        assert capacity.current_handoffs == 5

    @pytest.mark.asyncio
    async def test_set_manager_config(self):
        """Test setting manager config."""
        from app.services.capacity_planning import CapacityPlanningService

        call_count = 0

        async def mock_get(key):
            nonlocal call_count
            call_count += 1
            # First call returns None (no existing config)
            # Second call after set returns the new config
            if call_count == 1:
                return None  # First get (check existing)
            elif "manager:config:" in key:
                return '{"name":"New Manager","max_handoffs":20,"max_deals":25,"skills":[],"segments":[],"is_active":true}'
            return None

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=mock_get)
        mock_redis.set = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.scard = AsyncMock(return_value=0)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = CapacityPlanningService()
            capacity = await service.set_manager_config(
                manager_id="mgr-1",
                name="New Manager",
                max_handoffs=20,
            )

        assert capacity.manager_id == "mgr-1"
        assert capacity.max_handoffs == 20

    @pytest.mark.asyncio
    async def test_get_team_capacity(self):
        """Test getting team capacity."""
        from app.services.capacity_planning import CapacityPlanningService

        mock_redis = AsyncMock()
        mock_redis.smembers = AsyncMock(return_value=set())

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = CapacityPlanningService()
            team = await service.get_team_capacity()

        assert team.total_managers == 0


# ============================================================================
# Cohort Analytics Tests
# ============================================================================


class TestCohortAnalyticsService:
    """Tests for CohortAnalyticsService."""

    def test_cohort_type_enum_values(self):
        """Test CohortType enum has expected values."""
        from app.services.cohort_analytics import CohortType

        assert CohortType.WEEKLY.value == "weekly"
        assert CohortType.MONTHLY.value == "monthly"
        assert CohortType.SOURCE.value == "source"
        assert CohortType.SEGMENT.value == "segment"

    def test_anomaly_type_enum_values(self):
        """Test AnomalyType enum has expected values."""
        from app.services.cohort_analytics import AnomalyType

        assert AnomalyType.SPIKE.value == "spike"
        assert AnomalyType.DROP.value == "drop"
        assert AnomalyType.TREND_BREAK.value == "trend_break"

    def test_anomaly_severity_enum_values(self):
        """Test AnomalySeverity enum has expected values."""
        from app.services.cohort_analytics import AnomalySeverity

        assert AnomalySeverity.LOW.value == "low"
        assert AnomalySeverity.MEDIUM.value == "medium"
        assert AnomalySeverity.HIGH.value == "high"
        assert AnomalySeverity.CRITICAL.value == "critical"

    def test_cohort_metrics_to_dict(self):
        """Test CohortMetrics.to_dict() method."""
        from app.services.cohort_analytics import CohortMetrics, CohortType

        now = datetime.now(UTC)
        cohort = CohortMetrics(
            cohort_id="weekly-2024-W01",
            cohort_type=CohortType.WEEKLY,
            cohort_value="2024-W01",
            period_start=now,
            period_end=now + timedelta(days=7),
            size=100,
            metrics={"conversion_rate": 5.0},
        )

        d = cohort.to_dict()

        assert d["cohort_id"] == "weekly-2024-W01"
        assert d["cohort_type"] == "weekly"
        assert d["size"] == 100

    def test_anomaly_to_dict(self):
        """Test Anomaly.to_dict() method."""
        from app.services.cohort_analytics import (
            Anomaly,
            AnomalyType,
            AnomalySeverity,
        )

        now = datetime.now(UTC)
        anomaly = Anomaly(
            id="anomaly-1",
            anomaly_type=AnomalyType.SPIKE,
            severity=AnomalySeverity.HIGH,
            metric="leads_acquired",
            current_value=150,
            expected_value=100,
            deviation=50.0,
            detected_at=now,
            description="Leads spiked to 150",
        )

        d = anomaly.to_dict()

        assert d["id"] == "anomaly-1"
        assert d["anomaly_type"] == "spike"
        assert d["severity"] == "high"
        assert d["deviation"] == 50.0

    @pytest.mark.asyncio
    async def test_detect_anomalies(self):
        """Test anomaly detection."""
        from app.services.cohort_analytics import CohortAnalyticsService

        mock_redis = AsyncMock()
        # Return consistent values (no anomaly)
        mock_redis.get = AsyncMock(return_value="100")

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = CohortAnalyticsService()
            anomalies = await service.detect_anomalies(
                metric="leads_acquired",
                lookback_days=14,
            )

        # With consistent values, no anomalies expected
        assert isinstance(anomalies, list)

    @pytest.mark.asyncio
    async def test_get_weekly_cohorts(self):
        """Test getting weekly cohorts."""
        from app.services.cohort_analytics import CohortAnalyticsService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = CohortAnalyticsService()
            cohorts = await service.get_weekly_cohorts(weeks=4)

        assert isinstance(cohorts, list)

    @pytest.mark.asyncio
    async def test_get_analytics_summary(self):
        """Test getting analytics summary."""
        from app.services.cohort_analytics import CohortAnalyticsService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.smembers = AsyncMock(return_value=set())

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = CohortAnalyticsService()
            summary = await service.get_analytics_summary(days=7)

        assert "total_anomalies" in summary
        assert "weekly_cohorts_count" in summary
