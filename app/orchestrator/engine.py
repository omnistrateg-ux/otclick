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
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.state_machine import LeadStateMachine
from app.events.definitions import Event, EventType, create_event
from app.models.domain import EmployerLead
from app.models.enums import LeadStatus

logger = logging.getLogger(__name__)


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
    ) -> tuple[EmployerLead, Event]:
        """Transition lead to new status.

        Args:
            lead: Lead to transition
            target_status: Target status
            actor: Who initiated the transition
            reason: Reason for transition
            metadata: Additional metadata

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

        # Create event
        event_type = self._get_event_type(target_status)
        event = create_event(
            event_type,
            lead_id=str(lead.id),
            actor=actor,
            data={
                "old_status": old_status.value,
                "new_status": target_status.value,
                "reason": reason,
                **(metadata or {}),
            },
        )

        logger.info(
            f"Lead {lead.id} transitioned: {old_status} -> {target_status} "
            f"(actor={actor}, reason={reason})"
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
    ) -> tuple[EmployerLead, Event]:
        """Mark lead as enriched.

        Args:
            lead: Lead to mark
            actor: Who enriched
            enrichment_data: Enrichment details

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.ENRICHED,
            actor=actor,
            reason="Enrichment completed",
            metadata={"enrichment": enrichment_data or {}},
        )

    def score_lead(
        self,
        lead: EmployerLead,
        score: float,
        *,
        actor: str = "scoring_agent",
        segment: str | None = None,
    ) -> tuple[EmployerLead, Event]:
        """Score and potentially qualify lead.

        Note: Score is stored in a separate LeadScore record, not on EmployerLead.

        Args:
            lead: Lead to score
            score: Calculated score
            actor: Who scored
            segment: Determined segment

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
        )

    def start_outreach(
        self,
        lead: EmployerLead,
        *,
        campaign_id: str | None = None,
        actor: str = "outreach_agent",
    ) -> tuple[EmployerLead, Event]:
        """Start outreach to lead.

        Args:
            lead: Lead to contact
            campaign_id: Campaign ID
            actor: Who started

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.OUTREACH_SENT,
            actor=actor,
            reason="Outreach sequence started",
            metadata={"campaign_id": campaign_id},
        )

    def record_reply(
        self,
        lead: EmployerLead,
        *,
        email_id: str,
        reply_text: str | None = None,
        actor: str = "system",
    ) -> tuple[EmployerLead, Event]:
        """Record that lead replied.

        Args:
            lead: Lead who replied
            email_id: Email that was replied to
            reply_text: Reply content
            actor: Who recorded

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
        )

    def mark_interested(
        self,
        lead: EmployerLead,
        *,
        intent: str,
        confidence: float,
        actor: str = "qualification_agent",
    ) -> tuple[EmployerLead, Event]:
        """Mark lead as interested.

        Args:
            lead: Interested lead
            intent: Detected intent
            confidence: Confidence score
            actor: Who qualified

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.INTEREST_DETECTED,
            actor=actor,
            reason=f"Positive intent detected: {intent}",
            metadata={"intent": intent, "confidence": confidence},
        )

    def mark_not_interested(
        self,
        lead: EmployerLead,
        *,
        intent: str,
        confidence: float,
        actor: str = "qualification_agent",
    ) -> tuple[EmployerLead, Event]:
        """Mark lead as not interested.

        Args:
            lead: Not interested lead
            intent: Detected intent
            confidence: Confidence score
            actor: Who qualified

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.REFUSED,
            actor=actor,
            reason=f"Negative intent detected: {intent}",
            metadata={"intent": intent, "confidence": confidence},
        )

    def handoff_to_manager(
        self,
        lead: EmployerLead,
        *,
        manager_id: str,
        handoff_id: str,
        actor: str = "handoff_agent",
    ) -> tuple[EmployerLead, Event]:
        """Hand off lead to sales manager.

        Args:
            lead: Lead to hand off
            manager_id: Assigned manager
            handoff_id: Handoff record ID
            actor: Who created handoff

        Returns:
            Tuple of (lead, event)
        """
        return self.transition(
            lead,
            LeadStatus.HANDED_TO_MANAGER,
            actor=actor,
            reason=f"Handed off to manager {manager_id}",
            metadata={"manager_id": manager_id, "handoff_id": handoff_id},
        )

    def mark_converted(
        self,
        lead: EmployerLead,
        *,
        deal_value: float | None = None,
        actor: str = "system",
    ) -> tuple[EmployerLead, Event]:
        """Mark lead as converted (stays at HANDED_TO_MANAGER, records conversion).

        Note: There's no separate CONVERTED status - conversion is tracked
        in metadata while lead remains at HANDED_TO_MANAGER.

        Args:
            lead: Converted lead
            deal_value: Deal value
            actor: Who marked

        Returns:
            Tuple of (lead, event)
        """
        # Lead stays at HANDED_TO_MANAGER, but we record conversion event
        event = create_event(
            EventType.HANDOFF_COMPLETED,
            lead_id=str(lead.id),
            actor=actor,
            data={
                "deal_value": deal_value,
                "converted": True,
            },
        )

        logger.info(
            f"Lead {lead.id} converted with deal value {deal_value}"
        )

        return lead, event

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
