"""Tests for Governance and Trust Layer Service."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import json

from app.services.governance_trust import (
    GovernanceTrustService,
    TrustableType,
    TrustLevel,
    StalenessStatus,
    LifecycleState,
    ApprovalType,
    SandboxStatus,
    ExplainabilityLevel,
    TRUST_WEIGHTS,
    STALENESS_THRESHOLDS,
    VALID_TRANSITIONS,
)


UTC = timezone.utc


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.hget = AsyncMock(return_value=None)
    redis.hset = AsyncMock()
    redis.hgetall = AsyncMock(return_value={})
    redis.lpush = AsyncMock()
    redis.ltrim = AsyncMock()
    redis.lrange = AsyncMock(return_value=[])
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    return redis


@pytest.fixture
def governance_service():
    """Create governance trust service instance."""
    return GovernanceTrustService()


class TestTrustScoreCalculation:
    """Tests for unified trust score calculation."""

    @pytest.mark.asyncio
    async def test_calculate_trust_score_new_entity(self, governance_service, mock_redis):
        """Test trust score calculation for new entity."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            context = {
                "historical_success_rate": 0.8,
                "total_uses": 5,  # Low usage
                "recent_successes": 3,
                "recent_failures": 1,
                "last_updated": datetime.now(UTC).isoformat(),
                "validated": False,
                "source": "community",
                "peer_reviews": 0,
                "production_uses": 0,
            }

            score = await governance_service.calculate_trust_score(
                entity_id="test-123",
                entity_type=TrustableType.RUNBOOK,
                context=context,
            )

            assert score.entity_id == "test-123"
            assert score.entity_type == TrustableType.RUNBOOK
            assert 0 <= score.score <= 1
            assert score.level in TrustLevel
            assert len(score.components) == len(TRUST_WEIGHTS)
            assert score.trend == "stable"  # New entity
            assert len(score.warnings) > 0  # Should have warnings for new entity
            mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_calculate_trust_score_verified_entity(self, governance_service, mock_redis):
        """Test trust score calculation for verified entity."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            context = {
                "historical_success_rate": 0.95,
                "total_uses": 100,
                "recent_successes": 20,
                "recent_failures": 1,
                "last_updated": datetime.now(UTC).isoformat(),
                "validated": True,
                "validation_date": datetime.now(UTC).isoformat(),
                "source": "verified",
                "peer_reviews": 10,
                "positive_reviews": 9,
                "production_uses": 50,
                "production_incidents": 0,
            }

            score = await governance_service.calculate_trust_score(
                entity_id="trusted-entity",
                entity_type=TrustableType.PATTERN,
                context=context,
            )

            assert score.score >= 0.7  # Should be high trust
            assert score.level in [TrustLevel.HIGH, TrustLevel.VERIFIED]
            assert len(score.warnings) == 0  # No warnings for verified entity

    @pytest.mark.asyncio
    async def test_trust_level_classification(self, governance_service, mock_redis):
        """Test trust level classification based on score."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            # Test different score ranges
            test_cases = [
                (0.15, TrustLevel.UNTRUSTED),
                (0.35, TrustLevel.LOW),
                (0.55, TrustLevel.MEDIUM),
                (0.75, TrustLevel.HIGH),
                (0.95, TrustLevel.VERIFIED),
            ]

            for expected_range, expected_level in test_cases:
                # Create context that produces approximate score
                context = {
                    "historical_success_rate": expected_range,
                    "total_uses": 100,
                    "recent_successes": int(expected_range * 10),
                    "recent_failures": int((1 - expected_range) * 10),
                    "validated": expected_range > 0.5,
                    "source": "verified" if expected_range > 0.7 else "community",
                    "peer_reviews": 5 if expected_range > 0.5 else 0,
                    "positive_reviews": int(expected_range * 5),
                    "production_uses": 10 if expected_range > 0.5 else 0,
                }

                score = await governance_service.calculate_trust_score(
                    entity_id=f"test-{expected_level.value}",
                    entity_type=TrustableType.RECOMMENDATION,
                    context=context,
                )

                # Score should be in reasonable range
                assert 0 <= score.score <= 1

    @pytest.mark.asyncio
    async def test_get_low_trust_entities(self, governance_service, mock_redis):
        """Test retrieval of low trust entities."""
        mock_redis.hgetall.return_value = {
            "runbook:low-1": json.dumps({
                "entity_id": "low-1",
                "entity_type": "runbook",
                "score": 0.25,
                "level": "low",
                "components": {},
                "evidence": [],
                "last_evaluated": datetime.now(UTC).isoformat(),
                "evaluations_count": 1,
                "trend": "stable",
                "confidence": 0.5,
                "warnings": ["Low trust"],
                "recommendations": [],
            }),
            "runbook:high-1": json.dumps({
                "entity_id": "high-1",
                "entity_type": "runbook",
                "score": 0.85,
                "level": "high",
                "components": {},
                "evidence": [],
                "last_evaluated": datetime.now(UTC).isoformat(),
                "evaluations_count": 10,
                "trend": "stable",
                "confidence": 0.9,
                "warnings": [],
                "recommendations": [],
            }),
        }

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            entities = await governance_service.get_low_trust_entities(threshold=0.4)

            assert len(entities) == 1
            assert entities[0].entity_id == "low-1"
            assert entities[0].score == 0.25


