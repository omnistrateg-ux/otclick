"""Lead Freshness and Re-enrichment Service.

Tracks data freshness and triggers re-enrichment when needed.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.config.settings import settings

UTC = timezone.utc

logger = logging.getLogger(__name__)


class FreshnessStatus(str, Enum):
    """Data freshness status."""

    FRESH = "fresh"  # Recently updated
    AGING = "aging"  # Getting old but usable
    STALE = "stale"  # Should be re-enriched
    EXPIRED = "expired"  # Too old, needs refresh before use


@dataclass
class FreshnessAssessment:
    """Assessment of data freshness."""

    entity_type: str  # "lead", "contact", "profile"
    entity_id: str
    status: FreshnessStatus
    days_old: int
    last_updated: datetime | None
    last_enriched: datetime | None
    needs_enrichment: bool
    enrichment_priority: str  # "high", "medium", "low"
    stale_fields: list[str]
    confidence_adjustment: float  # Score adjustment based on freshness

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "status": self.status.value,
            "days_old": self.days_old,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "last_enriched": self.last_enriched.isoformat() if self.last_enriched else None,
            "needs_enrichment": self.needs_enrichment,
            "enrichment_priority": self.enrichment_priority,
            "stale_fields": self.stale_fields,
            "confidence_adjustment": self.confidence_adjustment,
        }


@dataclass
class EnrichmentTask:
    """Task for re-enrichment."""

    entity_type: str
    entity_id: str
    priority: str
    reason: str
    stale_fields: list[str]
    scheduled_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "priority": self.priority,
            "reason": self.reason,
            "stale_fields": self.stale_fields,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
        }


class LeadFreshnessService:
    """Manages lead/contact data freshness and re-enrichment.

    Features:
    - Freshness assessment for leads, contacts, profiles
    - Re-enrichment triggering based on staleness
    - Priority-based enrichment queue
    - Confidence adjustment based on data age
    """

    def __init__(self) -> None:
        """Initialize service."""
        self.lead_stale_days = settings.lead_stale_days
        self.reenrichment_days = settings.lead_reenrichment_days
        self.contact_stale_days = settings.contact_stale_days

    # ========================================================================
    # Freshness Assessment
    # ========================================================================

    def assess_lead_freshness(
        self,
        created_at: datetime,
        updated_at: datetime | None = None,
        enriched_at: datetime | None = None,
        last_activity_at: datetime | None = None,
    ) -> FreshnessAssessment:
        """Assess freshness of a lead.

        Args:
            created_at: When lead was created
            updated_at: When lead was last updated
            enriched_at: When lead was last enriched
            last_activity_at: When last activity occurred

        Returns:
            FreshnessAssessment
        """
        now = datetime.now(UTC)

        # Use most recent timestamp
        last_updated = max(filter(None, [created_at, updated_at, enriched_at, last_activity_at]))
        days_old = (now - last_updated).days

        # Determine status
        if days_old <= 7:
            status = FreshnessStatus.FRESH
            confidence_adj = 0.0
        elif days_old <= self.lead_stale_days:
            status = FreshnessStatus.AGING
            # Linear decay: -0.5% per day after 7 days
            confidence_adj = -0.005 * (days_old - 7)
        elif days_old <= self.lead_stale_days * 2:
            status = FreshnessStatus.STALE
            confidence_adj = -0.10
        else:
            status = FreshnessStatus.EXPIRED
            confidence_adj = -0.20

        # Check if needs enrichment
        needs_enrichment = False
        enrichment_priority = "low"
        stale_fields = []

        if enriched_at:
            days_since_enrichment = (now - enriched_at).days
            if days_since_enrichment >= self.reenrichment_days:
                needs_enrichment = True
                stale_fields.append("company_profile")
                if days_since_enrichment >= self.reenrichment_days * 2:
                    enrichment_priority = "high"
                else:
                    enrichment_priority = "medium"
        else:
            # Never enriched
            needs_enrichment = True
            enrichment_priority = "high"
            stale_fields.extend(["company_profile", "contacts"])

        return FreshnessAssessment(
            entity_type="lead",
            entity_id="",  # To be filled by caller
            status=status,
            days_old=days_old,
            last_updated=last_updated,
            last_enriched=enriched_at,
            needs_enrichment=needs_enrichment,
            enrichment_priority=enrichment_priority,
            stale_fields=stale_fields,
            confidence_adjustment=round(confidence_adj, 3),
        )

    def assess_contact_freshness(
        self,
        created_at: datetime,
        email_verified_at: datetime | None = None,
        last_email_at: datetime | None = None,
        last_bounce_at: datetime | None = None,
    ) -> FreshnessAssessment:
        """Assess freshness of a contact.

        Args:
            created_at: When contact was created
            email_verified_at: When email was last verified
            last_email_at: When last email was sent
            last_bounce_at: When last bounce occurred

        Returns:
            FreshnessAssessment
        """
        now = datetime.now(UTC)

        # Most recent verification or activity
        last_verified = email_verified_at or created_at
        days_since_verified = (now - last_verified).days

        # Determine status
        stale_fields = []

        if days_since_verified <= 30:
            status = FreshnessStatus.FRESH
            confidence_adj = 0.0
        elif days_since_verified <= self.contact_stale_days:
            status = FreshnessStatus.AGING
            confidence_adj = -0.003 * (days_since_verified - 30)
        elif days_since_verified <= self.contact_stale_days * 2:
            status = FreshnessStatus.STALE
            confidence_adj = -0.15
            stale_fields.append("email_verification")
        else:
            status = FreshnessStatus.EXPIRED
            confidence_adj = -0.25
            stale_fields.extend(["email_verification", "job_title", "phone"])

        # Bounces make data even more stale
        if last_bounce_at:
            days_since_bounce = (now - last_bounce_at).days
            if days_since_bounce <= 30:
                status = FreshnessStatus.STALE
                confidence_adj -= 0.15
                stale_fields.append("email_deliverability")

        needs_enrichment = status in (FreshnessStatus.STALE, FreshnessStatus.EXPIRED)

        # Determine priority
        if status == FreshnessStatus.EXPIRED:
            priority = "high"
        elif "email_deliverability" in stale_fields:
            priority = "high"
        elif status == FreshnessStatus.STALE:
            priority = "medium"
        else:
            priority = "low"

        return FreshnessAssessment(
            entity_type="contact",
            entity_id="",
            status=status,
            days_old=days_since_verified,
            last_updated=last_verified,
            last_enriched=email_verified_at,
            needs_enrichment=needs_enrichment,
            enrichment_priority=priority,
            stale_fields=stale_fields,
            confidence_adjustment=round(confidence_adj, 3),
        )

    # ========================================================================
    # Re-enrichment Queue
    # ========================================================================

    async def queue_for_enrichment(
        self,
        entity_type: str,
        entity_id: str,
        priority: str = "medium",
        reason: str = "stale_data",
        stale_fields: list[str] | None = None,
    ) -> bool:
        """Queue an entity for re-enrichment.

        Args:
            entity_type: Type of entity (lead, contact, profile)
            entity_id: Entity ID
            priority: Priority level (high, medium, low)
            reason: Reason for re-enrichment
            stale_fields: Fields that need refresh

        Returns:
            True if queued successfully
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        task = EnrichmentTask(
            entity_type=entity_type,
            entity_id=entity_id,
            priority=priority,
            reason=reason,
            stale_fields=stale_fields or [],
            scheduled_at=datetime.now(UTC),
        )

        # Use sorted set with priority score
        priority_scores = {"high": 0, "medium": 1, "low": 2}
        score = priority_scores.get(priority, 1)

        key = f"enrichment:queue:{entity_type}"
        await redis.zadd(key, {json.dumps(task.to_dict()): score})
        await redis.expire(key, 86400 * 7)  # 7 days

        logger.info(
            f"[FRESHNESS] Queued for enrichment | type={entity_type} | "
            f"id={entity_id} | priority={priority} | reason={reason}"
        )

        return True

    async def get_enrichment_queue(
        self,
        entity_type: str,
        limit: int = 50,
    ) -> list[EnrichmentTask]:
        """Get entities queued for re-enrichment.

        Args:
            entity_type: Type of entity
            limit: Maximum to return

        Returns:
            List of EnrichmentTasks (highest priority first)
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        key = f"enrichment:queue:{entity_type}"

        # Get by score (lower = higher priority)
        items = await redis.zrange(key, 0, limit - 1)

        tasks = []
        for item in items:
            data = json.loads(item)
            tasks.append(EnrichmentTask(
                entity_type=data["entity_type"],
                entity_id=data["entity_id"],
                priority=data["priority"],
                reason=data["reason"],
                stale_fields=data.get("stale_fields", []),
                scheduled_at=datetime.fromisoformat(data["scheduled_at"]) if data.get("scheduled_at") else None,
            ))

        return tasks

    async def dequeue_enrichment(
        self,
        entity_type: str,
        entity_id: str,
    ) -> bool:
        """Remove entity from enrichment queue (after enrichment done).

        Args:
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            True if removed
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        key = f"enrichment:queue:{entity_type}"

        # Find and remove matching entry
        items = await redis.zrange(key, 0, -1)
        for item in items:
            data = json.loads(item)
            if data.get("entity_id") == entity_id:
                await redis.zrem(key, item)
                return True

        return False

    async def record_enrichment(
        self,
        entity_type: str,
        entity_id: str,
        source: str,
        fields_updated: list[str],
    ) -> None:
        """Record that enrichment was performed.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            source: Enrichment source
            fields_updated: Fields that were updated
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        # Store enrichment record
        key = f"enrichment:history:{entity_type}:{entity_id}"
        record = {
            "enriched_at": now.isoformat(),
            "source": source,
            "fields_updated": fields_updated,
        }

        await redis.lpush(key, json.dumps(record))
        await redis.ltrim(key, 0, 9)  # Keep last 10 records
        await redis.expire(key, 86400 * 90)

        # Remove from queue
        await self.dequeue_enrichment(entity_type, entity_id)

        logger.info(
            f"[FRESHNESS] Enrichment recorded | type={entity_type} | "
            f"id={entity_id} | source={source} | fields={len(fields_updated)}"
        )

    # ========================================================================
    # Bulk Freshness Check
    # ========================================================================

    async def find_stale_leads(
        self,
        days_threshold: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Find leads that need re-enrichment.

        Args:
            days_threshold: Days since last enrichment (default: from settings)
            limit: Maximum to return

        Returns:
            List of stale lead info
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        threshold = days_threshold or self.reenrichment_days
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=threshold)

        stale_leads = []

        # Check enrichment history
        async for key in redis.scan_iter("enrichment:history:lead:*"):
            if len(stale_leads) >= limit:
                break

            lead_id = key.split(":")[-1]
            records = await redis.lrange(key, 0, 0)

            if records:
                last_record = json.loads(records[0])
                last_enriched = datetime.fromisoformat(last_record["enriched_at"])

                if last_enriched < cutoff:
                    days_old = (now - last_enriched).days
                    stale_leads.append({
                        "lead_id": lead_id,
                        "last_enriched": last_enriched.isoformat(),
                        "days_since_enrichment": days_old,
                        "last_source": last_record.get("source"),
                    })

        # Sort by staleness
        stale_leads.sort(key=lambda x: x["days_since_enrichment"], reverse=True)

        return stale_leads[:limit]

    def calculate_freshness_score(
        self,
        assessments: list[FreshnessAssessment],
    ) -> float:
        """Calculate overall freshness score from multiple assessments.

        Args:
            assessments: List of freshness assessments

        Returns:
            Freshness score (0-100)
        """
        if not assessments:
            return 50.0

        # Weight by entity type
        weights = {
            "lead": 0.3,
            "profile": 0.4,
            "contact": 0.3,
        }

        total_weight = 0
        weighted_score = 0

        for assessment in assessments:
            weight = weights.get(assessment.entity_type, 0.33)

            # Convert status to score
            status_scores = {
                FreshnessStatus.FRESH: 100,
                FreshnessStatus.AGING: 70,
                FreshnessStatus.STALE: 40,
                FreshnessStatus.EXPIRED: 10,
            }
            score = status_scores.get(assessment.status, 50)

            weighted_score += score * weight
            total_weight += weight

        return round(weighted_score / total_weight, 1) if total_weight > 0 else 50.0


# Singleton
lead_freshness = LeadFreshnessService()
