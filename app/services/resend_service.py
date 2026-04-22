"""Resend email service.

Send emails via Resend API for auto-replies.
"""

import logging
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel

from app.config import settings

UTC = timezone.utc
logger = logging.getLogger(__name__)


class ResendEmailResult(BaseModel):
    """Result of Resend email send."""

    success: bool
    message_id: str | None = None
    error: str | None = None
    sent_at: datetime | None = None


class ResendService:
    """Service for sending emails via Resend API."""

    BASE_URL = "https://api.resend.com"

    def __init__(self, api_key: str | None = None, from_email: str | None = None):
        """Initialize Resend service.

        Args:
            api_key: Resend API key (uses settings if None)
            from_email: From email (uses settings if None)
        """
        self.api_key = api_key
        if api_key is None and settings.resend_api_key:
            self.api_key = settings.resend_api_key.get_secret_value()
        self.from_email = from_email or settings.smtp_from_email

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        from_name: str = "Отклик",
        reply_to: str | None = None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
    ) -> ResendEmailResult:
        """Send email via Resend API.

        Args:
            to_email: Recipient email
            subject: Email subject
            body: Email body (plain text)
            from_name: Sender name
            reply_to: Reply-to email
            in_reply_to: In-Reply-To header for threading
            references: References header for threading

        Returns:
            Send result with message ID
        """
        if not self.api_key:
            return ResendEmailResult(
                success=False,
                error="Resend API key not configured",
            )

        # Build HTML body
        html_body = self._text_to_html(body)

        # Build request payload
        payload = {
            "from": f"{from_name} <{self.from_email}>",
            "to": [to_email],
            "subject": subject,
            "text": body,
            "html": html_body,
        }

        if reply_to:
            payload["reply_to"] = reply_to

        # Add threading headers if present
        headers = {}
        if in_reply_to:
            headers["In-Reply-To"] = in_reply_to
        if references:
            headers["References"] = " ".join(references)
        if headers:
            payload["headers"] = headers

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/emails",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return ResendEmailResult(
                        success=True,
                        message_id=data.get("id"),
                        sent_at=datetime.now(UTC),
                    )
                else:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get("message", f"HTTP {response.status_code}")
                    logger.error(f"Resend API error: {response.status_code} - {error_msg}")
                    return ResendEmailResult(
                        success=False,
                        error=error_msg,
                    )

        except httpx.TimeoutException:
            logger.error("Resend API timeout")
            return ResendEmailResult(
                success=False,
                error="Request timeout",
            )
        except Exception as e:
            logger.exception(f"Resend API error: {e}")
            return ResendEmailResult(
                success=False,
                error=str(e),
            )

    def _text_to_html(self, text: str) -> str:
        """Convert plain text to simple HTML.

        Args:
            text: Plain text

        Returns:
            HTML version
        """
        # Escape HTML entities
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace("\n", "<br>\n")

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px;
    line-height: 1.5;
    color: #333;
    max-width: 600px;
    margin: 0 auto;
    padding: 20px;
}}
</style>
</head>
<body>
{text}
</body>
</html>"""


# Singleton instance
resend_service = ResendService()
