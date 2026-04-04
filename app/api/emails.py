"""Email API endpoints.

Управление email отправками и отслеживание.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.enums import EmailType
from app.storage.database import async_session_factory

router = APIRouter(prefix="/emails", tags=["emails"])


# Request/Response models
class EmailResponse(BaseModel):
    """Email response model."""

    id: str
    lead_id: str
    to_email: str
    subject: str
    email_type: str
    status: str
    sent_at: datetime | None = None
    opened_at: datetime | None = None
    clicked_at: datetime | None = None
    replied_at: datetime | None = None


class EmailListResponse(BaseModel):
    """Email list response."""

    items: list[EmailResponse]
    total: int
    page: int
    page_size: int


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


@router.get("", response_model=EmailListResponse)
async def list_emails(
    lead_id: str | None = Query(None, description="Filter by lead ID"),
    email_type: str | None = Query(None, description="Filter by email type"),
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> EmailListResponse:
    """List emails with optional filters.

    Args:
        lead_id: Filter by lead
        email_type: Filter by type
        status: Filter by status
        page: Page number
        page_size: Items per page

    Returns:
        Paginated list of emails
    """
    from app.storage.repositories.email_repo import EmailRepository

    async with async_session_factory() as db:
        email_repo = EmailRepository(db)

        filters = {}
        if lead_id:
            filters["lead_id"] = lead_id
        if email_type:
            filters["email_type"] = email_type
        if status:
            filters["status"] = status

        emails, total = await email_repo.find_paginated(
            filters=filters,
            page=page,
            page_size=page_size,
        )

        return EmailListResponse(
            items=[
                EmailResponse(
                    id=email.id,
                    lead_id=email.lead_id,
                    to_email=email.to_email,
                    subject=email.subject,
                    email_type=email.email_type.value if hasattr(email.email_type, 'value') else email.email_type,
                    status=email.delivery_status or "pending",
                    sent_at=email.sent_at,
                    opened_at=email.opened_at,
                    clicked_at=email.clicked_at,
                    replied_at=email.replied_at,
                )
                for email in emails
            ],
            total=total,
            page=page,
            page_size=page_size,
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
    from app.storage.repositories.email_repo import EmailRepository

    async with async_session_factory() as db:
        email_repo = EmailRepository(db)
        email = await email_repo.get(email_id)

        if not email:
            raise HTTPException(404, f"Email {email_id} not found")

        return EmailResponse(
            id=email.id,
            lead_id=email.lead_id,
            to_email=email.to_email,
            subject=email.subject,
            email_type=email.email_type.value if hasattr(email.email_type, 'value') else email.email_type,
            status=email.delivery_status or "pending",
            sent_at=email.sent_at,
            opened_at=email.opened_at,
            clicked_at=email.clicked_at,
            replied_at=email.replied_at,
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
        compliance = ComplianceService()
        if not await compliance.can_send_email(request.lead_id, request.to_email):
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
            id=email.id,
            lead_id=email.lead_id,
            to_email=email.to_email,
            subject=email.subject,
            email_type=email.email_type.value,
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
            "delivered": email.delivery_status == "delivered",
            "opened": email.opened_at is not None,
            "opened_at": email.opened_at.isoformat() if email.opened_at else None,
            "clicked": email.clicked_at is not None,
            "clicked_at": email.clicked_at.isoformat() if email.clicked_at else None,
            "replied": email.replied_at is not None,
            "replied_at": email.replied_at.isoformat() if email.replied_at else None,
            "bounced": email.delivery_status == "bounced",
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

        if email.delivery_status not in ["failed", "bounced"]:
            raise HTTPException(
                400,
                f"Cannot resend email with status: {email.delivery_status}",
            )

        email_service = EmailService(db=db)
        new_email = await email_service.send_email(
            lead_id=email.lead_id,
            to_email=email.to_email,
            subject=email.subject,
            body=email.body,
            email_type=email.email_type,
        )

        return {
            "message": "Email resent",
            "original_email_id": email_id,
            "new_email_id": new_email.id if new_email else None,
        }
