"""Email Repository.

Repository для работы с email-последовательностями и сообщениями.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import EmailMessageDB, EmailSequenceDB

UTC = timezone.utc

class EmailRepository:
    """Repository for email sequences and messages."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    # ==================
    # Email Sequences
    # ==================

    async def create_sequence(
        self,
        lead_id: UUID,
        contact_id: UUID,
        campaign_id: UUID | None = None,
    ) -> EmailSequenceDB:
        """Create new email sequence.

        Args:
            lead_id: Lead ID
            contact_id: Contact ID
            campaign_id: Campaign ID (optional)

        Returns:
            Created sequence
        """
        sequence = EmailSequenceDB(
            lead_id=lead_id,
            contact_id=contact_id,
            campaign_id=campaign_id,
            current_step=0,
            is_active=True,
        )
        self.db.add(sequence)
        await self.db.flush()
        return sequence

    async def get_sequence(self, sequence_id: UUID) -> EmailSequenceDB | None:
        """Get sequence by ID.

        Args:
            sequence_id: Sequence ID

        Returns:
            Sequence or None
        """
        result = await self.db.execute(
            select(EmailSequenceDB).where(EmailSequenceDB.id == sequence_id)
        )
        return result.scalar_one_or_none()

    async def get_sequence_by_lead_contact(
        self,
        lead_id: UUID,
        contact_id: UUID,
    ) -> EmailSequenceDB | None:
        """Get active sequence for lead-contact pair.

        Args:
            lead_id: Lead ID
            contact_id: Contact ID

        Returns:
            Active sequence or None
        """
        result = await self.db.execute(
            select(EmailSequenceDB).where(
                and_(
                    EmailSequenceDB.lead_id == lead_id,
                    EmailSequenceDB.contact_id == contact_id,
                    EmailSequenceDB.is_active == True,  # noqa: E712
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_due_sequences(
        self,
        limit: int = 100,
    ) -> list[EmailSequenceDB]:
        """Get sequences due for follow-up.

        Args:
            limit: Maximum sequences to return

        Returns:
            List of due sequences
        """
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(EmailSequenceDB)
            .where(
                and_(
                    EmailSequenceDB.is_active == True,  # noqa: E712
                    EmailSequenceDB.next_email_at <= now,
                    EmailSequenceDB.current_step < 4,
                )
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_sequence_step(
        self,
        sequence_id: UUID,
        step: int,
        next_email_at: datetime | None = None,
    ) -> None:
        """Update sequence step.

        Args:
            sequence_id: Sequence ID
            step: New step number
            next_email_at: Next email time
        """
        sequence = await self.get_sequence(sequence_id)
        if sequence:
            sequence.current_step = step
            sequence.next_email_at = next_email_at
            sequence.last_email_at = datetime.now(UTC)

    async def complete_sequence(
        self,
        sequence_id: UUID,
    ) -> None:
        """Mark sequence as completed.

        Args:
            sequence_id: Sequence ID
        """
        sequence = await self.get_sequence(sequence_id)
        if sequence:
            sequence.is_active = False
            sequence.completed_at = datetime.now(UTC)

    async def deactivate_sequence(
        self,
        sequence_id: UUID,
    ) -> None:
        """Deactivate sequence (on reply, bounce, etc).

        Args:
            sequence_id: Sequence ID
        """
        sequence = await self.get_sequence(sequence_id)
        if sequence:
            sequence.is_active = False

    # ==================
    # Email Messages
    # ==================

    async def create_message(
        self,
        sequence_id: UUID,
        lead_id: UUID,
        contact_id: UUID,
        email_type: str,
        subject: str,
        body: str,
        step_number: int,
        generation_model: str | None = None,
        quality_gate_passed: bool = False,
        quality_gate_issues: list[str] | None = None,
    ) -> EmailMessageDB:
        """Create email message.

        Args:
            sequence_id: Sequence ID
            lead_id: Lead ID
            contact_id: Contact ID
            email_type: Type of email
            subject: Email subject
            body: Email body
            step_number: Step in sequence
            generation_model: LLM model used
            quality_gate_passed: Whether passed quality gate
            quality_gate_issues: Quality gate issues

        Returns:
            Created message
        """
        message = EmailMessageDB(
            sequence_id=sequence_id,
            lead_id=lead_id,
            contact_id=contact_id,
            email_type=email_type,
            subject=subject,
            body=body,
            step_number=step_number,
            generation_model=generation_model,
            quality_gate_passed=quality_gate_passed,
            quality_gate_issues=quality_gate_issues or [],
        )
        self.db.add(message)
        await self.db.flush()
        return message

    async def get_message(self, message_id: UUID) -> EmailMessageDB | None:
        """Get message by ID.

        Args:
            message_id: Message ID

        Returns:
            Message or None
        """
        result = await self.db.execute(
            select(EmailMessageDB).where(EmailMessageDB.id == message_id)
        )
        return result.scalar_one_or_none()

    async def get_sequence_messages(
        self,
        sequence_id: UUID,
    ) -> list[EmailMessageDB]:
        """Get all messages for sequence.

        Args:
            sequence_id: Sequence ID

        Returns:
            List of messages ordered by step
        """
        result = await self.db.execute(
            select(EmailMessageDB)
            .where(EmailMessageDB.sequence_id == sequence_id)
            .order_by(EmailMessageDB.step_number)
        )
        return list(result.scalars().all())

    async def get_last_message(
        self,
        sequence_id: UUID,
    ) -> EmailMessageDB | None:
        """Get last message in sequence.

        Args:
            sequence_id: Sequence ID

        Returns:
            Last message or None
        """
        result = await self.db.execute(
            select(EmailMessageDB)
            .where(EmailMessageDB.sequence_id == sequence_id)
            .order_by(EmailMessageDB.step_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_sent(
        self,
        message_id: UUID,
        message_id_header: str,
    ) -> None:
        """Mark message as sent.

        Args:
            message_id: Message ID
            message_id_header: SMTP Message-ID
        """
        message = await self.get_message(message_id)
        if message:
            message.sent_at = datetime.now(UTC)
            message.message_id_header = message_id_header
            message.delivered = True

    async def mark_bounced(
        self,
        message_id: UUID,
        bounce_type: str,
        bounce_reason: str,
    ) -> None:
        """Mark message as bounced.

        Args:
            message_id: Message ID
            bounce_type: hard/soft
            bounce_reason: Bounce reason
        """
        message = await self.get_message(message_id)
        if message:
            message.bounced = True
            message.bounce_type = bounce_type
            message.bounce_reason = bounce_reason
            message.delivered = False

    async def mark_replied(
        self,
        message_id: UUID,
        reply_text: str,
    ) -> None:
        """Mark message as replied.

        Args:
            message_id: Message ID
            reply_text: Reply text
        """
        message = await self.get_message(message_id)
        if message:
            message.replied = True
            message.replied_at = datetime.now(UTC)
            message.reply_text = reply_text

    async def mark_opened(
        self,
        message_id: UUID,
    ) -> None:
        """Mark message as opened.

        Args:
            message_id: Message ID
        """
        message = await self.get_message(message_id)
        if message:
            if not message.opened:
                message.opened = True
                message.opened_at = datetime.now(UTC)
            message.open_count += 1

    # ==================
    # Statistics
    # ==================

    async def count_sent_today(
        self,
        sender_email: str | None = None,
    ) -> int:
        """Count emails sent today.

        Args:
            sender_email: Filter by sender (optional)

        Returns:
            Count of sent emails
        """
        from sqlalchemy import func

        today_start = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        query = select(func.count(EmailMessageDB.id)).where(
            and_(
                EmailMessageDB.sent_at >= today_start,
                EmailMessageDB.sent_at.isnot(None),
            )
        )

        result = await self.db.execute(query)
        return result.scalar_one() or 0

    async def count_sent_to_domain_today(
        self,
        domain: str,
    ) -> int:
        """Count emails sent to domain today.

        Args:
            domain: Recipient domain

        Returns:
            Count of sent emails
        """
        # TODO: Implement with contact email domain join
        return 0

    # ==================
    # API Support Methods
    # ==================

    async def get(self, message_id: str | UUID) -> EmailMessageDB | None:
        """Get email message by ID (alias for get_message).

        Args:
            message_id: Message ID

        Returns:
            Message or None
        """
        if isinstance(message_id, str):
            try:
                message_id = UUID(message_id)
            except ValueError:
                return None
        return await self.get_message(message_id)

    async def update(self, message: EmailMessageDB) -> None:
        """Update email message.

        Args:
            message: Message to update
        """
        await self.db.flush()

    async def find_paginated(
        self,
        filters: dict | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[EmailMessageDB], int]:
        """Find emails with pagination.

        Args:
            filters: Filter criteria
            page: Page number
            limit: Items per page

        Returns:
            Tuple of (emails, total_count)
        """
        from sqlalchemy import func, or_

        from app.models.db import EmployerContactDB, EmployerLeadDB

        filters = filters or {}
        query = select(EmailMessageDB)

        # Apply filters
        if "lead_id" in filters:
            lead_id = filters["lead_id"]
            if isinstance(lead_id, str):
                lead_id = UUID(lead_id)
            query = query.where(EmailMessageDB.lead_id == lead_id)

        if "email_type" in filters:
            query = query.where(EmailMessageDB.email_type == filters["email_type"])

        if "status" in filters:
            # Map status to delivery_status or other fields
            status = filters["status"]
            if status == "sent":
                query = query.where(EmailMessageDB.sent_at.isnot(None))
            elif status == "opened":
                query = query.where(EmailMessageDB.opened == True)  # noqa: E712
            elif status == "replied":
                query = query.where(EmailMessageDB.replied == True)  # noqa: E712
            elif status == "bounced":
                query = query.where(EmailMessageDB.bounced == True)  # noqa: E712

        if "search" in filters and filters["search"]:
            search_term = f"%{filters['search']}%"
            # Search in subject and body, plus join with leads/contacts for company/name
            query = query.outerjoin(
                EmployerLeadDB, EmailMessageDB.lead_id == EmployerLeadDB.id
            ).outerjoin(
                EmployerContactDB, EmailMessageDB.contact_id == EmployerContactDB.id
            ).where(
                or_(
                    EmailMessageDB.subject.ilike(search_term),
                    EmailMessageDB.body.ilike(search_term),
                    EmployerLeadDB.company_name.ilike(search_term),
                    EmployerContactDB.full_name.ilike(search_term),
                    EmployerContactDB.email.ilike(search_term),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination
        offset = (page - 1) * limit
        query = query.order_by(EmailMessageDB.sent_at.desc().nullslast()).offset(offset).limit(limit)

        result = await self.db.execute(query)
        emails = list(result.scalars().all())

        return emails, total

    async def find_by_message_id(self, message_id_header: str) -> EmailMessageDB | None:
        """Find email by Message-ID header.

        Args:
            message_id_header: SMTP Message-ID

        Returns:
            Email or None
        """
        result = await self.db.execute(
            select(EmailMessageDB).where(
                EmailMessageDB.message_id_header == message_id_header
            )
        )
        return result.scalar_one_or_none()

    async def find_by_subject_and_recipient(
        self,
        subject: str,
        recipient: str,
    ) -> EmailMessageDB | None:
        """Find email by subject and recipient (for reply matching).

        Args:
            subject: Email subject
            recipient: Recipient email (who sent the reply, was our recipient)

        Returns:
            Email or None
        """
        from app.models.db import EmployerContactDB

        # Join with contacts to find by recipient email
        result = await self.db.execute(
            select(EmailMessageDB)
            .join(EmployerContactDB, EmailMessageDB.contact_id == EmployerContactDB.id)
            .where(
                and_(
                    EmailMessageDB.subject == subject,
                    EmployerContactDB.email == recipient,
                )
            )
            .order_by(EmailMessageDB.sent_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
