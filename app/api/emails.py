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
    sent_at: datetime | None = None
    error: str | None = None


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


@router.post("/test", response_model=TestEmailResponse)
async def send_test_email(request: TestEmailRequest) -> TestEmailResponse:
    """Send a test email manually.

    This endpoint allows sending test emails without requiring a lead.
    Use this to test email delivery to yourself before campaigns.

    Args:
        request: Test email request with recipient, subject, and body

    Returns:
        Result of the send attempt
    """
    from app.email.delivery import EmailDelivery

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

        return TestEmailResponse(
            success=True,
            message_id=message_id,
            sent_at=datetime.now(UTC),
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
