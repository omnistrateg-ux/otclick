"""Outbound Email Service.

Production-safe email sending with validation, throttling, and deliverability tracking.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

from app.config.settings import settings
from app.models.domain import EmployerContact, EmployerLead, CompanyProfile
from app.models.enums import LeadStatus

logger = logging.getLogger(__name__)


# ============================================================================
# Validation Result Types
# ============================================================================


class ValidationStatus(str, Enum):
    """Pre-send validation status."""

    VALID = "valid"
    BLOCKED = "blocked"
    WARNING = "warning"


@dataclass
class ValidationResult:
    """Result of pre-send validation."""

    status: ValidationStatus
    can_send: bool
    errors: list[str]
    warnings: list[str]
    checks_passed: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "can_send": self.can_send,
            "errors": self.errors,
            "warnings": self.warnings,
            "checks_passed": self.checks_passed,
        }


@dataclass
class ThrottleResult:
    """Result of throttle check."""

    allowed: bool
    reason: str | None = None
    retry_after_seconds: int | None = None
    current_rate: int = 0
    limit: int = 0


@dataclass
class CampaignHealth:
    """Campaign health metrics."""

    campaign_id: str
    total_sent: int
    total_delivered: int
    total_bounced: int
    total_complained: int
    bounce_rate: float
    complaint_rate: float
    is_healthy: bool
    should_pause: bool
    pause_reason: str | None = None


# ============================================================================
# Validation Rules
# ============================================================================


# Suspicious/disposable email domains
BLOCKED_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com",
    "tempmail.com", "throwaway.email", "fakeinbox.com",
    "trash-mail.com", "maildrop.cc", "sharklasers.com",
}

# Free email providers (suspicious for B2B)
FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "mail.ru", "yandex.ru",
    "outlook.com", "hotmail.com", "rambler.ru", "bk.ru",
    "list.ru", "inbox.ru",
}

# Catch-all patterns that indicate fake data
SUSPICIOUS_PATTERNS = [
    r"^test@",
    r"^info@",
    r"^admin@",
    r"^noreply@",
    r"^no-reply@",
    r"^support@",
    r"^sales@",
    r"^contact@",
    r"^hello@",
    r"^office@",
    r"\d{5,}@",  # Many digits
    r"^[a-z]@",  # Single letter
]

# Minimum requirements
MIN_COMPANY_NAME_LENGTH = 3
MIN_SUBJECT_LENGTH = 10
MIN_BODY_LENGTH = 100
MAX_SUBJECT_LENGTH = 150
MAX_BODY_LENGTH = 5000


# ============================================================================
# Campaign Health Thresholds
# ============================================================================

# Auto-pause thresholds
BOUNCE_RATE_WARNING = 0.05  # 5%
BOUNCE_RATE_CRITICAL = 0.10  # 10% - pause campaign
COMPLAINT_RATE_WARNING = 0.001  # 0.1%
COMPLAINT_RATE_CRITICAL = 0.005  # 0.5% - pause campaign
MIN_EMAILS_FOR_RATE_CALC = 50  # Need at least 50 emails to calculate rates


# ============================================================================
# Outbound Service
# ============================================================================


class OutboundService:
    """Service for safe outbound email operations.

    Provides:
    - Pre-send validation
    - Throttling
    - Bounce/complaint tracking
    - Campaign health monitoring
    - Deliverability metrics
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Pre-send Validation
    # ========================================================================

    async def validate_pre_send(
        self,
        lead: EmployerLead,
        contact: EmployerContact,
        subject: str,
        body: str,
        profile: CompanyProfile | None = None,
    ) -> ValidationResult:
        """Comprehensive pre-send validation.

        Blocks sending if critical issues found.
        Returns warnings for non-critical issues.

        Args:
            lead: Lead to email
            contact: Contact to email
            subject: Email subject
            body: Email body
            profile: Company profile (optional)

        Returns:
            ValidationResult with pass/fail and details
        """
        errors: list[str] = []
        warnings: list[str] = []
        passed: list[str] = []

        # 1. Lead validation
        lead_errors, lead_warnings, lead_passed = self._validate_lead(lead)
        errors.extend(lead_errors)
        warnings.extend(lead_warnings)
        passed.extend(lead_passed)

        # 2. Contact validation
        contact_errors, contact_warnings, contact_passed = self._validate_contact(contact)
        errors.extend(contact_errors)
        warnings.extend(contact_warnings)
        passed.extend(contact_passed)

        # 3. Email content validation
        content_errors, content_warnings, content_passed = self._validate_content(
            subject, body
        )
        errors.extend(content_errors)
        warnings.extend(content_warnings)
        passed.extend(content_passed)

        # 4. Profile validation (if provided)
        if profile:
            profile_errors, profile_warnings, profile_passed = self._validate_profile(
                profile
            )
            errors.extend(profile_errors)
            warnings.extend(profile_warnings)
            passed.extend(profile_passed)

        # Determine status
        if errors:
            status = ValidationStatus.BLOCKED
            can_send = False
        elif warnings:
            status = ValidationStatus.WARNING
            can_send = True
        else:
            status = ValidationStatus.VALID
            can_send = True

        result = ValidationResult(
            status=status,
            can_send=can_send,
            errors=errors,
            warnings=warnings,
            checks_passed=passed,
        )

        # Log validation result
        if not can_send:
            logger.warning(
                f"[OUTBOUND] Pre-send BLOCKED | lead_id={lead.id} | "
                f"contact={contact.email} | errors={errors}"
            )
        elif warnings:
            logger.info(
                f"[OUTBOUND] Pre-send WARNING | lead_id={lead.id} | "
                f"contact={contact.email} | warnings={warnings}"
            )

        return result

    def _validate_lead(
        self, lead: EmployerLead
    ) -> tuple[list[str], list[str], list[str]]:
        """Validate lead data."""
        errors: list[str] = []
        warnings: list[str] = []
        passed: list[str] = []

        # Check lead status
        blocked_statuses = {
            LeadStatus.OPTED_OUT,
            LeadStatus.BOUNCED,
            LeadStatus.DUPLICATE,
            LeadStatus.ARCHIVED,
        }
        if lead.status in blocked_statuses:
            errors.append(f"lead_status_blocked:{lead.status.value}")
        else:
            passed.append("lead_status_ok")

        # Check opt-out
        if lead.opted_out:
            errors.append("lead_opted_out")
        else:
            passed.append("lead_not_opted_out")

        # Check cooldown
        if lead.do_not_contact_until:
            if datetime.now(UTC) < lead.do_not_contact_until:
                errors.append("lead_in_cooldown")
            else:
                passed.append("lead_cooldown_expired")
        else:
            passed.append("lead_no_cooldown")

        # Check company name
        if not lead.company_name or len(lead.company_name.strip()) < MIN_COMPANY_NAME_LENGTH:
            errors.append("company_name_too_short")
        else:
            passed.append("company_name_ok")

        # Check domain
        if not lead.domain:
            warnings.append("lead_no_domain")
        else:
            passed.append("lead_has_domain")

        return errors, warnings, passed

    def _validate_contact(
        self, contact: EmployerContact
    ) -> tuple[list[str], list[str], list[str]]:
        """Validate contact data."""
        errors: list[str] = []
        warnings: list[str] = []
        passed: list[str] = []

        # Check email exists
        if not contact.email:
            errors.append("contact_no_email")
            return errors, warnings, passed
        else:
            passed.append("contact_has_email")

        email = contact.email.lower().strip()

        # Check email format
        if not self._is_valid_email_format(email):
            errors.append("contact_invalid_email_format")
            return errors, warnings, passed
        else:
            passed.append("contact_email_format_ok")

        # Check blocked domains
        domain = email.split("@")[1] if "@" in email else ""
        if domain in BLOCKED_DOMAINS:
            errors.append(f"contact_blocked_domain:{domain}")
        else:
            passed.append("contact_domain_not_blocked")

        # Check free email (warning for B2B)
        if domain in FREE_EMAIL_DOMAINS:
            warnings.append(f"contact_free_email_domain:{domain}")
        else:
            passed.append("contact_business_email")

        # Check suspicious patterns
        for pattern in SUSPICIOUS_PATTERNS:
            if re.match(pattern, email):
                errors.append(f"contact_suspicious_email_pattern")
                break
        else:
            passed.append("contact_email_not_suspicious")

        # Check opt-out
        if contact.opted_out:
            errors.append("contact_opted_out")
        else:
            passed.append("contact_not_opted_out")

        # Check bounce count
        if contact.bounce_count and contact.bounce_count >= 3:
            errors.append(f"contact_too_many_bounces:{contact.bounce_count}")
        elif contact.bounce_count and contact.bounce_count > 0:
            warnings.append(f"contact_has_bounces:{contact.bounce_count}")
        else:
            passed.append("contact_no_bounces")

        # Check name
        if not contact.full_name or len(contact.full_name.strip()) < 2:
            warnings.append("contact_name_missing_or_short")
        else:
            passed.append("contact_has_name")

        return errors, warnings, passed

    def _validate_content(
        self, subject: str, body: str
    ) -> tuple[list[str], list[str], list[str]]:
        """Validate email content."""
        errors: list[str] = []
        warnings: list[str] = []
        passed: list[str] = []

        # Check subject
        if not subject or len(subject.strip()) < MIN_SUBJECT_LENGTH:
            errors.append(f"subject_too_short:min_{MIN_SUBJECT_LENGTH}")
        elif len(subject) > MAX_SUBJECT_LENGTH:
            warnings.append(f"subject_too_long:max_{MAX_SUBJECT_LENGTH}")
        else:
            passed.append("subject_length_ok")

        # Check body
        if not body or len(body.strip()) < MIN_BODY_LENGTH:
            errors.append(f"body_too_short:min_{MIN_BODY_LENGTH}")
        elif len(body) > MAX_BODY_LENGTH:
            warnings.append(f"body_too_long:max_{MAX_BODY_LENGTH}")
        else:
            passed.append("body_length_ok")

        # Check for spam triggers
        spam_triggers = [
            r"(?i)\bfree\b.*\b(money|cash|prize)\b",
            r"(?i)\bclick here\b",
            r"(?i)\bact now\b",
            r"(?i)\blimited time\b",
            r"(?i)\b100%\s*(free|guaranteed)\b",
        ]
        for trigger in spam_triggers:
            if re.search(trigger, body):
                warnings.append("body_contains_spam_trigger")
                break
        else:
            passed.append("body_no_spam_triggers")

        # Check for personalization
        if "{{" in body or "{%" in body:
            warnings.append("body_has_unresolved_template")
        else:
            passed.append("body_no_unresolved_templates")

        return errors, warnings, passed

    def _validate_profile(
        self, profile: CompanyProfile
    ) -> tuple[list[str], list[str], list[str]]:
        """Validate company profile."""
        errors: list[str] = []
        warnings: list[str] = []
        passed: list[str] = []

        # Check if profile has minimal data
        if not profile.industry:
            warnings.append("profile_no_industry")
        else:
            passed.append("profile_has_industry")

        if not profile.city:
            warnings.append("profile_no_city")
        else:
            passed.append("profile_has_city")

        return errors, warnings, passed

    def _is_valid_email_format(self, email: str) -> bool:
        """Check if email has valid format."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    # ========================================================================
    # Throttling
    # ========================================================================

    async def check_throttle(
        self,
        sender_email: str,
        recipient_domain: str,
        campaign_id: str | None = None,
    ) -> ThrottleResult:
        """Check if sending is allowed based on throttle limits.

        Args:
            sender_email: Sender email address
            recipient_domain: Recipient's domain
            campaign_id: Campaign ID (optional)

        Returns:
            ThrottleResult with allowed status
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        today = now.strftime("%Y-%m-%d")
        current_hour = now.strftime("%Y-%m-%d-%H")

        checks = []

        # 1. Global hourly limit (prevent burst)
        hourly_key = f"throttle:global:hourly:{current_hour}"
        hourly_count = int(await redis.get(hourly_key) or 0)
        hourly_limit = 200  # 200 emails per hour globally

        if hourly_count >= hourly_limit:
            return ThrottleResult(
                allowed=False,
                reason=f"global_hourly_limit:{hourly_count}/{hourly_limit}",
                retry_after_seconds=3600 - now.minute * 60 - now.second,
                current_rate=hourly_count,
                limit=hourly_limit,
            )
        checks.append(f"global_hourly:{hourly_count}/{hourly_limit}")

        # 2. Sender daily limit
        sender_key = f"throttle:sender:{sender_email}:{today}"
        sender_count = int(await redis.get(sender_key) or 0)
        sender_limit = settings.max_emails_per_sender_per_day

        if sender_count >= sender_limit:
            return ThrottleResult(
                allowed=False,
                reason=f"sender_daily_limit:{sender_count}/{sender_limit}",
                retry_after_seconds=self._seconds_until_midnight(),
                current_rate=sender_count,
                limit=sender_limit,
            )
        checks.append(f"sender_daily:{sender_count}/{sender_limit}")

        # 3. Domain daily limit (per recipient domain)
        domain_key = f"throttle:domain:{recipient_domain}:{today}"
        domain_count = int(await redis.get(domain_key) or 0)
        domain_limit = settings.max_emails_per_domain_per_day

        if domain_count >= domain_limit:
            return ThrottleResult(
                allowed=False,
                reason=f"domain_daily_limit:{recipient_domain}:{domain_count}/{domain_limit}",
                retry_after_seconds=self._seconds_until_midnight(),
                current_rate=domain_count,
                limit=domain_limit,
            )
        checks.append(f"domain_daily:{domain_count}/{domain_limit}")

        # 4. Campaign daily limit (if campaign specified)
        if campaign_id:
            campaign_key = f"throttle:campaign:{campaign_id}:{today}"
            campaign_count = int(await redis.get(campaign_key) or 0)
            campaign_limit = 100  # 100 emails per campaign per day

            if campaign_count >= campaign_limit:
                return ThrottleResult(
                    allowed=False,
                    reason=f"campaign_daily_limit:{campaign_count}/{campaign_limit}",
                    retry_after_seconds=self._seconds_until_midnight(),
                    current_rate=campaign_count,
                    limit=campaign_limit,
                )
            checks.append(f"campaign_daily:{campaign_count}/{campaign_limit}")

        logger.debug(f"[OUTBOUND] Throttle OK | checks={checks}")

        return ThrottleResult(allowed=True)

    async def record_send(
        self,
        sender_email: str,
        recipient_email: str,
        campaign_id: str | None = None,
    ) -> None:
        """Record email send for throttle tracking.

        Args:
            sender_email: Sender email
            recipient_email: Recipient email
            campaign_id: Campaign ID (optional)
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        today = now.strftime("%Y-%m-%d")
        current_hour = now.strftime("%Y-%m-%d-%H")
        recipient_domain = recipient_email.split("@")[1] if "@" in recipient_email else ""

        # Increment all counters with TTL
        pipe = redis.pipeline()

        # Global hourly
        hourly_key = f"throttle:global:hourly:{current_hour}"
        pipe.incr(hourly_key)
        pipe.expire(hourly_key, 7200)  # 2 hours TTL

        # Sender daily
        sender_key = f"throttle:sender:{sender_email}:{today}"
        pipe.incr(sender_key)
        pipe.expire(sender_key, 172800)  # 48 hours TTL

        # Domain daily
        domain_key = f"throttle:domain:{recipient_domain}:{today}"
        pipe.incr(domain_key)
        pipe.expire(domain_key, 172800)

        # Campaign daily
        if campaign_id:
            campaign_key = f"throttle:campaign:{campaign_id}:{today}"
            pipe.incr(campaign_key)
            pipe.expire(campaign_key, 172800)

        await pipe.execute()

        logger.debug(
            f"[OUTBOUND] Recorded send | sender={sender_email} | "
            f"recipient={recipient_email} | campaign={campaign_id}"
        )

    def _seconds_until_midnight(self) -> int:
        """Get seconds until midnight UTC."""
        now = datetime.now(UTC)
        tomorrow = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return int((tomorrow - now).total_seconds())

    # ========================================================================
    # Bounce/Complaint Tracking
    # ========================================================================

    async def record_bounce(
        self,
        recipient_email: str,
        bounce_type: str,  # "hard" or "soft"
        campaign_id: str | None = None,
        lead_id: str | None = None,
    ) -> None:
        """Record email bounce for tracking.

        Args:
            recipient_email: Email that bounced
            bounce_type: Type of bounce
            campaign_id: Campaign ID
            lead_id: Lead ID
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        today = now.strftime("%Y-%m-%d")
        recipient_domain = recipient_email.split("@")[1] if "@" in recipient_email else ""

        pipe = redis.pipeline()

        # Global bounce count today
        global_key = f"deliverability:bounces:global:{today}"
        pipe.incr(global_key)
        pipe.expire(global_key, 604800)  # 7 days

        # Domain bounce count
        domain_key = f"deliverability:bounces:domain:{recipient_domain}:{today}"
        pipe.incr(domain_key)
        pipe.expire(domain_key, 604800)

        # Campaign bounce count
        if campaign_id:
            campaign_key = f"deliverability:bounces:campaign:{campaign_id}:{today}"
            pipe.incr(campaign_key)
            pipe.expire(campaign_key, 604800)

            # Track total campaign bounces (all time)
            campaign_total_key = f"deliverability:bounces:campaign:{campaign_id}:total"
            pipe.incr(campaign_total_key)
            pipe.expire(campaign_total_key, 2592000)  # 30 days

        await pipe.execute()

        logger.warning(
            f"[OUTBOUND] Bounce recorded | type={bounce_type} | "
            f"email={recipient_email} | domain={recipient_domain} | "
            f"campaign={campaign_id} | lead={lead_id}"
        )

    async def record_complaint(
        self,
        recipient_email: str,
        complaint_type: str,
        campaign_id: str | None = None,
        lead_id: str | None = None,
    ) -> None:
        """Record spam complaint.

        Args:
            recipient_email: Email that complained
            complaint_type: Type of complaint
            campaign_id: Campaign ID
            lead_id: Lead ID
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        today = now.strftime("%Y-%m-%d")

        pipe = redis.pipeline()

        # Global complaint count
        global_key = f"deliverability:complaints:global:{today}"
        pipe.incr(global_key)
        pipe.expire(global_key, 604800)

        # Campaign complaint count
        if campaign_id:
            campaign_key = f"deliverability:complaints:campaign:{campaign_id}:{today}"
            pipe.incr(campaign_key)
            pipe.expire(campaign_key, 604800)

            campaign_total_key = f"deliverability:complaints:campaign:{campaign_id}:total"
            pipe.incr(campaign_total_key)
            pipe.expire(campaign_total_key, 2592000)

        await pipe.execute()

        logger.error(
            f"[OUTBOUND] COMPLAINT recorded | type={complaint_type} | "
            f"email={recipient_email} | campaign={campaign_id} | lead={lead_id}"
        )

    async def record_delivery(
        self,
        recipient_email: str,
        campaign_id: str | None = None,
    ) -> None:
        """Record successful delivery.

        Args:
            recipient_email: Delivered email
            campaign_id: Campaign ID
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        today = now.strftime("%Y-%m-%d")
        recipient_domain = recipient_email.split("@")[1] if "@" in recipient_email else ""

        pipe = redis.pipeline()

        # Global delivery count
        global_key = f"deliverability:delivered:global:{today}"
        pipe.incr(global_key)
        pipe.expire(global_key, 604800)

        # Domain delivery count
        domain_key = f"deliverability:delivered:domain:{recipient_domain}:{today}"
        pipe.incr(domain_key)
        pipe.expire(domain_key, 604800)

        # Campaign delivery count
        if campaign_id:
            campaign_key = f"deliverability:delivered:campaign:{campaign_id}:{today}"
            pipe.incr(campaign_key)
            pipe.expire(campaign_key, 604800)

            campaign_total_key = f"deliverability:delivered:campaign:{campaign_id}:total"
            pipe.incr(campaign_total_key)
            pipe.expire(campaign_total_key, 2592000)

        await pipe.execute()

    # ========================================================================
    # Campaign Health & Auto-Pause
    # ========================================================================

    async def check_campaign_health(
        self,
        campaign_id: str,
    ) -> CampaignHealth:
        """Check campaign health and determine if it should be paused.

        Args:
            campaign_id: Campaign ID to check

        Returns:
            CampaignHealth with metrics and recommendation
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Get totals
        sent_key = f"throttle:campaign:{campaign_id}:total_sent"
        delivered_key = f"deliverability:delivered:campaign:{campaign_id}:total"
        bounced_key = f"deliverability:bounces:campaign:{campaign_id}:total"
        complained_key = f"deliverability:complaints:campaign:{campaign_id}:total"

        total_sent = int(await redis.get(sent_key) or 0)
        total_delivered = int(await redis.get(delivered_key) or 0)
        total_bounced = int(await redis.get(bounced_key) or 0)
        total_complained = int(await redis.get(complained_key) or 0)

        # Calculate rates
        if total_sent >= MIN_EMAILS_FOR_RATE_CALC:
            bounce_rate = total_bounced / total_sent
            complaint_rate = total_complained / total_sent
        else:
            bounce_rate = 0.0
            complaint_rate = 0.0

        # Determine health
        is_healthy = True
        should_pause = False
        pause_reason = None

        if total_sent >= MIN_EMAILS_FOR_RATE_CALC:
            if bounce_rate >= BOUNCE_RATE_CRITICAL:
                is_healthy = False
                should_pause = True
                pause_reason = f"bounce_rate_critical:{bounce_rate:.2%}"
            elif complaint_rate >= COMPLAINT_RATE_CRITICAL:
                is_healthy = False
                should_pause = True
                pause_reason = f"complaint_rate_critical:{complaint_rate:.2%}"
            elif bounce_rate >= BOUNCE_RATE_WARNING:
                is_healthy = False
                pause_reason = f"bounce_rate_warning:{bounce_rate:.2%}"
            elif complaint_rate >= COMPLAINT_RATE_WARNING:
                is_healthy = False
                pause_reason = f"complaint_rate_warning:{complaint_rate:.2%}"

        health = CampaignHealth(
            campaign_id=campaign_id,
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_bounced=total_bounced,
            total_complained=total_complained,
            bounce_rate=bounce_rate,
            complaint_rate=complaint_rate,
            is_healthy=is_healthy,
            should_pause=should_pause,
            pause_reason=pause_reason,
        )

        if should_pause:
            logger.error(
                f"[OUTBOUND] Campaign UNHEALTHY - PAUSE RECOMMENDED | "
                f"campaign={campaign_id} | bounce_rate={bounce_rate:.2%} | "
                f"complaint_rate={complaint_rate:.2%} | reason={pause_reason}"
            )
        elif not is_healthy:
            logger.warning(
                f"[OUTBOUND] Campaign health WARNING | campaign={campaign_id} | "
                f"bounce_rate={bounce_rate:.2%} | complaint_rate={complaint_rate:.2%}"
            )

        return health

    async def auto_pause_unhealthy_campaigns(self) -> list[str]:
        """Check all active campaigns and pause unhealthy ones.

        Returns:
            List of paused campaign IDs
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        paused_campaigns: list[str] = []

        # Get all campaign keys
        pattern = "throttle:campaign:*:total_sent"
        async for key in redis.scan_iter(pattern):
            # Extract campaign_id from key
            parts = key.split(":")
            if len(parts) >= 3:
                campaign_id = parts[2]

                # Check if already paused
                paused_key = f"campaign:paused:{campaign_id}"
                if await redis.exists(paused_key):
                    continue

                # Check health
                health = await self.check_campaign_health(campaign_id)

                if health.should_pause:
                    # Mark campaign as paused
                    await redis.set(paused_key, health.pause_reason, ex=86400)  # 24h
                    paused_campaigns.append(campaign_id)

                    logger.error(
                        f"[OUTBOUND] AUTO-PAUSED campaign | campaign={campaign_id} | "
                        f"reason={health.pause_reason}"
                    )

        return paused_campaigns

    async def is_campaign_paused(self, campaign_id: str) -> tuple[bool, str | None]:
        """Check if campaign is paused.

        Args:
            campaign_id: Campaign ID

        Returns:
            Tuple of (is_paused, reason)
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        paused_key = f"campaign:paused:{campaign_id}"
        reason = await redis.get(paused_key)

        if reason:
            return True, reason
        return False, None

    # ========================================================================
    # Deliverability Metrics
    # ========================================================================

    async def get_domain_metrics(
        self,
        domain: str,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get deliverability metrics for a domain.

        Args:
            domain: Email domain
            days: Number of days to look back

        Returns:
            Dict with metrics
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        total_sent = 0
        total_delivered = 0
        total_bounced = 0

        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")

            sent = int(await redis.get(f"throttle:domain:{domain}:{day}") or 0)
            delivered = int(
                await redis.get(f"deliverability:delivered:domain:{domain}:{day}") or 0
            )
            bounced = int(
                await redis.get(f"deliverability:bounces:domain:{domain}:{day}") or 0
            )

            total_sent += sent
            total_delivered += delivered
            total_bounced += bounced

        delivery_rate = total_delivered / total_sent if total_sent > 0 else 0
        bounce_rate = total_bounced / total_sent if total_sent > 0 else 0

        metrics = {
            "domain": domain,
            "period_days": days,
            "total_sent": total_sent,
            "total_delivered": total_delivered,
            "total_bounced": total_bounced,
            "delivery_rate": delivery_rate,
            "bounce_rate": bounce_rate,
        }

        logger.info(
            f"[OUTBOUND] Domain metrics | domain={domain} | "
            f"sent={total_sent} | delivered={total_delivered} | "
            f"bounced={total_bounced} | delivery_rate={delivery_rate:.2%}"
        )

        return metrics

    async def get_campaign_metrics(
        self,
        campaign_id: str,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get deliverability metrics for a campaign.

        Args:
            campaign_id: Campaign ID
            days: Number of days to look back

        Returns:
            Dict with metrics
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        daily_metrics = []
        total_sent = 0
        total_delivered = 0
        total_bounced = 0
        total_complained = 0

        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")

            sent = int(await redis.get(f"throttle:campaign:{campaign_id}:{day}") or 0)
            delivered = int(
                await redis.get(
                    f"deliverability:delivered:campaign:{campaign_id}:{day}"
                )
                or 0
            )
            bounced = int(
                await redis.get(f"deliverability:bounces:campaign:{campaign_id}:{day}")
                or 0
            )
            complained = int(
                await redis.get(
                    f"deliverability:complaints:campaign:{campaign_id}:{day}"
                )
                or 0
            )

            daily_metrics.append(
                {
                    "date": day,
                    "sent": sent,
                    "delivered": delivered,
                    "bounced": bounced,
                    "complained": complained,
                }
            )

            total_sent += sent
            total_delivered += delivered
            total_bounced += bounced
            total_complained += complained

        delivery_rate = total_delivered / total_sent if total_sent > 0 else 0
        bounce_rate = total_bounced / total_sent if total_sent > 0 else 0
        complaint_rate = total_complained / total_sent if total_sent > 0 else 0

        # Check if paused
        is_paused, pause_reason = await self.is_campaign_paused(campaign_id)

        metrics = {
            "campaign_id": campaign_id,
            "period_days": days,
            "total_sent": total_sent,
            "total_delivered": total_delivered,
            "total_bounced": total_bounced,
            "total_complained": total_complained,
            "delivery_rate": delivery_rate,
            "bounce_rate": bounce_rate,
            "complaint_rate": complaint_rate,
            "is_paused": is_paused,
            "pause_reason": pause_reason,
            "daily_metrics": daily_metrics,
        }

        logger.info(
            f"[OUTBOUND] Campaign metrics | campaign={campaign_id} | "
            f"sent={total_sent} | delivered={total_delivered} | "
            f"bounced={total_bounced} | complained={total_complained} | "
            f"delivery_rate={delivery_rate:.2%} | paused={is_paused}"
        )

        return metrics
