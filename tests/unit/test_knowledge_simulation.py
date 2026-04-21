"""Tests for Knowledge and Simulation service."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone, timedelta
import json

from app.services.knowledge_simulation import (
    KnowledgeSimulationService,
    KnowledgeCategory,
    KnowledgeConfidence,
    PatternType,
    SimulationStatus,
    SimulationOutcome,
    ConflictSeverity,
    TrainingScenarioType,
    TrainingDifficulty,
    KnowledgeEntry,
    IncidentPattern,
    PatternMatch,
    SimulationScenario,
    SimulationResult,
    PolicyConflict,
    RecommendationQuality,
    TrainingScenario,
    TrainingSession,
    OperatorSkillProfile,
    DEFAULT_KNOWLEDGE,
    DEFAULT_PATTERNS,
    DEFAULT_TRAINING_SCENARIOS,
)

REDIS_PATCH = "app.storage.redis.get_redis"


# ============================================================================
# Knowledge Base Tests
# ============================================================================


@pytest.mark.asyncio
async def test_initialize_knowledge():
    """Test initializing default knowledge."""
    service = KnowledgeSimulationService()

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=None)
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        created = await service.initialize_knowledge()

    assert created == len(DEFAULT_KNOWLEDGE)


@pytest.mark.asyncio
async def test_add_knowledge():
    """Test adding knowledge entry."""
    service = KnowledgeSimulationService()

    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        entry = await service.add_knowledge(
            title="Test Entry",
            category=KnowledgeCategory.TROUBLESHOOTING,
            content="Test content",
            tags=["test", "example"],
            confidence=KnowledgeConfidence.TRUSTED,
            source="test",
            created_by="tester",
        )

    assert entry.title == "Test Entry"
    assert entry.category == KnowledgeCategory.TROUBLESHOOTING
    assert entry.confidence == KnowledgeConfidence.TRUSTED


@pytest.mark.asyncio
async def test_search_knowledge():
    """Test searching knowledge base."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    knowledge_data = {
        "kb-001": json.dumps({
            "id": "kb-001",
            "title": "API Troubleshooting Guide",
            "category": "troubleshooting",
            "content": "How to fix API errors",
            "tags": ["api", "errors"],
            "confidence": "verified",
            "source": "system",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "created_by": "system",
            "views": 10,
            "helpful_votes": 5,
        }),
    }

    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value=knowledge_data)

    with patch(REDIS_PATCH, return_value=mock_redis):
        results = await service.search_knowledge("API errors")

    assert len(results) == 1
    assert "API" in results[0].title


@pytest.mark.asyncio
async def test_get_knowledge():
    """Test getting knowledge entry."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    entry_data = {
        "id": "kb-001",
        "title": "Test",
        "category": "troubleshooting",
        "content": "Content",
        "tags": [],
        "confidence": "verified",
        "source": "system",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "created_by": "system",
        "views": 0,
        "helpful_votes": 0,
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(entry_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        entry = await service.get_knowledge("kb-001")

    assert entry is not None
    assert entry.views == 1  # Incremented


@pytest.mark.asyncio
async def test_vote_helpful():
    """Test voting on knowledge."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    entry_data = {
        "id": "kb-001",
        "title": "Test",
        "category": "troubleshooting",
        "content": "Content",
        "tags": [],
        "confidence": "verified",
        "source": "system",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "created_by": "system",
        "views": 0,
        "helpful_votes": 5,
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(entry_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        entry = await service.vote_helpful("kb-001", helpful=True)

    assert entry is not None
    assert entry.helpful_votes == 6


# ============================================================================
# Pattern Memory Tests
# ============================================================================


@pytest.mark.asyncio
async def test_initialize_patterns():
    """Test initializing default patterns."""
    service = KnowledgeSimulationService()

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=None)
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        created = await service.initialize_patterns()

    assert created == len(DEFAULT_PATTERNS)


@pytest.mark.asyncio
async def test_record_pattern():
    """Test recording a new pattern."""
    service = KnowledgeSimulationService()

    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        pattern = await service.record_pattern(
            pattern_type=PatternType.SYMPTOM,
            name="High CPU Usage",
            description="CPU consistently above 90%",
            indicators=["cpu_high", "throttling"],
        )

    assert pattern.name == "High CPU Usage"
    assert pattern.pattern_type == PatternType.SYMPTOM


