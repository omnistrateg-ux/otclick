"""Manager Feedback Service.

Feedback loop from sales managers back into scoring system.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.config.settings import settings

UTC = timezone.utc

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Type of manager feedback."""

    # Positive outcomes
    MEETING_SCHEDULED = "meeting_scheduled"
    DEAL_CLOSED = "deal_closed"
    HIGH_QUALITY_LEAD = "high_quality_lead"
    GOOD_TIMING = "good_timing"

    # Negative outcomes
    NOT_INTERESTED = "not_interested"
    WRONG_CONTACT = "wrong_contact"
    BAD_TIMING = "bad_timing"
    LOW_QUALITY_LEAD = "low_quality_lead"
    ALREADY_CUSTOMER = "already_customer"
    COMPETITOR = "competitor"

    # Data quality feedback
    WRONG_EMAIL = "wrong_email"
    WRONG_PHONE = "wrong_phone"
    WRONG_COMPANY = "wrong_company"
    OUTDATED_INFO = "outdated_info"


class FeedbackSentiment(str, Enum):
    """Sentiment of feedback."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


# Feedback type to sentiment mapping
FEEDBACK_SENTIMENTS = {
    FeedbackType.MEETING_SCHEDULED: FeedbackSentiment.POSITIVE,
    FeedbackType.DEAL_CLOSED: FeedbackSentiment.POSITIVE,
    FeedbackType.HIGH_QUALITY_LEAD: FeedbackSentiment.POSITIVE,
    FeedbackType.GOOD_TIMING: FeedbackSentiment.POSITIVE,
    FeedbackType.NOT_INTERESTED: FeedbackSentiment.NEGATIVE,
    FeedbackType.WRONG_CONTACT: FeedbackSentiment.NEGATIVE,
    FeedbackType.BAD_TIMING: FeedbackSentiment.NEUTRAL,
    FeedbackType.LOW_QUALITY_LEAD: FeedbackSentiment.NEGATIVE,
    FeedbackType.ALREADY_CUSTOMER: FeedbackSentiment.NEUTRAL,
    FeedbackType.COMPETITOR: FeedbackSentiment.NEGATIVE,
    FeedbackType.WRONG_EMAIL: FeedbackSentiment.NEGATIVE,
    FeedbackType.WRONG_PHONE: FeedbackSentiment.NEGATIVE,
    FeedbackType.WRONG_COMPANY: FeedbackSentiment.NEGATIVE,
    FeedbackType.OUTDATED_INFO: FeedbackSentiment.NEGATIVE,
}

# Score adjustments by feedback type
FEEDBACK_SCORE_ADJUSTMENTS = {
    FeedbackType.DEAL_CLOSED: 0.15,  # +15%
    FeedbackType.MEETING_SCHEDULED: 0.10,
    FeedbackType.HIGH_QUALITY_LEAD: 0.08,
    FeedbackType.GOOD_TIMING: 0.05,
    FeedbackType.NOT_INTERESTED: -0.05,
    FeedbackType.WRONG_CONTACT: -0.10,
    FeedbackType.BAD_TIMING: 0.0,  # No adjustment
    FeedbackType.LOW_QUALITY_LEAD: -0.10,
    FeedbackType.ALREADY_CUSTOMER: -0.05,
    FeedbackType.COMPETITOR: -0.08,
    FeedbackType.WRONG_EMAIL: -0.12,
    FeedbackType.WRONG_PHONE: -0.08,
    FeedbackType.WRONG_COMPANY: -0.15,
    FeedbackType.OUTDATED_INFO: -0.10,
}


@dataclass
class ManagerFeedback:
    """Feedback from a manager about a lead."""

    id: str
    lead_id: str
    manager_id: str
    feedback_type: FeedbackType
    sentiment: FeedbackSentiment
    comment: str | None
    score_adjustment: float
    created_at: datetime

    # Optional context
    contact_id: str | None = None
    handoff_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "manager_id": self.manager_id,
            "feedback_type": self.feedback_type.value,
            "sentiment": self.sentiment.value,
            "comment": self.comment,
            "score_adjustment": self.score_adjustment,
            "created_at": self.created_at.isoformat(),
            "contact_id": self.contact_id,
            "handoff_id": self.handoff_id,
        }


@dataclass
class FeedbackAggregates:
    """Aggregated feedback statistics."""

    total_feedback: int
    positive_count: int
    negative_count: int
    neutral_count: int
    positive_rate: float
    negative_rate: float
    avg_score_adjustment: float
    by_type: dict[str, int]
    recent_trend: str  # "improving", "stable", "declining"

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_feedback": self.total_feedback,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "neutral_count": self.neutral_count,
            "positive_rate": round(self.positive_rate, 3),
            "negative_rate": round(self.negative_rate, 3),
            "avg_score_adjustment": round(self.avg_score_adjustment, 4),
            "by_type": self.by_type,
            "recent_trend": self.recent_trend,
        }


@dataclass
class ScoringAdjustment:
    """Recommended scoring adjustment based on feedback."""

    entity_type: str  # "source", "segment", "industry"
    entity_value: str
    original_weight: float
    suggested_weight: float
    confidence: float
    sample_size: int
    feedback_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_value": self.entity_value,
            "original_weight": round(self.original_weight, 3),
            "suggested_weight": round(self.suggested_weight, 3),
            "confidence": round(self.confidence, 3),
            "sample_size": self.sample_size,
            "feedback_summary": self.feedback_summary,
        }


class ManagerFeedbackService:
    """Manages manager feedback loop into scoring.

    Features:
    - Feedback collection from managers
    - Score adjustments based on feedback
    - Source/segment quality learning
    - Feedback aggregation and trends
    """

    def __init__(self) -> None:
        """Initialize service."""
        self.max_adjustment = settings.feedback_score_adjustment_max

    # ========================================================================
    # Feedback Collection
    # ========================================================================

    async def submit_feedback(
        self,
        lead_id: str,
        manager_id: str,
        feedback_type: FeedbackType,
        comment: str | None = None,
        contact_id: str | None = None,
        handoff_id: str | None = None,
        lead_source: str | None = None,
        lead_segment: str | None = None,
    ) -> ManagerFeedback:
        """Submit manager feedback for a lead.

        Args:
            lead_id: Lead ID
            manager_id: Manager who provided feedback
            feedback_type: Type of feedback
            comment: Optional comment
            contact_id: Related contact ID
            handoff_id: Related handoff ID
            lead_source: Lead's source (for learning)
            lead_segment: Lead's segment (for learning)

        Returns:
            Created ManagerFeedback
        """
        from app.storage.redis import get_redis
        import json
        from uuid import uuid4

        redis = await get_redis()

        sentiment = FEEDBACK_SENTIMENTS.get(feedback_type, FeedbackSentiment.NEUTRAL)
        base_adjustment = FEEDBACK_SCORE_ADJUSTMENTS.get(feedback_type, 0.0)

        # Clamp to max adjustment
        score_adjustment = max(-self.max_adjustment, min(self.max_adjustment, base_adjustment))

        feedback = ManagerFeedback(
            id=str(uuid4()),
            lead_id=lead_id,
            manager_id=manager_id,
            feedback_type=feedback_type,
            sentiment=sentiment,
            comment=comment,
            score_adjustment=score_adjustment,
            created_at=datetime.now(UTC),
            contact_id=contact_id,
            handoff_id=handoff_id,
        )

        # Store feedback
        key = f"feedback:lead:{lead_id}"
        await redis.lpush(key, json.dumps(feedback.to_dict()))
        await redis.ltrim(key, 0, 49)  # Keep last 50 feedback items per lead
        await redis.expire(key, 86400 * 180)  # 180 days

        # Store in manager's feedback list
        manager_key = f"feedback:manager:{manager_id}"
        await redis.lpush(manager_key, json.dumps(feedback.to_dict()))
        await redis.ltrim(manager_key, 0, 499)
        await redis.expire(manager_key, 86400 * 180)

        # Update aggregates
        await self._update_aggregates(feedback, lead_source, lead_segment)

        logger.info(
            f"[FEEDBACK] Received | lead={lead_id} | manager={manager_id} | "
            f"type={feedback_type.value} | sentiment={sentiment.value}"
        )

        return feedback

    async def _update_aggregates(
        self,
        feedback: ManagerFeedback,
        source: str | None,
        segment: str | None,
    ) -> None:
        """Update aggregate statistics from feedback."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        pipe = redis.pipeline()

        # Global aggregates
        pipe.incr("feedback:global:total")
        pipe.incr(f"feedback:global:sentiment:{feedback.sentiment.value}")
        pipe.incr(f"feedback:global:type:{feedback.feedback_type.value}")
        pipe.incr(f"feedback:global:daily:{today}:total")
        pipe.incr(f"feedback:global:daily:{today}:{feedback.sentiment.value}")

        # Increment score adjustment tracker
        adjustment_key = "feedback:global:adjustment_sum"
        pipe.incrbyfloat(adjustment_key, feedback.score_adjustment)

        # Source-specific aggregates
        if source:
            pipe.incr(f"feedback:source:{source}:total")
            pipe.incr(f"feedback:source:{source}:{feedback.sentiment.value}")
            pipe.incrbyfloat(f"feedback:source:{source}:adjustment_sum", feedback.score_adjustment)

        # Segment-specific aggregates
        if segment:
            pipe.incr(f"feedback:segment:{segment}:total")
            pipe.incr(f"feedback:segment:{segment}:{feedback.sentiment.value}")
            pipe.incrbyfloat(f"feedback:segment:{segment}:adjustment_sum", feedback.score_adjustment)

        await pipe.execute()

    # ========================================================================
    # Feedback Retrieval
    # ========================================================================

    async def get_lead_feedback(
        self,
        lead_id: str,
        limit: int = 20,
    ) -> list[ManagerFeedback]:
        """Get feedback for a lead.

        Args:
            lead_id: Lead ID
            limit: Maximum to return

        Returns:
            List of ManagerFeedback
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        key = f"feedback:lead:{lead_id}"

        items = await redis.lrange(key, 0, limit - 1)

        feedback_list = []
        for item in items:
            data = json.loads(item)
            feedback_list.append(ManagerFeedback(
                id=data["id"],
                lead_id=data["lead_id"],
                manager_id=data["manager_id"],
                feedback_type=FeedbackType(data["feedback_type"]),
                sentiment=FeedbackSentiment(data["sentiment"]),
                comment=data.get("comment"),
                score_adjustment=data["score_adjustment"],
                created_at=datetime.fromisoformat(data["created_at"]),
                contact_id=data.get("contact_id"),
                handoff_id=data.get("handoff_id"),
            ))

        return feedback_list

    async def get_feedback_aggregates(
        self,
        days: int = 30,
    ) -> FeedbackAggregates:
        """Get aggregated feedback statistics.

        Args:
            days: Days to analyze

        Returns:
            FeedbackAggregates
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        total = int(await redis.get("feedback:global:total") or 0)
        positive = int(await redis.get("feedback:global:sentiment:positive") or 0)
        negative = int(await redis.get("feedback:global:sentiment:negative") or 0)
        neutral = int(await redis.get("feedback:global:sentiment:neutral") or 0)

        adjustment_sum = float(await redis.get("feedback:global:adjustment_sum") or 0)

        # Get by type
        by_type = {}
        for ft in FeedbackType:
            count = int(await redis.get(f"feedback:global:type:{ft.value}") or 0)
            if count > 0:
                by_type[ft.value] = count

        # Calculate trend (compare last 7 days to previous 7 days)
        now = datetime.now(UTC)
        recent_positive = 0
        recent_total = 0
        prev_positive = 0
        prev_total = 0

        for i in range(14):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            day_total = int(await redis.get(f"feedback:global:daily:{day}:total") or 0)
            day_positive = int(await redis.get(f"feedback:global:daily:{day}:positive") or 0)

            if i < 7:
                recent_total += day_total
                recent_positive += day_positive
            else:
                prev_total += day_total
                prev_positive += day_positive

        # Determine trend
        if recent_total >= 10 and prev_total >= 10:
            recent_rate = recent_positive / recent_total
            prev_rate = prev_positive / prev_total
            if recent_rate > prev_rate * 1.1:
                trend = "improving"
            elif recent_rate < prev_rate * 0.9:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return FeedbackAggregates(
            total_feedback=total,
            positive_count=positive,
            negative_count=negative,
            neutral_count=neutral,
            positive_rate=positive / total if total > 0 else 0,
            negative_rate=negative / total if total > 0 else 0,
            avg_score_adjustment=adjustment_sum / total if total > 0 else 0,
            by_type=by_type,
            recent_trend=trend,
        )

    # ========================================================================
    # Scoring Adjustments
    # ========================================================================

    async def get_lead_score_adjustment(
        self,
        lead_id: str,
    ) -> float:
        """Get cumulative score adjustment for a lead based on feedback.

        Args:
            lead_id: Lead ID

        Returns:
            Score adjustment (-1.0 to 1.0)
        """
        feedback_list = await self.get_lead_feedback(lead_id)

        if not feedback_list:
            return 0.0

        # Sum adjustments with recency weighting
        now = datetime.now(UTC)
        total_adjustment = 0.0
        total_weight = 0.0

        for fb in feedback_list:
            days_old = (now - fb.created_at).days

            # Exponential decay: half-life of 30 days
            weight = 0.5 ** (days_old / 30)

            total_adjustment += fb.score_adjustment * weight
            total_weight += weight

        if total_weight > 0:
            adjustment = total_adjustment / total_weight
        else:
            adjustment = 0.0

        # Clamp to max
        return max(-self.max_adjustment, min(self.max_adjustment, adjustment))

    async def get_source_adjustment(
        self,
        source: str,
    ) -> ScoringAdjustment:
        """Get recommended scoring adjustment for a source.

        Args:
            source: Data source name

        Returns:
            ScoringAdjustment
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        source = source.lower().strip()

        total = int(await redis.get(f"feedback:source:{source}:total") or 0)
        positive = int(await redis.get(f"feedback:source:{source}:positive") or 0)
        negative = int(await redis.get(f"feedback:source:{source}:negative") or 0)
        adjustment_sum = float(await redis.get(f"feedback:source:{source}:adjustment_sum") or 0)

        # Current weight (from source quality baselines)
        from app.services.data_quality import SOURCE_QUALITY_BASELINES
        original_weight = SOURCE_QUALITY_BASELINES.get(source, 0.7)

        # Calculate suggested adjustment
        if total >= 20:  # Minimum sample
            positive_rate = positive / total
            avg_adjustment = adjustment_sum / total

            # Blend with original weight
            suggested_weight = original_weight + avg_adjustment
            suggested_weight = max(0.1, min(1.0, suggested_weight))

            confidence = min(1.0, total / 100)  # Full confidence at 100 samples

            if positive_rate >= 0.7:
                summary = f"High quality source ({positive_rate:.0%} positive)"
            elif positive_rate <= 0.3:
                summary = f"Low quality source ({positive_rate:.0%} positive)"
            else:
                summary = f"Average quality source ({positive_rate:.0%} positive)"
        else:
            suggested_weight = original_weight
            confidence = 0.0
            summary = f"Insufficient data ({total} samples, need 20+)"

        return ScoringAdjustment(
            entity_type="source",
            entity_value=source,
            original_weight=original_weight,
            suggested_weight=suggested_weight,
            confidence=confidence,
            sample_size=total,
            feedback_summary=summary,
        )

    async def get_segment_adjustment(
        self,
        segment: str,
    ) -> ScoringAdjustment:
        """Get recommended scoring adjustment for a segment.

        Args:
            segment: Industry segment

        Returns:
            ScoringAdjustment
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        segment = segment.lower().strip()

        total = int(await redis.get(f"feedback:segment:{segment}:total") or 0)
        positive = int(await redis.get(f"feedback:segment:{segment}:positive") or 0)
        adjustment_sum = float(await redis.get(f"feedback:segment:{segment}:adjustment_sum") or 0)

        # Original weight based on target industries
        from app.tools.scoring_tools import TARGET_INDUSTRIES
        from app.models.enums import IndustrySegment

        try:
            segment_enum = IndustrySegment(segment)
            original_weight = 0.9 if segment_enum in TARGET_INDUSTRIES else 0.5
        except ValueError:
            original_weight = 0.5

        if total >= 20:
            positive_rate = positive / total
            avg_adjustment = adjustment_sum / total

            suggested_weight = original_weight + avg_adjustment
            suggested_weight = max(0.1, min(1.0, suggested_weight))
            confidence = min(1.0, total / 100)

            if positive_rate >= 0.7:
                summary = f"High-converting segment ({positive_rate:.0%} positive)"
            elif positive_rate <= 0.3:
                summary = f"Low-converting segment ({positive_rate:.0%} positive)"
            else:
                summary = f"Average segment ({positive_rate:.0%} positive)"
        else:
            suggested_weight = original_weight
            confidence = 0.0
            summary = f"Insufficient data ({total} samples)"

        return ScoringAdjustment(
            entity_type="segment",
            entity_value=segment,
            original_weight=original_weight,
            suggested_weight=suggested_weight,
            confidence=confidence,
            sample_size=total,
            feedback_summary=summary,
        )

    async def get_all_adjustments(self) -> dict[str, list[ScoringAdjustment]]:
        """Get all recommended scoring adjustments.

        Returns:
            Dict with lists of adjustments by type
        """
        from app.storage.redis import get_redis
        from app.services.data_quality import SOURCE_QUALITY_BASELINES

        redis = await get_redis()

        # Get source adjustments
        source_adjustments = []
        for source in SOURCE_QUALITY_BASELINES.keys():
            adj = await self.get_source_adjustment(source)
            if adj.sample_size > 0:
                source_adjustments.append(adj)

        # Get segment adjustments
        segment_adjustments = []
        from app.models.enums import IndustrySegment
        for segment in IndustrySegment:
            adj = await self.get_segment_adjustment(segment.value)
            if adj.sample_size > 0:
                segment_adjustments.append(adj)

        return {
            "sources": sorted(source_adjustments, key=lambda x: x.sample_size, reverse=True),
            "segments": sorted(segment_adjustments, key=lambda x: x.sample_size, reverse=True),
        }

    async def get_feedback_stats(
        self,
        days: int = 30,
    ) -> dict[str, Any]:
        """Get feedback statistics.

        Args:
            days: Days to analyze

        Returns:
            Feedback statistics dict
        """
        aggregates = await self.get_feedback_aggregates(days=days)

        return {
            "period_days": days,
            "total_feedback": aggregates.total_feedback,
            "positive_count": aggregates.positive_count,
            "negative_count": aggregates.negative_count,
            "neutral_count": aggregates.neutral_count,
            "positive_rate": aggregates.positive_rate,
            "negative_rate": aggregates.negative_rate,
            "avg_score_adjustment": aggregates.avg_score_adjustment,
            "by_type": aggregates.by_type,
            "recent_trend": aggregates.recent_trend,
        }


# Singleton
manager_feedback = ManagerFeedbackService()
