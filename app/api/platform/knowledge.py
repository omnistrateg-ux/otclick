"""Knowledge and simulation API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

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
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["knowledge"])


# Request models
class AddKnowledgeRequest(BaseModel):
    """Add knowledge entry request."""

    title: str
    category: str
    content: str
    tags: list[str]
    confidence: str
    source: str
    created_by: str
    metadata: dict[str, Any] | None = None


class SearchKnowledgeRequest(BaseModel):
    """Search knowledge request."""

    query: str
    category: str | None = None
    tags: list[str] | None = None
    limit: int = 10


class RecordPatternRequest(BaseModel):
    """Record incident pattern request."""

    pattern_type: str
    name: str
    description: str
    indicators: list[str]
    regex_patterns: list[str] | None = None
    resolution_hints: list[str] | None = None
    tags: list[str] | None = None


class MatchPatternsRequest(BaseModel):
    """Match patterns request."""

    incident_title: str
    incident_description: str
    limit: int = 5


class CreateSimulationRequest(BaseModel):
    """Create simulation request."""

    name: str
    action_type: str
    action_parameters: dict[str, Any]
    pre_conditions: dict[str, Any]
    created_by: str


class ScoreRecommendationRequest(BaseModel):
    """Score recommendation request."""

    recommendation_id: str
    recommendation_type: str
    actual_outcome: dict[str, Any]
    predicted_outcome: dict[str, Any]


class SubmitFeedbackRequest(BaseModel):
    """Submit feedback request."""

    helpful: bool
    feedback_text: str | None = None


class ResolveConflictRequest(BaseModel):
    """Resolve conflict request."""

    resolution: str


class StartTrainingRequest(BaseModel):
    """Start training session request."""

    scenario_id: str
    operator_id: str


class RecordTrainingActionRequest(BaseModel):
    """Record training action request."""

    action: dict[str, Any]


# Knowledge base endpoints
@router.post("/knowledge/initialize")
async def initialize_knowledge() -> dict[str, Any]:
    """Initialize default knowledge entries."""
    service = KnowledgeSimulationService()
    created = await service.initialize_knowledge()
    return {"created": created, "message": f"Created {created} knowledge entries"}


@router.post("/knowledge/entries")
async def add_knowledge(request: AddKnowledgeRequest) -> dict[str, Any]:
    """Add a knowledge entry."""
    service = KnowledgeSimulationService()

    try:
        category = KnowledgeCategory(request.category)
    except ValueError:
        valid = [c.value for c in KnowledgeCategory]
        raise HTTPException(400, f"Invalid category. Valid: {valid}")

    try:
        confidence = KnowledgeConfidence(request.confidence)
    except ValueError:
        valid = [c.value for c in KnowledgeConfidence]
        raise HTTPException(400, f"Invalid confidence. Valid: {valid}")

    entry = await service.add_knowledge(
        title=request.title,
        category=category,
        content=request.content,
        tags=request.tags,
        confidence=confidence,
        source=request.source,
        created_by=request.created_by,
        metadata=request.metadata,
    )
    return entry.to_dict()


@router.post("/knowledge/search")
async def search_knowledge(request: SearchKnowledgeRequest) -> list[dict[str, Any]]:
    """Search knowledge base."""
    service = KnowledgeSimulationService()

    category = None
    if request.category:
        try:
            category = KnowledgeCategory(request.category)
        except ValueError:
            valid = [c.value for c in KnowledgeCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    entries = await service.search_knowledge(
        query=request.query,
        category=category,
        tags=request.tags,
        limit=request.limit,
    )
    return [e.to_dict() for e in entries]


@router.get("/knowledge/entries/{entry_id}")
async def get_knowledge(entry_id: str) -> dict[str, Any]:
    """Get knowledge entry."""
    service = KnowledgeSimulationService()
    entry = await service.get_knowledge(entry_id)
    if not entry:
        raise HTTPException(404, "Knowledge entry not found")
    return entry.to_dict()


@router.post("/knowledge/entries/{entry_id}/vote")
async def vote_knowledge(
    entry_id: str,
    helpful: bool = Query(...),
) -> dict[str, Any]:
    """Vote on knowledge entry helpfulness."""
    service = KnowledgeSimulationService()
    entry = await service.vote_helpful(entry_id, helpful)
    if not entry:
        raise HTTPException(404, "Knowledge entry not found")
    return entry.to_dict()


# Pattern memory endpoints
@router.post("/patterns/initialize")
async def initialize_patterns() -> dict[str, Any]:
    """Initialize default incident patterns."""
    service = KnowledgeSimulationService()
    created = await service.initialize_patterns()
    return {"created": created, "message": f"Created {created} patterns"}


@router.post("/patterns")
async def record_pattern(request: RecordPatternRequest) -> dict[str, Any]:
    """Record a new incident pattern."""
    service = KnowledgeSimulationService()

    try:
        pattern_type = PatternType(request.pattern_type)
    except ValueError:
        valid = [t.value for t in PatternType]
        raise HTTPException(400, f"Invalid pattern_type. Valid: {valid}")

    pattern = await service.record_pattern(
        pattern_type=pattern_type,
        name=request.name,
        description=request.description,
        indicators=request.indicators,
        regex_patterns=request.regex_patterns,
        resolution_hints=request.resolution_hints,
        tags=request.tags,
    )
    return pattern.to_dict()


@router.post("/patterns/match")
async def match_patterns(request: MatchPatternsRequest) -> list[dict[str, Any]]:
    """Match incident against known patterns."""
    service = KnowledgeSimulationService()
    matches = await service.match_patterns(
        incident_title=request.incident_title,
        incident_description=request.incident_description,
        limit=request.limit,
    )
    return [m.to_dict() for m in matches]


# Simulation endpoints
@router.post("/simulation/scenarios")
async def create_simulation(request: CreateSimulationRequest) -> dict[str, Any]:
    """Create a what-if simulation scenario."""
    service = KnowledgeSimulationService()
    scenario = await service.create_simulation(
        name=request.name,
        action_type=request.action_type,
        action_parameters=request.action_parameters,
        pre_conditions=request.pre_conditions,
        created_by=request.created_by,
    )
    return scenario.to_dict()


@router.post("/simulation/scenarios/{scenario_id}/run")
async def run_simulation(scenario_id: str) -> dict[str, Any]:
    """Run a what-if simulation."""
    service = KnowledgeSimulationService()
    try:
        result = await service.run_simulation(scenario_id)
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(404, str(e))


# Conflict detection endpoints
@router.post("/conflicts/detect")
async def detect_conflicts() -> list[dict[str, Any]]:
    """Detect policy conflicts."""
    service = KnowledgeSimulationService()
    conflicts = await service.detect_policy_conflicts()
    return [c.to_dict() for c in conflicts]


@router.get("/conflicts")
async def list_conflicts(
    include_resolved: bool = Query(default=False),
) -> list[dict[str, Any]]:
    """List policy conflicts."""
    service = KnowledgeSimulationService()
    conflicts = await service.list_conflicts(include_resolved=include_resolved)
    return [c.to_dict() for c in conflicts]


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: str,
    request: ResolveConflictRequest,
) -> dict[str, Any]:
    """Resolve a policy conflict."""
    service = KnowledgeSimulationService()
    conflict = await service.resolve_conflict(conflict_id, request.resolution)
    if not conflict:
        raise HTTPException(404, "Conflict not found")
    return conflict.to_dict()


# Quality scoring endpoints
@router.post("/quality/score")
async def score_recommendation(request: ScoreRecommendationRequest) -> dict[str, Any]:
    """Score recommendation quality."""
    service = KnowledgeSimulationService()
    quality = await service.score_recommendation(
        recommendation_id=request.recommendation_id,
        recommendation_type=request.recommendation_type,
        actual_outcome=request.actual_outcome,
        predicted_outcome=request.predicted_outcome,
    )
    return quality.to_dict()


@router.post("/quality/{recommendation_id}/feedback")
async def submit_quality_feedback(
    recommendation_id: str,
    request: SubmitFeedbackRequest,
) -> dict[str, Any]:
    """Submit feedback on a recommendation."""
    service = KnowledgeSimulationService()
    quality = await service.submit_feedback(
        recommendation_id=recommendation_id,
        helpful=request.helpful,
        feedback_text=request.feedback_text,
    )
    if not quality:
        raise HTTPException(404, "Recommendation not found")
    return quality.to_dict()


# Training endpoints
@router.post("/training/initialize")
async def initialize_training() -> dict[str, Any]:
    """Initialize default training scenarios."""
    service = KnowledgeSimulationService()
    created = await service.initialize_training()
    return {"created": created, "message": f"Created {created} training scenarios"}


@router.get("/training/scenarios")
async def list_training_scenarios(
    scenario_type: str = Query(default=None),
    difficulty: str = Query(default=None),
) -> list[dict[str, Any]]:
    """List training scenarios."""
    service = KnowledgeSimulationService()

    stype = None
    if scenario_type:
        try:
            stype = TrainingScenarioType(scenario_type)
        except ValueError:
            valid = [t.value for t in TrainingScenarioType]
            raise HTTPException(400, f"Invalid scenario_type. Valid: {valid}")

    diff = None
    if difficulty:
        try:
            diff = TrainingDifficulty(difficulty)
        except ValueError:
            valid = [d.value for d in TrainingDifficulty]
            raise HTTPException(400, f"Invalid difficulty. Valid: {valid}")

    scenarios = await service.list_training_scenarios(scenario_type=stype, difficulty=diff)
    return [s.to_dict() for s in scenarios]


@router.post("/training/sessions")
async def start_training_session(request: StartTrainingRequest) -> dict[str, Any]:
    """Start a training session."""
    service = KnowledgeSimulationService()
    try:
        session = await service.start_training_session(
            scenario_id=request.scenario_id,
            operator_id=request.operator_id,
        )
        return session.to_dict()
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/training/sessions/{session_id}")
async def get_training_session(session_id: str) -> dict[str, Any]:
    """Get training session."""
    service = KnowledgeSimulationService()
    session = await service.get_training_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session.to_dict()


@router.post("/training/sessions/{session_id}/action")
async def record_training_action(
    session_id: str,
    request: RecordTrainingActionRequest,
) -> dict[str, Any]:
    """Record an action in training session."""
    service = KnowledgeSimulationService()
    try:
        session = await service.record_training_action(session_id, request.action)
        return session.to_dict()
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/training/sessions/{session_id}/hint")
async def use_training_hint(session_id: str) -> dict[str, Any]:
    """Use a hint in training session."""
    service = KnowledgeSimulationService()
    try:
        result = await service.use_hint(session_id)
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/training/sessions/{session_id}/complete")
async def complete_training_session(session_id: str) -> dict[str, Any]:
    """Complete and score a training session."""
    service = KnowledgeSimulationService()
    try:
        session = await service.complete_training_session(session_id)
        return session.to_dict()
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/training/profiles/{operator_id}")
async def get_operator_profile(operator_id: str) -> dict[str, Any]:
    """Get operator skill profile."""
    service = KnowledgeSimulationService()
    profile = await service.get_operator_profile(operator_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile.to_dict()


# Reference endpoints
@router.get("/reference/knowledge-categories")
async def list_knowledge_categories() -> list[str]:
    """List available knowledge categories."""
    return [c.value for c in KnowledgeCategory]


@router.get("/reference/knowledge-confidences")
async def list_knowledge_confidences() -> list[str]:
    """List available knowledge confidence levels."""
    return [c.value for c in KnowledgeConfidence]


@router.get("/reference/pattern-types")
async def list_pattern_types() -> list[str]:
    """List available pattern types."""
    return [t.value for t in PatternType]


@router.get("/reference/simulation-outcomes")
async def list_simulation_outcomes() -> list[str]:
    """List available simulation outcomes."""
    return [o.value for o in SimulationOutcome]


@router.get("/reference/conflict-severities")
async def list_conflict_severities() -> list[str]:
    """List available conflict severities."""
    return [s.value for s in ConflictSeverity]


@router.get("/reference/training-types")
async def list_training_types() -> list[str]:
    """List available training scenario types."""
    return [t.value for t in TrainingScenarioType]


@router.get("/reference/training-difficulties")
async def list_training_difficulties() -> list[str]:
    """List available training difficulties."""
    return [d.value for d in TrainingDifficulty]
