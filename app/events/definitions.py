"""Event definitions for the system.

События хранятся в PostgreSQL для audit trail и replay.
Обработка через Celery tasks.
"""

from datetime import datetime, timezone

UTC = timezone.utc
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(StrEnum):
    """Types of events in the system."""

    # Lead lifecycle events
    LEAD_DISCOVERED = "lead.discovered"
    LEAD_ENRICHED = "lead.enriched"
    LEAD_SCORED = "lead.scored"
    LEAD_QUALIFIED = "lead.qualified"
    LEAD_DISQUALIFIED = "lead.disqualified"

    # Email events
    EMAIL_GENERATED = "email.generated"
    EMAIL_SENT = "email.sent"
    EMAIL_DELIVERED = "email.delivered"
    EMAIL_OPENED = "email.opened"
    EMAIL_CLICKED = "email.clicked"
    EMAIL_BOUNCED = "email.bounced"
    EMAIL_FAILED = "email.failed"

    # Reply events
    REPLY_RECEIVED = "reply.received"
    REPLY_ANALYZED = "reply.analyzed"

    # Outreach events
    OUTREACH_STARTED = "outreach.started"
    OUTREACH_PAUSED = "outreach.paused"
    OUTREACH_COMPLETED = "outreach.completed"
    FOLLOWUP_SCHEDULED = "followup.scheduled"
    FOLLOWUP_SENT = "followup.sent"

    # Qualification events
    QUALIFICATION_STARTED = "qualification.started"
    QUALIFICATION_COMPLETED = "qualification.completed"

    # Handoff events
    HANDOFF_CREATED = "handoff.created"
    HANDOFF_ACCEPTED = "handoff.accepted"
    HANDOFF_REJECTED = "handoff.rejected"
    HANDOFF_COMPLETED = "handoff.completed"

    # System events
    RATE_LIMIT_HIT = "system.rate_limit_hit"
    ERROR_OCCURRED = "system.error"
    CAMPAIGN_STARTED = "campaign.started"
    CAMPAIGN_PAUSED = "campaign.paused"
    CAMPAIGN_COMPLETED = "campaign.completed"


class Event(BaseModel):
    """Domain event model.

    Events are persisted to PostgreSQL for audit trail.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Entity references
    lead_id: str | None = None
    email_id: str | None = None
    campaign_id: str | None = None
    handoff_id: str | None = None

    # Event data
    data: dict[str, Any] = Field(default_factory=dict)

    # Metadata
    actor: str = "system"  # system, agent name, or user
    correlation_id: str | None = None  # For tracing related events
    causation_id: str | None = None  # ID of event that caused this one

    # Processing status
    processed: bool = False
    processed_at: datetime | None = None
    error: str | None = None


def create_event(
    event_type: EventType,
    *,
    lead_id: str | None = None,
    email_id: str | None = None,
    campaign_id: str | None = None,
    handoff_id: str | None = None,
    data: dict[str, Any] | None = None,
    actor: str = "system",
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> Event:
    """Create a new event.

    Args:
        event_type: Type of event
        lead_id: Related lead ID
        email_id: Related email ID
        campaign_id: Related campaign ID
        handoff_id: Related handoff ID
        data: Additional event data
        actor: Who caused the event
        correlation_id: For tracing related events
        causation_id: ID of event that caused this one

    Returns:
        New Event instance
    """
    return Event(
        event_type=event_type,
        lead_id=lead_id,
        email_id=email_id,
        campaign_id=campaign_id,
        handoff_id=handoff_id,
        data=data or {},
        actor=actor,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


# Event type to handler mapping hints
LEAD_EVENTS = {
    EventType.LEAD_DISCOVERED,
    EventType.LEAD_ENRICHED,
    EventType.LEAD_SCORED,
    EventType.LEAD_QUALIFIED,
    EventType.LEAD_DISQUALIFIED,
}

EMAIL_EVENTS = {
    EventType.EMAIL_GENERATED,
    EventType.EMAIL_SENT,
    EventType.EMAIL_DELIVERED,
    EventType.EMAIL_OPENED,
    EventType.EMAIL_CLICKED,
    EventType.EMAIL_BOUNCED,
    EventType.EMAIL_FAILED,
}

REPLY_EVENTS = {
    EventType.REPLY_RECEIVED,
    EventType.REPLY_ANALYZED,
}

OUTREACH_EVENTS = {
    EventType.OUTREACH_STARTED,
    EventType.OUTREACH_PAUSED,
    EventType.OUTREACH_COMPLETED,
    EventType.FOLLOWUP_SCHEDULED,
    EventType.FOLLOWUP_SENT,
}
