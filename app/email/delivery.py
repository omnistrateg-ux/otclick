"""Email delivery via SMTP.

SMTP отправка + bounce handling из ARCHITECTURE.md.
"""

import logging
import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from typing import Any

from pydantic import BaseModel

from app.config.settings import settings
from app.models.domain import EmailMessage, EmployerContact

logger = logging.getLogger(__name__)


class DeliveryResult(BaseModel):
    """Result of email delivery attempt."""

    success: bool
    message_id: str | None = None
    error: str | None = None
    sent_at: datetime | None = None


class EmailDelivery:
    """Handles email delivery via SMTP.

    Поддерживает:
    - SMTP отправку
    - List-Unsubscribe headers (RFC 8058)
    - Message-ID tracking
    - Bounce handling
    """

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        from_email: str | None = None,
        from_name: str = "Отклик",
    ) -> None:
        """Initialize delivery with SMTP settings.

        Args:
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            smtp_user: SMTP username
            smtp_password: SMTP password
            from_email: Sender email
            from_name: Sender name
        """
        self.smtp_host = smtp_host or settings.smtp_host
        self.smtp_port = smtp_port or settings.smtp_port
        self.smtp_user = smtp_user or settings.smtp_user
        self.smtp_password = smtp_password
        if smtp_password is None and settings.smtp_password:
            self.smtp_password = settings.smtp_password.get_secret_value()
        self.from_email = from_email or settings.smtp_from_email
        self.from_name = from_name

    async def send_email(
        self,
        email: EmailMessage,
        contact: EmployerContact,
        unsubscribe_url: str | None = None,
    ) -> DeliveryResult:
        """Send single email.

        Args:
            email: Email message to send
            contact: Recipient contact
            unsubscribe_url: URL for unsubscribe (required for compliance)

        Returns:
            Delivery result
        """
        if not contact.email:
            return DeliveryResult(
                success=False,
                error="Contact has no email address",
            )

        try:
            # Build MIME message
            msg = self._build_mime_message(
                to_email=contact.email,
                to_name=contact.full_name,
                subject=email.subject,
                body=email.body,
                unsubscribe_url=unsubscribe_url,
            )

            # Send via SMTP
            message_id = msg["Message-ID"]
            self._send_smtp(msg, contact.email)

            return DeliveryResult(
                success=True,
                message_id=message_id,
                sent_at=datetime.now(UTC),
            )

        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"Recipients refused: {e}")
            return DeliveryResult(
                success=False,
                error=f"Recipient refused: {e}",
            )

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return DeliveryResult(
                success=False,
                error=f"SMTP error: {e}",
            )

        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return DeliveryResult(
                success=False,
                error=str(e),
            )

    def _build_mime_message(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        body: str,
        unsubscribe_url: str | None = None,
    ) -> MIMEMultipart:
        """Build MIME message with proper headers.

        Args:
            to_email: Recipient email
            to_name: Recipient name
            subject: Email subject
            body: Email body (plain text)
            unsubscribe_url: Unsubscribe URL

        Returns:
            MIME message
        """
        msg = MIMEMultipart("alternative")

        # Basic headers
        msg["Subject"] = subject
        msg["From"] = formataddr((self.from_name, self.from_email))
        msg["To"] = formataddr((to_name, to_email))
        msg["Message-ID"] = make_msgid(domain=self._get_domain())

        # Compliance headers (RFC 8058)
        if unsubscribe_url:
            msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        # Add plain text body
        text_part = MIMEText(body, "plain", "utf-8")
        msg.attach(text_part)

        # Simple HTML version (just wrapping in basic HTML)
        html_body = self._text_to_html(body)
        html_part = MIMEText(html_body, "html", "utf-8")
        msg.attach(html_part)

        return msg

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

        # Convert newlines to <br>
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

    def _send_smtp(self, msg: MIMEMultipart, to_email: str) -> None:
        """Send message via SMTP.

        Args:
            msg: MIME message
            to_email: Recipient email
        """
        # Choose connection method based on port
        if self.smtp_port == 465:
            # SSL
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
        else:
            # STARTTLS or plain
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                # Try STARTTLS if not local
                if self.smtp_port not in (25, 1025):
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

    def _get_domain(self) -> str:
        """Get domain from from_email.

        Returns:
            Domain part of email
        """
        if "@" in self.from_email:
            return self.from_email.split("@")[1]
        return "otclick.ru"

    async def send_batch(
        self,
        emails: list[tuple[EmailMessage, EmployerContact]],
        unsubscribe_url_template: str | None = None,
    ) -> list[DeliveryResult]:
        """Send batch of emails.

        Args:
            emails: List of (email, contact) tuples
            unsubscribe_url_template: URL template with {lead_id} placeholder

        Returns:
            List of delivery results
        """
        results = []

        for email, contact in emails:
            unsubscribe_url = None
            if unsubscribe_url_template:
                unsubscribe_url = unsubscribe_url_template.format(
                    lead_id=email.lead_id,
                    contact_id=contact.id,
                )

            result = await self.send_email(email, contact, unsubscribe_url)
            results.append(result)

        return results

    def verify_connection(self) -> bool:
        """Verify SMTP connection is working.

        Returns:
            True if connection successful
        """
        try:
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=10) as server:
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    return True
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                    if self.smtp_port not in (25, 1025):
                        server.starttls()
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    return True
        except Exception as e:
            logger.error(f"SMTP connection verification failed: {e}")
            return False


# Singleton instance
email_delivery = EmailDelivery()
