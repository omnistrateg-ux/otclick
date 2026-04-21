"""Playbook and Next Best Action API endpoints.

Playbook management and action recommendations.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.playbooks import (
    PlaybookService,
    PlaybookStage,
    Segment,
)
from app.services.next_best_action import (
    NextBestActionEngine,
    ActionCategory,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playbooks", tags=["playbooks"])


# ============================================================================
# Request/Response Models
# ============================================================================


class StartPlaybookRequest(BaseModel):
    """Start playbook request."""

    playbook_id: str
    resource_type: str
    resource_id: str


class CompleteActionRequest(BaseModel):
    """Complete action request."""

    resource_type: str
    resource_id: str
    action_id: str


class SkipActionRequest(BaseModel):
    """Skip action request."""

    resource_type: str
    resource_id: str
    action_id: str
    reason: str | None = None


class AbandonPlaybookRequest(BaseModel):
    """Abandon playbook request."""

    resource_type: str
    resource_id: str
    reason: str | None = None


# ============================================================================
# Playbook Endpoints
# ============================================================================


@router.get("/")
async def list_playbooks(
    stage: str = Query(default=None),
    active_only: bool = Query(default=True),
) -> list[dict[str, Any]]:
    """List all playbooks.

    Args:
        stage: Filter by stage
        active_only: Only active playbooks

    Returns:
        List of playbooks
    """
    service = PlaybookService()

    stage_enum = None
    if stage:
        try:
            stage_enum = PlaybookStage(stage)
        except ValueError:
            valid_stages = [s.value for s in PlaybookStage]
            raise HTTPException(400, f"Invalid stage. Valid: {valid_stages}")

    playbooks = await service.list_playbooks(stage=stage_enum, active_only=active_only)
    return [p.to_dict() for p in playbooks]


@router.get("/{playbook_id}")
async def get_playbook(
    playbook_id: str,
) -> dict[str, Any]:
    """Get playbook by ID.

    Args:
        playbook_id: Playbook ID

    Returns:
        Playbook details
    """
    service = PlaybookService()
    playbook = await service.get_playbook(playbook_id)

    if not playbook:
        raise HTTPException(404, f"Playbook {playbook_id} not found")

    return playbook.to_dict()


@router.get("/for-stage/{stage}")
async def get_playbooks_for_stage(
    stage: str,
    segment: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get playbooks for a stage.

    Args:
        stage: Pipeline stage
        segment: Optional segment filter

    Returns:
        List of matching playbooks
    """
    service = PlaybookService()

    try:
        stage_enum = PlaybookStage(stage)
    except ValueError:
        valid_stages = [s.value for s in PlaybookStage]
        raise HTTPException(400, f"Invalid stage. Valid: {valid_stages}")

    segment_enum = None
    if segment:
        try:
            segment_enum = Segment(segment)
        except ValueError:
            valid_segments = [s.value for s in Segment]
            raise HTTPException(400, f"Invalid segment. Valid: {valid_segments}")

    playbooks = await service.get_playbooks_for_stage(stage_enum, segment_enum)
    return [p.to_dict() for p in playbooks]


@router.get("/best/{stage}")
async def get_best_playbook(
    stage: str,
    segment: str = Query(default=None),
) -> dict[str, Any]:
    """Get best playbook for stage/segment.

    Args:
        stage: Pipeline stage
        segment: Account segment

    Returns:
        Best matching playbook
    """
    service = PlaybookService()

    try:
        stage_enum = PlaybookStage(stage)
    except ValueError:
        valid_stages = [s.value for s in PlaybookStage]
        raise HTTPException(400, f"Invalid stage. Valid: {valid_stages}")

    segment_enum = None
    if segment:
        try:
            segment_enum = Segment(segment)
        except ValueError:
            valid_segments = [s.value for s in Segment]
            raise HTTPException(400, f"Invalid segment. Valid: {valid_segments}")

    playbook = await service.get_best_playbook(stage_enum, segment_enum)

    if not playbook:
        raise HTTPException(404, f"No playbook found for stage {stage}")

    return playbook.to_dict()


# ============================================================================
# Progress Tracking Endpoints
# ============================================================================


