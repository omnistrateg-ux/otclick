"""Email Service.

Управление email-последовательностями из ARCHITECTURE.md.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.email.delivery import DeliveryResult, EmailDelivery
from app.email.engine import EmailGenerationResult, EmailIntelligenceEngine
from app.email.templates import FOLLOWUP_DELAYS_DAYS
from app.llm.router import LLMRouter
from app.models.domain import (
    CompanyProfile,
    EmailMessage,
    EmailSequence,
    EmployerContact,
    EmployerLead,
    LeadSegment,
)
from app.models.enums import EmailType, LeadStatus

logger = logging.getLogger(__name__)


class EmailService:
    """Service for managing email sequences.

    Управляет:
    - Созданием email sequences
    - Генерацией писем
    - Отправкой
    - Расписанием follow-up
    """

    def __init__(
        self,
        db: AsyncSession,
        llm_router: LLMRouter,
        delivery: EmailDelivery | None = None,
    ) -> None:
        """Initialize service.

        Args:
            db: Database session
            llm_router: LLM router
            delivery: Email delivery (optional)
        """
        self.db = db
        self.llm_router = llm_router
        self.email_engine = EmailIntelligenceEngine(llm_router)
        self.delivery = delivery or EmailDelivery()

    async def create_sequence(
        self,
        lead: EmployerLead,
        contact: EmployerContact,
        campaign_id: UUID | None = None,
    ) -> EmailSequence:
        """Create new email sequence.

        Args:
            lead: Lead
            contact: Contact
            campaign_id: Campaign ID (optional)

        Returns:
            New email sequence
        """
        sequence = EmailSequence(
            id=uuid4(),
            lead_id=lead.id,
            contact_id=contact.id,
            campaign_id=campaign_id,
            current_step=0,
            is_active=True,
        )

        # TODO: Save to database via repository

        return sequence

    async def generate_first_email(
        self,
        lead: EmployerLead,
        profile: CompanyProfile,
        segment: LeadSegment,
        contact: EmployerContact,
        sequence: EmailSequence,
    ) -> EmailGenerationResult:
        """Generate first touch email for sequence.

        Args:
            lead: Lead
            profile: Company profile
            segment: Lead segment
            contact: Contact
            sequence: Email sequence

        Returns:
            Generation result
        """
        result = await self.email_engine.generate_email(
            lead=lead,
            profile=profile,
            segment=segment,
            contact=contact,
            email_type=EmailType.FIRST_TOUCH,
            sequence_id=str(sequence.id),
        )

        return result

    async def generate_followup(
        self,
        lead: EmployerLead,
        profile: CompanyProfile,
        segment: LeadSegment,
        contact: EmployerContact,
        sequence: EmailSequence,
        previous_emails: list[EmailMessage],
    ) -> EmailGenerationResult:
        """Generate next follow-up email.

        Args:
            lead: Lead
            profile: Company profile
            segment: Lead segment
            contact: Contact
            sequence: Email sequence
            previous_emails: Previous emails in sequence

        Returns:
            Generation result
        """
        # Determine next email type
        email_type = self._get_next_email_type(sequence.current_step)
        if not email_type:
            return EmailGenerationResult(
                success=False,
                error="Sequence complete, no more follow-ups",
            )

        # Build previous emails context
        prev_context = [
            {"subject": e.subject, "body": e.body}
            for e in previous_emails
        ]

        result = await self.email_engine.generate_email(
            lead=lead,
            profile=profile,
            segment=segment,
            contact=contact,
            email_type=email_type,
            sequence_id=str(sequence.id),
            previous_emails=prev_context,
        )

        return result

    async def send_email(
        self,
        email: EmailMessage,
        contact: EmployerContact,
        lead: EmployerLead,
    ) -> DeliveryResult:
        """Send email and update status.

        Args:
            email: Email to send
            contact: Recipient
            lead: Lead

        Returns:
            Delivery result
        """
        # Build unsubscribe URL
        unsubscribe_url = self._build_unsubscribe_url(lead.id, contact.id)

        # Send
        result = await self.delivery.send_email(
            email=email,
            contact=contact,
            unsubscribe_url=unsubscribe_url,
        )

        # Update email status
        if result.success:
            email.sent_at = result.sent_at
            email.message_id_header = result.message_id
            email.delivered = True
            # TODO: Save to database

        return result

    async def schedule_followup(
        self,
        sequence: EmailSequence,
        last_email: EmailMessage,
    ) -> datetime | None:
        """Schedule next follow-up.

        Args:
            sequence: Email sequence
            last_email: Last sent email

        Returns:
            Scheduled time or None if no more follow-ups
        """
        if not sequence.is_active:
            return None

        next_type = self._get_next_email_type(sequence.current_step)
        if not next_type:
            return None

        delay_days = FOLLOWUP_DELAYS_DAYS.get(next_type, 3)
        last_sent = last_email.sent_at or datetime.now(UTC)
        scheduled_time = last_sent + timedelta(days=delay_days)

        sequence.next_email_at = scheduled_time
        # TODO: Save to database

        return scheduled_time

    async def process_bounce(
        self,
        email: EmailMessage,
        bounce_type: str,
        bounce_reason: str,
    ) -> None:
        """Process email bounce.

        Args:
            email: Bounced email
            bounce_type: Type of bounce (hard/soft)
            bounce_reason: Bounce reason
        """
        email.bounced = True
        email.bounce_type = bounce_type
        email.bounce_reason = bounce_reason
        email.delivered = False

        # TODO: Update in database
        # TODO: If hard bounce, mark contact as invalid
        # TODO: If soft bounce count > 3, mark as bounced

    async def process_reply(
        self,
        email: EmailMessage,
        reply_text: str,
        sequence: EmailSequence,
    ) -> None:
        """Process incoming reply.

        Args:
            email: Email that was replied to
            reply_text: Reply text
            sequence: Email sequence
        """
        email.replied = True
        email.replied_at = datetime.now(UTC)
        email.reply_text = reply_text

        # Pause sequence on reply
        sequence.is_active = False

        # TODO: Save to database
        # TODO: Emit REPLY_RECEIVED event

    async def complete_sequence(
        self,
        sequence: EmailSequence,
        reason: str = "completed",
    ) -> None:
        """Mark sequence as complete.

        Args:
            sequence: Sequence to complete
            reason: Completion reason
        """
        sequence.is_active = False
        sequence.completed_at = datetime.now(UTC)
        # TODO: Save to database

    async def get_due_followups(
        self,
        limit: int = 100,
    ) -> list[tuple[EmailSequence, EmailMessage]]:
        """Get sequences due for follow-up.

        Args:
            limit: Maximum sequences to return

        Returns:
            List of (sequence, last_email) tuples
        """
        # TODO: Query from database
        # SELECT sequences WHERE
        #   is_active = true
        #   AND next_email_at <= now()
        #   AND current_step < 4
        # JOIN last_email
        return []

    def _get_next_email_type(self, current_step: int) -> EmailType | None:
        """Get next email type based on current step.

        Args:
            current_step: Current step (0-3)

        Returns:
            Next email type or None if complete
        """
        type_map = {
            0: EmailType.FIRST_TOUCH,
            1: EmailType.FOLLOWUP_1,
            2: EmailType.FOLLOWUP_2,
            3: EmailType.BREAKUP,
        }
        return type_map.get(current_step)

    def _build_unsubscribe_url(
        self,
        lead_id: UUID,
        contact_id: UUID,
    ) -> str:
        """Build unsubscribe URL.

        Args:
            lead_id: Lead ID
            contact_id: Contact ID

        Returns:
            Unsubscribe URL
        """
        # TODO: Use actual domain from settings
        return f"https://otclick.ru/unsubscribe?lead={lead_id}&contact={contact_id}"


class EmailSequenceManager:
    """Manager for batch email sequence operations."""

    def __init__(self, email_service: EmailService) -> None:
        """Initialize manager.

        Args:
            email_service: Email service
        """
        self.service = email_service

    async def process_due_followups(self) -> int:
        """Process all due follow-ups.

        Returns:
            Number of follow-ups processed
        """
        due = await self.service.get_due_followups()
        count = 0

        for sequence, last_email in due:
            try:
                # TODO: Get lead, profile, segment, contact from database
                # TODO: Generate and send follow-up
                count += 1
            except Exception as e:
                logger.error(f"Failed to process followup for sequence {sequence.id}: {e}")

        return count

    async def cleanup_stale_sequences(self, days: int = 30) -> int:
        """Clean up stale sequences.

        Args:
            days: Days after which sequence is stale

        Returns:
            Number of sequences cleaned up
        """
        # TODO: Query and mark stale sequences as completed
        return 0