@pytest.mark.asyncio
async def test_match_patterns():
    """Test matching incident against patterns."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    pattern_data = {
        "p-001": json.dumps({
            "id": "p-001",
            "pattern_type": "symptom",
            "name": "Memory Leak Pattern",
            "description": "Gradual memory increase",
            "indicators": ["memory", "oom"],
            "regex_patterns": ["Out of memory"],
            "severity_correlation": {},
            "category_correlation": {},
            "resolution_hints": ["Restart service"],
            "avg_resolution_minutes": 30,
            "occurrence_count": 5,
            "last_seen": now.isoformat(),
            "confidence": 0.8,
            "tags": [],
        }),
    }

    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value=pattern_data)

    with patch(REDIS_PATCH, return_value=mock_redis):
        matches = await service.match_patterns(
            incident_title="Service OOM killed",
            incident_description="Out of memory error after high traffic",
        )

    assert len(matches) >= 1
    assert matches[0].match_score > 0


@pytest.mark.asyncio
async def test_update_pattern_stats():
    """Test updating pattern statistics."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    pattern_data = {
        "id": "p-001",
        "pattern_type": "symptom",
        "name": "Test Pattern",
        "description": "Test",
        "indicators": [],
        "regex_patterns": [],
        "severity_correlation": {"p1": 0.5},
        "category_correlation": {"availability": 0.5},
        "resolution_hints": [],
        "avg_resolution_minutes": 30,
        "occurrence_count": 5,
        "last_seen": now.isoformat(),
        "confidence": 0.7,
        "tags": [],
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(pattern_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        pattern = await service.update_pattern_stats(
            pattern_id="p-001",
            resolution_minutes=20,
            severity="p0",
            category="availability",
        )

    assert pattern is not None
    assert pattern.occurrence_count == 6
    assert pattern.confidence > 0.7  # Should increase


# ============================================================================
# Simulation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_simulation():
    """Test creating a simulation scenario."""
    service = KnowledgeSimulationService()

    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        scenario = await service.create_simulation(
            name="Test Deploy Simulation",
            action_type="deploy",
            action_parameters={"version": "1.2.3"},
            pre_conditions={"error_rate": 1},
            created_by="tester",
        )

    assert scenario.name == "Test Deploy Simulation"
    assert scenario.action_type == "deploy"


@pytest.mark.asyncio
async def test_run_simulation_success():
    """Test running a simulation with success outcome."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    scenario_data = {
        "id": "sim-001",
        "name": "Deploy v1.2.3",
        "action_type": "deploy",
        "action_parameters": {"version": "1.2.3"},
        "pre_conditions": {"error_rate": 0.5},
        "created_by": "tester",
        "created_at": now.isoformat(),
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(scenario_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        result = await service.run_simulation("sim-001")

    assert result.status == SimulationStatus.COMPLETED
    assert result.outcome in [SimulationOutcome.SUCCESS, SimulationOutcome.PARTIAL_SUCCESS]
    assert len(result.predicted_impacts) >= 0


@pytest.mark.asyncio
async def test_run_simulation_not_found():
    """Test running simulation with missing scenario."""
    service = KnowledgeSimulationService()

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=None)

    with patch(REDIS_PATCH, return_value=mock_redis):
        with pytest.raises(ValueError, match="Scenario not found"):
            await service.run_simulation("missing")


@pytest.mark.asyncio
async def test_simulation_with_risks():
    """Test simulation identifies risks."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    scenario_data = {
        "id": "sim-002",
        "name": "Database Migration",
        "action_type": "database_migration",
        "action_parameters": {},
        "pre_conditions": {"peak_hours": True, "error_rate": 10},
        "created_by": "tester",
        "created_at": now.isoformat(),
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(scenario_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        result = await service.run_simulation("sim-002")

    assert len(result.risk_factors) > 0
    assert len(result.mitigation_suggestions) > 0


# ============================================================================
# Policy Conflict Tests
# ============================================================================


@pytest.mark.asyncio
async def test_detect_policy_conflicts():
    """Test detecting policy conflicts."""
    service = KnowledgeSimulationService()

    policies = [
        {
            "id": "pol-001",
            "name": "Allow Deploys",
            "action": "allow",
            "rules": {"action": "deploy", "environment": "production"},
        },
        {
            "id": "pol-002",
            "name": "Deny Deploys Off-Hours",
            "action": "deny",
            "rules": {"action": "deploy", "environment": "production"},
        },
    ]

    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        conflicts = await service.detect_policy_conflicts(policies)

    assert len(conflicts) >= 1
    assert conflicts[0].conflict_type == "contradicting_actions"


@pytest.mark.asyncio
async def test_resolve_conflict():
    """Test resolving a policy conflict."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    conflict_data = {
        "id": "conf-001",
        "policy_a_id": "pol-001",
        "policy_a_name": "Policy A",
        "policy_b_id": "pol-002",
        "policy_b_name": "Policy B",
        "conflict_type": "contradicting_actions",
        "severity": "high",
        "description": "Test conflict",
        "resolution_options": ["Adjust priority"],
        "detected_at": now.isoformat(),
        "resolved": False,
        "resolution": None,
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(conflict_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        conflict = await service.resolve_conflict(
            "conf-001",
            "Adjusted policy priorities",
        )

    assert conflict is not None
    assert conflict.resolved is True
    assert conflict.resolution == "Adjusted policy priorities"


@pytest.mark.asyncio
async def test_list_conflicts():
    """Test listing conflicts."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    conflict_data = {
        "conf-001": json.dumps({
            "id": "conf-001",
            "policy_a_id": "pol-001",
            "policy_a_name": "A",
            "policy_b_id": "pol-002",
            "policy_b_name": "B",
            "conflict_type": "contradicting",
            "severity": "high",
            "description": "Test",
            "resolution_options": [],
            "detected_at": now.isoformat(),
            "resolved": False,
        }),
    }

    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value=conflict_data)

    with patch(REDIS_PATCH, return_value=mock_redis):
        conflicts = await service.list_conflicts()

    assert len(conflicts) == 1
    assert conflicts[0].severity == ConflictSeverity.HIGH


