"""Email API endpoints.

Управление email отправками и отслеживание.
"""

from datetime import datetime, timezone

UTC = timezone.utc
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.enums import EmailType
from app.storage.database import async_session_factory

router = APIRouter(prefix="/emails", tags=["emails"])


# Request/Response models
class ThreadMessage(BaseModel):
    """A message in the email thread."""

    id: str
    direction: str  # "outbound" or "inbound"
    subject: str
    body: str
    sent_at: datetime | None = None


class EmailResponse(BaseModel):
    """Email response model."""

    id: str
    lead_id: str
    company_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    to_email: str
    subject: str
    body: str | None = None
    email_type: str
    status: str
    sent_at: datetime | None = None
    opened_at: datetime | None = None
    clicked_at: datetime | None = None
    replied_at: datetime | None = None
    reply_text: str | None = None
    thread: list[ThreadMessage] | None = None


class EmailListResponse(BaseModel):
    """Email list response."""

    items: list[EmailResponse]
    total: int
    page: int
    limit: int
    pages: int


class EmailStatsResponse(BaseModel):
    """Email statistics."""

    total_sent: int
    total_delivered: int
    total_opened: int
    total_clicked: int
    total_replied: int
    total_bounced: int
    open_rate: float
    click_rate: float
    reply_rate: float
    bounce_rate: float


class NotificationCountsResponse(BaseModel):
    """Notification counts for badges."""

    unread_replies: int = 0  # Replies not yet viewed/processed
    new_bounces: int = 0  # Bounces in last 24h
    pending_handoffs: int = 0  # Handoffs not yet actioned
    total_unread: int = 0  # Total for main badge


class ThreadSummary(BaseModel):
    """Summary of an email thread (grouped by lead)."""

    lead_id: str
    company_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    last_subject: str
    last_snippet: str  # Preview of last message
    message_count: int
    has_reply: bool
    status: str  # Latest status
    last_message_at: datetime | None = None


class ThreadListResponse(BaseModel):
    """Thread list response."""

    items: list[ThreadSummary]
    total: int
    page: int
    limit: int
    pages: int


class SendEmailRequest(BaseModel):
    """Send email request."""

    lead_id: str
    to_email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    email_type: str = "first_touch"


class PreviewEmailRequest(BaseModel):
    """Preview email request."""

    lead_id: str
    email_type: str = "first_touch"


class PreviewEmailResponse(BaseModel):
    """Preview email response."""

    subject: str
    body: str
    word_count: int
    quality_check: dict[str, Any]


class ReplyRequest(BaseModel):
    """Manager reply request."""

    lead_id: str
    body: str = Field(..., min_length=1, description="Reply message body (plain text or HTML)")


class ReplyResponse(BaseModel):
    """Reply response."""

    success: bool
    email_id: str | None = None
    message_id: str | None = None
    sent_at: datetime | None = None
    error: str | None = None


class TestEmailRequest(BaseModel):
    """Test email request - for manual testing without lead."""

    to_email: str = Field(..., pattern=r"^[\w\.\-\+]+@[\w\.-]+\.\w+$")
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    from_name: str = Field(default="Отклик", max_length=100)


class TestEmailResponse(BaseModel):
    """Test email response."""

    success: bool
    message_id: str | None = None
    email_db_id: str | None = None  # ID in email_messages table
    sent_at: datetime | None = None
    error: str | None = None


# Test email constants
TEST_LEAD_COMPANY = "__TEST_EMAILS__"
TEST_CONTACT_NAME = "Test Recipient"


def _get_email_status(email) -> str:
    """Get email status from boolean fields."""
    if email.replied:
        return "replied"
    if email.bounced:
        return "bounced"
    if email.opened:
        return "opened"
    if email.delivered:
        return "delivered"
    if email.sent_at:
        return "sent"
    return "pending"


def _strip_html(html: str | None) -> str:
    """Strip HTML tags for plain text snippet."""
    if not html:
        return ""
    import re
    text = re.sub(r"<[^>]+>", "", html)
    text = text.replace("&nbsp;", " ").strip()
    return text[:100] + "..." if len(text) > 100 else text


