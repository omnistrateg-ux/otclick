"""Deliverability API endpoints.

Endpoints for monitoring email deliverability metrics.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.outbound_service import OutboundService, CampaignHealth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deliverability", tags=["deliverability"])


# ============================================================================
# Response Models
# ============================================================================


class DomainMetricsResponse(BaseModel):
    """Domain deliverability metrics."""

    domain: str
    period_days: int
    total_sent: int
    total_delivered: int
    total_bounced: int
    delivery_rate: float
    bounce_rate: float


class CampaignMetricsResponse(BaseModel):
    """Campaign deliverability metrics."""

    campaign_id: str
    period_days: int
    total_sent: int
    total_delivered: int
    total_bounced: int
    total_complained: int
    delivery_rate: float
    bounce_rate: float
    complaint_rate: float
    is_paused: bool
    pause_reason: str | None
    daily_metrics: list[dict[str, Any]]


class CampaignHealthResponse(BaseModel):
    """Campaign health status."""

    campaign_id: str
    total_sent: int
    total_delivered: int
    total_bounced: int
    total_complained: int
    bounce_rate: float
    complaint_rate: float
    is_healthy: bool
    should_pause: bool
    pause_reason: str | None


class ValidationRequest(BaseModel):
    """Pre-send validation request."""

    lead_id: str
    contact_email: str
    subject: str
    body: str


class ValidationResponse(BaseModel):
    """Pre-send validation response."""

    status: str
    can_send: bool
    errors: list[str]
    warnings: list[str]
    checks_passed: list[str]


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/domain/{domain}", response_model=DomainMetricsResponse)
async def get_domain_metrics(
    domain: str,
    days: int = Query(default=7, ge=1, le=30),
) -> DomainMetricsResponse:
    """Get deliverability metrics for a specific domain.

    Args:
        domain: Email domain to check
        days: Number of days to look back (1-30)

    Returns:
        Domain metrics
    """
    outbound = OutboundService()
    metrics = await outbound.get_domain_metrics(domain, days=days)

    return DomainMetricsResponse(**metrics)


@router.get("/campaign/{campaign_id}", response_model=CampaignMetricsResponse)
async def get_campaign_metrics(
    campaign_id: str,
    days: int = Query(default=7, ge=1, le=30),
) -> CampaignMetricsResponse:
    """Get deliverability metrics for a campaign.

    Args:
        campaign_id: Campaign ID
        days: Number of days to look back (1-30)

    Returns:
        Campaign metrics with daily breakdown
    """
    outbound = OutboundService()
    metrics = await outbound.get_campaign_metrics(campaign_id, days=days)

    return CampaignMetricsResponse(**metrics)


@router.get("/campaign/{campaign_id}/health", response_model=CampaignHealthResponse)
async def get_campaign_health(
    campaign_id: str,
) -> CampaignHealthResponse:
    """Get campaign health status.

    Checks if campaign should be paused based on bounce/complaint rates.

    Args:
        campaign_id: Campaign ID

    Returns:
        Campaign health status
    """
    outbound = OutboundService()
    health = await outbound.check_campaign_health(campaign_id)

    return CampaignHealthResponse(
        campaign_id=health.campaign_id,
        total_sent=health.total_sent,
        total_delivered=health.total_delivered,
        total_bounced=health.total_bounced,
        total_complained=health.total_complained,
        bounce_rate=health.bounce_rate,
        complaint_rate=health.complaint_rate,
        is_healthy=health.is_healthy,
        should_pause=health.should_pause,
        pause_reason=health.pause_reason,
    )


@router.post("/campaign/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    reason: str = Query(default="manual_pause"),
) -> dict[str, Any]:
    """Manually pause a campaign.

    Args:
        campaign_id: Campaign ID
        reason: Pause reason

    Returns:
        Pause result
    """
    from app.storage.redis import get_redis

    redis = await get_redis()
    paused_key = f"campaign:paused:{campaign_id}"

    await redis.set(paused_key, reason, ex=86400 * 7)  # 7 days

    logger.warning(f"[API] Campaign manually paused | campaign={campaign_id} | reason={reason}")

    return {
        "success": True,
        "campaign_id": campaign_id,
        "paused": True,
        "reason": reason,
    }


@router.post("/campaign/{campaign_id}/unpause")
async def unpause_campaign(
    campaign_id: str,
) -> dict[str, Any]:
    """Unpause a campaign.

    Args:
        campaign_id: Campaign ID

    Returns:
        Unpause result
    """
    from app.storage.redis import get_redis

    redis = await get_redis()
    paused_key = f"campaign:paused:{campaign_id}"

    deleted = await redis.delete(paused_key)

    logger.info(f"[API] Campaign unpaused | campaign={campaign_id}")

    return {
        "success": True,
        "campaign_id": campaign_id,
        "paused": False,
        "was_paused": deleted > 0,
    }


@router.post("/validate", response_model=ValidationResponse)
async def validate_pre_send(
    request: ValidationRequest,
) -> ValidationResponse:
    """Validate email before sending.

    Performs comprehensive pre-send validation without actually sending.

    Args:
        request: Validation request with lead, contact, and email content

    Returns:
        Validation result with errors and warnings
    """
    from app.storage.database import async_session_factory
    from app.storage.repositories.lead_repo import LeadRepository
    from app.storage.repositories.contact_repo import ContactRepository

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        contact_repo = ContactRepository(db)

        lead = await lead_repo.get(request.lead_id)
        if not lead:
            raise HTTPException(404, f"Lead {request.lead_id} not found")

        # Find contact by email
        contacts = await contact_repo.find_by_lead(request.lead_id)
        contact = next(
            (c for c in contacts if c.email == request.contact_email),
            None,
        )
        if not contact:
            raise HTTPException(404, f"Contact {request.contact_email} not found")

        outbound = OutboundService()
        result = await outbound.validate_pre_send(
            lead=lead,
            contact=contact,
            subject=request.subject,
            body=request.body,
        )

        return ValidationResponse(
            status=result.status.value,
            can_send=result.can_send,
            errors=result.errors,
            warnings=result.warnings,
            checks_passed=result.checks_passed,
        )


@router.get("/throttle/status")
async def get_throttle_status(
    sender_email: str = Query(...),
    recipient_domain: str = Query(default=""),
    campaign_id: str = Query(default=None),
) -> dict[str, Any]:
    """Check current throttle status.

    Args:
        sender_email: Sender email
        recipient_domain: Recipient domain (optional)
        campaign_id: Campaign ID (optional)

    Returns:
        Throttle status
    """
    outbound = OutboundService()
    result = await outbound.check_throttle(
        sender_email=sender_email,
        recipient_domain=recipient_domain,
        campaign_id=campaign_id,
    )

    return {
        "allowed": result.allowed,
        "reason": result.reason,
        "retry_after_seconds": result.retry_after_seconds,
        "current_rate": result.current_rate,
        "limit": result.limit,
    }