# ============================================================================
# Recommendation Quality Tests
# ============================================================================


@pytest.mark.asyncio
async def test_score_recommendation():
    """Test scoring a recommendation."""
    service = KnowledgeSimulationService()

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=None)
    mock_redis.hset = AsyncMock()

    actual = {
        "outcome": "success",
        "duration_minutes": 15,
        "severity": "p1",
        "recommendation_used": True,
        "response_time_minutes": 10,
        "missing_steps": 1,
    }

    predicted = {
        "outcome": "success",
        "estimated_duration": 12,
        "predicted_severity": "p1",
    }

    with patch(REDIS_PATCH, return_value=mock_redis):
        quality = await service.score_recommendation(
            recommendation_id="rec-001",
            recommendation_type="runbook",
            actual_outcome=actual,
            predicted_outcome=predicted,
        )

    assert quality.overall_score > 0
    assert quality.accuracy_score >= 0.66  # 2/3 matches


@pytest.mark.asyncio
async def test_submit_feedback():
    """Test submitting feedback."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    quality_data = {
        "recommendation_id": "rec-001",
        "recommendation_type": "runbook",
        "accuracy_score": 0.8,
        "relevance_score": 0.9,
        "timeliness_score": 0.7,
        "completeness_score": 0.8,
        "overall_score": 0.8,
        "feedback_count": 5,
        "positive_feedback": 4,
        "negative_feedback": 1,
        "improvement_suggestions": [],
        "scored_at": now.isoformat(),
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(quality_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        quality = await service.submit_feedback("rec-001", helpful=True)

    assert quality is not None
    assert quality.feedback_count == 6
    assert quality.positive_feedback == 5


# ============================================================================
# Training Mode Tests
# ============================================================================


@pytest.mark.asyncio
async def test_initialize_training():
    """Test initializing default training scenarios."""
    service = KnowledgeSimulationService()

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=None)
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        created = await service.initialize_training()

    assert created == len(DEFAULT_TRAINING_SCENARIOS)


@pytest.mark.asyncio
async def test_list_training_scenarios():
    """Test listing training scenarios."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    scenario_data = {
        "ts-001": json.dumps({
            "id": "ts-001",
            "name": "P0 Response",
            "scenario_type": "incident_response",
            "difficulty": "intermediate",
            "description": "Test",
            "objectives": ["Respond quickly"],
            "initial_state": {},
            "expected_actions": [],
            "hints": [],
            "time_limit_minutes": 15,
            "passing_score": 0.7,
            "created_at": now.isoformat(),
        }),
    }

    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value=scenario_data)

    with patch(REDIS_PATCH, return_value=mock_redis):
        scenarios = await service.list_training_scenarios()

    assert len(scenarios) == 1
    assert scenarios[0].scenario_type == TrainingScenarioType.INCIDENT_RESPONSE


