"""Webhook API endpoints.

Приём внешних событий (bounces, opens, clicks, replies).
"""

import hashlib
import hmac
import logging
from datetime import datetime, timezone

UTC = timezone.utc
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from app.config import settings
from app.storage.database import async_session_factory

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


# Webhook payload models
class EmailEventPayload(BaseModel):
    """Email event webhook payload."""

    event_type: str  # delivered, bounced, opened, clicked, complained
    email_id: str | None = None
    message_id: str | None = None
    recipient: str | None = None
    timestamp: datetime | None = None
    metadata: dict[str, Any] | None = None


class BouncePayload(BaseModel):
    """Bounce notification payload."""

    email: str
    bounce_type: str  # hard, soft
    bounce_code: str | None = None
    diagnostic: str | None = None
    message_id: str | None = None


class UnsubscribePayload(BaseModel):
    """Unsubscribe request payload."""

    email: str
    list_id: str | None = None
    reason: str | None = None


class ReplyPayload(BaseModel):
    """Email reply webhook payload."""

    from_email: str
    to_email: str
    subject: str
    body: str
    in_reply_to: str | None = None
    message_id: str | None = None
    received_at: datetime | None = None


def verify_webhook_signature(
    payload: bytes,
    signature: str | None,
    secret: str,
) -> bool:
    """Verify webhook signature.

    Args:
        payload: Raw request body
        signature: Signature from header
        secret: Webhook secret

    Returns:
        True if signature is valid
    """
    if not signature:
        return False

    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


@router.post("/email-events")
async def handle_email_event(
    payload: EmailEventPayload,
    request: Request,
    x_webhook_signature: str | None = Header(None),
) -> dict[str, str]:
    """Handle email delivery events (SendGrid, Mailgun, etc.).

    Args:
        payload: Event payload
        request: Raw request for signature verification
        x_webhook_signature: Webhook signature header

    Returns:
        Acknowledgment
    """
    # Verify signature in production
    # if settings.webhook_secret:
    #     body = await request.body()
    #     if not verify_webhook_signature(body, x_webhook_signature, settings.webhook_secret):
    #         raise HTTPException(401, "Invalid signature")

    logger.info(f"Received email event: {payload.event_type} for {payload.email_id}")

    # Route to appropriate handler
    handlers = {
        "delivered": _handle_delivered,
        "bounced": _handle_bounced,
        "opened": _handle_opened,
        "clicked": _handle_clicked,
        "complained": _handle_complained,
    }

    handler = handlers.get(payload.event_type)
    if handler:
        await handler(payload)
    else:
        logger.warning(f"Unknown event type: {payload.event_type}")

    return {"status": "received"}


async def _handle_delivered(payload: EmailEventPayload) -> None:
    """Handle email delivered event."""
    from workers.analysis_tasks import track_email_delivery

    if payload.email_id:
        track_email_delivery.delay(
            email_id=payload.email_id,
            status="delivered",
        )


async def _handle_bounced(payload: EmailEventPayload) -> None:
    """Handle email bounced event."""
    from workers.analysis_tasks import process_bounce

    if payload.email_id:
        metadata = payload.metadata or {}
        process_bounce.delay(
            email_id=payload.email_id,
            bounce_type=metadata.get("bounce_type", "soft"),
            bounce_reason=metadata.get("reason"),
        )


async def _handle_opened(payload: EmailEventPayload) -> None:
    """Handle email opened event."""
    from workers.analysis_tasks import track_email_open

    if payload.email_id:
        track_email_open.delay(email_id=payload.email_id)


async def _handle_clicked(payload: EmailEventPayload) -> None:
    """Handle email link clicked event."""
    from workers.analysis_tasks import track_email_click

    if payload.email_id:
        metadata = payload.metadata or {}
        track_email_click.delay(
            email_id=payload.email_id,
            link_url=metadata.get("url"),
        )


async def _handle_complained(payload: EmailEventPayload) -> None:
    """Handle spam complaint event."""
    from app.services.compliance_service import ComplianceService

    if payload.recipient:
        async with async_session_factory() as db:
            compliance = ComplianceService(db)
            # Note: add_to_blacklist doesn't exist yet, just log for now
            logger.warning(f"Spam complaint from {payload.recipient} - should be blacklisted")


