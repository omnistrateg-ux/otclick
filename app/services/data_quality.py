"""Data Quality Scoring Service.

Contact confidence scores and source quality tracking.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config.settings import settings

UTC = timezone.utc

logger = logging.getLogger(__name__)


# Source quality baseline scores (0.0-1.0)
SOURCE_QUALITY_BASELINES = {
    # Primary sources (direct/verified)
    "hh.ru": 0.85,
    "avito": 0.70,
    "superjob": 0.80,
    "trudvsem": 0.75,
    "linkedin": 0.90,
    "company_website": 0.95,

    # Aggregators
    "hunter.io": 0.75,
    "clearbit": 0.80,
    "snov.io": 0.70,
    "apollo": 0.75,

    # Manual/Import
    "csv_import": 0.60,
    "manual": 0.50,
    "crm_sync": 0.70,

    # Enrichment sources
    "dadata": 0.85,
    "spark": 0.90,
    "kontur": 0.85,

    # Default
    "unknown": 0.50,
}


@dataclass
class ContactConfidence:
    """Confidence score for a contact."""

    contact_id: str
    overall_score: float  # 0.0-1.0
    email_confidence: float
    phone_confidence: float
    name_confidence: float
    role_confidence: float
    source_quality: float
    verification_status: str  # "verified", "unverified", "bounced", "unknown"
    issues: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contact_id": self.contact_id,
            "overall_score": round(self.overall_score, 3),
            "email_confidence": round(self.email_confidence, 3),
            "phone_confidence": round(self.phone_confidence, 3),
            "name_confidence": round(self.name_confidence, 3),
            "role_confidence": round(self.role_confidence, 3),
            "source_quality": round(self.source_quality, 3),
            "verification_status": self.verification_status,
            "issues": self.issues,
            "recommendations": self.recommendations,
        }


@dataclass
class SourceQualityScore:
    """Quality score for a data source."""

    source: str
    base_score: float
    adjusted_score: float
    sample_size: int
    success_rate: float  # Successful deliveries / total
    bounce_rate: float
    reply_rate: float
    conversion_rate: float  # Qualified / total
    last_updated: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "base_score": round(self.base_score, 3),
            "adjusted_score": round(self.adjusted_score, 3),
            "sample_size": self.sample_size,
            "success_rate": round(self.success_rate, 3),
            "bounce_rate": round(self.bounce_rate, 3),
            "reply_rate": round(self.reply_rate, 3),
            "conversion_rate": round(self.conversion_rate, 3),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class DataQualityService:
    """Service for contact confidence and source quality scoring.

    Features:
    - Contact confidence scoring
    - Email pattern validation
    - Source quality tracking and learning
    - Quality-based prioritization
    """

    def __init__(self) -> None:
        """Initialize service."""
        self.default_source_quality = settings.default_source_quality

    # ========================================================================
    # Contact Confidence Scoring
    # ========================================================================

    def calculate_contact_confidence(
        self,
        email: str | None,
        email_verified: bool = False,
        email_source: str | None = None,
        phone: str | None = None,
        full_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        job_title: str | None = None,
        role: str | None = None,
        contact_source: str | None = None,
        bounce_count: int = 0,
        reply_received: bool = False,
    ) -> ContactConfidence:
        """Calculate confidence score for a contact.

        Args:
            email: Email address
            email_verified: Whether email was verified
            email_source: Where email came from
            phone: Phone number
            full_name: Full name
            first_name: First name
            last_name: Last name
            job_title: Job title
            role: Contact role enum
            contact_source: Primary source of contact
            bounce_count: Number of bounces
            reply_received: Whether a reply was received

        Returns:
            ContactConfidence
        """
        issues = []
        recommendations = []

        # Email confidence
        email_conf = self._score_email_confidence(
            email, email_verified, email_source, bounce_count, reply_received
        )
        if email_conf < 0.5:
            issues.append("low_email_confidence")
            if not email_verified:
                recommendations.append("verify_email")

        # Phone confidence
        phone_conf = self._score_phone_confidence(phone)
        if phone and phone_conf < 0.5:
            issues.append("suspicious_phone_format")

        # Name confidence
        name_conf = self._score_name_confidence(full_name, first_name, last_name)
        if name_conf < 0.5:
            issues.append("incomplete_name")
            recommendations.append("enrich_contact_name")

        # Role confidence
        role_conf = self._score_role_confidence(job_title, role)
        if role_conf < 0.5:
            issues.append("unclear_role")
            recommendations.append("enrich_job_title")

        # Source quality
        source = contact_source or email_source or "unknown"
        source_quality = SOURCE_QUALITY_BASELINES.get(
            source.lower(), self.default_source_quality
        )

        # Calculate overall score
        weights = {
            "email": 0.35,
            "phone": 0.15,
            "name": 0.20,
            "role": 0.15,
            "source": 0.15,
        }

        overall = (
            email_conf * weights["email"] +
            phone_conf * weights["phone"] +
            name_conf * weights["name"] +
            role_conf * weights["role"] +
            source_quality * weights["source"]
        )

        # Determine verification status
        if reply_received:
            verification_status = "verified"  # Reply = definitely valid
        elif bounce_count > 0:
            verification_status = "bounced"
        elif email_verified:
            verification_status = "verified"
        elif email:
            verification_status = "unverified"
        else:
            verification_status = "unknown"

        return ContactConfidence(
            contact_id="",  # To be filled by caller
            overall_score=overall,
            email_confidence=email_conf,
            phone_confidence=phone_conf,
            name_confidence=name_conf,
            role_confidence=role_conf,
            source_quality=source_quality,
            verification_status=verification_status,
            issues=issues,
            recommendations=recommendations,
        )

    def _score_email_confidence(
        self,
        email: str | None,
        verified: bool,
        source: str | None,
        bounce_count: int,
        reply_received: bool,
    ) -> float:
        """Score email confidence."""
        if not email:
            return 0.0

        # Reply = 100% confidence
        if reply_received:
            return 1.0

        # Bounced = low confidence
        if bounce_count > 0:
            return max(0.1, 0.5 - bounce_count * 0.2)

        score = 0.5  # Base score

        # Verified boost
        if verified:
            score += 0.35

        # Pattern checks
        email = email.lower().strip()

        # Check for corporate domain
        free_domains = {"gmail.com", "yahoo.com", "hotmail.com", "mail.ru", "yandex.ru"}
        domain = email.split("@")[1] if "@" in email else ""
        if domain not in free_domains:
            score += 0.10

        # Check for suspicious patterns
        suspicious_patterns = [
            r"^info@",
            r"^admin@",
            r"^noreply@",
            r"^support@",
            r"^contact@",
            r"\d{5,}",  # Many digits
        ]
        for pattern in suspicious_patterns:
            if re.search(pattern, email):
                score -= 0.15
                break

        # Source quality boost
        if source:
            source_quality = SOURCE_QUALITY_BASELINES.get(source.lower(), 0.7)
            score = score * 0.7 + source_quality * 0.3

        return max(0.0, min(1.0, score))

    def _score_phone_confidence(self, phone: str | None) -> float:
        """Score phone number confidence."""
        if not phone:
            return 0.5  # Neutral - phone not required

        phone = re.sub(r"[\s\-\(\)]", "", phone)

        # Russian phone patterns
        if re.match(r"^(\+7|8|7)\d{10}$", phone):
            return 0.9

        # International format
        if re.match(r"^\+\d{10,15}$", phone):
            return 0.85

        # Too short or too long
        if len(phone) < 10 or len(phone) > 15:
            return 0.3

        return 0.6

    def _score_name_confidence(
        self,
        full_name: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> float:
        """Score name confidence."""
        score = 0.0

        # Full name present and has multiple parts
        if full_name:
            parts = full_name.strip().split()
            if len(parts) >= 2:
                score = 0.9
            elif len(parts) == 1:
                score = 0.5
            else:
                score = 0.3

            # Check for suspicious names
            suspicious = ["test", "admin", "user", "manager", "hr"]
            if any(s in full_name.lower() for s in suspicious):
                score -= 0.3

        # First + last name
        elif first_name and last_name:
            score = 0.85

        elif first_name or last_name:
            score = 0.5

        return max(0.0, min(1.0, score))

    def _score_role_confidence(
        self,
        job_title: str | None,
        role: str | None,
    ) -> float:
        """Score role confidence."""
        if not job_title and not role:
            return 0.3

        score = 0.5

        # Role enum present
        if role and role not in ("other", "unknown"):
            score += 0.25

        # Job title present
        if job_title:
            title_lower = job_title.lower()

            # HR-related titles = high confidence
            hr_keywords = ["hr", "кадр", "персонал", "рекрутер", "recruiter", "hiring"]
            if any(kw in title_lower for kw in hr_keywords):
                score += 0.25

            # Director/Head level
            director_keywords = ["director", "директор", "head", "руководитель", "начальник"]
            if any(kw in title_lower for kw in director_keywords):
                score += 0.15

        return min(1.0, score)

    # ========================================================================
    # Source Quality Tracking
    # ========================================================================

    async def record_source_outcome(
        self,
        source: str,
        outcome: str,  # "delivered", "bounced", "replied", "qualified"
    ) -> None:
        """Record outcome for source quality tracking.

        Args:
            source: Data source name
            outcome: Outcome type
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        source = source.lower().strip()
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        # Increment counters
        pipe = redis.pipeline()

        pipe.incr(f"source:quality:{source}:total")
        pipe.incr(f"source:quality:{source}:{outcome}")
        pipe.incr(f"source:quality:{source}:daily:{today}:total")
        pipe.incr(f"source:quality:{source}:daily:{today}:{outcome}")

        # Set expiry
        for key in [
            f"source:quality:{source}:total",
            f"source:quality:{source}:{outcome}",
            f"source:quality:{source}:daily:{today}:total",
            f"source:quality:{source}:daily:{today}:{outcome}",
        ]:
            pipe.expire(key, 86400 * 90)

        await pipe.execute()

    async def get_source_quality(self, source: str) -> SourceQualityScore:
        """Get quality score for a source.

        Args:
            source: Source name

        Returns:
            SourceQualityScore
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        source = source.lower().strip()

        # Get base score
        base_score = SOURCE_QUALITY_BASELINES.get(source, self.default_source_quality)

        # Get metrics
        total = int(await redis.get(f"source:quality:{source}:total") or 0)
        delivered = int(await redis.get(f"source:quality:{source}:delivered") or 0)
        bounced = int(await redis.get(f"source:quality:{source}:bounced") or 0)
        replied = int(await redis.get(f"source:quality:{source}:replied") or 0)
        qualified = int(await redis.get(f"source:quality:{source}:qualified") or 0)

        # Calculate rates
        if total > 0:
            success_rate = delivered / total
            bounce_rate = bounced / total
            reply_rate = replied / total if delivered > 0 else replied / total
            conversion_rate = qualified / total
        else:
            success_rate = 0.0
            bounce_rate = 0.0
            reply_rate = 0.0
            conversion_rate = 0.0

        # Adjust score based on actual performance
        if total >= 50:  # Minimum sample for adjustment
            # Blend base score with actual performance
            performance_score = (
                success_rate * 0.3 +
                (1 - bounce_rate) * 0.3 +
                reply_rate * 5 * 0.2 +  # Reply rate is typically low, boost
                conversion_rate * 10 * 0.2  # Conversion is even lower
            )
            adjusted_score = base_score * 0.4 + performance_score * 0.6
        else:
            adjusted_score = base_score

        return SourceQualityScore(
            source=source,
            base_score=base_score,
            adjusted_score=max(0.1, min(1.0, adjusted_score)),
            sample_size=total,
            success_rate=success_rate,
            bounce_rate=bounce_rate,
            reply_rate=reply_rate,
            conversion_rate=conversion_rate,
            last_updated=datetime.now(UTC),
        )

    async def get_all_source_qualities(self) -> list[SourceQualityScore]:
        """Get quality scores for all tracked sources.

        Returns:
            List of SourceQualityScore
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        sources = set()

        # Find all tracked sources
        async for key in redis.scan_iter("source:quality:*:total"):
            parts = key.split(":")
            if len(parts) >= 3:
                source = parts[2]
                sources.add(source)

        # Also include baseline sources
        sources.update(SOURCE_QUALITY_BASELINES.keys())

        results = []
        for source in sorted(sources):
            quality = await self.get_source_quality(source)
            results.append(quality)

        # Sort by adjusted score
        results.sort(key=lambda x: x.adjusted_score, reverse=True)

        return results

    # ========================================================================
    # Contact Prioritization
    # ========================================================================

    def prioritize_contacts(
        self,
        contacts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Prioritize contacts by confidence score.

        Args:
            contacts: List of contact dicts with at least email, name, role

        Returns:
            Sorted list with confidence scores added
        """
        scored_contacts = []

        for contact in contacts:
            confidence = self.calculate_contact_confidence(
                email=contact.get("email"),
                email_verified=contact.get("email_verified", False),
                email_source=contact.get("email_source"),
                phone=contact.get("phone"),
                full_name=contact.get("full_name"),
                first_name=contact.get("first_name"),
                last_name=contact.get("last_name"),
                job_title=contact.get("job_title"),
                role=contact.get("role"),
                contact_source=contact.get("contact_source"),
                bounce_count=contact.get("bounce_count", 0),
                reply_received=contact.get("reply_received", False),
            )

            contact_with_score = {
                **contact,
                "confidence_score": confidence.overall_score,
                "confidence_details": confidence.to_dict(),
            }
            scored_contacts.append(contact_with_score)

        # Sort by confidence (highest first)
        scored_contacts.sort(key=lambda x: x["confidence_score"], reverse=True)

        return scored_contacts


# Singleton
data_quality = DataQualityService()