@pytest.mark.asyncio
async def test_start_training_session():
    """Test starting a training session."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    scenario_data = json.dumps({
        "id": "ts-001",
        "name": "Test",
        "scenario_type": "incident_response",
        "difficulty": "beginner",
        "description": "Test",
        "objectives": [],
        "initial_state": {},
        "expected_actions": [],
        "hints": [],
        "time_limit_minutes": 10,
        "passing_score": 0.7,
        "created_at": now.isoformat(),
    })

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=scenario_data)
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        session = await service.start_training_session("ts-001", "operator1")

    assert session.scenario_id == "ts-001"
    assert session.operator_id == "operator1"
    assert session.score is None


@pytest.mark.asyncio
async def test_record_training_action():
    """Test recording action in session."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    session_data = {
        "id": "sess-001",
        "scenario_id": "ts-001",
        "operator_id": "operator1",
        "started_at": now.isoformat(),
        "completed_at": None,
        "actions_taken": [],
        "hints_used": 0,
        "score": None,
        "passed": None,
        "feedback": "",
        "time_spent_minutes": 0,
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(session_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        session = await service.record_training_action(
            "sess-001",
            {"action": "acknowledge_incident"},
        )

    assert len(session.actions_taken) == 1
    assert session.actions_taken[0]["action"] == "acknowledge_incident"


@pytest.mark.asyncio
async def test_use_hint():
    """Test using a hint."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    session_data = json.dumps({
        "id": "sess-001",
        "scenario_id": "ts-001",
        "operator_id": "operator1",
        "started_at": now.isoformat(),
        "completed_at": None,
        "actions_taken": [],
        "hints_used": 0,
        "score": None,
        "passed": None,
        "feedback": "",
        "time_spent_minutes": 0,
    })

    scenario_data = json.dumps({
        "id": "ts-001",
        "hints": ["Hint 1", "Hint 2"],
    })

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(side_effect=[session_data, scenario_data])
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        result = await service.use_hint("sess-001")

    assert result["hint"] == "Hint 1"
    assert result["hints_remaining"] == 1


@pytest.mark.asyncio
async def test_complete_training_session():
    """Test completing a training session."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    session_data = json.dumps({
        "id": "sess-001",
        "scenario_id": "ts-001",
        "operator_id": "operator1",
        "started_at": now.isoformat(),
        "completed_at": None,
        "actions_taken": [
            {"action": "acknowledge_incident"},
            {"action": "check_logs"},
        ],
        "hints_used": 1,
        "score": None,
        "passed": None,
        "feedback": "",
        "time_spent_minutes": 5,
    })

    scenario_data = json.dumps({
        "id": "ts-001",
        "name": "Test",
        "scenario_type": "incident_response",
        "expected_actions": [
            {"action": "acknowledge_incident", "points": 20},
            {"action": "check_logs", "points": 20},
            {"action": "execute_runbook", "points": 60},
        ],
        "passing_score": 0.3,
    })

    profile_data = None

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(side_effect=[session_data, scenario_data, profile_data])
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        session = await service.complete_training_session("sess-001")

    assert session.completed_at is not None
    assert session.score is not None
    # 40 points out of 100 = 0.4, minus 5% hint penalty = 0.35
    assert session.score == pytest.approx(0.35, abs=0.05)
    assert session.passed is True  # >= 0.3


@pytest.mark.asyncio
async def test_get_operator_profile():
    """Test getting operator profile."""
    service = KnowledgeSimulationService()

    now = datetime.now(timezone.utc)
    profile_data = json.dumps({
        "operator_id": "operator1",
        "scenarios_completed": 10,
        "scenarios_passed": 8,
        "total_training_minutes": 120,
        "skill_scores": {"incident_response": 0.85, "triage": 0.75},
        "certifications": ["L1 Certified"],
        "last_training": now.isoformat(),
        "strengths": ["incident_response"],
        "areas_for_improvement": [],
    })

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=profile_data)

    with patch(REDIS_PATCH, return_value=mock_redis):
        profile = await service.get_operator_profile("operator1")

    assert profile is not None
    assert profile.scenarios_completed == 10
    assert profile.scenarios_passed == 8
    assert "incident_response" in profile.skill_scores