@router.post("/bounce")
async def handle_bounce(payload: BouncePayload) -> dict[str, str]:
    """Handle bounce notification.

    Args:
        payload: Bounce data

    Returns:
        Acknowledgment
    """
    logger.info(f"Bounce received: {payload.email} ({payload.bounce_type})")

    if payload.bounce_type == "hard":
        # Note: should blacklist email, logging for now
        logger.warning(f"Hard bounce for {payload.email} - should be blacklisted: {payload.diagnostic or 'Unknown'}")

    # Find and update email if message_id provided
    if payload.message_id:
        from app.storage.repositories.email_repo import EmailRepository

        async with async_session_factory() as db:
            email_repo = EmailRepository(db)
            email = await email_repo.find_by_message_id(payload.message_id)

            if email:
                from workers.analysis_tasks import process_bounce

                process_bounce.delay(
                    email_id=email.id,
                    bounce_type=payload.bounce_type,
                    bounce_reason=payload.diagnostic,
                )

    return {"status": "processed"}


@router.post("/unsubscribe")
async def handle_unsubscribe(payload: UnsubscribePayload) -> dict[str, str]:
    """Handle unsubscribe request.

    Args:
        payload: Unsubscribe data

    Returns:
        Acknowledgment
    """
    logger.info(f"Unsubscribe request: {payload.email}")

    # Note: should add to opt-out list, logging for now
    logger.info(f"User {payload.email} unsubscribed: {payload.reason or 'User requested'}")

    return {"status": "unsubscribed"}


@router.post("/reply")
async def handle_reply(
    payload: ReplyPayload,
    request: Request,
    x_webhook_signature: str | None = Header(None),
) -> dict[str, str]:
    """Handle incoming email reply.

    Args:
        payload: Reply data
        request: Raw request
        x_webhook_signature: Webhook signature

    Returns:
        Acknowledgment
    """
    logger.info(f"Reply received from {payload.from_email}")

    from app.storage.repositories.email_repo import EmailRepository

    async with async_session_factory() as db:
        email_repo = EmailRepository(db)

        # Find original email by in_reply_to or subject matching
        original_email = None

        if payload.in_reply_to:
            original_email = await email_repo.find_by_message_id(payload.in_reply_to)

        if not original_email and payload.subject:
            # Try to match by subject (remove Re: prefix)
            clean_subject = payload.subject
            for prefix in ["Re:", "RE:", "Ответ:", "re:"]:
                if clean_subject.startswith(prefix):
                    clean_subject = clean_subject[len(prefix):].strip()
                    break

            original_email = await email_repo.find_by_subject_and_recipient(
                subject=clean_subject,
                recipient=payload.from_email,
            )

        if original_email:
            # Trigger analysis
            from workers.analysis_tasks import analyze_reply

            analyze_reply.delay(
                email_id=original_email.id,
                lead_id=original_email.lead_id,
                reply_text=payload.body,
            )

            # Update email with reply timestamp
            original_email.replied_at = payload.received_at or datetime.now(UTC)
            await email_repo.update(original_email)

            logger.info(f"Matched reply to email {original_email.id}")
        else:
            logger.warning(
                f"Could not match reply from {payload.from_email} "
                f"to any outgoing email"
            )

    return {"status": "processed"}


@router.get("/tracking/open/{email_id}")
async def track_open(email_id: str) -> dict[str, str]:
    """Tracking pixel endpoint for email opens.

    Args:
        email_id: Email ID

    Returns:
        Empty response (tracking pixel)
    """
    from fastapi.responses import Response

    from workers.analysis_tasks import track_email_open

    # Track the open
    track_email_open.delay(email_id=email_id)

    # Return 1x1 transparent GIF
    gif_data = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"

    return Response(
        content=gif_data,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/tracking/click/{email_id}")
async def track_click(
    email_id: str,
    url: str,
) -> dict[str, str]:
    """Track link click and redirect.

    Args:
        email_id: Email ID
        url: Target URL

    Returns:
        Redirect response
    """
    from fastapi.responses import RedirectResponse

    from workers.analysis_tasks import track_email_click

    # Track the click
    track_email_click.delay(email_id=email_id, link_url=url)

    # Redirect to target URL
    return RedirectResponse(url=url, status_code=302)


@router.post("/hh-callback")
async def handle_hh_callback(
    request: Request,
) -> dict[str, str]:
    """Handle hh.ru API callbacks.

    Args:
        request: Callback request

    Returns:
        Acknowledgment
    """
    body = await request.json()
    logger.info(f"HH callback received: {body}")

    # Process based on callback type
    # This would handle responses from hh.ru API

    return {"status": "received"}