class TestStalenessDetection:
    """Tests for stale knowledge detection."""

    @pytest.mark.asyncio
    async def test_detect_fresh_entity(self, governance_service, mock_redis):
        """Test detection of fresh entity."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            context = {
                "last_updated": datetime.now(UTC).isoformat(),
                "last_used": datetime.now(UTC).isoformat(),
                "last_validated": datetime.now(UTC).isoformat(),
                "usage_count_30d": 50,
            }

            report = await governance_service.detect_staleness(
                entity_id="fresh-entity",
                entity_type=TrustableType.KNOWLEDGE,
                entity_name="Fresh Knowledge",
                context=context,
            )

            assert report.status == StalenessStatus.FRESH
            assert report.age_days < 1
            assert report.staleness_score < 0.2
            assert not report.needs_review

    @pytest.mark.asyncio
    async def test_detect_stale_entity(self, governance_service, mock_redis):
        """Test detection of stale entity."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            old_date = (datetime.now(UTC) - timedelta(days=200)).isoformat()
            context = {
                "last_updated": old_date,
                "usage_count_30d": 2,
            }

            report = await governance_service.detect_staleness(
                entity_id="stale-entity",
                entity_type=TrustableType.KNOWLEDGE,
                entity_name="Stale Knowledge",
                context=context,
            )

            assert report.status == StalenessStatus.STALE
            assert report.age_days >= 180
            assert report.staleness_score > 0.8
            assert report.needs_review
            assert len(report.suggested_actions) > 0

    @pytest.mark.asyncio
    async def test_detect_expired_entity(self, governance_service, mock_redis):
        """Test detection of expired entity."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            past_expiry = (datetime.now(UTC) - timedelta(days=30)).isoformat()
            context = {
                "last_updated": (datetime.now(UTC) - timedelta(days=100)).isoformat(),
                "expiration_date": past_expiry,
                "usage_count_30d": 0,
            }

            report = await governance_service.detect_staleness(
                entity_id="expired-entity",
                entity_type=TrustableType.POLICY,
                entity_name="Expired Policy",
                context=context,
            )

            assert report.status == StalenessStatus.EXPIRED
            assert report.needs_review

    @pytest.mark.asyncio
    async def test_detect_deprecated_entity(self, governance_service, mock_redis):
        """Test detection of deprecated entity."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            context = {
                "last_updated": datetime.now(UTC).isoformat(),
                "deprecated": True,
                "usage_count_30d": 10,
            }

            report = await governance_service.detect_staleness(
                entity_id="deprecated-entity",
                entity_type=TrustableType.RUNBOOK,
                entity_name="Deprecated Runbook",
                context=context,
            )

            assert report.status == StalenessStatus.DEPRECATED
            assert report.needs_review
            assert any("archive" in action.lower() for action in report.suggested_actions)


