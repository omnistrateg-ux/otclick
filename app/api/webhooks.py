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


class ResendInboundEmail(BaseModel):
    """Resend inbound webhook payload.

    https://resend.com/docs/dashboard/webhooks/inbound
    """

    # Resend uses 'from' but it's a Python keyword
    from_: str | None = None
    to: list[str] | str | None = None
    subject: str | None = None
    text: str | None = None
    html: str | None = None
    headers: list[dict[str, str]] | None = None
    attachments: list[dict] | None = None

    class Config:
        populate_by_name = True

    @property
    def in_reply_to(self) -> str | None:
        """Extract In-Reply-To header."""
        if not self.headers:
            return None
        for h in self.headers:
            if h.get("name", "").lower() == "in-reply-to":
                return h.get("value")
        return None

    @property
    def message_id(self) -> str | None:
        """Extract Message-ID header."""
        if not self.headers:
            return None
        for h in self.headers:
            if h.get("name", "").lower() == "message-id":
                return h.get("value")
        return None

    @property
    def references(self) -> list[str]:
        """Extract References header (chain of message IDs)."""
        if not self.headers:
            return []
        for h in self.headers:
            if h.get("name", "").lower() == "references":
                # References is space-separated list of message IDs
                return h.get("value", "").split()
        return []


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


async def _verify_signature(request: Request, signature: str | None) -> None:
    """Verify webhook signature if required.

    Args:
        request: HTTP request
        signature: Signature from header

    Raises:
        HTTPException: If signature verification fails
    """
    if not settings.webhook_signature_required:
        return

    webhook_secret = settings.webhook_secret
    if not webhook_secret:
        logger.warning("Webhook signature required but no secret configured")
        return

    body = await request.body()
    if not verify_webhook_signature(body, signature, webhook_secret.get_secret_value()):
        logger.warning(
            f"Invalid webhook signature for {request.method} {request.url.path}",
            extra={"client_ip": request.client.host if request.client else "unknown"},
        )
        raise HTTPException(401, "Invalid webhook signature")


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
    await _verify_signature(request, x_webhook_signature)

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
    await _verify_signature(request, x_webhook_signature)

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


@router.post("/resend/inbound")
async def handle_resend_inbound(
    request: Request,
) -> dict[str, Any]:
    """Handle Resend inbound email webhook.

    When a recipient replies to our email, Resend sends the reply here.
    We match it to the original email and update the lead status.

    Webhook URL: https://176.126.166.94:8443/api/v1/webhooks/resend/inbound

    Args:
        request: Raw request with JSON body

    Returns:
        Processing result
    """
    from app.core.state_machine import LeadStatus
    from app.events.definitions import EventType
    from app.events.helpers import create_event
    from app.storage.repositories.email_repo import EmailRepository
    from app.storage.repositories.lead_repo import LeadRepository

    # Parse JSON body (Resend uses 'from' which is a Python keyword)
    body = await request.json()

    # Handle 'from' field renamed to 'from_'
    if "from" in body:
        body["from_"] = body.pop("from")

    payload = ResendInboundEmail(**body)

    sender_email = payload.from_ or ""
    subject = payload.subject or ""
    reply_text = payload.text or ""
    reply_html = payload.html or ""

    logger.info(
        f"[Resend Inbound] Reply received | from={sender_email} | subject={subject[:50]}"
    )

    async with async_session_factory() as db:
        email_repo = EmailRepository(db)
        lead_repo = LeadRepository(db)

        original_email = None

        # Strategy 1: Match by In-Reply-To header (most reliable)
        if payload.in_reply_to:
            # Clean Message-ID (remove angle brackets if present)
            msg_id = payload.in_reply_to.strip("<>")
            original_email = await email_repo.find_by_message_id(msg_id)
            if original_email:
                logger.info(f"[Resend Inbound] Matched by In-Reply-To: {msg_id}")

        # Strategy 2: Match by References header
        if not original_email and payload.references:
            for ref in payload.references:
                msg_id = ref.strip("<>")
                original_email = await email_repo.find_by_message_id(msg_id)
                if original_email:
                    logger.info(f"[Resend Inbound] Matched by References: {msg_id}")
                    break

        # Strategy 3: Match by subject (remove Re: prefix)
        if not original_email and subject:
            clean_subject = subject
            for prefix in ["Re:", "RE:", "Ответ:", "re:", "Fwd:", "FWD:"]:
                if clean_subject.startswith(prefix):
                    clean_subject = clean_subject[len(prefix):].strip()
            # Also try matching with sender email
            original_email = await email_repo.find_by_subject_and_recipient(
                subject=clean_subject,
                recipient=sender_email,
            )
            if original_email:
                logger.info(f"[Resend Inbound] Matched by subject: {clean_subject[:30]}")

        if not original_email:
            logger.warning(
                f"[Resend Inbound] Could not match reply | from={sender_email} | "
                f"subject={subject[:50]} | in_reply_to={payload.in_reply_to}"
            )
            return {
                "status": "unmatched",
                "message": "Could not find original email",
                "from": sender_email,
                "subject": subject,
            }

        # Update email_messages via ORM
        original_email.replied = True
        original_email.replied_at = datetime.now(UTC)
        original_email.reply_text = reply_text or reply_html
        await email_repo.update(original_email)

        # Get and update lead status
        lead = await lead_repo.get(str(original_email.lead_id))
        if lead:
            # Only transition if not already in a later stage
            valid_for_transition = [
                LeadStatus.OUTREACH_SENT.value,
                LeadStatus.QUALIFIED.value,
                LeadStatus.SCORED.value,
            ]
            if lead.status in valid_for_transition:
                lead.status = LeadStatus.REPLY_RECEIVED.value
                lead.status_changed_at = datetime.now(UTC)
                await lead_repo.update(lead)

                # Create event
                event = create_event(
                    event_type=EventType.REPLY_RECEIVED,
                    lead_id=str(lead.id),
                    data={
                        "email_id": str(original_email.id),
                        "from_email": sender_email,
                        "subject": subject,
                        "reply_preview": (reply_text or reply_html)[:200],
                    },
                )
                logger.info(
                    f"[Resend Inbound] Lead updated to REPLY_RECEIVED | "
                    f"lead_id={lead.id} | email_id={original_email.id}"
                )

            # Trigger reply analysis
            try:
                from workers.analysis_tasks import analyze_reply

                analyze_reply.delay(
                    email_id=str(original_email.id),
                    lead_id=str(original_email.lead_id),
                    reply_text=reply_text or reply_html,
                )
            except Exception as e:
                logger.warning(f"[Resend Inbound] Failed to trigger analyze_reply: {e}")

        await db.commit()

        return {
            "status": "processed",
            "email_id": str(original_email.id),
            "lead_id": str(original_email.lead_id),
            "matched_by": "in_reply_to" if payload.in_reply_to else "subject",
        }


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
