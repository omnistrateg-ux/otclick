"""Playbook Service.

Stage and segment-based action playbooks.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class PlaybookStage(str, Enum):
    """Playbook stages aligned with deal pipeline."""

    LEAD_FOUND = "lead_found"
    ENRICHMENT = "enrichment"
    SCORING = "scoring"
    OUTREACH = "outreach"
    REPLY_HANDLING = "reply_handling"
    HANDOFF = "handoff"
    MEETING = "meeting"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSING = "closing"


class Segment(str, Enum):
    """Lead/account segments."""

    ENTERPRISE = "enterprise"  # Large companies
    MID_MARKET = "mid_market"  # Medium companies
    SMB = "smb"  # Small businesses
    STARTUP = "startup"  # Early-stage startups
    GOVERNMENT = "government"  # Government/public sector


class ActionType(str, Enum):
    """Types of playbook actions."""

    EMAIL = "email"
    CALL = "call"
    LINKEDIN = "linkedin"
    MEETING = "meeting"
    PROPOSAL = "proposal"
    FOLLOWUP = "followup"
    ESCALATE = "escalate"
    WAIT = "wait"
    INTERNAL = "internal"


@dataclass
class PlaybookAction:
    """A single action in a playbook."""

    id: str
    action_type: ActionType
    name: str
    description: str
    delay_hours: int = 0  # Hours to wait before this action
    template_id: str | None = None
    required: bool = True
    conditions: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action_type": self.action_type.value,
            "name": self.name,
            "description": self.description,
            "delay_hours": self.delay_hours,
            "template_id": self.template_id,
            "required": self.required,
            "conditions": self.conditions,
            "metadata": self.metadata,
        }


@dataclass
class Playbook:
    """A complete playbook for a stage/segment."""

    id: str
    name: str
    stage: PlaybookStage
    segment: Segment | None
    description: str
    actions: list[PlaybookAction]
    is_active: bool = True
    priority: int = 0  # Higher = more important
    success_metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "stage": self.stage.value,
            "segment": self.segment.value if self.segment else None,
            "description": self.description,
            "actions": [a.to_dict() for a in self.actions],
            "is_active": self.is_active,
            "priority": self.priority,
            "success_metrics": self.success_metrics,
            "metadata": self.metadata,
        }


@dataclass
class PlaybookProgress:
    """Progress through a playbook."""

    playbook_id: str
    resource_type: str
    resource_id: str
    current_action_index: int
    started_at: datetime
    completed_actions: list[str]
    skipped_actions: list[str]
    status: str  # "in_progress", "completed", "abandoned"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "playbook_id": self.playbook_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "current_action_index": self.current_action_index,
            "started_at": self.started_at.isoformat(),
            "completed_actions": self.completed_actions,
            "skipped_actions": self.skipped_actions,
            "status": self.status,
            "metadata": self.metadata,
        }


# Default playbooks
DEFAULT_PLAYBOOKS: list[dict[str, Any]] = [
    # Outreach playbook for Enterprise
    {
        "id": "outreach-enterprise",
        "name": "Enterprise Outreach Sequence",
        "stage": PlaybookStage.OUTREACH,
        "segment": Segment.ENTERPRISE,
        "description": "Multi-touch outreach for enterprise accounts",
        "priority": 10,
        "actions": [
            {
                "id": "research",
                "action_type": ActionType.INTERNAL,
                "name": "Account Research",
                "description": "Research company and decision makers",
                "delay_hours": 0,
            },
            {
                "id": "email-1",
                "action_type": ActionType.EMAIL,
                "name": "Initial Outreach",
                "description": "Personalized introduction email",
                "delay_hours": 0,
                "template_id": "enterprise-intro",
            },
            {
                "id": "linkedin-connect",
                "action_type": ActionType.LINKEDIN,
                "name": "LinkedIn Connection",
                "description": "Send connection request",
                "delay_hours": 24,
            },
            {
                "id": "email-2",
                "action_type": ActionType.EMAIL,
                "name": "Value Proposition",
                "description": "Share case study or ROI data",
                "delay_hours": 72,
                "template_id": "enterprise-value",
            },
            {
                "id": "call-1",
                "action_type": ActionType.CALL,
                "name": "Discovery Call Attempt",
                "description": "Call to schedule meeting",
                "delay_hours": 48,
            },
            {
                "id": "email-3",
                "action_type": ActionType.EMAIL,
                "name": "Final Follow-up",
                "description": "Last touch before pause",
                "delay_hours": 72,
                "template_id": "enterprise-final",
            },
        ],
    },
    # Outreach playbook for SMB
    {
        "id": "outreach-smb",
        "name": "SMB Quick Outreach",
        "stage": PlaybookStage.OUTREACH,
        "segment": Segment.SMB,
        "description": "Fast-paced outreach for small businesses",
        "priority": 5,
        "actions": [
            {
                "id": "email-1",
                "action_type": ActionType.EMAIL,
                "name": "Quick Intro",
                "description": "Short, benefit-focused email",
                "delay_hours": 0,
                "template_id": "smb-intro",
            },
            {
                "id": "email-2",
                "action_type": ActionType.EMAIL,
                "name": "Follow-up",
                "description": "Quick follow-up with offer",
                "delay_hours": 48,
                "template_id": "smb-followup",
            },
            {
                "id": "email-3",
                "action_type": ActionType.EMAIL,
                "name": "Last Chance",
                "description": "Final email with urgency",
                "delay_hours": 72,
                "template_id": "smb-final",
            },
        ],
    },
    # Reply handling playbook
    {
        "id": "reply-positive",
        "name": "Positive Reply Handling",
        "stage": PlaybookStage.REPLY_HANDLING,
        "segment": None,  # All segments
        "description": "Handle positive/interested replies",
        "priority": 20,
        "actions": [
            {
                "id": "acknowledge",
                "action_type": ActionType.EMAIL,
                "name": "Acknowledge Interest",
                "description": "Thank and confirm next steps",
                "delay_hours": 0,
                "template_id": "reply-acknowledge",
            },
            {
                "id": "schedule",
                "action_type": ActionType.MEETING,
                "name": "Schedule Meeting",
                "description": "Send calendar invite",
                "delay_hours": 1,
            },
            {
                "id": "handoff",
                "action_type": ActionType.INTERNAL,
                "name": "Create Handoff",
                "description": "Hand off to sales manager",
                "delay_hours": 0,
            },
        ],
    },
    # Meeting prep playbook
    {
        "id": "meeting-prep",
        "name": "Meeting Preparation",
        "stage": PlaybookStage.MEETING,
        "segment": None,
        "description": "Pre-meeting preparation tasks",
        "priority": 15,
        "actions": [
            {
                "id": "reminder",
                "action_type": ActionType.EMAIL,
                "name": "Meeting Reminder",
                "description": "Send reminder 24h before",
                "delay_hours": 0,
                "template_id": "meeting-reminder",
            },
            {
                "id": "prep-notes",
                "action_type": ActionType.INTERNAL,
                "name": "Prepare Notes",
                "description": "Review account history and prepare talking points",
                "delay_hours": 0,
            },
            {
                "id": "confirm",
                "action_type": ActionType.EMAIL,
                "name": "Day-of Confirmation",
                "description": "Confirm meeting on the day",
                "delay_hours": 0,
                "template_id": "meeting-confirm",
            },
        ],
    },
    # Post-meeting playbook
    {
        "id": "post-meeting",
        "name": "Post-Meeting Follow-up",
        "stage": PlaybookStage.PROPOSAL,
        "segment": None,
        "description": "Actions after a successful meeting",
        "priority": 15,
        "actions": [
            {
                "id": "thank-you",
                "action_type": ActionType.EMAIL,
                "name": "Thank You Email",
                "description": "Send recap and next steps",
                "delay_hours": 2,
                "template_id": "meeting-thankyou",
            },
            {
                "id": "proposal",
                "action_type": ActionType.PROPOSAL,
                "name": "Send Proposal",
                "description": "Create and send proposal",
                "delay_hours": 24,
            },
            {
                "id": "followup",
                "action_type": ActionType.FOLLOWUP,
                "name": "Proposal Follow-up",
                "description": "Check if proposal was reviewed",
                "delay_hours": 72,
            },
        ],
    },
]


class PlaybookService:
    """Playbook management service.

    Features:
    - Playbook definition by stage and segment
    - Progress tracking
    - Action recommendations
    - Success metrics
    """

    def __init__(self) -> None:
        """Initialize service."""
        self._playbooks: dict[str, Playbook] = {}
        self._load_default_playbooks()

    def _load_default_playbooks(self) -> None:
        """Load default playbooks."""
        for pb_data in DEFAULT_PLAYBOOKS:
            actions = [
                PlaybookAction(
                    id=a["id"],
                    action_type=a["action_type"],
                    name=a["name"],
                    description=a["description"],
                    delay_hours=a.get("delay_hours", 0),
                    template_id=a.get("template_id"),
                    required=a.get("required", True),
                    conditions=a.get("conditions", {}),
                    metadata=a.get("metadata", {}),
                )
                for a in pb_data["actions"]
            ]

            playbook = Playbook(
                id=pb_data["id"],
                name=pb_data["name"],
                stage=pb_data["stage"],
                segment=pb_data["segment"],
                description=pb_data["description"],
                actions=actions,
                priority=pb_data.get("priority", 0),
            )
            self._playbooks[playbook.id] = playbook

    # ========================================================================
    # Playbook Management
    # ========================================================================

    async def get_playbook(self, playbook_id: str) -> Playbook | None:
        """Get playbook by ID.

        Args:
            playbook_id: Playbook ID

        Returns:
            Playbook or None
        """
        return self._playbooks.get(playbook_id)

    async def get_playbooks_for_stage(
        self,
        stage: PlaybookStage,
        segment: Segment | None = None,
    ) -> list[Playbook]:
        """Get playbooks for a stage.

        Args:
            stage: Pipeline stage
            segment: Optional segment filter

        Returns:
            Matching playbooks
        """
        playbooks = []

        for pb in self._playbooks.values():
            if pb.stage != stage or not pb.is_active:
                continue

            # Match segment or use universal (None segment)
            if segment is not None:
                if pb.segment is not None and pb.segment != segment:
                    continue

            playbooks.append(pb)

        # Sort by priority (higher first)
        playbooks.sort(key=lambda p: p.priority, reverse=True)
        return playbooks

    async def get_best_playbook(
        self,
        stage: PlaybookStage,
        segment: Segment | None = None,
    ) -> Playbook | None:
        """Get the best playbook for stage/segment.

        Args:
            stage: Pipeline stage
            segment: Account segment

        Returns:
            Best matching playbook or None
        """
        playbooks = await self.get_playbooks_for_stage(stage, segment)
        return playbooks[0] if playbooks else None

    async def list_playbooks(
        self,
        stage: PlaybookStage | None = None,
        active_only: bool = True,
    ) -> list[Playbook]:
        """List all playbooks.

        Args:
            stage: Optional stage filter
            active_only: Only return active playbooks

        Returns:
            List of playbooks
        """
        playbooks = []

        for pb in self._playbooks.values():
            if active_only and not pb.is_active:
                continue
            if stage and pb.stage != stage:
                continue
            playbooks.append(pb)

        return playbooks

    # ========================================================================
    # Progress Tracking
    # ========================================================================

    async def start_playbook(
        self,
        playbook_id: str,
        resource_type: str,
        resource_id: str,
    ) -> PlaybookProgress:
        """Start a playbook for a resource.

        Args:
            playbook_id: Playbook to start
            resource_type: Resource type (lead, deal, handoff)
            resource_id: Resource ID

        Returns:
            PlaybookProgress
        """
        from app.storage.redis import get_redis
        import json

        playbook = await self.get_playbook(playbook_id)
        if not playbook:
            raise ValueError(f"Playbook {playbook_id} not found")

        redis = await get_redis()
        now = datetime.now(UTC)

        progress = PlaybookProgress(
            playbook_id=playbook_id,
            resource_type=resource_type,
            resource_id=resource_id,
            current_action_index=0,
            started_at=now,
            completed_actions=[],
            skipped_actions=[],
            status="in_progress",
        )

        key = f"playbook:progress:{resource_type}:{resource_id}"
        await redis.set(key, json.dumps(progress.to_dict()), ex=86400 * 90)

        logger.info(
            f"[Playbook] Started | playbook={playbook_id} | "
            f"resource={resource_type}:{resource_id}"
        )

        return progress

    async def get_progress(
        self,
        resource_type: str,
        resource_id: str,
    ) -> PlaybookProgress | None:
        """Get playbook progress for a resource.

        Args:
            resource_type: Resource type
            resource_id: Resource ID

        Returns:
            PlaybookProgress or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        key = f"playbook:progress:{resource_type}:{resource_id}"
        data = await redis.get(key)

        if not data:
            return None

        d = json.loads(data)
        return PlaybookProgress(
            playbook_id=d["playbook_id"],
            resource_type=d["resource_type"],
            resource_id=d["resource_id"],
            current_action_index=d["current_action_index"],
            started_at=datetime.fromisoformat(d["started_at"]),
            completed_actions=d["completed_actions"],
            skipped_actions=d["skipped_actions"],
            status=d["status"],
            metadata=d.get("metadata", {}),
        )

    async def complete_action(
        self,
        resource_type: str,
        resource_id: str,
        action_id: str,
    ) -> PlaybookProgress | None:
        """Mark an action as completed.

        Args:
            resource_type: Resource type
            resource_id: Resource ID
            action_id: Action that was completed

        Returns:
            Updated progress or None
        """
        from app.storage.redis import get_redis
        import json

        progress = await self.get_progress(resource_type, resource_id)
        if not progress or progress.status != "in_progress":
            return None

        playbook = await self.get_playbook(progress.playbook_id)
        if not playbook:
            return None

        # Mark action as completed
        if action_id not in progress.completed_actions:
            progress.completed_actions.append(action_id)

        # Advance to next action
        if progress.current_action_index < len(playbook.actions) - 1:
            progress.current_action_index += 1
        else:
            progress.status = "completed"

        # Save
        redis = await get_redis()
        key = f"playbook:progress:{resource_type}:{resource_id}"
        await redis.set(key, json.dumps(progress.to_dict()), ex=86400 * 90)

        logger.info(
            f"[Playbook] Action completed | action={action_id} | "
            f"resource={resource_type}:{resource_id}"
        )

        return progress

    async def skip_action(
        self,
        resource_type: str,
        resource_id: str,
        action_id: str,
        reason: str | None = None,
    ) -> PlaybookProgress | None:
        """Skip an action.

        Args:
            resource_type: Resource type
            resource_id: Resource ID
            action_id: Action to skip
            reason: Why it was skipped

        Returns:
            Updated progress or None
        """
        from app.storage.redis import get_redis
        import json

        progress = await self.get_progress(resource_type, resource_id)
        if not progress or progress.status != "in_progress":
            return None

        playbook = await self.get_playbook(progress.playbook_id)
        if not playbook:
            return None

        # Mark action as skipped
        if action_id not in progress.skipped_actions:
            progress.skipped_actions.append(action_id)

        # Advance to next action
        if progress.current_action_index < len(playbook.actions) - 1:
            progress.current_action_index += 1
        else:
            progress.status = "completed"

        # Save
        redis = await get_redis()
        key = f"playbook:progress:{resource_type}:{resource_id}"
        await redis.set(key, json.dumps(progress.to_dict()), ex=86400 * 90)

        logger.info(
            f"[Playbook] Action skipped | action={action_id} | "
            f"reason={reason} | resource={resource_type}:{resource_id}"
        )

        return progress

    async def get_next_action(
        self,
        resource_type: str,
        resource_id: str,
    ) -> PlaybookAction | None:
        """Get the next action to take.

        Args:
            resource_type: Resource type
            resource_id: Resource ID

        Returns:
            Next PlaybookAction or None
        """
        progress = await self.get_progress(resource_type, resource_id)
        if not progress or progress.status != "in_progress":
            return None

        playbook = await self.get_playbook(progress.playbook_id)
        if not playbook:
            return None

        if progress.current_action_index >= len(playbook.actions):
            return None

        return playbook.actions[progress.current_action_index]

    async def abandon_playbook(
        self,
        resource_type: str,
        resource_id: str,
        reason: str | None = None,
    ) -> PlaybookProgress | None:
        """Abandon a playbook in progress.

        Args:
            resource_type: Resource type
            resource_id: Resource ID
            reason: Why it was abandoned

        Returns:
            Final progress state
        """
        from app.storage.redis import get_redis
        import json

        progress = await self.get_progress(resource_type, resource_id)
        if not progress:
            return None

        progress.status = "abandoned"
        if reason:
            progress.metadata["abandon_reason"] = reason

        redis = await get_redis()
        key = f"playbook:progress:{resource_type}:{resource_id}"
        await redis.set(key, json.dumps(progress.to_dict()), ex=86400 * 90)

        logger.info(
            f"[Playbook] Abandoned | playbook={progress.playbook_id} | "
            f"reason={reason} | resource={resource_type}:{resource_id}"
        )

        return progress


# Singleton
playbook_service = PlaybookService()