@router.get("/threads", response_model=ThreadListResponse)
async def list_threads(
    status: str | None = Query(None, description="Filter by status"),
    search: str | None = Query(None, description="Search by company, contact or subject"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
) -> ThreadListResponse:
    """List email threads grouped by lead (like Gmail).

    Each row = one company/lead with thread summary.

    Args:
        status: Filter by status
        search: Search by company, contact or subject
        page: Page number
        limit: Items per page

    Returns:
        Paginated list of threads
    """
    from sqlalchemy import func, select, case, or_

    from app.models.db import EmailMessageDB, EmployerContactDB, EmployerLeadDB

    async with async_session_factory() as db:
        # Subquery to get thread stats per lead
        thread_stats = (
            select(
                EmailMessageDB.lead_id,
                func.count(EmailMessageDB.id).label("message_count"),
                func.max(EmailMessageDB.sent_at).label("last_sent_at"),
                func.max(EmailMessageDB.replied_at).label("last_replied_at"),
                func.bool_or(EmailMessageDB.replied).label("has_reply"),
                func.bool_or(EmailMessageDB.bounced).label("has_bounce"),
                func.bool_or(EmailMessageDB.opened).label("has_open"),
            )
            .group_by(EmailMessageDB.lead_id)
            .subquery()
        )

        # Main query joining with leads and contacts
        query = (
            select(
                EmployerLeadDB.id.label("lead_id"),
                EmployerLeadDB.company_name,
                thread_stats.c.message_count,
                thread_stats.c.last_sent_at,
                thread_stats.c.last_replied_at,
                thread_stats.c.has_reply,
                thread_stats.c.has_bounce,
                thread_stats.c.has_open,
            )
            .join(thread_stats, EmployerLeadDB.id == thread_stats.c.lead_id)
        )

        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    EmployerLeadDB.company_name.ilike(search_term),
                )
            )

        # Apply status filter
        if status:
            if status == "replied":
                query = query.where(thread_stats.c.has_reply == True)
            elif status == "bounced":
                query = query.where(thread_stats.c.has_bounce == True)
            elif status == "opened":
                query = query.where(thread_stats.c.has_open == True)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination and ordering
        offset = (page - 1) * limit
        query = query.order_by(
            func.coalesce(thread_stats.c.last_replied_at, thread_stats.c.last_sent_at).desc()
        ).offset(offset).limit(limit)

        result = await db.execute(query)
        rows = result.all()

        # Build response with last message info
        items = []
        for row in rows:
            lead_id = row.lead_id

            # Get last email for this lead
            last_email_result = await db.execute(
                select(EmailMessageDB)
                .where(EmailMessageDB.lead_id == lead_id)
                .order_by(EmailMessageDB.sent_at.desc().nullslast())
                .limit(1)
            )
            last_email = last_email_result.scalar_one_or_none()

            # Get contact info
            contact_name = None
            contact_email = None
            if last_email and last_email.contact_id:
                contact_result = await db.execute(
                    select(EmployerContactDB).where(
                        EmployerContactDB.id == last_email.contact_id
                    )
                )
                contact = contact_result.scalar_one_or_none()
                if contact:
                    contact_name = contact.full_name
                    contact_email = contact.email

            # Determine status
            if row.has_reply:
                status_val = "replied"
            elif row.has_bounce:
                status_val = "bounced"
            elif row.has_open:
                status_val = "opened"
            else:
                status_val = "sent"

            # Determine last message (reply or sent)
            last_message_at = row.last_replied_at or row.last_sent_at
            last_body = last_email.reply_text if last_email and last_email.replied else (last_email.body if last_email else "")

            items.append(
                ThreadSummary(
                    lead_id=str(lead_id),
                    company_name=row.company_name,
                    contact_name=contact_name,
                    contact_email=contact_email,
                    last_subject=last_email.subject if last_email else "",
                    last_snippet=_strip_html(last_body),
                    message_count=row.message_count + (1 if row.has_reply else 0),  # +1 for replies
                    has_reply=row.has_reply or False,
                    status=status_val,
                    last_message_at=last_message_at,
                )
            )

        pages = (total + limit - 1) // limit if total > 0 else 1
        return ThreadListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )


