"""Tests for Ops Assistant service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import json

from app.services.ops_assistant import (
    OpsAssistantService,
    TriageSeverity,
    TriageCategory,
    RemediationStatus,
    RunbookSafetyLevel,
    EscalationLevel,
    HandoffStatus,
    TriageResult,
    RemediationPlan,
    RemediationStep,
    SafeRunbook,
    RunbookExecution,
    EscalationRule,
    OperatorNote,
    ShiftHandoff,
    HistoricalFix,
    FixRecommendation,
    TRIAGE_PATTERNS,
    DEFAULT_RUNBOOKS,
    DEFAULT_ESCALATION_RULES,
)

REDIS_PATCH = "app.storage.redis.get_redis"


# ============================================================================
# Auto-Triage Tests
# ============================================================================


@pytest.mark.asyncio
async def test_auto_triage_p0_outage():
    """Test P0 severity for outage keywords."""
    service = OpsAssistantService()

    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value={})

    with patch(REDIS_PATCH, return_value=mock_redis):
        triage = await service.auto_triage(
            incident_id="inc-001",
            title="API service outage",
            description="Service is down and returning 503 errors",
        )

    assert triage.severity == TriageSeverity.P0
    assert triage.category == TriageCategory.AVAILABILITY
    assert triage.escalation_required is True
    assert triage.auto_triaged is True
    assert "api" in triage.affected_services


@pytest.mark.asyncio
async def test_auto_triage_p1_performance():
    """Test P1 severity for performance issues."""
    service = OpsAssistantService()

    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value={})

    with patch(REDIS_PATCH, return_value=mock_redis):
        triage = await service.auto_triage(
            incident_id="inc-002",
            title="Redis slow response",
            description="Redis cache latency increased to 500ms",
        )

    assert triage.severity == TriageSeverity.P1
    assert triage.category == TriageCategory.PERFORMANCE
    assert "redis" in triage.affected_services


@pytest.mark.asyncio
async def test_auto_triage_security():
    """Test P0 security incidents."""
    service = OpsAssistantService()

    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value={})

    with patch(REDIS_PATCH, return_value=mock_redis):
        triage = await service.auto_triage(
            incident_id="inc-003",
            title="Unauthorized access detected",
            description="Security breach in auth system",
        )

    assert triage.severity == TriageSeverity.P0
    assert triage.category == TriageCategory.SECURITY
    # P0 matches first in escalation rules, returns L3
    assert triage.escalation_level == EscalationLevel.L3
    assert triage.escalation_required is True


@pytest.mark.asyncio
async def test_auto_triage_operational():
    """Test operational issues."""
    service = OpsAssistantService()

    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value={})

    with patch(REDIS_PATCH, return_value=mock_redis):
        triage = await service.auto_triage(
            incident_id="inc-004",
            title="Celery queue backlog",
            description="Worker queue has 10k pending tasks",
        )

    assert triage.severity == TriageSeverity.P2
    assert triage.category == TriageCategory.OPERATIONAL
    assert "celery" in triage.affected_services


@pytest.mark.asyncio
async def test_get_triage():
    """Test retrieving triage result."""
    service = OpsAssistantService()

    triage_data = {
        "id": "t-001",
        "incident_id": "inc-001",
        "severity": "p0",
        "category": "availability",
        "confidence": 0.85,
        "summary": "Test",
        "impact_assessment": "High",
        "affected_services": ["api"],
        "affected_users_estimate": 1000,
        "suggested_assignee": "oncall-infra",
        "escalation_required": True,
        "escalation_level": "l3",
        "similar_incidents": [],
        "triaged_at": datetime.now(timezone.utc).isoformat(),
        "auto_triaged": True,
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(triage_data))

    with patch(REDIS_PATCH, return_value=mock_redis):
        triage = await service.get_triage("inc-001")

    assert triage is not None
    assert triage.severity == TriageSeverity.P0
    assert triage.incident_id == "inc-001"


# ============================================================================
# Remediation Plan Tests
# ============================================================================


@pytest.mark.asyncio
async def test_generate_remediation_plan_availability():
    """Test generating plan for availability issues."""
    service = OpsAssistantService()

    triage_data = {
        "id": "t-001",
        "incident_id": "inc-001",
        "severity": "p0",
        "category": "availability",
        "confidence": 0.85,
        "summary": "Test",
        "impact_assessment": "High",
        "affected_services": ["api"],
        "affected_users_estimate": 1000,
        "suggested_assignee": None,
        "escalation_required": True,
        "escalation_level": "l3",
        "similar_incidents": [],
        "triaged_at": datetime.now(timezone.utc).isoformat(),
        "auto_triaged": True,
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(triage_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        plan = await service.generate_remediation_plan("inc-001", "operator")

    assert plan is not None
    assert plan.incident_id == "inc-001"
    assert len(plan.steps) == 3  # Availability has 3 steps
    assert plan.status == RemediationStatus.READY


@pytest.mark.asyncio
async def test_generate_remediation_plan_performance():
    """Test generating plan for performance issues."""
    service = OpsAssistantService()

    triage_data = {
        "id": "t-002",
        "incident_id": "inc-002",
        "severity": "p1",
        "category": "performance",
        "confidence": 0.75,
        "summary": "Test",
        "impact_assessment": "Medium",
        "affected_services": ["redis"],
        "affected_users_estimate": 500,
        "suggested_assignee": None,
        "escalation_required": False,
        "escalation_level": None,
        "similar_incidents": [],
        "triaged_at": datetime.now(timezone.utc).isoformat(),
        "auto_triaged": True,
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(triage_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        plan = await service.generate_remediation_plan("inc-002")

    assert plan is not None
    assert len(plan.steps) == 3  # Performance has 3 steps
    assert any(s.runbook_id == "rb-clear-cache" for s in plan.steps)


@pytest.mark.asyncio
async def test_advance_plan():
    """Test advancing plan through steps."""
    service = OpsAssistantService()

    plan_data = {
        "id": "plan-001",
        "incident_id": "inc-001",
        "triage_id": "t-001",
        "title": "Test Plan",
        "status": "ready",
        "steps": [
            {
                "order": 1,
                "action": "Step 1",
                "description": "First",
                "runbook_id": None,
                "manual": True,
                "estimated_minutes": 5,
                "rollback_action": None,
                "verification": "Check",
            },
            {
                "order": 2,
                "action": "Step 2",
                "description": "Second",
                "runbook_id": None,
                "manual": True,
                "estimated_minutes": 5,
                "rollback_action": None,
                "verification": "Check",
            },
        ],
        "current_step": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "test",
        "started_at": None,
        "completed_at": None,
        "total_estimated_minutes": 10,
        "notes": "",
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(plan_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        plan = await service.advance_plan("plan-001", "operator")

    assert plan is not None
    assert plan.current_step == 1
    assert plan.status == RemediationStatus.IN_PROGRESS


# ============================================================================
# Runbook Tests
# ============================================================================


@pytest.mark.asyncio
async def test_initialize_runbooks():
    """Test initializing default runbooks."""
    service = OpsAssistantService()

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=None)  # No existing
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        created = await service.initialize_runbooks()

    assert created == len(DEFAULT_RUNBOOKS)


@pytest.mark.asyncio
async def test_list_runbooks():
    """Test listing runbooks."""
    service = OpsAssistantService()

    runbook_data = {
        "rb-restart-api": json.dumps({
            "id": "rb-restart-api",
            "name": "Restart API Service",
            "description": "Gracefully restart",
            "category": "availability",
            "safety_level": "caution",
            "commands": [],
            "pre_checks": [],
            "post_checks": [],
            "rollback_commands": [],
            "requires_approval": False,
            "approval_roles": [],
            "cooldown_minutes": 5,
        }),
    }

    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value=runbook_data)

    with patch(REDIS_PATCH, return_value=mock_redis):
        runbooks = await service.list_runbooks()

    assert len(runbooks) == 1
    assert runbooks[0].id == "rb-restart-api"


@pytest.mark.asyncio
async def test_execute_runbook_safe():
    """Test executing a safe runbook."""
    service = OpsAssistantService()

    runbook_data = {
        "id": "rb-scale-workers",
        "name": "Scale Celery Workers",
        "description": "Increase worker count",
        "category": "operational",
        "safety_level": "safe",
        "commands": [{"type": "action", "cmd": "scale_workers"}],
        "pre_checks": [],
        "post_checks": [],
        "rollback_commands": [],
        "requires_approval": False,
        "approval_roles": [],
        "cooldown_minutes": 5,
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(runbook_data))
    mock_redis.hset = AsyncMock()
    mock_redis.lpush = AsyncMock()
    mock_redis.ltrim = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        execution = await service.execute_runbook("rb-scale-workers", "operator")

    assert execution.status == "success"
    assert execution.runbook_id == "rb-scale-workers"
    assert execution.pre_check_passed is True


@pytest.mark.asyncio
async def test_execute_runbook_requires_approval():
    """Test runbook requiring approval."""
    service = OpsAssistantService()

    runbook_data = {
        "id": "rb-pause-processing",
        "name": "Pause Lead Processing",
        "description": "Pause all processing",
        "category": "operational",
        "safety_level": "dangerous",
        "commands": [],
        "pre_checks": [],
        "post_checks": [],
        "rollback_commands": [],
        "requires_approval": True,
        "approval_roles": ["admin"],
        "cooldown_minutes": 0,
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(runbook_data))

    with patch(REDIS_PATCH, return_value=mock_redis):
        with pytest.raises(ValueError, match="Approval required"):
            await service.execute_runbook("rb-pause-processing", "operator")


@pytest.mark.asyncio
async def test_execute_runbook_cooldown():
    """Test runbook cooldown enforcement."""
    service = OpsAssistantService()

    # Runbook executed recently
    runbook_data = {
        "id": "rb-restart-api",
        "name": "Restart API",
        "description": "Restart",
        "category": "availability",
        "safety_level": "caution",
        "commands": [],
        "pre_checks": [],
        "post_checks": [],
        "rollback_commands": [],
        "requires_approval": False,
        "approval_roles": [],
        "cooldown_minutes": 5,
        "last_executed": datetime.now(timezone.utc).isoformat(),
        "execution_count": 1,
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(runbook_data))

    with patch(REDIS_PATCH, return_value=mock_redis):
        with pytest.raises(ValueError, match="Cooldown active"):
            await service.execute_runbook("rb-restart-api", "operator")


# ============================================================================
# Escalation Rules Tests
# ============================================================================


@pytest.mark.asyncio
async def test_initialize_escalation_rules():
    """Test initializing escalation rules."""
    service = OpsAssistantService()

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=None)
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        created = await service.initialize_escalation_rules()

    assert created == len(DEFAULT_ESCALATION_RULES)


@pytest.mark.asyncio
async def test_list_escalation_rules():
    """Test listing escalation rules."""
    service = OpsAssistantService()

    rule_data = {
        "rule-001": json.dumps({
            "id": "rule-001",
            "name": "P0 Immediate",
            "condition": {"severity": "p0"},
            "escalation_level": "l3",
            "notify_channels": ["slack"],
            "auto_escalate_minutes": 0,
            "enabled": True,
        }),
    }

    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value=rule_data)

    with patch(REDIS_PATCH, return_value=mock_redis):
        rules = await service.list_escalation_rules()

    assert len(rules) == 1
    assert rules[0].escalation_level == EscalationLevel.L3


# ============================================================================
# Operator Notes Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_note():
    """Test creating operator note."""
    service = OpsAssistantService()

    mock_redis = AsyncMock()
    mock_redis.lpush = AsyncMock()
    mock_redis.ltrim = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        note = await service.create_note(
            author="operator1",
            content="Investigated slow queries",
            shift="night",
            incident_ids=["inc-001"],
            action_items=["Review indexes"],
            tags=["database"],
        )

    assert note.author == "operator1"
    assert note.shift == "night"
    assert "inc-001" in note.incident_ids


@pytest.mark.asyncio
async def test_get_recent_notes():
    """Test getting recent notes."""
    service = OpsAssistantService()

    now = datetime.now(timezone.utc)
    note_data = json.dumps({
        "id": "note-001",
        "author": "operator1",
        "created_at": now.isoformat(),
        "shift": "day",
        "content": "Test note",
        "incident_ids": [],
        "action_items": [],
        "tags": [],
    })

    mock_redis = AsyncMock()
    mock_redis.lrange = AsyncMock(return_value=[note_data])

    with patch(REDIS_PATCH, return_value=mock_redis):
        notes = await service.get_recent_notes(hours=24)

    assert len(notes) == 1
    assert notes[0].author == "operator1"


# ============================================================================
# Handoff Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_handoff():
    """Test creating shift handoff."""
    service = OpsAssistantService()

    now = datetime.now(timezone.utc)

    mock_redis = AsyncMock()
    mock_redis.lrange = AsyncMock(return_value=[])  # No notes
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        handoff = await service.create_handoff(
            from_operator="operator1",
            to_operator="operator2",
            shift_start=now,
            shift_end=now + timedelta(hours=8),
        )

    assert handoff.from_operator == "operator1"
    assert handoff.to_operator == "operator2"
    assert handoff.status == HandoffStatus.PENDING


@pytest.mark.asyncio
async def test_acknowledge_handoff():
    """Test acknowledging handoff."""
    service = OpsAssistantService()

    now = datetime.now(timezone.utc)
    handoff_data = {
        "id": "ho-001",
        "from_operator": "operator1",
        "to_operator": "operator2",
        "shift_start": now.isoformat(),
        "shift_end": (now + timedelta(hours=8)).isoformat(),
        "status": "pending",
        "notes": [],
        "active_incidents": [],
        "pending_actions": [],
        "acknowledged_at": None,
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(handoff_data))
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        handoff = await service.acknowledge_handoff("ho-001", "operator2")

    assert handoff is not None
    assert handoff.status == HandoffStatus.ACKNOWLEDGED
    assert handoff.acknowledged_at is not None


# ============================================================================
# Historical Fixes Tests
# ============================================================================


@pytest.mark.asyncio
async def test_record_fix():
    """Test recording a fix."""
    service = OpsAssistantService()

    triage_data = {
        "id": "t-001",
        "incident_id": "inc-001",
        "severity": "p1",
        "category": "performance",
        "confidence": 0.75,
        "summary": "Test",
        "impact_assessment": "Medium",
        "affected_services": [],
        "affected_users_estimate": 100,
        "suggested_assignee": None,
        "escalation_required": False,
        "escalation_level": None,
        "similar_incidents": [],
        "triaged_at": datetime.now(timezone.utc).isoformat(),
        "auto_triaged": True,
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(side_effect=[json.dumps(triage_data), None])
    mock_redis.hset = AsyncMock()

    with patch(REDIS_PATCH, return_value=mock_redis):
        fix = await service.record_fix(
            incident_id="inc-001",
            fix_description="Cleared stale cache entries",
            runbook_id="rb-clear-cache",
            resolution_minutes=15,
            tags=["cache", "performance"],
        )

    assert fix.category == TriageCategory.PERFORMANCE
    assert fix.times_used == 1
    assert "rb-clear-cache" == fix.runbook_id


@pytest.mark.asyncio
async def test_get_fix_recommendations():
    """Test getting fix recommendations."""
    service = OpsAssistantService()

    now = datetime.now(timezone.utc)

    triage_data = {
        "id": "t-001",
        "incident_id": "inc-001",
        "severity": "p1",
        "category": "performance",
        "confidence": 0.75,
        "summary": "Test",
        "impact_assessment": "Medium",
        "affected_services": [],
        "affected_users_estimate": 100,
        "suggested_assignee": None,
        "escalation_required": False,
        "escalation_level": None,
        "similar_incidents": [],
        "triaged_at": now.isoformat(),
        "auto_triaged": True,
    }

    fix_data = {
        "fix-001": json.dumps({
            "id": "fix-001",
            "incident_pattern": "performance:Cleared cache",
            "category": "performance",
            "fix_description": "Cleared cache entries",
            "runbook_id": "rb-clear-cache",
            "success_rate": 0.95,
            "avg_resolution_minutes": 10,
            "times_used": 5,
            "last_used": (now - timedelta(days=1)).isoformat(),
            "tags": ["cache"],
        }),
    }

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=json.dumps(triage_data))
    mock_redis.hgetall = AsyncMock(return_value=fix_data)

    with patch(REDIS_PATCH, return_value=mock_redis):
        recommendations = await service.get_fix_recommendations("inc-001")

    assert len(recommendations) >= 1
    assert recommendations[0].confidence > 0.3


@pytest.mark.asyncio
async def test_list_historical_fixes():
    """Test listing historical fixes."""
    service = OpsAssistantService()

    now = datetime.now(timezone.utc)
    fix_data = {
        "fix-001": json.dumps({
            "id": "fix-001",
            "incident_pattern": "performance:test",
            "category": "performance",
            "fix_description": "Test fix",
            "runbook_id": None,
            "success_rate": 0.9,
            "avg_resolution_minutes": 15,
            "times_used": 3,
            "last_used": now.isoformat(),
            "tags": [],
        }),
    }

    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value=fix_data)

    with patch(REDIS_PATCH, return_value=mock_redis):
        fixes = await service.list_historical_fixes()

    assert len(fixes) == 1
    assert fixes[0].times_used == 3


# ============================================================================
# Data Class Tests
# ============================================================================


def test_triage_result_to_dict():
    """Test TriageResult serialization."""
    now = datetime.now(timezone.utc)
    triage = TriageResult(
        id="t-001",
        incident_id="inc-001",
        severity=TriageSeverity.P0,
        category=TriageCategory.AVAILABILITY,
        confidence=0.85,
        summary="Test",
        impact_assessment="High",
        affected_services=["api"],
        affected_users_estimate=1000,
        suggested_assignee="oncall",
        escalation_required=True,
        escalation_level=EscalationLevel.L3,
        similar_incidents=["inc-000"],
        triaged_at=now,
        auto_triaged=True,
    )

    data = triage.to_dict()
    assert data["severity"] == "p0"
    assert data["category"] == "availability"
    assert data["escalation_level"] == "l3"


def test_remediation_step_to_dict():
    """Test RemediationStep serialization."""
    step = RemediationStep(
        order=1,
        action="Restart service",
        description="Graceful restart",
        runbook_id="rb-restart-api",
        manual=False,
        estimated_minutes=5,
        rollback_action="Rollback deployment",
        verification="Health check",
    )

    data = step.to_dict()
    assert data["order"] == 1
    assert data["runbook_id"] == "rb-restart-api"


def test_safe_runbook_to_dict():
    """Test SafeRunbook serialization."""
    runbook = SafeRunbook(
        id="rb-001",
        name="Test Runbook",
        description="Test",
        category=TriageCategory.AVAILABILITY,
        safety_level=RunbookSafetyLevel.CAUTION,
        commands=[{"type": "action", "cmd": "test"}],
        pre_checks=["Check health"],
        post_checks=["Verify recovery"],
        rollback_commands=[],
        requires_approval=False,
        approval_roles=[],
        cooldown_minutes=5,
    )

    data = runbook.to_dict()
    assert data["safety_level"] == "caution"
    assert data["category"] == "availability"


def test_operator_note_to_dict():
    """Test OperatorNote serialization."""
    now = datetime.now(timezone.utc)
    note = OperatorNote(
        id="note-001",
        author="operator1",
        created_at=now,
        shift="day",
        content="Test note",
        incident_ids=["inc-001"],
        action_items=["Review logs"],
        tags=["investigation"],
    )

    data = note.to_dict()
    assert data["author"] == "operator1"
    assert "inc-001" in data["incident_ids"]


def test_fix_recommendation_to_dict():
    """Test FixRecommendation serialization."""
    now = datetime.now(timezone.utc)
    fix = HistoricalFix(
        id="fix-001",
        incident_pattern="test",
        category=TriageCategory.PERFORMANCE,
        fix_description="Test fix",
        runbook_id=None,
        success_rate=0.95,
        avg_resolution_minutes=10,
        times_used=5,
        last_used=now,
        tags=[],
    )

    recommendation = FixRecommendation(
        historical_fix=fix,
        confidence=0.8,
        reasoning="Same category; High success rate",
        estimated_resolution_minutes=10,
    )

    data = recommendation.to_dict()
    assert data["confidence"] == 0.8
    assert "historical_fix" in data


# ============================================================================
# Triage Patterns Tests
# ============================================================================


def test_triage_patterns_exist():
    """Test that triage patterns are defined."""
    assert len(TRIAGE_PATTERNS) > 0

    # Verify all patterns have required fields
    for pattern in TRIAGE_PATTERNS:
        assert "keywords" in pattern
        assert "severity" in pattern
        assert "category" in pattern
        assert "impact" in pattern


def test_default_runbooks_exist():
    """Test that default runbooks are defined."""
    assert len(DEFAULT_RUNBOOKS) == 8

    # Verify all runbooks have required fields
    for rb in DEFAULT_RUNBOOKS:
        assert "id" in rb
        assert "name" in rb
        assert "safety_level" in rb
        assert "commands" in rb


def test_default_escalation_rules_exist():
    """Test that default escalation rules are defined."""
    assert len(DEFAULT_ESCALATION_RULES) == 5

    # Verify all rules have required fields
    for rule in DEFAULT_ESCALATION_RULES:
        assert "name" in rule
        assert "condition" in rule
        assert "escalation_level" in rule
