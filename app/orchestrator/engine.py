"""Lead Orchestrator - manages lead lifecycle transitions.

Координирует переходы лидов между состояниями,
вызывает агентов и эмитит события.

Note: LeadStatus enum values:
- LEAD_FOUND (initial)
- ENRICHED
- SCORED
- EMAIL_READY
- OUTREACH_SENT
- IN_SEQUENCE
- REPLY_RECEIVED
- INTEREST_DETECTED
- QUALIFIED
- HANDED_TO_MANAGER
- ARCHIVED (disqualified/lost)
- REFUSED
- COOLDOWN
- OPTED_OUT
- BOUNCED
- DUPLICATE

IMPORTANT: All LeadStatus changes MUST go through this orchestrator.
Direct status assignments (lead.status = ...) are prohibited in workers.
"""

import logging
import uuid
from datetime import datetime, timezone

UTC = timezone.utc
from typing import Any

from app.core.state_machine import LeadStateMachine
from app.events.definitions import Event, EventType, create_event
from app.models.domain import EmployerLead
from app.models.enums import LeadStatus

logger = logging.getLogger(__name__)


def generate_pipeline_run_id() -> str:
    """Generate unique pipeline run ID for idempotency tracking.

    Returns:
        UUID string for pipeline run
    """
    return str(uuid.uuid4())


def _log_transition(
    lead_id: str,
    from_status: LeadStatus,
    to_status: LeadStatus,
    actor: str,
    reason: str | None,
    pipeline_run_id: str | None,
) -> None:
    """Log status transition with structured data.

    Args:
        lead_id: Lead ID
        from_status: Previous status
        to_status: New status
        actor: Who initiated
        reason: Reason for transition
        pipeline_run_id: Pipeline run ID
    """
    parts = [
        f"[ORCHESTRATOR] Transition",
        f"lead_id={lead_id}",
        f"from={from_status.value}",
        f"to={to_status.value}",
        f"actor={actor}",
    ]
    if reason:
        parts.append(f"reason={reason}")
    if pipeline_run_id:
        parts.append(f"run_id={pipeline_run_id}")

    logger.info(" | ".join(parts))