@router.post("/reply", response_model=ReplyResponse)
async def send_manager_reply(request: ReplyRequest) -> ReplyResponse:
    """Send a manual reply from manager to a lead.

    The email is sent from Владислав Наков <team@otclick-hr.ru>.
    Client sees no difference between AI and manager responses.

    Args:
        request: Reply request with lead_id and body

    Returns:
        Reply result with email_id and message_id
    """
    from uuid import UUID

    from sqlalchemy import select

    from app.email.delivery import EmailDelivery
    from app.models.db import EmailMessageDB, EmailSequenceDB, EmployerContactDB, EmployerLeadDB

    async with async_session_factory() as db:
        # Get lead
        try:
            lead_uuid = UUID(request.lead_id)
        except ValueError:
            return ReplyResponse(success=False, error=f"Invalid lead_id: {request.lead_id}")

        lead_result = await db.execute(
            select(EmployerLeadDB).where(EmployerLeadDB.id == lead_uuid)
        )
        lead = lead_result.scalar_one_or_none()
        if not lead:
            return ReplyResponse(success=False, error=f"Lead {request.lead_id} not found")

        # Get last email to this lead (for subject and contact)
        last_email_result = await db.execute(
            select(EmailMessageDB)
            .where(EmailMessageDB.lead_id == lead_uuid)
            .order_by(EmailMessageDB.sent_at.desc().nullslast())
            .limit(1)
        )
        last_email = last_email_result.scalar_one_or_none()
        if not last_email:
            return ReplyResponse(success=False, error="No previous emails found for this lead")

        # Get contact
        contact_result = await db.execute(
            select(EmployerContactDB).where(EmployerContactDB.id == last_email.contact_id)
        )
        contact = contact_result.scalar_one_or_none()
        if not contact or not contact.email:
            return ReplyResponse(success=False, error="Contact email not found")

        # Build subject as Re: original
        original_subject = last_email.subject
        if not original_subject.startswith("Re:"):
            subject = f"Re: {original_subject}"
        else:
            subject = original_subject

        # Send email from manager
        delivery = EmailDelivery(from_name="Владислав Наков")

        try:
            msg = delivery._build_mime_message(
                to_email=contact.email,
                to_name=contact.full_name,
                subject=subject,
                body=request.body,
                unsubscribe_url=None,
            )

            message_id = msg["Message-ID"]
            delivery._send_smtp(msg, contact.email)
            sent_at = datetime.now(UTC)

            # Save to database
            # Get or create sequence
            seq_result = await db.execute(
                select(EmailSequenceDB).where(
                    EmailSequenceDB.lead_id == lead_uuid,
                    EmailSequenceDB.contact_id == contact.id,
                    EmailSequenceDB.is_active == True,
                )
            )
            sequence = seq_result.scalar_one_or_none()

            if not sequence:
                # Create new sequence
                from uuid import uuid4
                sequence = EmailSequenceDB(
                    id=uuid4(),
                    lead_id=lead_uuid,
                    contact_id=contact.id,
                    current_step=0,
                    is_active=True,
                )
                db.add(sequence)
                await db.flush()

            # Get next step number
            from sqlalchemy import func
            step_result = await db.execute(
                select(func.coalesce(func.max(EmailMessageDB.step_number), 0))
                .where(EmailMessageDB.sequence_id == sequence.id)
            )
            max_step = step_result.scalar_one()

            # Create email record
            email_msg = EmailMessageDB(
                sequence_id=sequence.id,
                lead_id=lead_uuid,
                contact_id=contact.id,
                email_type="manager_reply",
                subject=subject,
                body=request.body,
                step_number=max_step + 1,
                sent_at=sent_at,
                message_id_header=message_id,
                delivered=True,
            )
            db.add(email_msg)
            await db.commit()

            return ReplyResponse(
                success=True,
                email_id=str(email_msg.id),
                message_id=message_id,
                sent_at=sent_at,
            )

        except Exception as e:
            return ReplyResponse(success=False, error=str(e))