# ============================================================================
# Data Class Tests
# ============================================================================


def test_knowledge_entry_to_dict():
    """Test KnowledgeEntry serialization."""
    now = datetime.now(timezone.utc)
    entry = KnowledgeEntry(
        id="kb-001",
        title="Test",
        category=KnowledgeCategory.TROUBLESHOOTING,
        content="Content",
        tags=["test"],
        confidence=KnowledgeConfidence.VERIFIED,
        source="system",
        created_at=now,
        updated_at=now,
        created_by="system",
    )

    data = entry.to_dict()
    assert data["category"] == "troubleshooting"
    assert data["confidence"] == "verified"


def test_incident_pattern_to_dict():
    """Test IncidentPattern serialization."""
    now = datetime.now(timezone.utc)
    pattern = IncidentPattern(
        id="p-001",
        pattern_type=PatternType.SYMPTOM,
        name="Test Pattern",
        description="Test",
        indicators=["test"],
        regex_patterns=[],
        severity_correlation={"p0": 0.5},
        category_correlation={"availability": 0.5},
        resolution_hints=["Fix it"],
        avg_resolution_minutes=30,
        occurrence_count=5,
        last_seen=now,
        confidence=0.8,
        tags=[],
    )

    data = pattern.to_dict()
    assert data["pattern_type"] == "symptom"
    assert data["confidence"] == 0.8


def test_simulation_result_to_dict():
    """Test SimulationResult serialization."""
    now = datetime.now(timezone.utc)
    result = SimulationResult(
        id="res-001",
        scenario_id="scen-001",
        status=SimulationStatus.COMPLETED,
        outcome=SimulationOutcome.SUCCESS,
        confidence=0.85,
        predicted_impacts=[],
        risk_factors=[],
        mitigation_suggestions=[],
        estimated_duration_minutes=5,
        estimated_rollback_time_minutes=3,
        side_effects=[],
        dependencies_affected=[],
        executed_at=now,
        completed_at=now,
    )

    data = result.to_dict()
    assert data["status"] == "completed"
    assert data["outcome"] == "success"


def test_training_session_to_dict():
    """Test TrainingSession serialization."""
    now = datetime.now(timezone.utc)
    session = TrainingSession(
        id="sess-001",
        scenario_id="ts-001",
        operator_id="operator1",
        started_at=now,
        completed_at=now,
        actions_taken=[{"action": "test"}],
        hints_used=1,
        score=0.8,
        passed=True,
        feedback="Good job",
        time_spent_minutes=10.5,
    )

    data = session.to_dict()
    assert data["score"] == 0.8
    assert data["passed"] is True


def test_operator_skill_profile_to_dict():
    """Test OperatorSkillProfile serialization."""
    now = datetime.now(timezone.utc)
    profile = OperatorSkillProfile(
        operator_id="operator1",
        scenarios_completed=5,
        scenarios_passed=4,
        total_training_minutes=60,
        skill_scores={"incident_response": 0.8},
        certifications=["L1"],
        last_training=now,
        strengths=["incident_response"],
        areas_for_improvement=[],
    )

    data = profile.to_dict()
    assert data["scenarios_completed"] == 5
    assert "incident_response" in data["skill_scores"]


# ============================================================================
# Default Data Tests
# ============================================================================


def test_default_knowledge_exists():
    """Test that default knowledge is defined."""
    assert len(DEFAULT_KNOWLEDGE) >= 5

    for kb in DEFAULT_KNOWLEDGE:
        assert "title" in kb
        assert "category" in kb
        assert "content" in kb


def test_default_patterns_exist():
    """Test that default patterns are defined."""
    assert len(DEFAULT_PATTERNS) >= 4

    for p in DEFAULT_PATTERNS:
        assert "name" in p
        assert "pattern_type" in p
        assert "indicators" in p


def test_default_training_scenarios_exist():
    """Test that default training scenarios are defined."""
    assert len(DEFAULT_TRAINING_SCENARIOS) >= 3

    for ts in DEFAULT_TRAINING_SCENARIOS:
        assert "name" in ts
        assert "scenario_type" in ts
        assert "difficulty" in ts
        assert "passing_score" in ts
