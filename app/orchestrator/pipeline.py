"""Pipeline definitions for lead processing.

Определяет стадии обработки лидов и их последовательность.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.models.domain import EmployerLead
from app.models.enums import LeadStatus

logger = logging.getLogger(__name__)


class PipelineStageName(StrEnum):
    """Names of pipeline stages."""

    DISCOVERY = "discovery"
    ENRICHMENT = "enrichment"
    SCORING = "scoring"
    QUALIFICATION = "qualification"
    OUTREACH = "outreach"
    FOLLOWUP = "followup"
    ANALYSIS = "analysis"
    HANDOFF = "handoff"


@dataclass
class PipelineStage:
    """A stage in the lead processing pipeline.

    Each stage has conditions for entry and actions to perform.
    """

    name: PipelineStageName
    description: str

    # Required status to enter this stage
    required_statuses: list[LeadStatus]

    # Target status after stage completion
    success_status: LeadStatus
    failure_status: LeadStatus | None = None

    # Stage configuration
    max_retries: int = 3
    timeout_seconds: int = 300
    parallel: bool = False  # Can run in parallel with other stages

    # Actions
    actions: list[str] = field(default_factory=list)  # Celery task names

    def can_enter(self, lead: EmployerLead) -> bool:
        """Check if lead can enter this stage.

        Args:
            lead: Lead to check

        Returns:
            True if lead can enter
        """
        return lead.status in self.required_statuses


# Stage action type
StageAction = Callable[[EmployerLead, dict[str, Any]], Awaitable[dict[str, Any]]]


class Pipeline:
    """Pipeline for processing leads through stages.

    Manages the flow of leads through discovery, enrichment,
    scoring, outreach, and handoff stages.
    """

    def __init__(self) -> None:
        self._stages: dict[PipelineStageName, PipelineStage] = {}
        self._actions: dict[str, StageAction] = {}
        self._setup_default_stages()

    def _setup_default_stages(self) -> None:
        """Set up default pipeline stages."""
        # Discovery stage
        self._stages[PipelineStageName.DISCOVERY] = PipelineStage(
            name=PipelineStageName.DISCOVERY,
            description="Discover new leads from hh.ru",
            required_statuses=[],  # Entry point
            success_status=LeadStatus.LEAD_FOUND,
            actions=["workers.discovery_tasks.discover_employers"],
        )

        # Enrichment stage
        self._stages[PipelineStageName.ENRICHMENT] = PipelineStage(
            name=PipelineStageName.ENRICHMENT,
            description="Enrich lead with profile and contacts",
            required_statuses=[LeadStatus.LEAD_FOUND],
            success_status=LeadStatus.ENRICHED,
            actions=["workers.discovery_tasks.enrich_lead"],
        )

        # Scoring stage
        self._stages[PipelineStageName.SCORING] = PipelineStage(
            name=PipelineStageName.SCORING,
            description="Score and segment lead",
            required_statuses=[LeadStatus.ENRICHED],
            success_status=LeadStatus.SCORED,
            failure_status=LeadStatus.ARCHIVED,
            actions=["workers.discovery_tasks.score_lead"],
        )

        # Qualification stage
        self._stages[PipelineStageName.QUALIFICATION] = PipelineStage(
            name=PipelineStageName.QUALIFICATION,
            description="Qualify lead for outreach",
            required_statuses=[LeadStatus.SCORED],
            success_status=LeadStatus.EMAIL_READY,
            failure_status=LeadStatus.ARCHIVED,
            actions=["workers.discovery_tasks.qualify_lead"],
        )

        # Outreach stage
        self._stages[PipelineStageName.OUTREACH] = PipelineStage(
            name=PipelineStageName.OUTREACH,
            description="Start email outreach sequence",
            required_statuses=[LeadStatus.EMAIL_READY],
            success_status=LeadStatus.OUTREACH_SENT,
            actions=["workers.outreach_tasks.start_outreach"],
        )

        # Follow-up stage
        self._stages[PipelineStageName.FOLLOWUP] = PipelineStage(
            name=PipelineStageName.FOLLOWUP,
            description="Send follow-up emails",
            required_statuses=[LeadStatus.OUTREACH_SENT, LeadStatus.IN_SEQUENCE],
            success_status=LeadStatus.IN_SEQUENCE,
            actions=["workers.outreach_tasks.send_followup"],
        )

        # Analysis stage
        self._stages[PipelineStageName.ANALYSIS] = PipelineStage(
            name=PipelineStageName.ANALYSIS,
            description="Analyze replies",
            required_statuses=[LeadStatus.REPLY_RECEIVED],
            success_status=LeadStatus.INTEREST_DETECTED,
            failure_status=LeadStatus.REFUSED,
            actions=["workers.analysis_tasks.analyze_reply"],
        )

        # Handoff stage
        self._stages[PipelineStageName.HANDOFF] = PipelineStage(
            name=PipelineStageName.HANDOFF,
            description="Hand off to sales manager",
            required_statuses=[LeadStatus.INTEREST_DETECTED, LeadStatus.QUALIFIED],
            success_status=LeadStatus.HANDED_TO_MANAGER,
            actions=["workers.outreach_tasks.create_handoff"],
        )

    def get_stage(self, name: PipelineStageName) -> PipelineStage | None:
        """Get stage by name.

        Args:
            name: Stage name

        Returns:
            Stage if found
        """
        return self._stages.get(name)

    def get_next_stage(self, lead: EmployerLead) -> PipelineStage | None:
        """Get next stage for lead based on current status.

        Args:
            lead: Lead to check

        Returns:
            Next stage if available
        """
        # Map current status to next stage
        status_to_stage = {
            LeadStatus.LEAD_FOUND: PipelineStageName.ENRICHMENT,
            LeadStatus.ENRICHED: PipelineStageName.SCORING,
            LeadStatus.SCORED: PipelineStageName.QUALIFICATION,
            LeadStatus.EMAIL_READY: PipelineStageName.OUTREACH,
            LeadStatus.OUTREACH_SENT: PipelineStageName.FOLLOWUP,
            LeadStatus.IN_SEQUENCE: PipelineStageName.FOLLOWUP,
            LeadStatus.REPLY_RECEIVED: PipelineStageName.ANALYSIS,
            LeadStatus.INTEREST_DETECTED: PipelineStageName.HANDOFF,
            LeadStatus.QUALIFIED: PipelineStageName.HANDOFF,
        }

        next_stage_name = status_to_stage.get(lead.status)
        if next_stage_name:
            return self._stages.get(next_stage_name)
        return None

    def get_stages_for_status(
        self,
        status: LeadStatus,
    ) -> list[PipelineStage]:
        """Get stages that can process leads with given status.

        Args:
            status: Current lead status

        Returns:
            List of applicable stages
        """
        return [
            stage
            for stage in self._stages.values()
            if status in stage.required_statuses
        ]

    def register_action(
        self,
        name: str,
        action: StageAction,
    ) -> None:
        """Register a stage action.

        Args:
            name: Action name
            action: Action function
        """
        self._actions[name] = action
        logger.debug(f"Registered pipeline action: {name}")

    async def execute_stage(
        self,
        lead: EmployerLead,
        stage: PipelineStage,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a pipeline stage for a lead.

        Args:
            lead: Lead to process
            stage: Stage to execute
            context: Additional context

        Returns:
            Stage execution result
        """
        if not stage.can_enter(lead):
            raise ValueError(
                f"Lead {lead.id} cannot enter stage {stage.name}. "
                f"Current status: {lead.status}, required: {stage.required_statuses}"
            )

        logger.info(f"Executing stage {stage.name} for lead {lead.id}")

        results = []
        for action_name in stage.actions:
            action = self._actions.get(action_name)
            if action:
                result = await action(lead, context or {})
                results.append(result)
            else:
                logger.warning(f"Action {action_name} not registered")

        return {
            "stage": stage.name,
            "lead_id": lead.id,
            "success": True,
            "results": results,
        }

    def get_pipeline_status(self, lead: EmployerLead) -> dict[str, Any]:
        """Get pipeline status for a lead.

        Args:
            lead: Lead to check

        Returns:
            Pipeline status info
        """
        current_stages = self.get_stages_for_status(lead.status)
        next_stage = self.get_next_stage(lead)

        return {
            "lead_id": lead.id,
            "current_status": lead.status.value,
            "current_stages": [s.name for s in current_stages],
            "next_stage": next_stage.name if next_stage else None,
            "can_proceed": next_stage is not None,
        }


# Global pipeline instance
_pipeline: Pipeline | None = None


def get_pipeline() -> Pipeline:
    """Get the global pipeline instance.

    Returns:
        Pipeline instance
    """
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline()
    return _pipeline
