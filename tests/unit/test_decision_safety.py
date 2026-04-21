"""Tests for Decision Safety service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import json

from app.services.decision_safety import (
    DecisionSafetyService,
    ConfidenceLevel,
    AutoRemediationMode,
    RollbackUrgency,
    ReviewStatus,
    PolicyLearningType,
    ProdGuardLevel,
    ConfidenceScore,
    AutoRemediationDecision,
    RollbackSuggestion,
    PostIncidentReview,
    TimelineEntry,
    LearnedPolicy,
    ProdGuard,
    GuardViolation,
    DEFAULT_PROD_GUARDS,
    CONFIDENCE_FACTORS,
)

REDIS_PATCH = "app.storage.redis.get_redis"


# ============================================================================
# Confidence Scoring Tests
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_confidence_high():
    """Test high confidence calculation."""
    service = DecisionSafetyService()

    context = {
        "historical_success_rate": 0.95,
        "pattern_match_strength": 0.9,
        "incident_id": "inc-001",
        "category": "availability",
        "severity": "p0",
        "similar_incident_count": 15,
        "runbook_reliability": 0.9,
        "hours_since_last_success": 2,
        "environmental_stability": 0.95,
    }

    score = await service.calculate_confidence(
        recommendation_type="runbook",
        recommendation_id="rb-001",
        context=context,
    )

    assert score.level in [ConfidenceLevel.VERY_HIGH, ConfidenceLevel.HIGH]
    assert score.score >= 0.75
    assert score.auto_executable is True


@pytest.mark.asyncio
async def test_calculate_confidence_low():
    """Test low confidence calculation."""
    service = DecisionSafetyService()

    context = {
        "historical_success_rate": 0.2,
        "pattern_match_strength": 0.3,
        "similar_incident_count": 0,
        "runbook_reliability": 0.4,
        "hours_since_last_success": 500,
        "environmental_stability": 0.3,
    }

    score = await service.calculate_confidence(
        recommendation_type="runbook",
        recommendation_id="rb-001",
        context=context,
    )

    assert score.level in [ConfidenceLevel.LOW, ConfidenceLevel.VERY_LOW]
    assert score.score < 0.5
    assert score.requires_approval is True


@pytest.mark.asyncio
async def test_confidence_factors_sum():
    """Test that confidence factors sum to 1.0."""
    total = sum(CONFIDENCE_FACTORS.values())
    assert abs(total - 1.0) < 0.001


# ============================================================================
# Auto-Remediation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_evaluate_auto_remediation_safe_mode():
    """Test auto-remediation in safe mode."""
    service = DecisionSafetyService()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="safe_only")
    mock_redis.lpush = AsyncMock()
    mock_redis.ltrim = AsyncMock()

    context = {
        "runbook_safety_level": "safe",
        "historical_success_rate": 0.9,
        "pattern_match_strength": 0.85,
        "incident_id": "inc-001",
        "category": "operational",
        "severity": "p2",
        "runbook_reliability": 0.9,
        "current_error_rate": 1,
        "active_p0_incidents": 0,
        "recent_runbook_failures": 0,
    }

    with patch(REDIS_PATCH, return_value=mock_redis):
        decision = await service.evaluate_auto_remediation(
            incident_id="inc-001",
            runbook_id="rb-scale-workers",
            context=context,
        )

    assert decision.decision == "execute"
    assert decision.safety_checks_passed is True


@pytest.mark.asyncio
async def test_evaluate_auto_remediation_disabled():
    """Test auto-remediation when disabled."""
    service = DecisionSafetyService()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="disabled")
    mock_redis.lpush = AsyncMock()
    mock_redis.ltrim = AsyncMock()

    context = {
        "runbook_safety_level": "safe",
        "historical_success_rate": 0.9,
    }

    with patch(REDIS_PATCH, return_value=mock_redis):
        decision = await service.evaluate_auto_remediation(
            incident_id="inc-001",
            runbook_id="rb-001",
            context=context,
        )

    assert decision.decision == "reject"


@pytest.mark.asyncio
async def test_evaluate_auto_remediation_dangerous_runbook():
    """Test auto-remediation with dangerous runbook."""
    service = DecisionSafetyService()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="safe_only")
    mock_redis.lpush = AsyncMock()
    mock_redis.ltrim = AsyncMock()

    context = {
        "runbook_safety_level": "dangerous",
        "historical_success_rate": 0.9,
    }

    with patch(REDIS_PATCH, return_value=mock_redis):
        decision = await service.evaluate_auto_remediation(
            incident_id="inc-001",
            runbook_id="rb-failover-db",
            context=context,
        )

    assert decision.decision == "reject"


@pytest.mark.asyncio
async def test_set_remediation_mode():
    """Test setting remediation mode."""
    service = DecisionSafetyService()

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        result = await service.set_auto_remediation_mode(
            AutoRemediationMode.WITH_APPROVAL,
            "admin",
        )

    assert result["mode"] == "with_approval"


@pytest.mark.asyncio
async def test_get_remediation_mode():
    """Test getting remediation mode."""
    service = DecisionSafetyService()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="with_approval")

    with patch(REDIS_PATCH, return_value=mock_redis):
        mode = await service.get_auto_remediation_mode()

    assert mode == AutoRemediationMode.WITH_APPROVAL


# ============================================================================
# Rollback Suggestions Tests
# ============================================================================


@pytest.mark.asyncio
async def test_generate_rollback_suggestion_deploy():
    """Test rollback suggestion for deploy."""
    service = DecisionSafetyService()

    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()

    action_details = {
        "description": "Deploy v1.2.3",
        "previous_version": "v1.2.2",
        "current_error_rate": 15,
        "latency_increase_percent": 60,
    }

    with patch(REDIS_PATCH, return_value=mock_redis):
        suggestion = await service.generate_rollback_suggestion(
            action_id="deploy-001",
            action_type="deploy",
            action_details=action_details,
        )

    assert suggestion.urgency == RollbackUrgency.RECOMMENDED
    assert len(suggestion.rollback_steps) >= 2
    assert suggestion.data_loss_risk == "low"


@pytest.mark.asyncio
async def test_generate_rollback_suggestion_immediate():
    """Test immediate rollback urgency."""
    service = DecisionSafetyService()

    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()

    action_details = {
        "current_error_rate": 60,
        "latency_increase_percent": 300,
    }

    with patch(REDIS_PATCH, return_value=mock_redis):
        suggestion = await service.generate_rollback_suggestion(
            action_id="deploy-002",
            action_type="deploy",
            action_details=action_details,
        )

    assert suggestion.urgency == RollbackUrgency.IMMEDIATE


@pytest.mark.asyncio
async def test_rollback_suggestion_config_change():
    """Test rollback for config change."""
    service = DecisionSafetyService()

    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        suggestion = await service.generate_rollback_suggestion(
            action_id="config-001",
            action_type="config_change",
            action_details={},
        )

    assert suggestion.auto_rollback_available is True
    assert len(suggestion.rollback_steps) >= 1


# ============================================================================
# Post-Incident Review Tests
# ============================================================================


@pytest.mark.asyncio
async def test_generate_post_incident_review():
    """Test generating PIR."""
    service = DecisionSafetyService()

    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()

    now = datetime.now(timezone.utc)
    incident_data = {
        "id": "inc-001",
        "title": "API Outage",
        "severity": "p0",
        "affected_services": ["api", "web"],
        "created_at": (now - timedelta(hours=2)).isoformat(),
        "resolved_at": now.isoformat(),
    }

    triage_data = {
        "category": "availability",
        "affected_users_estimate": 5000,
    }

    with patch(REDIS_PATCH, return_value=mock_redis):
        with patch.object(service, "_get_incident_data", return_value=incident_data):
            with patch.object(service, "_get_triage_data", return_value=triage_data):
                with patch.object(service, "_build_incident_timeline", return_value=[]):
                    review = await service.generate_post_incident_review(
                        incident_id="inc-001",
                        created_by="oncall",
                    )

    assert review is not None
    assert review.status == ReviewStatus.DRAFT
    assert review.severity == "p0"
    assert len(review.root_causes) > 0
    assert len(review.action_items) > 0


@pytest.mark.asyncio
async def test_generate_review_no_incident():
    """Test PIR generation with missing incident."""
    service = DecisionSafetyService()

    mock_redis = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        with patch.object(service, "_get_incident_data", return_value=None):
            review = await service.generate_post_incident_review(
                incident_id="missing",
                created_by="oncall",
            )

    assert review is None


@pytest.mark.asyncio
async def test_list_reviews():
    """Test listing reviews."""
    service = DecisionSafetyService()

    now = datetime.now(timezone.utc)
    review_data = {
        "review-001": json.dumps({
            "id": "review-001",
            "incident_id": "inc-001",
            "title": "PIR: Test",
            "status": "draft",
            "severity": "p1",
            "duration_minutes": 60,
            "affected_services": ["api"],
            "affected_users_estimate": 100,
            "summary": "Test summary",
            "timeline": [],
            "root_causes": ["Test cause"],
            "contributing_factors": [],
            "what_went_well": [],
            "what_went_wrong": [],
            "action_items": [],
            "lessons_learned": [],
            "created_at": now.isoformat(),
            "created_by": "test",
            "reviewed_by": [],
        }),
    }

    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value=review_data)

    with patch(REDIS_PATCH, return_value=mock_redis):
        reviews = await service.list_reviews()

    assert len(reviews) == 1
    assert reviews[0].status == ReviewStatus.DRAFT


# ============================================================================
# Policy Learning Tests
# ============================================================================


@pytest.mark.asyncio
async def test_learn_policy_from_incident():
    """Test learning policies from incident."""
    service = DecisionSafetyService()

    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()

    incident_data = {
        "id": "inc-001",
        "title": "Test Incident",
        "severity": "p0",
    }

    triage_data = {
        "category": "availability",
    }

    with patch(REDIS_PATCH, return_value=mock_redis):
        with patch.object(service, "_get_incident_data", return_value=incident_data):
            with patch.object(service, "_get_triage_data", return_value=triage_data):
                policies = await service.learn_policy_from_incident("inc-001")

    assert len(policies) == 3  # prevention, detection, response
    assert any(p.policy_type == PolicyLearningType.PREVENTION for p in policies)
    assert any(p.policy_type == PolicyLearningType.DETECTION for p in policies)
    assert any(p.policy_type == PolicyLearningType.RESPONSE for p in policies)


@pytest.mark.asyncio
async def test_approve_learned_policy():
    """Test approving a learned policy."""
    service = DecisionSafetyService()

    now = datetime.now(timezone.utc)
    policy_data = {
        "id": "pol-001",
        "incident_id": "inc-001",
        "policy_type": "prevention",
        "name": "Test Policy",
        "description": "Test",
        "rule_template": {},
        "confidence": 0.8,
        "effectiveness_estimate": 0.75,
        "implementation_effort": "medium",
        "priority": "p1",
        "status": "suggested",
        "created_at": now.isoformat(),
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(policy_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        policy = await service.approve_learned_policy("pol-001", "admin")

    assert policy is not None
    assert policy.status == "approved"


# ============================================================================
# Production Guards Tests
# ============================================================================


@pytest.mark.asyncio
async def test_initialize_guards():
    """Test initializing default guards."""
    service = DecisionSafetyService()

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=None)
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        created = await service.initialize_guards()

    assert created == len(DEFAULT_PROD_GUARDS)


@pytest.mark.asyncio
async def test_check_guard_blocked():
    """Test guard blocking action."""
    service = DecisionSafetyService()

    guard_data = {
        "guard-001": json.dumps({
            "id": "guard-001",
            "name": "No Database Drops",
            "description": "Block DROP commands",
            "guard_level": "strict",
            "action_patterns": ["drop_table"],
            "conditions": {"environment": "production"},
            "enforcement": "block",
            "bypass_roles": ["dba_admin"],
            "bypass_requires_reason": True,
            "active": True,
            "violations_count": 0,
            "last_violation": None,
        }),
    }

    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value=guard_data)
    mock_redis.lpush = AsyncMock()
    mock_redis.ltrim = AsyncMock()
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        allowed, message, violation = await service.check_guard(
            action="drop_table",
            actor="developer",
            context={"environment": "production", "actor_roles": ["developer"]},
        )

    assert allowed is False
    assert "Blocked" in message
    assert violation is not None
    assert violation.enforcement_result == "blocked"


@pytest.mark.asyncio
async def test_check_guard_bypass():
    """Test guard bypass with reason."""
    service = DecisionSafetyService()

    guard_data = {
        "guard-001": json.dumps({
            "id": "guard-001",
            "name": "Test Guard",
            "description": "Test",
            "guard_level": "standard",
            "action_patterns": ["test_action"],
            "conditions": {},
            "enforcement": "block",
            "bypass_roles": ["admin"],
            "bypass_requires_reason": True,
            "active": True,
            "violations_count": 0,
            "last_violation": None,
        }),
    }

    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value=guard_data)
    mock_redis.lpush = AsyncMock()
    mock_redis.ltrim = AsyncMock()
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        allowed, message, violation = await service.check_guard(
            action="test_action",
            actor="admin_user",
            context={"actor_roles": ["admin"]},
            bypass_reason="Emergency maintenance",
        )

    assert allowed is True
    assert "bypassed" in message
    assert violation.bypass_used is True


@pytest.mark.asyncio
async def test_check_guard_warn():
    """Test guard warning."""
    service = DecisionSafetyService()

    guard_data = {
        "guard-001": json.dumps({
            "id": "guard-001",
            "name": "Off-Hours Warning",
            "description": "Warn about off-hours",
            "guard_level": "standard",
            "action_patterns": ["deploy"],
            "conditions": {},
            "enforcement": "warn",
            "bypass_roles": [],
            "bypass_requires_reason": False,
            "active": True,
            "violations_count": 0,
            "last_violation": None,
        }),
    }

    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value=guard_data)
    mock_redis.lpush = AsyncMock()
    mock_redis.ltrim = AsyncMock()
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        allowed, message, violation = await service.check_guard(
            action="deploy",
            actor="developer",
            context={},
        )

    assert allowed is True
    assert "Warning" in message
    assert violation.enforcement_result == "warned"


@pytest.mark.asyncio
async def test_check_guard_no_match():
    """Test no guard matches."""
    service = DecisionSafetyService()

    guard_data = {
        "guard-001": json.dumps({
            "id": "guard-001",
            "name": "Test Guard",
            "description": "Test",
            "guard_level": "standard",
            "action_patterns": ["specific_action"],
            "conditions": {},
            "enforcement": "block",
            "bypass_roles": [],
            "bypass_requires_reason": False,
            "active": True,
        }),
    }

    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value=guard_data)

    with patch(REDIS_PATCH, return_value=mock_redis):
        allowed, message, violation = await service.check_guard(
            action="different_action",
            actor="developer",
            context={},
        )

    assert allowed is True
    assert "No guards triggered" in message
    assert violation is None


@pytest.mark.asyncio
async def test_toggle_guard():
    """Test toggling guard."""
    service = DecisionSafetyService()

    guard_data = {
        "id": "guard-001",
        "name": "Test Guard",
        "description": "Test",
        "guard_level": "standard",
        "action_patterns": [],
        "conditions": {},
        "enforcement": "block",
        "bypass_roles": [],
        "bypass_requires_reason": False,
        "active": True,
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(guard_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        guard = await service.toggle_guard("guard-001", False, "admin")

    assert guard is not None
    assert guard.active is False


@pytest.mark.asyncio
async def test_get_violations():
    """Test getting violations."""
    service = DecisionSafetyService()

    now = datetime.now(timezone.utc)
    violation_data = json.dumps({
        "id": "viol-001",
        "guard_id": "guard-001",
        "guard_name": "Test Guard",
        "action_attempted": "drop_table",
        "actor": "developer",
        "enforcement_result": "blocked",
        "bypass_used": False,
        "bypass_reason": None,
        "context": {},
        "occurred_at": now.isoformat(),
    })

    mock_redis = AsyncMock()
    mock_redis.lrange = AsyncMock(return_value=[violation_data])

    with patch(REDIS_PATCH, return_value=mock_redis):
        violations = await service.get_violations()

    assert len(violations) == 1
    assert violations[0].enforcement_result == "blocked"


# ============================================================================
# Data Class Tests
# ============================================================================


def test_confidence_score_to_dict():
    """Test ConfidenceScore serialization."""
    score = ConfidenceScore(
        score=0.85,
        level=ConfidenceLevel.HIGH,
        factors={"test": 0.9},
        reasoning="High confidence",
        auto_executable=True,
        requires_approval=False,
        human_review_recommended=True,
    )

    data = score.to_dict()
    assert data["level"] == "high"
    assert data["score"] == 0.85


def test_rollback_suggestion_to_dict():
    """Test RollbackSuggestion serialization."""
    now = datetime.now(timezone.utc)
    suggestion = RollbackSuggestion(
        id="rb-001",
        action_id="act-001",
        action_description="Test",
        urgency=RollbackUrgency.IMMEDIATE,
        rollback_steps=[],
        estimated_rollback_time_minutes=10,
        data_loss_risk="low",
        service_impact="minimal",
        confidence=0.9,
        auto_rollback_available=True,
        created_at=now,
    )

    data = suggestion.to_dict()
    assert data["urgency"] == "immediate"


def test_prod_guard_to_dict():
    """Test ProdGuard serialization."""
    guard = ProdGuard(
        id="guard-001",
        name="Test Guard",
        description="Test",
        guard_level=ProdGuardLevel.STRICT,
        action_patterns=["drop"],
        conditions={"env": "prod"},
        enforcement="block",
        bypass_roles=["admin"],
        bypass_requires_reason=True,
        active=True,
    )

    data = guard.to_dict()
    assert data["guard_level"] == "strict"
    assert data["enforcement"] == "block"


def test_learned_policy_to_dict():
    """Test LearnedPolicy serialization."""
    now = datetime.now(timezone.utc)
    policy = LearnedPolicy(
        id="pol-001",
        incident_id="inc-001",
        policy_type=PolicyLearningType.PREVENTION,
        name="Test Policy",
        description="Test",
        rule_template={},
        confidence=0.8,
        effectiveness_estimate=0.75,
        implementation_effort="medium",
        priority="p1",
        status="suggested",
        created_at=now,
    )

    data = policy.to_dict()
    assert data["policy_type"] == "prevention"
    assert data["status"] == "suggested"


# ============================================================================
# Default Guards Tests
# ============================================================================


def test_default_guards_exist():
    """Test that default guards are defined."""
    assert len(DEFAULT_PROD_GUARDS) == 8

    for guard in DEFAULT_PROD_GUARDS:
        assert "name" in guard
        assert "guard_level" in guard
        assert "action_patterns" in guard
        assert "enforcement" in guard


def test_default_guards_have_required_fields():
    """Test default guards have all required fields."""
    required_fields = [
        "name", "description", "guard_level", "action_patterns",
        "conditions", "enforcement", "bypass_roles", "bypass_requires_reason"
    ]

    for guard in DEFAULT_PROD_GUARDS:
        for field in required_fields:
            assert field in guard, f"Guard {guard['name']} missing {field}"


# ============================================================================
# Safety Checks Tests
# ============================================================================


@pytest.mark.asyncio
async def test_safety_checks_high_error_rate():
    """Test safety check fails on high error rate."""
    service = DecisionSafetyService()

    context = {"current_error_rate": 60}
    passed = await service._run_safety_checks(context)

    assert passed is False


@pytest.mark.asyncio
async def test_safety_checks_many_p0_incidents():
    """Test safety check fails on many P0 incidents."""
    service = DecisionSafetyService()

    context = {"active_p0_incidents": 5}
    passed = await service._run_safety_checks(context)

    assert passed is False


@pytest.mark.asyncio
async def test_safety_checks_recent_failures():
    """Test safety check fails on recent failures."""
    service = DecisionSafetyService()

    context = {"recent_runbook_failures": 5}
    passed = await service._run_safety_checks(context)

    assert passed is False


@pytest.mark.asyncio
async def test_safety_checks_pass():
    """Test safety checks pass with good context."""
    service = DecisionSafetyService()

    context = {
        "current_error_rate": 1,
        "active_p0_incidents": 0,
        "recent_runbook_failures": 0,
    }
    passed = await service._run_safety_checks(context)

    assert passed is True