class LeadOrchestrator:
    """Orchestrates lead lifecycle transitions.

    Manages state transitions, triggers agents, and emits events.
    All transitions go through the state machine for validation.
    """

    def __init__(
        self,
        state_machine: LeadStateMachine | None = None,
    ) -> None:
        """Initialize orchestrator.

        Args:
            state_machine: State machine for validation (creates new if None)
        """
        self._state_machine = state_machine or LeadStateMachine()
        self._event_queue: list[Event] = []

    @property
    def state_machine(self) -> LeadStateMachine:
        """Get state machine instance."""
        return self._state_machine

    def can_transition(
        self,
        lead: EmployerLead,
        target_status: LeadStatus,
    ) -> bool:
        """Check if transition is valid.

        Args:
            lead: Lead to check
            target_status: Target status

        Returns:
            True if transition is valid
        """
        return self._state_machine.can_transition(lead.status, target_status)

    def get_valid_transitions(
        self,
        lead: EmployerLead,
    ) -> list[LeadStatus]:
        """Get all valid transitions from current state.

        Args:
            lead: Lead to check

        Returns:
            List of valid target statuses
        """
        return self._state_machine.get_valid_transitions(lead.status)

    def transition(
        self,
        lead: EmployerLead,
        target_status: LeadStatus,
        *,
        actor: str = "system",
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        pipeline_run_id: str | None = None,
    ) -> tuple[EmployerLead, Event]:
        """Transition lead to new status.

        This is the ONLY approved way to change lead status.
        Workers MUST NOT assign status directly.

        Args:
            lead: Lead to transition
            target_status: Target status
            actor: Who initiated the transition
            reason: Reason for transition
            metadata: Additional metadata
            pipeline_run_id: Pipeline run ID for idempotency tracking

        Returns:
            Tuple of (updated lead, event)

        Raises:
            ValueError: If transition is not valid
        """
        # Validate transition
        if not self.can_transition(lead, target_status):
            allowed = self.get_valid_transitions(lead)
            raise ValueError(
                f"Invalid transition from {lead.status} to {target_status}. "
                f"Allowed: {allowed}"
            )

        old_status = lead.status
        now = datetime.now(UTC)

        # Update lead
        lead.status = target_status
        lead.updated_at = now
        lead.status_changed_at = now

        # Update terminal state fields
        if target_status == LeadStatus.ARCHIVED:
            lead.archived_at = now
            lead.archived_reason = reason

        if target_status == LeadStatus.OPTED_OUT:
            lead.opted_out = True
            lead.opted_out_at = now

        # Create event
        event_type = self._get_event_type(target_status)
        event_data = {
            "old_status": old_status.value,
            "new_status": target_status.value,
            "reason": reason,
            **(metadata or {}),
        }
        if pipeline_run_id:
            event_data["pipeline_run_id"] = pipeline_run_id

        event = create_event(
            event_type,
            lead_id=str(lead.id),
            actor=actor,
            data=event_data,
        )

        _log_transition(
            lead_id=str(lead.id),
            from_status=old_status,
            to_status=target_status,
            actor=actor,
            reason=reason,
            pipeline_run_id=pipeline_run_id,
        )

        return lead, event

    def _get_event_type(self, status: LeadStatus) -> EventType:
        """Map lead status to event type.

        Args:
            status: Lead status

        Returns:
            Corresponding event type
        """
        mapping = {
            LeadStatus.LEAD_FOUND: EventType.LEAD_DISCOVERED,
            LeadStatus.ENRICHED: EventType.LEAD_ENRICHED,
            LeadStatus.SCORED: EventType.LEAD_SCORED,
            LeadStatus.EMAIL_READY: EventType.EMAIL_GENERATED,
            LeadStatus.QUALIFIED: EventType.LEAD_QUALIFIED,
            LeadStatus.ARCHIVED: EventType.LEAD_DISQUALIFIED,
            LeadStatus.OUTREACH_SENT: EventType.OUTREACH_STARTED,
            LeadStatus.IN_SEQUENCE: EventType.FOLLOWUP_SENT,
            LeadStatus.REPLY_RECEIVED: EventType.REPLY_RECEIVED,
            LeadStatus.INTEREST_DETECTED: EventType.QUALIFICATION_COMPLETED,
            LeadStatus.REFUSED: EventType.LEAD_DISQUALIFIED,
            LeadStatus.HANDED_TO_MANAGER: EventType.HANDOFF_CREATED,
            LeadStatus.CONVERTED: EventType.HANDOFF_COMPLETED,
            LeadStatus.OPTED_OUT: EventType.LEAD_DISQUALIFIED,
            LeadStatus.BOUNCED: EventType.EMAIL_BOUNCED,
        }
        return mapping.get(status, EventType.LEAD_DISCOVERED)

    def discover_lead(
        self,
        lead: EmployerLead,
        *,
        source: str = "hh.ru",
        actor: str = "discovery_agent",
    ) -> tuple[EmployerLead, Event]:
        """Process newly discovered lead.

        Args:
            lead: Discovered lead
            source: Discovery source
            actor: Who discovered

        Returns:
            Tuple of (lead, event)
        """
        if lead.status != LeadStatus.LEAD_FOUND:
            lead.status = LeadStatus.LEAD_FOUND

        event = create_event(
            EventType.LEAD_DISCOVERED,
            lead_id=str(lead.id),
            actor=actor,
            data={"source": source, "company_name": lead.company_name},
        )

        logger.info(f"Lead discovered: {lead.company_name} from {source}")
        return lead, event

    def enrich_lead(
        self,
        lead: EmployerLead,
        *,
        actor: str = "enrichment_agent",
        enrichment_data: dict[str, Any] | None = None,
        pipeline_run_id: str | None = None,
    ) -> tuple[EmployerLead, Event]:
        """Mark lead as enriched.

        Args:
            lead: Lead to mark
            actor: Who enriched
            enrichment_data: Enrichment details
            pipeline_run_id: Pipeline run ID for tracking

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.ENRICHED,
            actor=actor,
            reason="Enrichment completed",
            metadata={"enrichment": enrichment_data or {}},
            pipeline_run_id=pipeline_run_id,
        )

    def score_lead(
        self,
        lead: EmployerLead,
        score: float,
        *,
        actor: str = "scoring_agent",
        segment: str | None = None,
        pipeline_run_id: str | None = None,
    ) -> tuple[EmployerLead, Event]:
        """Score and potentially qualify lead.

        Note: Score is stored in a separate LeadScore record, not on EmployerLead.

        Args:
            lead: Lead to score
            score: Calculated score
            actor: Who scored
            segment: Determined segment
            pipeline_run_id: Pipeline run ID for tracking

        Returns:
            Tuple of (lead, event)
        """
        # Determine target status based on score
        if score >= 50:  # Qualified threshold
            target = LeadStatus.SCORED
            reason = f"Score {score} >= 50, ready for email"
        else:
            target = LeadStatus.ARCHIVED
            reason = f"Score {score} < 50, archived"

        return self.transition(
            lead,
            target,
            actor=actor,
            reason=reason,
            metadata={"score": score, "segment": segment},
            pipeline_run_id=pipeline_run_id,
        )

    def start_outreach(
        self,
        lead: EmployerLead,
        *,
        campaign_id: str | None = None,
        actor: str = "outreach_agent",
        pipeline_run_id: str | None = None,
    ) -> tuple[EmployerLead, Event]:
        """Start outreach to lead.

        Args:
            lead: Lead to contact
            campaign_id: Campaign ID
            actor: Who started
            pipeline_run_id: Pipeline run ID for tracking

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.OUTREACH_SENT,
            actor=actor,
            reason="Outreach sequence started",
            metadata={"campaign_id": campaign_id},
            pipeline_run_id=pipeline_run_id,
        )

    def record_reply(
        self,
        lead: EmployerLead,
        *,
        email_id: str,
        reply_text: str | None = None,
        actor: str = "system",
        pipeline_run_id: str | None = None,
    ) -> tuple[EmployerLead, Event]:
        """Record that lead replied.

        Args:
            lead: Lead who replied
            email_id: Email that was replied to
            reply_text: Reply content
            actor: Who recorded
            pipeline_run_id: Pipeline run ID for tracking

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.REPLY_RECEIVED,
            actor=actor,
            reason="Lead replied to email",
            metadata={
                "email_id": email_id,
                "reply_preview": (reply_text[:100] + "...") if reply_text else None,
            },
            pipeline_run_id=pipeline_run_id,
        )

    def mark_interested(
        self,
        lead: EmployerLead,
        *,
        intent: str,
        confidence: float,
        actor: str = "qualification_agent",
        pipeline_run_id: str | None = None,
    ) -> tuple[EmployerLead, Event]:
        """Mark lead as interested.

        Args:
            lead: Interested lead
            intent: Detected intent
            confidence: Confidence score
            actor: Who qualified
            pipeline_run_id: Pipeline run ID for tracking

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.INTEREST_DETECTED,
            actor=actor,
            reason=f"Positive intent detected: {intent}",
            metadata={"intent": intent, "confidence": confidence},
            pipeline_run_id=pipeline_run_id,
        )

    def mark_not_interested(
        self,
        lead: EmployerLead,
        *,
        intent: str,
        confidence: float,
        actor: str = "qualification_agent",
        pipeline_run_id: str | None = None,
    ) -> tuple[EmployerLead, Event]:
        """Mark lead as not interested.

        Args:
            lead: Not interested lead
            intent: Detected intent
            confidence: Confidence score
            actor: Who qualified
            pipeline_run_id: Pipeline run ID for tracking

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.REFUSED,
            actor=actor,
            reason=f"Negative intent detected: {intent}",
            metadata={"intent": intent, "confidence": confidence},
            pipeline_run_id=pipeline_run_id,
        )

    def handoff_to_manager(
        self,
        lead: EmployerLead,
        *,
        manager_id: str,
        handoff_id: str,
        actor: str = "handoff_agent",
        pipeline_run_id: str | None = None,
    ) -> tuple[EmployerLead, Event]:
        """Hand off lead to sales manager.

        Args:
            lead: Lead to hand off
            manager_id: Assigned manager
            handoff_id: Handoff record ID
            actor: Who created handoff
            pipeline_run_id: Pipeline run ID for tracking

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.HANDED_TO_MANAGER,
            actor=actor,
            reason=f"Handed off to manager {manager_id}",
            metadata={"manager_id": manager_id, "handoff_id": handoff_id},
            pipeline_run_id=pipeline_run_id,
        )

    def mark_converted(
        self,
        lead: EmployerLead,
        *,
        deal_value: float | None = None,
        actor: str = "system",
        pipeline_run_id: str | None = None,
    ) -> tuple[EmployerLead, Event]:
        """Mark lead as converted.

        Transitions lead to CONVERTED status (terminal).

        Args:
            lead: Converted lead
            deal_value: Deal value
            actor: Who marked
            pipeline_run_id: Pipeline run ID

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.CONVERTED,
            actor=actor,
            reason=f"Deal closed, value: {deal_value}",
            metadata={"deal_value": deal_value},
            pipeline_run_id=pipeline_run_id,
        )

    def mark_lost(
        self,
        lead: EmployerLead,
        *,
        reason: str,
        actor: str = "system",
    ) -> tuple[EmployerLead, Event]:
        """Mark lead as lost (archived).

        Args:
            lead: Lost lead
            reason: Why lost
            actor: Who marked

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.ARCHIVED,
            actor=actor,
            reason=reason,
        )

    def qualify_lead(
        self,
        lead: EmployerLead,
        *,
        score: float,
        reason: str,
        actor: str = "qualification_agent",
        pipeline_run_id: str | None = None,
    ) -> tuple[EmployerLead, Event]:
        """Qualify lead based on scoring.

        Transitions lead to EMAIL_READY if qualified.

        Args:
            lead: Lead to qualify
            score: Qualification score
            reason: Qualification reason
            actor: Who qualified
            pipeline_run_id: Pipeline run ID

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.EMAIL_READY,
            actor=actor,
            reason=reason,
            metadata={"score": score, "qualified": True},
            pipeline_run_id=pipeline_run_id,
        )

    def disqualify_lead(
        self,
        lead: EmployerLead,
        *,
        reason: str,
        actor: str = "qualification_agent",
        pipeline_run_id: str | None = None,
    ) -> tuple[EmployerLead, Event]:
        """Disqualify lead and archive.

        Args:
            lead: Lead to disqualify
            reason: Disqualification reason
            actor: Who disqualified
            pipeline_run_id: Pipeline run ID

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.ARCHIVED,
            actor=actor,
            reason=reason,
            metadata={"qualified": False},
            pipeline_run_id=pipeline_run_id,
        )