class TestLifecycleManagement:
    """Tests for lifecycle and approval workflows."""

    @pytest.mark.asyncio
    async def test_create_lifecycle_entry(self, governance_service, mock_redis):
        """Test lifecycle entry creation."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            entry = await governance_service.create_lifecycle_entry(
                entity_id="new-rule",
                entity_type=TrustableType.RULE,
                entity_name="New Rule",
                created_by="admin",
                approval_type=ApprovalType.DUAL,
            )

            assert entry.entity_id == "new-rule"
            assert entry.state == LifecycleState.DRAFT
            assert entry.version == 1
            assert entry.approval_type == ApprovalType.DUAL
            assert len(entry.state_history) == 1
            mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_valid_state_transition(self, governance_service, mock_redis):
        """Test valid lifecycle state transition."""
        existing_entry = {
            "entity_id": "test-rule",
            "entity_type": "rule",
            "entity_name": "Test Rule",
            "state": "draft",
            "version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "created_by": "admin",
            "updated_at": datetime.now(UTC).isoformat(),
            "updated_by": "admin",
            "state_history": [{"state": "draft", "timestamp": datetime.now(UTC).isoformat(), "by": "admin", "reason": "Initial"}],
            "approval_type": "none",
            "approvers": [],
            "pending_approvers": [],
            "rejection_reason": None,
            "auto_approve_criteria": {},
            "metadata": {},
        }
        mock_redis.hget.return_value = json.dumps(existing_entry)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            entry = await governance_service.transition_state(
                entity_id="test-rule",
                entity_type=TrustableType.RULE,
                new_state=LifecycleState.PENDING_REVIEW,
                by="reviewer",
                reason="Ready for review",
            )

            assert entry is not None
            assert entry.state == LifecycleState.PENDING_REVIEW
            assert entry.version == 2
            assert len(entry.state_history) == 2

    @pytest.mark.asyncio
    async def test_invalid_state_transition(self, governance_service, mock_redis):
        """Test invalid lifecycle state transition."""
        existing_entry = {
            "entity_id": "test-rule",
            "entity_type": "rule",
            "entity_name": "Test Rule",
            "state": "draft",  # DRAFT cannot go directly to ACTIVE
            "version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "created_by": "admin",
            "updated_at": datetime.now(UTC).isoformat(),
            "updated_by": "admin",
            "state_history": [],
            "approval_type": "none",
            "approvers": [],
            "pending_approvers": [],
            "rejection_reason": None,
            "auto_approve_criteria": {},
            "metadata": {},
        }
        mock_redis.hget.return_value = json.dumps(existing_entry)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            entry = await governance_service.transition_state(
                entity_id="test-rule",
                entity_type=TrustableType.RULE,
                new_state=LifecycleState.ACTIVE,  # Invalid direct transition
                by="admin",
            )

            assert entry is None  # Should fail

    @pytest.mark.asyncio
    async def test_request_approval(self, governance_service, mock_redis):
        """Test approval request creation."""
        mock_redis.hget.return_value = json.dumps({
            "entity_id": "test-policy",
            "entity_type": "policy",
            "entity_name": "Test Policy",
            "state": "pending_review",
            "version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "created_by": "admin",
            "updated_at": datetime.now(UTC).isoformat(),
            "updated_by": "admin",
            "state_history": [],
            "approval_type": "dual",
            "approvers": [],
            "pending_approvers": [],
            "auto_approve_criteria": {},
            "metadata": {},
        })

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            request = await governance_service.request_approval(
                entity_id="test-policy",
                entity_type=TrustableType.POLICY,
                entity_name="Test Policy",
                requested_state=LifecycleState.APPROVED,
                requested_by="admin",
                urgency="high",
            )

            assert request.entity_id == "test-policy"
            assert request.status == "pending"
            assert request.approval_type == ApprovalType.DUAL
            assert request.urgency == "high"
            assert len(request.required_approvers) == 2  # Dual approval

    @pytest.mark.asyncio
    async def test_approve_request(self, governance_service, mock_redis):
        """Test approval of request."""
        pending_request = {
            "id": "req-123",
            "entity_id": "test-policy",
            "entity_type": "policy",
            "entity_name": "Test Policy",
            "requested_state": "approved",
            "requested_by": "admin",
            "requested_at": datetime.now(UTC).isoformat(),
            "approval_type": "single",
            "required_approvers": ["any_approver"],
            "current_approvals": [],
            "rejections": [],
            "status": "pending",
            "expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            "context": {},
            "urgency": "normal",
        }
        mock_redis.hget.return_value = json.dumps(pending_request)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            result = await governance_service.approve(
                entity_id="test-policy",
                entity_type=TrustableType.POLICY,
                approver="reviewer1",
                comment="Looks good",
            )

            assert result is not None
            assert result.status == "approved"
            assert len(result.current_approvals) == 1

    @pytest.mark.asyncio
    async def test_reject_request(self, governance_service, mock_redis):
        """Test rejection of request."""
        pending_request = {
            "id": "req-456",
            "entity_id": "risky-rule",
            "entity_type": "rule",
            "entity_name": "Risky Rule",
            "requested_state": "approved",
            "requested_by": "admin",
            "requested_at": datetime.now(UTC).isoformat(),
            "approval_type": "single",
            "required_approvers": ["any_approver"],
            "current_approvals": [],
            "rejections": [],
            "status": "pending",
            "expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            "context": {},
            "urgency": "normal",
        }
        mock_redis.hget.return_value = json.dumps(pending_request)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            result = await governance_service.reject(
                entity_id="risky-rule",
                entity_type=TrustableType.RULE,
                rejector="security-team",
                reason="Security concerns",
            )

            assert result is not None
            assert result.status == "rejected"
            assert len(result.rejections) == 1
            assert result.rejections[0]["reason"] == "Security concerns"


class TestSandboxTesting:
    """Tests for sandbox rule testing."""

    @pytest.mark.asyncio
    async def test_sandbox_test_passing(self, governance_service, mock_redis):
        """Test sandbox test that passes."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            rule_definition = {
                "type": "threshold",
                "threshold": 100,
                "action": "alert",
            }

            test_cases = [
                {"name": "below_threshold", "input": {"value": 50}, "expected": {"triggered": False}},
                {"name": "at_threshold", "input": {"value": 100}, "expected": {"triggered": True}},
            ]

            result = await governance_service.run_sandbox_test(
                entity_id="test-rule",
                entity_type=TrustableType.RULE,
                entity_name="Test Rule",
                rule_definition=rule_definition,
                test_cases=test_cases,
            )

            assert result.status == SandboxStatus.PASSED
            assert result.test_cases_run == 2
            assert result.test_cases_passed == 2
            assert result.test_cases_failed == 0
            assert result.recommendation == "promote"

    @pytest.mark.asyncio
    async def test_sandbox_test_failing(self, governance_service, mock_redis):
        """Test sandbox test that fails."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            rule_definition = {
                "type": "threshold",
                "threshold": 100,
                "action": "alert",
            }

            test_cases = [
                {"name": "wrong_expectation", "input": {"value": 50}, "expected": {"triggered": True}},  # Wrong!
            ]

            result = await governance_service.run_sandbox_test(
                entity_id="bad-rule",
                entity_type=TrustableType.RULE,
                entity_name="Bad Rule",
                rule_definition=rule_definition,
                test_cases=test_cases,
            )

            assert result.status == SandboxStatus.FAILED
            assert result.test_cases_failed > 0
            assert result.recommendation == "reject"

    @pytest.mark.asyncio
    async def test_sandbox_safety_violations(self, governance_service, mock_redis):
        """Test sandbox detection of safety violations."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            # Rule with dangerous pattern
            rule_definition = {
                "type": "cleanup",
                "command": "DROP TABLE users",  # Dangerous!
                "action": "execute",
            }

            result = await governance_service.run_sandbox_test(
                entity_id="dangerous-rule",
                entity_type=TrustableType.RULE,
                entity_name="Dangerous Rule",
                rule_definition=rule_definition,
            )

            assert result.status == SandboxStatus.FAILED
            assert len(result.safety_violations) > 0
            assert any("DROP" in v for v in result.safety_violations)
            assert result.recommendation == "reject"

    @pytest.mark.asyncio
    async def test_default_test_case_generation(self, governance_service, mock_redis):
        """Test automatic generation of default test cases."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            rule_definition = {
                "type": "threshold",
                "threshold": 50,
                "action": "alert",
            }

            result = await governance_service.run_sandbox_test(
                entity_id="auto-test-rule",
                entity_type=TrustableType.RULE,
                entity_name="Auto Test Rule",
                rule_definition=rule_definition,
                test_cases=None,  # Should generate defaults
            )

            # Should generate basic validity, boundary, and null tests
            assert result.test_cases_run >= 4


class TestExplainability:
    """Tests for recommendation explainability."""

    @pytest.mark.asyncio
    async def test_generate_standard_explanation(self, governance_service, mock_redis):
        """Test generation of standard explanation."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            context = {
                "historical_success_rate": 0.85,
                "pattern_match_score": 0.7,
                "incident_severity": "p1",
                "time_sensitive": True,
                "resources_available": 0.8,
                "incident_data": True,
                "historical_incidents": True,
                "metrics": True,
                "data_quality_score": 0.9,
                "model_confidence": 0.85,
            }

            explanation = await governance_service.generate_explanation(
                recommendation_id="rec-123",
                recommendation_type="runbook",
                recommendation_text="Execute runbook rb-restart-api",
                decision_context=context,
                level=ExplainabilityLevel.STANDARD,
            )

            assert explanation.recommendation_id == "rec-123"
            assert len(explanation.decision_factors) > 0
            assert len(explanation.data_sources) > 0
            assert len(explanation.confidence_breakdown) > 0
            assert explanation.summary != ""
            assert explanation.human_readable != ""

    @pytest.mark.asyncio
    async def test_generate_detailed_explanation(self, governance_service, mock_redis):
        """Test generation of detailed explanation."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            context = {
                "historical_success_rate": 0.75,
                "incident_severity": "p0",
                "limited_data": True,
                "novel_situation": True,
            }

            explanation = await governance_service.generate_explanation(
                recommendation_id="rec-456",
                recommendation_type="fix",
                recommendation_text="Apply hotfix v2.1.1",
                decision_context=context,
                level=ExplainabilityLevel.DETAILED,
            )

            assert len(explanation.assumptions) > 0
            assert len(explanation.limitations) > 0
            assert "Assumptions" in explanation.human_readable
            assert "Limitations" in explanation.human_readable

    @pytest.mark.asyncio
    async def test_alternatives_and_why_not(self, governance_service, mock_redis):
        """Test generation of alternatives and why-not explanations."""
        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            explanation = await governance_service.generate_explanation(
                recommendation_id="rec-789",
                recommendation_type="runbook",
                recommendation_text="Execute runbook",
                decision_context={"incident_severity": "p1"},
                level=ExplainabilityLevel.DETAILED,
            )

            assert len(explanation.alternatives_considered) > 0
            assert len(explanation.why_not_alternatives) > 0


class TestGovernanceDashboard:
    """Tests for governance dashboard."""

    @pytest.mark.asyncio
    async def test_get_governance_summary(self, governance_service, mock_redis):
        """Test governance summary retrieval."""
        # Mock data
        mock_redis.hgetall.side_effect = [
            # Trust scores
            {
                "runbook:1": json.dumps({"score": 0.3}),  # Low trust
                "runbook:2": json.dumps({"score": 0.8}),
            },
            # Staleness
            {
                "knowledge:1": json.dumps({"status": "stale"}),
            },
            # Approvals
            {
                "policy:1": json.dumps({"status": "pending"}),
                "policy:2": json.dumps({"status": "approved"}),
            },
            # Sandbox
            {
                "rule:1": json.dumps({"status": "failed"}),
            },
        ]

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            summary = await governance_service.get_governance_summary()

            assert summary["total_trust_scores"] == 2
            assert summary["low_trust_entities"] == 1
            assert summary["stale_entities"] == 1
            assert summary["pending_approvals"] == 1
            assert summary["sandbox_failures"] == 1
            assert "health_status" in summary


class TestValidTransitions:
    """Test lifecycle state transition validation."""

    def test_valid_transitions_defined(self):
        """Test that all states have defined transitions."""
        for state in LifecycleState:
            assert state in VALID_TRANSITIONS

    def test_draft_transitions(self):
        """Test DRAFT state transitions."""
        valid = VALID_TRANSITIONS[LifecycleState.DRAFT]
        assert LifecycleState.PENDING_REVIEW in valid
        assert LifecycleState.ARCHIVED in valid
        assert LifecycleState.ACTIVE not in valid

    def test_archived_no_transitions(self):
        """Test ARCHIVED state has no transitions."""
        valid = VALID_TRANSITIONS[LifecycleState.ARCHIVED]
        assert len(valid) == 0


class TestStalenessThresholds:
    """Test staleness threshold configuration."""

    def test_all_types_have_thresholds(self):
        """Test that all trustable types have staleness thresholds."""
        for t_type in TrustableType:
            assert t_type in STALENESS_THRESHOLDS

    def test_threshold_ordering(self):
        """Test that thresholds are in correct order (fresh < aging < stale)."""
        for thresholds in STALENESS_THRESHOLDS.values():
            assert thresholds["fresh"] < thresholds["aging"]
            assert thresholds["aging"] < thresholds["stale"]


class TestTrustWeights:
    """Test trust score weight configuration."""

    def test_weights_sum_to_one(self):
        """Test that trust weights sum to 1.0."""
        total = sum(TRUST_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_all_weights_positive(self):
        """Test that all weights are positive."""
        for weight in TRUST_WEIGHTS.values():
            assert weight > 0