@router.get("", response_model=EmailListResponse)
async def list_emails(
    lead_id: str | None = Query(None, description="Filter by lead ID"),
    email_type: str | None = Query(None, description="Filter by email type"),
    status: str | None = Query(None, description="Filter by status"),
    search: str | None = Query(None, description="Search by company, contact or subject"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
) -> EmailListResponse:
    """List emails with optional filters.

    Args:
        lead_id: Filter by lead
        email_type: Filter by type
        status: Filter by status
        page: Page number
        limit: Items per page

    Returns:
        Paginated list of emails
    """
    from app.storage.repositories.contact_repo import ContactRepository
    from app.storage.repositories.email_repo import EmailRepository
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        email_repo = EmailRepository(db)
        contact_repo = ContactRepository(db)
        lead_repo = LeadRepository(db)

        filters = {}
        if lead_id:
            filters["lead_id"] = lead_id
        if email_type:
            filters["email_type"] = email_type
        if status:
            filters["status"] = status
        if search:
            filters["search"] = search

        emails, total = await email_repo.find_paginated(
            filters=filters,
            page=page,
            limit=limit,
        )

        # Build response with contact and lead info
        items = []
        for email in emails:
            # Get contact info
            contact = await contact_repo.get_by_id(email.contact_id) if email.contact_id else None
            to_email = contact.email if contact and contact.email else "unknown@example.com"
            contact_name = contact.full_name if contact else None

            # Get lead/company info
            lead = await lead_repo.get(str(email.lead_id)) if email.lead_id else None
            company_name = lead.company_name if lead else None

            # Build thread if reply exists
            thread = None
            if email.replied and email.reply_text:
                thread = [
                    ThreadMessage(
                        id=f"{email.id}-out",
                        direction="outbound",
                        subject=email.subject,
                        body=email.body,
                        sent_at=email.sent_at,
                    ),
                    ThreadMessage(
                        id=f"{email.id}-in",
                        direction="inbound",
                        subject=f"Re: {email.subject}",
                        body=email.reply_text,
                        sent_at=email.replied_at,
                    ),
                ]

            items.append(
                EmailResponse(
                    id=str(email.id),
                    lead_id=str(email.lead_id),
                    company_name=company_name,
                    contact_name=contact_name,
                    contact_email=to_email,
                    to_email=to_email,
                    subject=email.subject,
                    body=email.body,
                    email_type=email.email_type.value if hasattr(email.email_type, 'value') else email.email_type,
                    status=_get_email_status(email),
                    sent_at=email.sent_at,
                    opened_at=email.opened_at,
                    clicked_at=getattr(email, 'clicked_at', None),
                    replied_at=email.replied_at,
                    reply_text=email.reply_text,
                    thread=thread,
                )
            )

        pages = (total + limit - 1) // limit if total > 0 else 1
        return EmailListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )


@router.get("/stats", response_model=EmailStatsResponse)
async def get_email_stats(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> EmailStatsResponse:
    """Get email statistics.

    Args:
        start_date: Start of date range
        end_date: End of date range

    Returns:
        Email statistics
    """
    from app.services.analytics_service import AnalyticsService

    async with async_session_factory() as db:
        analytics = AnalyticsService(db=db)

        perf = await analytics.get_email_performance(
            start_date=start_date,
            end_date=end_date,
        )

        return EmailStatsResponse(
            total_sent=perf.total_sent,
            total_delivered=perf.total_delivered,
            total_opened=perf.total_opened,
            total_clicked=perf.total_clicked,
            total_replied=perf.total_replied,
            total_bounced=perf.total_bounced,
            open_rate=perf.open_rate,
            click_rate=perf.click_rate,
            reply_rate=perf.reply_rate,
            bounce_rate=perf.bounce_rate,
        )


@router.get("/notifications/counts", response_model=NotificationCountsResponse)
async def get_notification_counts() -> NotificationCountsResponse:
    """Get notification counts for dashboard badges.

    Returns counts of:
    - Unread replies (replies received in last 24h)
    - New bounces (bounces in last 24h)
    - Pending handoffs (from handoffs API)

    Returns:
        Notification counts
    """
    from datetime import timedelta

    from sqlalchemy import func, select

    from app.models.db import EmailMessageDB, ManagerHandoffDB

    async with async_session_factory() as db:
        now = datetime.now(UTC)
        last_24h = now - timedelta(hours=24)

        # Count replies in last 24h
        replies_result = await db.execute(
            select(func.count(EmailMessageDB.id)).where(
                EmailMessageDB.replied == True,
                EmailMessageDB.replied_at >= last_24h,
            )
        )
        unread_replies = replies_result.scalar_one() or 0

        # Count bounces in last 24h
        bounces_result = await db.execute(
            select(func.count(EmailMessageDB.id)).where(
                EmailMessageDB.bounced == True,
                EmailMessageDB.sent_at >= last_24h,
            )
        )
        new_bounces = bounces_result.scalar_one() or 0

        # Count pending handoffs
        try:
            handoffs_result = await db.execute(
                select(func.count(ManagerHandoffDB.id)).where(
                    ManagerHandoffDB.status == "pending",
                )
            )
            pending_handoffs = handoffs_result.scalar_one() or 0
        except Exception:
            # ManagerHandoffDB may not exist in all setups
            pending_handoffs = 0

        total_unread = unread_replies + new_bounces + pending_handoffs

        return NotificationCountsResponse(
            unread_replies=unread_replies,
            new_bounces=new_bounces,
            pending_handoffs=pending_handoffs,
            total_unread=total_unread,
        )


class ThreadResponse(BaseModel):
    """Email thread response."""

    lead_id: str
    company_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    thread: list[ThreadMessage]


@router.get("/thread/{lead_id}", response_model=ThreadResponse)
async def get_email_thread(lead_id: str) -> ThreadResponse:
    """Get full email thread for a lead.

    Returns all emails (outbound and inbound) for a lead, sorted by time.

    Args:
        lead_id: Lead ID

    Returns:
        Thread with all messages
    """
    from uuid import UUID

    from sqlalchemy import select

    from app.models.db import EmailMessageDB, EmployerContactDB, EmployerLeadDB

    async with async_session_factory() as db:
        # Get lead info
        try:
            lead_uuid = UUID(lead_id)
        except ValueError:
            raise HTTPException(400, f"Invalid lead_id: {lead_id}")

        lead_result = await db.execute(
            select(EmployerLeadDB).where(EmployerLeadDB.id == lead_uuid)
        )
        lead = lead_result.scalar_one_or_none()
        if not lead:
            raise HTTPException(404, f"Lead {lead_id} not found")

        # Get all emails for this lead
        emails_result = await db.execute(
            select(EmailMessageDB)
            .where(EmailMessageDB.lead_id == lead_uuid)
            .order_by(EmailMessageDB.sent_at.asc().nullslast())
        )
        emails = list(emails_result.scalars().all())

        # Get contact info from first email
        contact_name = None
        contact_email = None
        if emails and emails[0].contact_id:
            contact_result = await db.execute(
                select(EmployerContactDB).where(
                    EmployerContactDB.id == emails[0].contact_id
                )
            )
            contact = contact_result.scalar_one_or_none()
            if contact:
                contact_name = contact.full_name
                contact_email = contact.email

        # Build thread with both outbound and inbound messages
        thread: list[ThreadMessage] = []
        for email in emails:
            # Add outbound message
            if email.sent_at:
                thread.append(
                    ThreadMessage(
                        id=f"{email.id}-out",
                        direction="outbound",
                        subject=email.subject,
                        body=email.body,
                        sent_at=email.sent_at,
                    )
                )

            # Add inbound reply if exists
            if email.replied and email.reply_text:
                thread.append(
                    ThreadMessage(
                        id=f"{email.id}-in",
                        direction="inbound",
                        subject=f"Re: {email.subject}",
                        body=email.reply_text,
                        sent_at=email.replied_at,
                    )
                )

        # Sort by time
        thread.sort(key=lambda m: m.sent_at or datetime.min.replace(tzinfo=UTC))

        return ThreadResponse(
            lead_id=lead_id,
            company_name=lead.company_name,
            contact_name=contact_name,
            contact_email=contact_email,
            thread=thread,
        )


@router.get("/{email_id}", response_model=EmailResponse)
async def get_email(email_id: str) -> EmailResponse:
    """Get email by ID.

    Args:
        email_id: Email ID

    Returns:
        Email details
    """
    from app.storage.repositories.contact_repo import ContactRepository
    from app.storage.repositories.email_repo import EmailRepository
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        email_repo = EmailRepository(db)
        contact_repo = ContactRepository(db)
        lead_repo = LeadRepository(db)
        email = await email_repo.get(email_id)

        if not email:
            raise HTTPException(404, f"Email {email_id} not found")

        # Get contact info
        contact = await contact_repo.get_by_id(email.contact_id) if email.contact_id else None
        to_email = contact.email if contact and contact.email else "unknown@example.com"
        contact_name = contact.full_name if contact else None

        # Get lead/company info
        lead = await lead_repo.get(str(email.lead_id)) if email.lead_id else None
        company_name = lead.company_name if lead else None

        # Build thread if reply exists
        thread = None
        if email.replied and email.reply_text:
            thread = [
                ThreadMessage(
                    id=f"{email.id}-out",
                    direction="outbound",
                    subject=email.subject,
                    body=email.body,
                    sent_at=email.sent_at,
                ),
                ThreadMessage(
                    id=f"{email.id}-in",
                    direction="inbound",
                    subject=f"Re: {email.subject}",
                    body=email.reply_text,
                    sent_at=email.replied_at,
                ),
            ]

        return EmailResponse(
            id=str(email.id),
            lead_id=str(email.lead_id),
            company_name=company_name,
            contact_name=contact_name,
            contact_email=to_email,
            to_email=to_email,
            subject=email.subject,
            body=email.body,
            email_type=email.email_type.value if hasattr(email.email_type, 'value') else email.email_type,
            status=_get_email_status(email),
            sent_at=email.sent_at,
            opened_at=email.opened_at,
            clicked_at=getattr(email, 'clicked_at', None),
            replied_at=email.replied_at,
            reply_text=email.reply_text,
            thread=thread,
        )


@router.post("", response_model=EmailResponse, status_code=201)
async def send_email(request: SendEmailRequest) -> EmailResponse:
    """Send an email.

    Args:
        request: Email send request

    Returns:
        Sent email info
    """
    from app.services.compliance_service import ComplianceService
    from app.services.email_service import EmailService
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        # Check lead exists
        lead_repo = LeadRepository(db)
        lead = await lead_repo.get(request.lead_id)

        if not lead:
            raise HTTPException(404, f"Lead {request.lead_id} not found")

        # Check compliance
        compliance = ComplianceService(db)
        if not await compliance.can_send_email(lead, None, request.to_email):
            raise HTTPException(400, "Cannot send email: compliance check failed")

        # Send email
        try:
            email_type = EmailType(request.email_type)
        except ValueError:
            email_type = EmailType.FIRST_TOUCH

        email_service = EmailService(db=db)
        email = await email_service.send_email(
            lead_id=request.lead_id,
            to_email=request.to_email,
            subject=request.subject,
            body=request.body,
            email_type=email_type,
        )

        if not email:
            raise HTTPException(500, "Failed to send email")

        return EmailResponse(
            id=str(email.id),
            lead_id=str(email.lead_id),
            company_name=lead.company_name if lead else None,
            contact_name=None,
            contact_email=request.to_email,
            to_email=request.to_email,
            subject=email.subject,
            body=email.body,
            email_type=email.email_type.value if hasattr(email.email_type, 'value') else str(email.email_type),
            status=email.delivery_status or "sent",
            sent_at=email.sent_at,
            opened_at=None,
            clicked_at=None,
            replied_at=None,
        )


@router.post("/preview", response_model=PreviewEmailResponse)
async def preview_email(request: PreviewEmailRequest) -> PreviewEmailResponse:
    """Preview email without sending.

    Args:
        request: Preview request

    Returns:
        Email preview with quality check
    """
    from app.agents.email_copy_agent import EmailCopyAgent
    from app.email.quality_gate import QualityGate
    from app.llm.router import get_router
    from app.models.domain import AgentTask
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        lead = await lead_repo.get(request.lead_id)

        if not lead:
            raise HTTPException(404, f"Lead {request.lead_id} not found")

        llm_router = get_router()
        email_agent = EmailCopyAgent(llm_router=llm_router, db=db)

        try:
            email_type = EmailType(request.email_type)
        except ValueError:
            email_type = EmailType.FIRST_TOUCH

        task = AgentTask(
            agent_name="email_copy",
            input_data={
                "lead_id": request.lead_id,
                "email_type": email_type.value,
            },
        )

        result = await email_agent.execute(task)

        if not result.success:
            raise HTTPException(500, f"Failed to generate email: {result.error}")

        subject = result.data.get("subject", "")
        body = result.data.get("body", "")

        # Run quality check
        quality_gate = QualityGate()
        issues = quality_gate.check(
            subject=subject,
            body=body,
            email_type=email_type,
            company_name=lead.company_name,
        )

        return PreviewEmailResponse(
            subject=subject,
            body=body,
            word_count=len(body.split()),
            quality_check={
                "passed": len(issues) == 0,
                "issues": issues,
            },
        )


async def _get_or_create_test_entities(db, to_email: str):
    """Get or create test lead, contact, and sequence for test emails.

    Args:
        db: Database session
        to_email: Recipient email

    Returns:
        Tuple of (lead_id, contact_id, sequence_id)
    """
    from uuid import UUID
    from sqlalchemy import select
    from app.models.db import EmployerLeadDB, EmployerContactDB, EmailSequenceDB

    # Find or create test lead
    result = await db.execute(
        select(EmployerLeadDB).where(EmployerLeadDB.company_name == TEST_LEAD_COMPANY)
    )
    lead = result.scalar_one_or_none()

    if not lead:
        from uuid import uuid4
        lead = EmployerLeadDB(
            id=uuid4(),
            company_name=TEST_LEAD_COMPANY,
            source="test",
            status="lead_found",
        )
        db.add(lead)
        await db.flush()

    # Find or create contact for this email
    result = await db.execute(
        select(EmployerContactDB).where(
            EmployerContactDB.lead_id == lead.id,
            EmployerContactDB.email == to_email,
        )
    )
    contact = result.scalar_one_or_none()

    if not contact:
        from uuid import uuid4
        contact = EmployerContactDB(
            id=uuid4(),
            lead_id=lead.id,
            full_name=TEST_CONTACT_NAME,
            email=to_email,
            role="other",
        )
        db.add(contact)
        await db.flush()

    # Find or create sequence
    result = await db.execute(
        select(EmailSequenceDB).where(
            EmailSequenceDB.lead_id == lead.id,
            EmailSequenceDB.contact_id == contact.id,
            EmailSequenceDB.is_active == True,
        )
    )
    sequence = result.scalar_one_or_none()

    if not sequence:
        from uuid import uuid4
        sequence = EmailSequenceDB(
            id=uuid4(),
            lead_id=lead.id,
            contact_id=contact.id,
            current_step=0,
            is_active=True,
        )
        db.add(sequence)
        await db.flush()

    return lead.id, contact.id, sequence.id


@router.post("/test", response_model=TestEmailResponse)
async def send_test_email(request: TestEmailRequest) -> TestEmailResponse:
    """Send a test email manually.

    This endpoint allows sending test emails without requiring a lead.
    Use this to test email delivery to yourself before campaigns.
    The email is saved to email_messages table for tracking and webhook matching.

    Args:
        request: Test email request with recipient, subject, and body

    Returns:
        Result of the send attempt with DB record ID
    """
    from app.email.delivery import EmailDelivery
    from app.models.db import EmailMessageDB

    delivery = EmailDelivery(from_name=request.from_name)

    try:
        # Build and send email directly via SMTP
        msg = delivery._build_mime_message(
            to_email=request.to_email,
            to_name=request.to_email.split("@")[0],
            subject=request.subject,
            body=request.body,
            unsubscribe_url=None,
        )

        message_id = msg["Message-ID"]
        delivery._send_smtp(msg, request.to_email)
        sent_at = datetime.now(UTC)

        # Save to database for webhook matching
        email_db_id = None
        try:
            async with async_session_factory() as db:
                lead_id, contact_id, sequence_id = await _get_or_create_test_entities(
                    db, request.to_email
                )

                # Get next step number
                from sqlalchemy import select, func
                result = await db.execute(
                    select(func.coalesce(func.max(EmailMessageDB.step_number), 0))
                    .where(EmailMessageDB.sequence_id == sequence_id)
                )
                max_step = result.scalar_one()

                email_msg = EmailMessageDB(
                    sequence_id=sequence_id,
                    lead_id=lead_id,
                    contact_id=contact_id,
                    email_type="test",
                    subject=request.subject,
                    body=request.body,
                    step_number=max_step + 1,
                    sent_at=sent_at,
                    message_id_header=message_id,
                    delivered=True,
                )
                db.add(email_msg)
                await db.commit()
                email_db_id = str(email_msg.id)
        except Exception as db_error:
            # Log but don't fail - email was sent successfully
            import logging
            logging.getLogger(__name__).warning(
                f"Failed to save test email to DB: {db_error}"
            )

        return TestEmailResponse(
            success=True,
            message_id=message_id,
            email_db_id=email_db_id,
            sent_at=sent_at,
        )

    except Exception as e:
        return TestEmailResponse(
            success=False,
            error=str(e),
        )


@router.get("/{email_id}/tracking")
async def get_email_tracking(email_id: str) -> dict[str, Any]:
    """Get email tracking data.

    Args:
        email_id: Email ID

    Returns:
        Tracking information
    """
    from app.storage.repositories.email_repo import EmailRepository

    async with async_session_factory() as db:
        email_repo = EmailRepository(db)
        email = await email_repo.get(email_id)

        if not email:
            raise HTTPException(404, f"Email {email_id} not found")

        return {
            "email_id": email_id,
            "sent_at": email.sent_at.isoformat() if email.sent_at else None,
            "delivered": email.delivered or False,
            "opened": email.opened or False,
            "opened_at": email.opened_at.isoformat() if email.opened_at else None,
            "clicked": email.clicked or False,
            "replied": email.replied or False,
            "replied_at": email.replied_at.isoformat() if email.replied_at else None,
            "bounced": email.bounced or False,
        }


@router.post("/{email_id}/resend")
async def resend_email(email_id: str) -> dict[str, Any]:
    """Resend an email.

    Args:
        email_id: Email ID

    Returns:
        Resend confirmation
    """
    from app.services.email_service import EmailService
    from app.storage.repositories.email_repo import EmailRepository

    async with async_session_factory() as db:
        email_repo = EmailRepository(db)
        email = await email_repo.get(email_id)

        if not email:
            raise HTTPException(404, f"Email {email_id} not found")

        # Can only resend bounced emails
        if not email.bounced:
            raise HTTPException(
                400,
                "Cannot resend email: only bounced emails can be resent",
            )

        # Get recipient email from contact
        from app.storage.repositories.contact_repo import ContactRepository
        contact_repo = ContactRepository(db)
        contact = await contact_repo.get_by_id(email.contact_id) if email.contact_id else None
        if not contact or not contact.email:
            raise HTTPException(400, "Cannot resend: contact email not found")

        email_service = EmailService(db=db)
        new_email = await email_service.send_email(
            lead_id=str(email.lead_id),
            to_email=contact.email,
            subject=email.subject,
            body=email.body,
            email_type=email.email_type,
        )

        return {
            "message": "Email resent",
            "original_email_id": email_id,
            "new_email_id": new_email.id if new_email else None,
        }