@router.post("/start")
async def start_playbook(
    request: StartPlaybookRequest,
) -> dict[str, Any]:
    """Start a playbook for a resource.

    Args:
        request: Start request

    Returns:
        Playbook progress
    """
    service = PlaybookService()

    try:
        progress = await service.start_playbook(
            playbook_id=request.playbook_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    return progress.to_dict()


@router.get("/progress/{resource_type}/{resource_id}")
async def get_progress(
    resource_type: str,
    resource_id: str,
) -> dict[str, Any]:
    """Get playbook progress for a resource.

    Args:
        resource_type: Resource type
        resource_id: Resource ID

    Returns:
        Playbook progress
    """
    service = PlaybookService()
    progress = await service.get_progress(resource_type, resource_id)

    if not progress:
        raise HTTPException(404, f"No playbook in progress for {resource_type}/{resource_id}")

    return progress.to_dict()


@router.get("/progress/{resource_type}/{resource_id}/next-action")
async def get_next_action(
    resource_type: str,
    resource_id: str,
) -> dict[str, Any]:
    """Get next action in playbook.

    Args:
        resource_type: Resource type
        resource_id: Resource ID

    Returns:
        Next action
    """
    service = PlaybookService()
    action = await service.get_next_action(resource_type, resource_id)

    if not action:
        return {"message": "No pending actions", "action": None}

    return action.to_dict()


@router.post("/complete-action")
async def complete_action(
    request: CompleteActionRequest,
) -> dict[str, Any]:
    """Mark an action as completed.

    Args:
        request: Complete action request

    Returns:
        Updated progress
    """
    service = PlaybookService()

    progress = await service.complete_action(
        resource_type=request.resource_type,
        resource_id=request.resource_id,
        action_id=request.action_id,
    )

    if not progress:
        raise HTTPException(404, "Playbook progress not found or not active")

    return progress.to_dict()


@router.post("/skip-action")
async def skip_action(
    request: SkipActionRequest,
) -> dict[str, Any]:
    """Skip an action.

    Args:
        request: Skip action request

    Returns:
        Updated progress
    """
    service = PlaybookService()

    progress = await service.skip_action(
        resource_type=request.resource_type,
        resource_id=request.resource_id,
        action_id=request.action_id,
        reason=request.reason,
    )

    if not progress:
        raise HTTPException(404, "Playbook progress not found or not active")

    return progress.to_dict()


@router.post("/abandon")
async def abandon_playbook(
    request: AbandonPlaybookRequest,
) -> dict[str, Any]:
    """Abandon a playbook.

    Args:
        request: Abandon request

    Returns:
        Final progress state
    """
    service = PlaybookService()

    progress = await service.abandon_playbook(
        resource_type=request.resource_type,
        resource_id=request.resource_id,
        reason=request.reason,
    )

    if not progress:
        raise HTTPException(404, "Playbook progress not found")

    return progress.to_dict()


# ============================================================================
# Next Best Action Endpoints
# ============================================================================


@router.get("/recommendations/{user_id}")
async def get_recommendations(
    user_id: str,
    role: str = Query(default="sales_rep"),
    limit: int = Query(default=10, ge=1, le=50),
    categories: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get recommended actions for a user.

    Args:
        user_id: User to get recommendations for
        role: User's role
        limit: Max recommendations
        categories: Comma-separated category filter

    Returns:
        List of recommended actions
    """
    engine = NextBestActionEngine()

    cat_list = None
    if categories:
        cat_list = []
        for cat in categories.split(","):
            try:
                cat_list.append(ActionCategory(cat.strip()))
            except ValueError:
                valid_cats = [c.value for c in ActionCategory]
                raise HTTPException(400, f"Invalid category: {cat}. Valid: {valid_cats}")

    recommendations = await engine.get_recommendations(
        user_id=user_id,
        role=role,
        limit=limit,
        categories=cat_list,
    )

    return [r.to_dict() for r in recommendations]


@router.get("/recommendations/{user_id}/stats")
async def get_action_stats(
    user_id: str,
    days: int = Query(default=7, ge=1, le=30),
) -> dict[str, Any]:
    """Get action statistics for a user.

    Args:
        user_id: User ID
        days: Days to analyze

    Returns:
        Action statistics
    """
    engine = NextBestActionEngine()
    stats = await engine.get_action_stats(user_id, days)
    return stats


# ============================================================================
# Reference Data
# ============================================================================


@router.get("/stages")
async def get_stages() -> list[dict[str, str]]:
    """Get all playbook stages.

    Returns:
        List of stages
    """
    return [{"stage": s.value} for s in PlaybookStage]


@router.get("/segments")
async def get_segments() -> list[dict[str, str]]:
    """Get all segments.

    Returns:
        List of segments
    """
    return [{"segment": s.value} for s in Segment]


@router.get("/action-categories")
async def get_action_categories() -> list[dict[str, str]]:
    """Get all action categories.

    Returns:
        List of categories
    """
    return [{"category": c.value} for c in ActionCategory]
