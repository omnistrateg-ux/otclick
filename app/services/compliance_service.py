"""Compliance Service.

Unsubscribe, opt-out, 152-ФЗ, дедупликация из ARCHITECTURE.md раздел 12.
"""

import logging
import re
from datetime import datetime, timezone

UTC = timezone.utc, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.domain import EmployerContact, EmployerLead
from app.models.enums import LeadStatus

logger = logging.getLogger(__name__)


class RateLimitResult:
    """Result of rate limit check."""

    def __init__(
        self,
        allowed: bool,
        reason: str | None = None,
        retry_after: datetime | None = None,
    ) -> None:
        self.allowed = allowed
        self.reason = reason
        self.retry_after = retry_after


class ComplianceService:
    """Service for email compliance.

    Управляет:
    - Unsubscribe / opt-out
    - Rate limiting
    - Дедупликация лидов
    - Bounce handling
    - 152-ФЗ compliance
    """

    # Cooldown periods
    DEFAULT_COOLDOWN_DAYS = 90
    SOFT_BOUNCE_COOLDOWN_DAYS = 7
    DUPLICATE_MERGE_WINDOW_DAYS = 30

    def __init__(self, db: AsyncSession) -> None:
        """Initialize service.

        Args:
            db: Database session
        """
        self.db = db

    # ==================
    # Opt-out management
    # ==================

    async def process_unsubscribe(
        self,
        lead_id: UUID,
        contact_id: UUID | None = None,
        reason: str = "user_request",
    ) -> bool:
        """Process unsubscribe request.

        Args:
            lead_id: Lead ID
            contact_id: Contact ID (optional)
            reason: Unsubscribe reason

        Returns:
            True if processed successfully
        """
        # TODO: Load lead and contact from database
        # lead = await lead_repo.get(lead_id)

        # Mark lead as opted out
        # lead.opted_out = True
        # lead.opted_out_at = datetime.now(UTC)
        # lead.status = LeadStatus.OPTED_OUT

        # If contact specified, mark contact too
        # if contact_id:
        #     contact = await contact_repo.get(contact_id)
        #     contact.opted_out = True

        # TODO: Save to database

        logger.info(f"Processed unsubscribe for lead {lead_id}, reason: {reason}")
        return True

    async def check_opt_out(
        self,
        lead: EmployerLead,
        contact: EmployerContact | None = None,
    ) -> tuple[bool, str | None]:
        """Check if lead/contact is opted out.

        Args:
            lead: Lead to check
            contact: Contact to check (optional)

        Returns:
            Tuple of (is_opted_out, reason)
        """
        # Check lead opt-out
        if lead.opted_out:
            return True, "lead_opted_out"

        if lead.status == LeadStatus.OPTED_OUT:
            return True, "lead_status_opted_out"

        # Check cooldown
        if lead.do_not_contact_until:
            if datetime.now(UTC) < lead.do_not_contact_until:
                return True, "lead_in_cooldown"

        # Check contact opt-out
        if contact and contact.opted_out:
            return True, "contact_opted_out"

        return False, None

    async def set_cooldown(
        self,
        lead: EmployerLead,
        days: int | None = None,
        reason: str = "refused",
    ) -> datetime:
        """Set cooldown period for lead.

        Args:
            lead: Lead
            days: Cooldown days (default: 90)
            reason: Cooldown reason

        Returns:
            Cooldown end datetime
        """
        days = days or self.DEFAULT_COOLDOWN_DAYS
        cooldown_until = datetime.now(UTC) + timedelta(days=days)

        lead.do_not_contact_until = cooldown_until
        lead.status = LeadStatus.COOLDOWN

        # TODO: Save to database

        logger.info(f"Set cooldown for lead {lead.id} until {cooldown_until}, reason: {reason}")
        return cooldown_until

    # ==================
    # Rate limiting
    # ==================

    async def check_rate_limit_sender(
        self,
        sender_email: str,
    ) -> RateLimitResult:
        """Check rate limit for sender.

        Args:
            sender_email: Sender email address

        Returns:
            Rate limit result
        """
        max_per_day = settings.max_emails_per_sender_per_day

        # TODO: Query sent count from database/redis
        # sent_today = await email_repo.count_sent_today(sender_email)

        # For now, always allow
        sent_today = 0

        if sent_today >= max_per_day:
            return RateLimitResult(
                allowed=False,
                reason=f"Sender limit exceeded: {sent_today}/{max_per_day}",
                retry_after=self._get_tomorrow_start(),
            )

        return RateLimitResult(allowed=True)

    async def check_rate_limit_domain(
        self,
        recipient_domain: str,
    ) -> RateLimitResult:
        """Check rate limit for recipient domain.

        Args:
            recipient_domain: Recipient email domain

        Returns:
            Rate limit result
        """
        max_per_day = settings.max_emails_per_domain_per_day

        # TODO: Query sent count from database/redis
        sent_today = 0

        if sent_today >= max_per_day:
            return RateLimitResult(
                allowed=False,
                reason=f"Domain limit exceeded: {sent_today}/{max_per_day}",
                retry_after=self._get_tomorrow_start(),
            )

        return RateLimitResult(allowed=True)

    async def can_send_email(
        self,
        lead: EmployerLead,
        contact: EmployerContact,
        sender_email: str,
    ) -> tuple[bool, str | None]:
        """Check if email can be sent.

        Combines all compliance checks.

        Args:
            lead: Lead
            contact: Contact
            sender_email: Sender email

        Returns:
            Tuple of (can_send, reason)
        """
        # Check opt-out
        opted_out, reason = await self.check_opt_out(lead, contact)
        if opted_out:
            return False, reason

        # Check contact has email
        if not contact.email:
            return False, "no_contact_email"

        # Check contact bounce count
        if contact.bounce_count >= 3:
            return False, "contact_bounced"

        # Check sender rate limit
        sender_result = await self.check_rate_limit_sender(sender_email)
        if not sender_result.allowed:
            return False, sender_result.reason

        # Check domain rate limit
        domain = self._extract_domain(contact.email)
        domain_result = await self.check_rate_limit_domain(domain)
        if not domain_result.allowed:
            return False, domain_result.reason

        return True, None

    # ==================
    # Bounce handling
    # ==================

    async def process_hard_bounce(
        self,
        contact: EmployerContact,
        reason: str,
    ) -> None:
        """Process hard bounce.

        Args:
            contact: Contact that bounced
            reason: Bounce reason
        """
        contact.bounce_count += 1
        contact.last_bounce_at = datetime.now(UTC)
        contact.email_verified = False

        # TODO: Save to database
        # TODO: Mark lead as BOUNCED if primary contact

        logger.info(f"Processed hard bounce for contact {contact.id}: {reason}")

    async def process_soft_bounce(
        self,
        contact: EmployerContact,
        reason: str,
    ) -> bool:
        """Process soft bounce.

        Args:
            contact: Contact that bounced
            reason: Bounce reason

        Returns:
            True if should retry, False if exceeded limit
        """
        contact.bounce_count += 1
        contact.last_bounce_at = datetime.now(UTC)

        # TODO: Save to database

        # If too many soft bounces, treat as hard bounce
        if contact.bounce_count >= 3:
            await self.process_hard_bounce(contact, reason)
            return False

        return True

    # ==================
    # Deduplication
    # ==================

    async def find_duplicate_lead(
        self,
        company_name: str,
        domain: str | None = None,
        inn: str | None = None,
        city: str | None = None,
    ) -> UUID | None:
        """Find duplicate lead.

        Args:
            company_name: Company name
            domain: Company domain
            inn: Company INN
            city: City

        Returns:
            Existing lead ID if duplicate found
        """
        # Priority 1: Check by INN (most reliable)
        if inn:
            # TODO: Query by INN
            pass

        # Priority 2: Check by domain
        if domain:
            # TODO: Query by domain
            pass

        # Priority 3: Check by normalized name + city
        normalized_name = self._normalize_company_name(company_name)
        # TODO: Query by normalized name + city

        return None

    async def find_duplicate_contact(
        self,
        email: str,
    ) -> UUID | None:
        """Find duplicate contact by email.

        Args:
            email: Contact email

        Returns:
            Existing contact ID if duplicate found
        """
        # TODO: Query by email
        return None

    async def merge_duplicates(
        self,
        primary_lead_id: UUID,
        duplicate_lead_id: UUID,
    ) -> bool:
        """Merge duplicate leads.

        Args:
            primary_lead_id: Primary lead to keep
            duplicate_lead_id: Duplicate lead to merge

        Returns:
            True if merged successfully
        """
        # TODO: Implement merge logic
        # - Move contacts to primary
        # - Move email sequences to primary
        # - Mark duplicate as DUPLICATE status
        # - Link duplicate to primary

        logger.info(f"Merged lead {duplicate_lead_id} into {primary_lead_id}")
        return True

    # ==================
    # Helpers
    # ==================

    def _get_tomorrow_start(self) -> datetime:
        """Get start of tomorrow.

        Returns:
            Datetime of tomorrow 00:00:00 UTC
        """
        now = datetime.now(UTC)
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)

    def _extract_domain(self, email: str) -> str:
        """Extract domain from email.

        Args:
            email: Email address

        Returns:
            Domain part
        """
        if "@" in email:
            return email.split("@")[1].lower()
        return ""

    def _normalize_company_name(self, name: str) -> str:
        """Normalize company name for comparison.

        Args:
            name: Company name

        Returns:
            Normalized name
        """
        # Remove common suffixes
        suffixes = [
            "ООО", "ОАО", "ЗАО", "ПАО", "АО", "ИП",
            "LLC", "Inc", "Ltd", "GmbH",
        ]

        name = name.lower().strip()

        for suffix in suffixes:
            name = re.sub(rf'\b{suffix.lower()}\b', '', name)

        # Remove quotes and extra spaces
        name = re.sub(r'["\'\«\»]', '', name)
        name = re.sub(r'\s+', ' ', name).strip()

        return name


# Watchlist for manual review
WATCHLIST_DOMAINS = [
    # Competitors
    "competitor.ru",

    # Large corporations requiring careful approach
    "sberbank.ru",
    "gazprom.ru",
    "rosneft.ru",

    # Government
    "gov.ru",
    "mos.ru",
]

WATCHLIST_KEYWORDS = [
    "администрация",
    "министерство",
    "департамент",
    "федеральн",
    "государствен",
]


def is_on_watchlist(company_name: str, domain: str | None) -> bool:
    """Check if company is on watchlist.

    Args:
        company_name: Company name
        domain: Company domain

    Returns:
        True if on watchlist
    """
    # Check domain
    if domain:
        for watchlist_domain in WATCHLIST_DOMAINS:
            if watchlist_domain in domain.lower():
                return True

    # Check keywords in name
    name_lower = company_name.lower()
    for keyword in WATCHLIST_KEYWORDS:
        if keyword in name_lower:
            return True

    return False
