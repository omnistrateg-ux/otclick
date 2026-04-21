"""Account Score Service.

Composite scoring for accounts/companies.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.config.settings import settings

UTC = timezone.utc

logger = logging.getLogger(__name__)


class AccountTier(str, Enum):
    """Account tier based on score."""

    ENTERPRISE = "enterprise"  # 80+
    MID_MARKET = "mid_market"  # 60-79
    SMB = "smb"  # 40-59
    STARTUP = "startup"  # 20-39
    UNQUALIFIED = "unqualified"  # <20


class EngagementLevel(str, Enum):
    """Engagement level."""

    HOT = "hot"  # Recent engagement, high interest
    WARM = "warm"  # Some engagement
    COLD = "cold"  # No recent engagement
    DORMANT = "dormant"  # No engagement for long time


@dataclass
class AccountScoreComponents:
    """Individual score components."""

    lead_score: float  # From scoring service
    contact_quality: float  # Average contact confidence
    engagement_score: float  # Engagement signals
    freshness_score: float  # Data freshness
    feedback_adjustment: float  # Manager feedback
    revenue_potential: float  # Revenue signals

    def to_dict(self) -> dict[str, Any]:
        return {
            "lead_score": round(self.lead_score, 3),
            "contact_quality": round(self.contact_quality, 3),
            "engagement_score": round(self.engagement_score, 3),
            "freshness_score": round(self.freshness_score, 3),
            "feedback_adjustment": round(self.feedback_adjustment, 3),
            "revenue_potential": round(self.revenue_potential, 3),
        }


@dataclass
class AccountScore:
    """Composite account score."""

    account_id: str
    lead_id: str | None
    overall_score: float  # 0-100
    tier: AccountTier
    engagement_level: EngagementLevel
    components: AccountScoreComponents
    signals: list[str]  # Positive/negative signals
    recommendations: list[str]
    last_calculated: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "lead_id": self.lead_id,
            "overall_score": round(self.overall_score, 1),
            "tier": self.tier.value,
            "engagement_level": self.engagement_level.value,
            "components": self.components.to_dict(),
            "signals": self.signals,
            "recommendations": self.recommendations,
            "last_calculated": self.last_calculated.isoformat(),
        }


@dataclass
class AccountHealthIndicator:
    """Account health indicator."""

    indicator: str
    status: str  # "healthy", "warning", "critical"
    value: float | str
    threshold: float | str | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicator": self.indicator,
            "status": self.status,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
        }


# Scoring weights
SCORE_WEIGHTS = {
    "lead_score": 0.25,
    "contact_quality": 0.20,
    "engagement": 0.25,
    "freshness": 0.10,
    "feedback": 0.10,
    "revenue": 0.10,
}


class AccountScoreService:
    """Calculates composite account scores.

    Features:
    - Multi-factor scoring
    - Engagement tracking
    - Tier classification
    - Health indicators
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Score Calculation
    # ========================================================================

    async def calculate_account_score(
        self,
        account_id: str,
        lead_id: str | None = None,
    ) -> AccountScore:
        """Calculate composite score for an account.

        Args:
            account_id: Account/company ID
            lead_id: Optional lead ID

        Returns:
            AccountScore
        """
        now = datetime.now(UTC)
        signals = []
        recommendations = []

        # Get component scores
        lead_score = await self._get_lead_score(lead_id) if lead_id else 50.0
        contact_quality = await self._get_contact_quality(account_id, lead_id)
        engagement_score = await self._get_engagement_score(account_id)
        freshness_score = await self._get_freshness_score(lead_id) if lead_id else 50.0
        feedback_adj = await self._get_feedback_adjustment(lead_id) if lead_id else 0.0
        revenue_potential = await self._get_revenue_potential(account_id)

        # Build signals
        if lead_score >= 80:
            signals.append("high_lead_score")
        elif lead_score < 40:
            signals.append("low_lead_score")
            recommendations.append("review_lead_qualification")

        if contact_quality >= 0.8:
            signals.append("quality_contacts")
        elif contact_quality < 0.5:
            signals.append("low_contact_quality")
            recommendations.append("enrich_contacts")

        if engagement_score >= 70:
            signals.append("high_engagement")
        elif engagement_score < 30:
            signals.append("low_engagement")
            recommendations.append("increase_touchpoints")

        if freshness_score < 50:
            signals.append("stale_data")
            recommendations.append("refresh_data")

        if feedback_adj > 0.05:
            signals.append("positive_feedback")
        elif feedback_adj < -0.05:
            signals.append("negative_feedback")
            recommendations.append("review_qualification")

        if revenue_potential >= 70:
            signals.append("high_revenue_potential")

        # Calculate weighted score
        components = AccountScoreComponents(
            lead_score=lead_score,
            contact_quality=contact_quality * 100,
            engagement_score=engagement_score,
            freshness_score=freshness_score,
            feedback_adjustment=feedback_adj * 100,
            revenue_potential=revenue_potential,
        )

        overall_score = (
            lead_score * SCORE_WEIGHTS["lead_score"] +
            contact_quality * 100 * SCORE_WEIGHTS["contact_quality"] +
            engagement_score * SCORE_WEIGHTS["engagement"] +
            freshness_score * SCORE_WEIGHTS["freshness"] +
            (50 + feedback_adj * 100) * SCORE_WEIGHTS["feedback"] +
            revenue_potential * SCORE_WEIGHTS["revenue"]
        )

        # Clamp score
        overall_score = max(0, min(100, overall_score))

        # Determine tier
        tier = self._determine_tier(overall_score)

        # Determine engagement level
        engagement_level = self._determine_engagement_level(engagement_score)

        score = AccountScore(
            account_id=account_id,
            lead_id=lead_id,
            overall_score=overall_score,
            tier=tier,
            engagement_level=engagement_level,
            components=components,
            signals=signals,
            recommendations=recommendations,
            last_calculated=now,
        )

        # Cache score
        await self._cache_score(score)

        return score

    async def _get_lead_score(self, lead_id: str) -> float:
        """Get lead score from scoring service."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        score = await redis.get(f"lead:score:{lead_id}")
        return float(score) if score else 50.0

    async def _get_contact_quality(
        self,
        account_id: str,
        lead_id: str | None,
    ) -> float:
        """Get average contact quality."""
        from app.services.data_quality import DataQualityService
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Try to get cached contact scores
        key = f"account:contact_quality:{account_id}"
        cached = await redis.get(key)
        if cached:
            return float(cached)

        # Default if no contacts
        return 0.5

    async def _get_engagement_score(self, account_id: str) -> float:
        """Calculate engagement score from signals."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Get engagement signals
        opens = int(await redis.get(f"engagement:account:{account_id}:opens") or 0)
        clicks = int(await redis.get(f"engagement:account:{account_id}:clicks") or 0)
        replies = int(await redis.get(f"engagement:account:{account_id}:replies") or 0)
        meetings = int(await redis.get(f"engagement:account:{account_id}:meetings") or 0)

        # Weighted engagement
        score = 0.0
        if opens > 0:
            score += min(20, opens * 5)
        if clicks > 0:
            score += min(25, clicks * 10)
        if replies > 0:
            score += min(35, replies * 15)
        if meetings > 0:
            score += min(20, meetings * 20)

        return min(100, score)

    async def _get_freshness_score(self, lead_id: str) -> float:
        """Get freshness score."""
        from app.services.lead_freshness import LeadFreshnessService, FreshnessStatus

        service = LeadFreshnessService()

        # Get lead data
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        lead_data = await redis.get(f"lead:data:{lead_id}")

        if not lead_data:
            return 50.0

        # Simplified freshness
        status_scores = {
            "fresh": 100,
            "aging": 70,
            "stale": 40,
            "expired": 10,
        }

        status = await redis.get(f"lead:freshness:{lead_id}")
        return status_scores.get(status, 50.0) if status else 50.0

    async def _get_feedback_adjustment(self, lead_id: str) -> float:
        """Get feedback adjustment."""
        from app.services.manager_feedback import ManagerFeedbackService

        service = ManagerFeedbackService()
        return await service.get_lead_score_adjustment(lead_id)

    async def _get_revenue_potential(self, account_id: str) -> float:
        """Estimate revenue potential."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Check for existing deals
        deal_ids = await redis.smembers(f"deals:account:{account_id}")
        if deal_ids:
            # Has deals - high potential
            return 80.0

        # Check company size signals
        size_score = await redis.get(f"account:size_score:{account_id}")
        if size_score:
            return float(size_score)

        return 50.0

    def _determine_tier(self, score: float) -> AccountTier:
        """Determine account tier from score."""
        if score >= 80:
            return AccountTier.ENTERPRISE
        elif score >= 60:
            return AccountTier.MID_MARKET
        elif score >= 40:
            return AccountTier.SMB
        elif score >= 20:
            return AccountTier.STARTUP
        else:
            return AccountTier.UNQUALIFIED

    def _determine_engagement_level(self, engagement_score: float) -> EngagementLevel:
        """Determine engagement level."""
        if engagement_score >= 70:
            return EngagementLevel.HOT
        elif engagement_score >= 40:
            return EngagementLevel.WARM
        elif engagement_score >= 10:
            return EngagementLevel.COLD
        else:
            return EngagementLevel.DORMANT

    async def _cache_score(self, score: AccountScore) -> None:
        """Cache account score."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        key = f"account:score:{score.account_id}"
        await redis.set(key, json.dumps(score.to_dict()), ex=3600)  # 1 hour cache

    # ========================================================================
    # Engagement Tracking
    # ========================================================================

    async def record_engagement(
        self,
        account_id: str,
        engagement_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an engagement event.

        Args:
            account_id: Account ID
            engagement_type: Type (open, click, reply, meeting)
            metadata: Optional metadata
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Increment counter
        key = f"engagement:account:{account_id}:{engagement_type}s"
        await redis.incr(key)
        await redis.expire(key, 86400 * 90)

        # Record timestamp
        await redis.set(
            f"engagement:account:{account_id}:last_{engagement_type}",
            now.isoformat(),
            ex=86400 * 90,
        )

        # Invalidate cached score
        await redis.delete(f"account:score:{account_id}")

        logger.info(
            f"[ACCOUNT] Engagement recorded | account={account_id} | "
            f"type={engagement_type}"
        )

    async def get_engagement_timeline(
        self,
        account_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get engagement timeline for account.

        Args:
            account_id: Account ID
            limit: Max events

        Returns:
            Timeline events
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        key = f"engagement:account:{account_id}:timeline"

        items = await redis.lrange(key, 0, limit - 1)
        return [json.loads(item) for item in items]

    # ========================================================================
    # Health Indicators
    # ========================================================================

    async def get_health_indicators(
        self,
        account_id: str,
    ) -> list[AccountHealthIndicator]:
        """Get account health indicators.

        Args:
            account_id: Account ID

        Returns:
            List of health indicators
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        indicators = []

        # Check engagement recency
        last_open = await redis.get(f"engagement:account:{account_id}:last_open")
        if last_open:
            last_dt = datetime.fromisoformat(last_open)
            days_ago = (datetime.now(UTC) - last_dt).days
            if days_ago <= 7:
                status = "healthy"
                message = "Recent engagement"
            elif days_ago <= 30:
                status = "warning"
                message = f"No engagement in {days_ago} days"
            else:
                status = "critical"
                message = f"No engagement in {days_ago} days"

            indicators.append(AccountHealthIndicator(
                indicator="engagement_recency",
                status=status,
                value=days_ago,
                threshold=7,
                message=message,
            ))

        # Check contact quality
        quality = await redis.get(f"account:contact_quality:{account_id}")
        if quality:
            q = float(quality)
            if q >= 0.7:
                status = "healthy"
            elif q >= 0.5:
                status = "warning"
            else:
                status = "critical"

            indicators.append(AccountHealthIndicator(
                indicator="contact_quality",
                status=status,
                value=round(q, 2),
                threshold=0.7,
                message=f"Contact quality score: {q:.0%}",
            ))

        # Check bounce rate
        bounces = int(await redis.get(f"engagement:account:{account_id}:bounces") or 0)
        sends = int(await redis.get(f"engagement:account:{account_id}:sends") or 1)
        bounce_rate = bounces / sends if sends > 0 else 0

        if bounce_rate <= 0.05:
            status = "healthy"
        elif bounce_rate <= 0.10:
            status = "warning"
        else:
            status = "critical"

        indicators.append(AccountHealthIndicator(
            indicator="bounce_rate",
            status=status,
            value=round(bounce_rate, 3),
            threshold=0.05,
            message=f"Bounce rate: {bounce_rate:.1%}",
        ))

        return indicators

    # ========================================================================
    # Bulk Operations
    # ========================================================================

    async def get_top_accounts(
        self,
        limit: int = 20,
        tier: AccountTier | None = None,
    ) -> list[AccountScore]:
        """Get top scored accounts.

        Args:
            limit: Max accounts
            tier: Filter by tier

        Returns:
            List of account scores
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        scores = []

        async for key in redis.scan_iter("account:score:*"):
            data = await redis.get(key)
            if data:
                d = json.loads(data)
                if tier and d.get("tier") != tier.value:
                    continue
                scores.append(d)

        # Sort by score
        scores.sort(key=lambda x: x["overall_score"], reverse=True)

        return scores[:limit]


# Singleton
account_score = AccountScoreService()
