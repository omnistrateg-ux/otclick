"""Tests for Round 8 Services.

Environment Guardrails, Deployment Safety, Feature Flags, Costs,
SLOs, Incidents, Synthetic Probes, Chaos Drills.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

UTC = timezone.utc


# ============================================================================
# Environment Guardrails Tests
# ============================================================================


class TestEnvironmentGuardrailsService:
    """Tests for EnvironmentGuardrailsService."""

    def test_environment_enum_values(self):
        """Test Environment enum values."""
        from app.services.environment_guardrails import Environment

        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"

    def test_action_severity_enum_values(self):
        """Test ActionSeverity enum values."""
        from app.services.environment_guardrails import ActionSeverity

        assert ActionSeverity.SAFE.value == "safe"
        assert ActionSeverity.FORBIDDEN.value == "forbidden"

    def test_action_category_enum_values(self):
        """Test ActionCategory enum values."""
        from app.services.environment_guardrails import ActionCategory

        assert ActionCategory.DATA_DELETE.value == "data_delete"
        assert ActionCategory.DEPLOYMENT.value == "deployment"

    def test_detect_environment_default(self):
        """Test environment detection."""
        from app.services.environment_guardrails import EnvironmentGuardrailsService, Environment

        with patch.dict("os.environ", {"OTCLICK_ENVIRONMENT": "development"}):
            service = EnvironmentGuardrailsService()
            service._current_env = None
            env = service.detect_environment()

        assert env == Environment.DEVELOPMENT

    def test_get_config(self):
        """Test getting environment config."""
        from app.services.environment_guardrails import (
            EnvironmentGuardrailsService, Environment
        )

        service = EnvironmentGuardrailsService()
        config = service.get_config(Environment.PRODUCTION)

        assert config.name == Environment.PRODUCTION
        assert config.require_approval_for_deploys is True

    def test_is_production(self):
        """Test production check."""
        from app.services.environment_guardrails import EnvironmentGuardrailsService

        with patch.dict("os.environ", {"OTCLICK_ENVIRONMENT": "production"}):
            service = EnvironmentGuardrailsService()
            service._current_env = None
            assert service.is_production() is True

    @pytest.mark.asyncio
    async def test_check_action_allowed(self):
        """Test checking allowed action."""
        from app.services.environment_guardrails import (
            EnvironmentGuardrailsService, ActionCategory
        )

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=False)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            with patch.dict("os.environ", {"OTCLICK_ENVIRONMENT": "development"}):
                service = EnvironmentGuardrailsService()
                service._current_env = None
                result = await service.check_action(
                    action=ActionCategory.DATA_MODIFY,
                    actor="admin",
                )

        assert result["allowed"] is True


# ============================================================================
# Deployment Safety Tests
# ============================================================================


class TestDeploymentSafetyService:
    """Tests for DeploymentSafetyService."""

    def test_deployment_status_enum_values(self):
        """Test DeploymentStatus enum values."""
        from app.services.deployment_safety import DeploymentStatus

        assert DeploymentStatus.PENDING.value == "pending"
        assert DeploymentStatus.DEPLOYED.value == "deployed"
        assert DeploymentStatus.ROLLED_BACK.value == "rolled_back"

    def test_check_status_enum_values(self):
        """Test CheckStatus enum values."""
        from app.services.deployment_safety import CheckStatus

        assert CheckStatus.PASSED.value == "passed"
        assert CheckStatus.FAILED.value == "failed"
        assert CheckStatus.WARNING.value == "warning"

    def test_safety_check_to_dict(self):
        """Test SafetyCheck.to_dict()."""
        from app.services.deployment_safety import SafetyCheck, CheckCategory, CheckStatus

        check = SafetyCheck(
            name="Test Check",
            category=CheckCategory.TESTS,
            status=CheckStatus.PASSED,
            message="All tests pass",
            duration_ms=100.0,
        )

        d = check.to_dict()

        assert d["name"] == "Test Check"
        assert d["status"] == "passed"

    def test_deployment_plan_to_dict(self):
        """Test DeploymentPlan.to_dict()."""
        from app.services.deployment_safety import (
            DeploymentPlan, DeploymentStatus, SafetyCheck, CheckCategory, CheckStatus
        )

        now = datetime.now(UTC)
        plan = DeploymentPlan(
            id="plan-1",
            version="1.0.0",
            environment="staging",
            status=DeploymentStatus.PENDING,
            created_at=now,
            created_by="admin",
            checks=[
                SafetyCheck(
                    name="Test",
                    category=CheckCategory.TESTS,
                    status=CheckStatus.PASSED,
                    message="OK",
                )
            ],
        )

        d = plan.to_dict()

        assert d["id"] == "plan-1"
        assert d["version"] == "1.0.0"
        assert d["can_deploy"] is True

    @pytest.mark.asyncio
    async def test_create_deployment_plan(self):
        """Test creating deployment plan."""
        from app.services.deployment_safety import DeploymentSafetyService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.zadd = AsyncMock()
        mock_redis.set = AsyncMock()

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = DeploymentSafetyService()
            plan = await service.create_deployment_plan(
                version="1.0.0",
                environment="staging",
                created_by="admin",
            )

        assert plan is not None
        assert plan.version == "1.0.0"
        assert len(plan.checks) > 0


# ============================================================================
# Feature Flags Tests
# ============================================================================


class TestFeatureFlagsService:
    """Tests for FeatureFlagsService."""

    def test_flag_status_enum_values(self):
        """Test FlagStatus enum values."""
        from app.services.feature_flags import FlagStatus

        assert FlagStatus.ENABLED.value == "enabled"
        assert FlagStatus.DISABLED.value == "disabled"
        assert FlagStatus.GRADUAL.value == "gradual"

    def test_feature_flag_to_dict(self):
        """Test FeatureFlag.to_dict()."""
        from app.services.feature_flags import (
            FeatureFlag, FlagStatus, FlagEnvironment
        )

        now = datetime.now(UTC)
        flag = FeatureFlag(
            key="test_flag",
            name="Test Flag",
            description="A test flag",
            status=FlagStatus.ENABLED,
            environments=[FlagEnvironment.ALL],
            created_at=now,
            updated_at=now,
        )

        d = flag.to_dict()

        assert d["key"] == "test_flag"
        assert d["status"] == "enabled"

    def test_flag_evaluation_to_dict(self):
        """Test FlagEvaluation.to_dict()."""
        from app.services.feature_flags import FlagEvaluation

        eval = FlagEvaluation(
            flag_key="test",
            enabled=True,
            reason="flag_enabled",
            user_id="user-1",
        )

        d = eval.to_dict()

        assert d["enabled"] is True
        assert d["reason"] == "flag_enabled"

    @pytest.mark.asyncio
    async def test_evaluate_enabled_flag(self):
        """Test evaluating enabled flag."""
        from app.services.feature_flags import FeatureFlagsService

        mock_redis = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={})
        mock_redis.hget = AsyncMock(return_value=None)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = FeatureFlagsService()
            # Test against default flag
            eval = await service.evaluate("email_ai_generation")

        assert eval.enabled is True
        assert eval.reason == "flag_enabled"

    @pytest.mark.asyncio
    async def test_is_enabled(self):
        """Test is_enabled helper."""
        from app.services.feature_flags import FeatureFlagsService

        mock_redis = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={})
        mock_redis.hget = AsyncMock(return_value=None)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = FeatureFlagsService()
            enabled = await service.is_enabled("email_ai_generation")

        assert enabled is True


# ============================================================================
# Cost Observability Tests
# ============================================================================


class TestCostObservabilityService:
    """Tests for CostObservabilityService."""

    def test_cost_category_enum_values(self):
        """Test CostCategory enum values."""
        from app.services.cost_observability import CostCategory

        assert CostCategory.LLM_API.value == "llm_api"
        assert CostCategory.EMAIL_SENDING.value == "email_sending"

    def test_cost_period_enum_values(self):
        """Test CostPeriod enum values."""
        from app.services.cost_observability import CostPeriod

        assert CostPeriod.DAILY.value == "daily"
        assert CostPeriod.MONTHLY.value == "monthly"

    def test_cost_entry_to_dict(self):
        """Test CostEntry.to_dict()."""
        from app.services.cost_observability import CostEntry, CostCategory

        now = datetime.now(UTC)
        entry = CostEntry(
            category=CostCategory.LLM_API,
            amount_usd=0.05,
            quantity=1000,
            unit="tokens",
            description="API call",
            timestamp=now,
        )

        d = entry.to_dict()

        assert d["category"] == "llm_api"
        assert d["amount_usd"] == 0.05

    def test_budget_status_to_dict(self):
        """Test BudgetStatus.to_dict()."""
        from app.services.cost_observability import BudgetStatus, CostBudget, CostPeriod

        budget = CostBudget(
            category=None,
            period=CostPeriod.MONTHLY,
            budget_usd=1000.0,
        )

        status = BudgetStatus(
            budget=budget,
            spent_usd=500.0,
            remaining_usd=500.0,
            percent_used=50.0,
            on_track=True,
            projected_overage=None,
            alert_triggered=False,
        )

        d = status.to_dict()

        assert d["spent_usd"] == 500.0
        assert d["percent_used"] == 50.0

    @pytest.mark.asyncio
    async def test_record_cost(self):
        """Test recording a cost."""
        from app.services.cost_observability import CostObservabilityService, CostCategory

        mock_redis = AsyncMock()
        mock_redis.zadd = AsyncMock()
        mock_redis.hincrbyfloat = AsyncMock()
        mock_redis.expire = AsyncMock()
        mock_redis.lrange = AsyncMock(return_value=[])
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.sismember = AsyncMock(return_value=False)
        mock_redis.sadd = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={})  # For get_summary
        mock_redis.zrangebyscore = AsyncMock(return_value=[])  # For entries

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = CostObservabilityService()
            entry = await service.record_cost(
                category=CostCategory.LLM_API,
                amount_usd=0.05,
                quantity=1000,
                unit="tokens",
            )

        assert entry.amount_usd == 0.05
        assert entry.category == CostCategory.LLM_API


# ============================================================================
# SLO Budgets Tests
# ============================================================================


class TestSLOBudgetsService:
    """Tests for SLOBudgetsService."""

    def test_slo_type_enum_values(self):
        """Test SLOType enum values."""
        from app.services.slo_budgets import SLOType

        assert SLOType.AVAILABILITY.value == "availability"
        assert SLOType.LATENCY.value == "latency"

    def test_slo_status_enum_values(self):
        """Test SLOStatus enum values."""
        from app.services.slo_budgets import SLOStatus

        assert SLOStatus.HEALTHY.value == "healthy"
        assert SLOStatus.CRITICAL.value == "critical"

    def test_slo_to_dict(self):
        """Test SLO.to_dict()."""
        from app.services.slo_budgets import SLO, SLOType

        slo = SLO(
            id="test_slo",
            name="Test SLO",
            description="Test description",
            slo_type=SLOType.AVAILABILITY,
            target_percent=99.9,
            window_days=30,
            measurement_query="test:query",
            service="api",
        )

        d = slo.to_dict()

        assert d["id"] == "test_slo"
        assert d["target_percent"] == 99.9

    def test_error_budget_to_dict(self):
        """Test ErrorBudget.to_dict()."""
        from app.services.slo_budgets import ErrorBudget, SLOStatus

        now = datetime.now(UTC)
        budget = ErrorBudget(
            slo_id="test",
            slo_name="Test SLO",
            target_percent=99.9,
            current_percent=99.95,
            budget_total_minutes=43.2,
            budget_consumed_minutes=10.0,
            budget_remaining_minutes=33.2,
            budget_remaining_percent=76.9,
            burn_rate=0.5,
            time_to_exhaustion_hours=66.4,
            status=SLOStatus.HEALTHY,
            window_start=now - timedelta(days=30),
            window_end=now,
        )

        d = budget.to_dict()

        assert d["budget_remaining_percent"] == 76.9
        assert d["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_list_slos(self):
        """Test listing SLOs."""
        from app.services.slo_budgets import SLOBudgetsService

        mock_redis = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={})

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = SLOBudgetsService()
            slos = await service.list_slos()

        assert len(slos) > 0  # Should have defaults


# ============================================================================
# Incident Timeline Tests
# ============================================================================


class TestIncidentTimelineService:
    """Tests for IncidentTimelineService."""

    def test_incident_severity_enum_values(self):
        """Test IncidentSeverity enum values."""
        from app.services.incident_timeline import IncidentSeverity

        assert IncidentSeverity.SEV1.value == "sev1"
        assert IncidentSeverity.SEV4.value == "sev4"

    def test_incident_status_enum_values(self):
        """Test IncidentStatus enum values."""
        from app.services.incident_timeline import IncidentStatus

        assert IncidentStatus.DETECTED.value == "detected"
        assert IncidentStatus.RESOLVED.value == "resolved"

    def test_timeline_event_to_dict(self):
        """Test TimelineEvent.to_dict()."""
        from app.services.incident_timeline import TimelineEvent, TimelineEventType

        now = datetime.now(UTC)
        event = TimelineEvent(
            id="event-1",
            event_type=TimelineEventType.CREATED,
            timestamp=now,
            actor="admin",
            content="Incident created",
        )

        d = event.to_dict()

        assert d["id"] == "event-1"
        assert d["event_type"] == "created"

    def test_incident_to_dict(self):
        """Test Incident.to_dict()."""
        from app.services.incident_timeline import (
            Incident, IncidentSeverity, IncidentStatus, TimelineEvent, TimelineEventType
        )

        now = datetime.now(UTC)
        incident = Incident(
            id="inc-1",
            title="API Down",
            description="API not responding",
            severity=IncidentSeverity.SEV1,
            status=IncidentStatus.INVESTIGATING,
            created_at=now,
            created_by="admin",
            assignee="oncall",
            affected_services=["api"],
            timeline=[
                TimelineEvent(
                    id="e1",
                    event_type=TimelineEventType.CREATED,
                    timestamp=now,
                    actor="admin",
                    content="Created",
                )
            ],
        )

        d = incident.to_dict()

        assert d["id"] == "inc-1"
        assert d["severity"] == "sev1"
        assert d["duration_minutes"] is not None

    @pytest.mark.asyncio
    async def test_create_incident(self):
        """Test creating incident."""
        from app.services.incident_timeline import IncidentTimelineService, IncidentSeverity

        mock_redis = AsyncMock()
        mock_redis.hset = AsyncMock()
        mock_redis.sadd = AsyncMock()

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = IncidentTimelineService()
            incident = await service.create_incident(
                title="Test Incident",
                description="Test description",
                severity=IncidentSeverity.SEV2,
                created_by="admin",
            )

        assert incident is not None
        assert incident.title == "Test Incident"
        assert len(incident.timeline) > 0


# ============================================================================
# Synthetic Probes Tests
# ============================================================================


class TestSyntheticProbesService:
    """Tests for SyntheticProbesService."""

    def test_probe_status_enum_values(self):
        """Test ProbeStatus enum values."""
        from app.services.synthetic_probes import ProbeStatus

        assert ProbeStatus.SUCCESS.value == "success"
        assert ProbeStatus.FAILURE.value == "failure"
        assert ProbeStatus.TIMEOUT.value == "timeout"

    def test_probe_type_enum_values(self):
        """Test ProbeType enum values."""
        from app.services.synthetic_probes import ProbeType

        assert ProbeType.HTTP.value == "http"
        assert ProbeType.DATABASE.value == "database"
        assert ProbeType.END_TO_END.value == "end_to_end"

    def test_probe_result_to_dict(self):
        """Test ProbeResult.to_dict()."""
        from app.services.synthetic_probes import ProbeResult, ProbeStatus

        now = datetime.now(UTC)
        result = ProbeResult(
            probe_id="test",
            status=ProbeStatus.SUCCESS,
            latency_ms=50.5,
            timestamp=now,
            message="OK",
        )

        d = result.to_dict()

        assert d["status"] == "success"
        assert d["latency_ms"] == 50.5

    def test_probe_definition_to_dict(self):
        """Test ProbeDefinition.to_dict()."""
        from app.services.synthetic_probes import (
            ProbeDefinition, ProbeType, ProbeSeverity
        )

        probe = ProbeDefinition(
            id="test",
            name="Test Probe",
            description="Test",
            probe_type=ProbeType.HTTP,
            severity=ProbeSeverity.HIGH,
            interval_seconds=30,
            timeout_seconds=5,
            endpoint="/health",
        )

        d = probe.to_dict()

        assert d["id"] == "test"
        assert d["probe_type"] == "http"

    @pytest.mark.asyncio
    async def test_list_probes(self):
        """Test listing probes."""
        from app.services.synthetic_probes import SyntheticProbesService

        mock_redis = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={})

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = SyntheticProbesService()
            probes = await service.list_probes()

        assert len(probes) > 0  # Should have defaults

    @pytest.mark.asyncio
    async def test_execute_cache_probe(self):
        """Test executing cache probe."""
        from app.services.synthetic_probes import SyntheticProbesService

        mock_redis = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={})
        mock_redis.hget = AsyncMock(return_value=None)
        mock_redis.ping = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=lambda key: key.split(":")[-1] if "probe:test" in key else None)
        mock_redis.zadd = AsyncMock()

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = SyntheticProbesService()
            result = await service.execute_probe("redis_connection")

        assert result.probe_id == "redis_connection"


# ============================================================================
# Chaos Drills Tests
# ============================================================================


class TestChaosDrillsService:
    """Tests for ChaosDrillsService."""

    def test_drill_type_enum_values(self):
        """Test DrillType enum values."""
        from app.services.chaos_drills import DrillType

        assert DrillType.LATENCY_INJECTION.value == "latency_injection"
        assert DrillType.ERROR_INJECTION.value == "error_injection"
        assert DrillType.WORKER_KILL.value == "worker_kill"

    def test_drill_status_enum_values(self):
        """Test DrillStatus enum values."""
        from app.services.chaos_drills import DrillStatus

        assert DrillStatus.PENDING.value == "pending"
        assert DrillStatus.RUNNING.value == "running"
        assert DrillStatus.COMPLETED.value == "completed"

    def test_drill_definition_to_dict(self):
        """Test DrillDefinition.to_dict()."""
        from app.services.chaos_drills import (
            DrillDefinition, DrillType, DrillSeverity
        )

        drill = DrillDefinition(
            id="test",
            name="Test Drill",
            description="Test",
            drill_type=DrillType.LATENCY_INJECTION,
            severity=DrillSeverity.LOW,
            target_service="redis",
            duration_seconds=60,
            parameters={"latency_ms": 50},
            rollback_steps=["Remove injection"],
            safe_for_production=True,
        )

        d = drill.to_dict()

        assert d["id"] == "test"
        assert d["safe_for_production"] is True

    def test_drill_execution_to_dict(self):
        """Test DrillExecution.to_dict()."""
        from app.services.chaos_drills import DrillExecution, DrillStatus

        now = datetime.now(UTC)
        execution = DrillExecution(
            id="exec-1",
            drill_id="test",
            drill_name="Test Drill",
            status=DrillStatus.COMPLETED,
            started_at=now - timedelta(minutes=5),
            ended_at=now,
            initiated_by="admin",
            approved_by="lead",
            environment="staging",
            observations=["Started", "Completed"],
            metrics_before={"error_rate": 0},
            metrics_during={"error_rate": 0.05},
            metrics_after={"error_rate": 0},
            success_criteria_met=True,
        )

        d = execution.to_dict()

        assert d["id"] == "exec-1"
        assert d["status"] == "completed"
        assert d["duration_seconds"] == 300

    def test_list_drills(self):
        """Test listing drills."""
        from app.services.chaos_drills import ChaosDrillsService

        service = ChaosDrillsService()
        drills = service.list_drills()

        assert len(drills) > 0

    def test_list_drills_production_safe(self):
        """Test listing production-safe drills."""
        from app.services.chaos_drills import ChaosDrillsService

        service = ChaosDrillsService()
        drills = service.list_drills(safe_for_production=True)

        assert all(d.safe_for_production for d in drills)

    def test_get_drill(self):
        """Test getting drill by ID."""
        from app.services.chaos_drills import ChaosDrillsService

        service = ChaosDrillsService()
        drill = service.get_drill("redis_latency_50ms")

        assert drill is not None
        assert drill.id == "redis_latency_50ms"

    def test_drill_report_to_dict(self):
        """Test DrillReport.to_dict()."""
        from app.services.chaos_drills import DrillReport

        now = datetime.now(UTC)
        report = DrillReport(
            execution_id="exec-1",
            drill_name="Test Drill",
            summary="Drill completed successfully",
            impact_assessment="LOW: System handled chaos gracefully",
            resilience_score=95,
            recommendations=["Consider more aggressive scenarios"],
            generated_at=now,
        )

        d = report.to_dict()

        assert d["resilience_score"] == 95
        assert len(d["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_start_drill_validation(self):
        """Test drill start validation."""
        from app.services.chaos_drills import ChaosDrillsService

        service = ChaosDrillsService()

        # Should fail for non-production-safe drill in production
        with pytest.raises(ValueError):
            await service.start_drill(
                drill_id="redis_latency_500ms",
                initiated_by="admin",
                environment="production",
            )
