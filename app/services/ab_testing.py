"""Simple A/B Testing for Email Campaigns.

Production-safe A/B testing for subject lines and email sequences.
"""

import hashlib
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class VariantType(str, Enum):
    """Type of A/B test variant."""

    SUBJECT = "subject"
    SEQUENCE = "sequence"
    BODY = "body"


@dataclass
class Variant:
    """A/B test variant."""

    id: str
    name: str
    content: str  # Subject line or sequence ID
    weight: float = 0.5  # Traffic weight (0.0-1.0)


@dataclass
class ABTest:
    """A/B test configuration."""

    test_id: str
    campaign_id: str
    variant_type: VariantType
    variants: list[Variant]
    created_at: datetime
    is_active: bool = True
    winner_variant_id: str | None = None
    min_sample_size: int = 100
    confidence_threshold: float = 0.95
    holdout_percent: float = 0.0  # 0.0-1.0, portion held out from all variants
    winner_metric: str = "qualified_rate"  # reply_rate, qualified_rate, handoff_rate


@dataclass
class VariantStats:
    """Statistics for a variant."""

    variant_id: str
    variant_name: str
    sent: int
    delivered: int
    opened: int
    clicked: int
    replied: int
    qualified: int  # Qualified replies (positive intent)
    handoffs: int  # Handed to sales manager
    bounced: int
    delivery_rate: float
    open_rate: float
    click_rate: float
    reply_rate: float
    qualified_rate: float  # qualified / delivered
    handoff_rate: float  # handoffs / delivered
    bounce_rate: float
    is_holdout: bool = False  # True if this is the holdout group


class WinnerMetric(str, Enum):
    """Metric used to determine A/B test winner."""

    REPLY_RATE = "reply_rate"
    QUALIFIED_RATE = "qualified_rate"
    HANDOFF_RATE = "handoff_rate"


@dataclass
class ABTestResults:
    """Results of an A/B test."""

    test_id: str
    campaign_id: str
    variant_type: str
    is_active: bool
    total_sent: int
    variants: list[VariantStats]
    holdout: VariantStats | None = None  # Holdout group stats
    winner_id: str | None = None
    winner_confidence: float | None = None
    winner_metric: str | None = None
    can_declare_winner: bool = False
    lift_vs_holdout: float | None = None  # % improvement over holdout

    def to_dict(self) -> dict[str, Any]:
        result = {
            "test_id": self.test_id,
            "campaign_id": self.campaign_id,
            "variant_type": self.variant_type,
            "is_active": self.is_active,
            "total_sent": self.total_sent,
            "variants": [
                {
                    "variant_id": v.variant_id,
                    "variant_name": v.variant_name,
                    "sent": v.sent,
                    "delivered": v.delivered,
                    "opened": v.opened,
                    "clicked": v.clicked,
                    "replied": v.replied,
                    "qualified": v.qualified,
                    "handoffs": v.handoffs,
                    "bounced": v.bounced,
                    "delivery_rate": v.delivery_rate,
                    "open_rate": v.open_rate,
                    "click_rate": v.click_rate,
                    "reply_rate": v.reply_rate,
                    "qualified_rate": v.qualified_rate,
                    "handoff_rate": v.handoff_rate,
                    "bounce_rate": v.bounce_rate,
                    "is_holdout": v.is_holdout,
                }
                for v in self.variants
            ],
            "winner_id": self.winner_id,
            "winner_confidence": self.winner_confidence,
            "winner_metric": self.winner_metric,
            "can_declare_winner": self.can_declare_winner,
            "lift_vs_holdout": self.lift_vs_holdout,
        }
        if self.holdout:
            result["holdout"] = {
                "variant_id": self.holdout.variant_id,
                "variant_name": self.holdout.variant_name,
                "sent": self.holdout.sent,
                "qualified_rate": self.holdout.qualified_rate,
                "handoff_rate": self.holdout.handoff_rate,
            }
        return result


class ABTestingService:
    """Simple A/B testing for email campaigns.

    Features:
    - Create subject line A/B tests
    - Create sequence A/B tests
    - Deterministic variant assignment (based on lead_id hash)
    - Track variant performance
    - Auto-detect winner based on reply rate
    """

    def __init__(self) -> None:
        """Initialize A/B testing service."""
        pass

    # ========================================================================
    # Test Management
    # ========================================================================

    async def create_test(
        self,
        campaign_id: str,
        variant_type: VariantType,
        variants: list[dict[str, Any]],
        min_sample_size: int = 100,
        holdout_percent: float | None = None,
        winner_metric: str = "qualified_rate",
    ) -> ABTest:
        """Create a new A/B test.

        Args:
            campaign_id: Campaign to test
            variant_type: Type of test (subject, sequence, body)
            variants: List of variant configs [{name: str, content: str, weight: float}]
            min_sample_size: Min emails per variant before declaring winner
            holdout_percent: Percent of leads to hold out (0.0-1.0), uses settings default if None
            winner_metric: Metric for winner detection (reply_rate, qualified_rate, handoff_rate)

        Returns:
            Created ABTest
        """
        from app.storage.redis import get_redis
        from app.config.settings import settings

        redis = await get_redis()

        # Use settings default for holdout if not specified
        if holdout_percent is None:
            holdout_percent = settings.ab_holdout_percent

        # Generate test ID
        test_id = f"ab_{campaign_id}_{variant_type.value}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

        # Normalize weights (account for holdout)
        effective_weight = 1.0 - holdout_percent
        total_weight = sum(v.get("weight", 1.0) for v in variants)
        variant_objects = []
        for i, v in enumerate(variants):
            variant_id = f"{test_id}_v{i}"
            weight = (v.get("weight", 1.0) / total_weight) * effective_weight
            variant_objects.append(
                Variant(
                    id=variant_id,
                    name=v.get("name", f"Variant {chr(65 + i)}"),
                    content=v["content"],
                    weight=weight,
                )
            )

        # Add holdout as a special variant if enabled
        if holdout_percent > 0:
            holdout_id = f"{test_id}_holdout"
            variant_objects.append(
                Variant(
                    id=holdout_id,
                    name="Holdout",
                    content="__HOLDOUT__",  # Special marker
                    weight=holdout_percent,
                )
            )

        test = ABTest(
            test_id=test_id,
            campaign_id=campaign_id,
            variant_type=variant_type,
            variants=variant_objects,
            created_at=datetime.now(UTC),
            is_active=True,
            min_sample_size=min_sample_size,
            holdout_percent=holdout_percent,
            winner_metric=winner_metric,
        )

        # Store test config
        test_data = {
            "test_id": test.test_id,
            "campaign_id": test.campaign_id,
            "variant_type": test.variant_type.value,
            "variants": [
                {
                    "id": v.id,
                    "name": v.name,
                    "content": v.content,
                    "weight": v.weight,
                }
                for v in test.variants
            ],
            "created_at": test.created_at.isoformat(),
            "is_active": test.is_active,
            "min_sample_size": test.min_sample_size,
            "holdout_percent": test.holdout_percent,
            "winner_metric": test.winner_metric,
        }

        import json

        await redis.set(f"abtest:{test_id}", json.dumps(test_data))
        await redis.sadd(f"abtest:campaign:{campaign_id}", test_id)

        logger.info(
            f"[AB_TEST] Created test | test_id={test_id} | "
            f"campaign={campaign_id} | type={variant_type.value} | "
            f"variants={len(variants)}"
        )

        return test

    async def get_test(self, test_id: str) -> ABTest | None:
        """Get A/B test by ID.

        Args:
            test_id: Test ID

        Returns:
            ABTest or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        data = await redis.get(f"abtest:{test_id}")

        if not data:
            return None

        test_data = json.loads(data)
        return ABTest(
            test_id=test_data["test_id"],
            campaign_id=test_data["campaign_id"],
            variant_type=VariantType(test_data["variant_type"]),
            variants=[
                Variant(
                    id=v["id"],
                    name=v["name"],
                    content=v["content"],
                    weight=v["weight"],
                )
                for v in test_data["variants"]
            ],
            created_at=datetime.fromisoformat(test_data["created_at"]),
            is_active=test_data.get("is_active", True),
            winner_variant_id=test_data.get("winner_variant_id"),
            min_sample_size=test_data.get("min_sample_size", 100),
            holdout_percent=test_data.get("holdout_percent", 0.0),
            winner_metric=test_data.get("winner_metric", "qualified_rate"),
        )

    async def get_campaign_tests(self, campaign_id: str) -> list[ABTest]:
        """Get all A/B tests for a campaign.

        Args:
            campaign_id: Campaign ID

        Returns:
            List of ABTests
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        test_ids = await redis.smembers(f"abtest:campaign:{campaign_id}")

        tests = []
        for test_id in test_ids:
            test = await self.get_test(test_id)
            if test:
                tests.append(test)

        return tests

    async def stop_test(self, test_id: str, winner_variant_id: str | None = None) -> bool:
        """Stop an A/B test.

        Args:
            test_id: Test ID
            winner_variant_id: Winning variant ID (optional)

        Returns:
            True if stopped successfully
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        data = await redis.get(f"abtest:{test_id}")

        if not data:
            return False

        test_data = json.loads(data)
        test_data["is_active"] = False
        if winner_variant_id:
            test_data["winner_variant_id"] = winner_variant_id

        await redis.set(f"abtest:{test_id}", json.dumps(test_data))

        logger.info(
            f"[AB_TEST] Stopped test | test_id={test_id} | "
            f"winner={winner_variant_id}"
        )

        return True

    # ========================================================================
    # Variant Assignment
    # ========================================================================

    async def assign_variant(
        self,
        test_id: str,
        lead_id: str,
    ) -> Variant | None:
        """Assign a variant to a lead (deterministic).

        Uses hash-based assignment to ensure same lead always gets same variant.
        This enables consistent experience across retries.

        Args:
            test_id: A/B test ID
            lead_id: Lead ID

        Returns:
            Assigned Variant or None if test not found
        """
        test = await self.get_test(test_id)
        if not test or not test.is_active:
            return None

        # If winner declared, always return winner
        if test.winner_variant_id:
            for v in test.variants:
                if v.id == test.winner_variant_id:
                    return v

        # Deterministic hash-based assignment
        hash_input = f"{test_id}:{lead_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        normalized = (hash_value % 10000) / 10000.0  # 0.0 - 1.0

        # Find variant based on cumulative weights
        cumulative = 0.0
        for variant in test.variants:
            cumulative += variant.weight
            if normalized < cumulative:
                return variant

        # Fallback to last variant
        return test.variants[-1] if test.variants else None

    async def get_assigned_variant_id(
        self,
        test_id: str,
        lead_id: str,
    ) -> str | None:
        """Get previously assigned variant ID for a lead.

        Args:
            test_id: Test ID
            lead_id: Lead ID

        Returns:
            Variant ID or None
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        key = f"abtest:assignment:{test_id}:{lead_id}"
        return await redis.get(key)

    async def record_assignment(
        self,
        test_id: str,
        lead_id: str,
        variant_id: str,
    ) -> None:
        """Record variant assignment for tracking.

        Args:
            test_id: Test ID
            lead_id: Lead ID
            variant_id: Assigned variant ID
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Store assignment
        key = f"abtest:assignment:{test_id}:{lead_id}"
        await redis.set(key, variant_id, ex=2592000)  # 30 days

        # Increment sent counter for variant
        await redis.incr(f"abtest:stats:{variant_id}:sent")

    # ========================================================================
    # Statistics Tracking
    # ========================================================================

    async def record_event(
        self,
        variant_id: str,
        event_type: str,
    ) -> None:
        """Record an event for a variant.

        Args:
            variant_id: Variant ID
            event_type: Event type (delivered, opened, clicked, replied, bounced)
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        key = f"abtest:stats:{variant_id}:{event_type}"
        await redis.incr(key)

    async def get_test_results(self, test_id: str) -> ABTestResults | None:
        """Get A/B test results with statistics.

        Args:
            test_id: Test ID

        Returns:
            ABTestResults or None
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        test = await self.get_test(test_id)

        if not test:
            return None

        variant_stats = []
        holdout_stats = None
        total_sent = 0

        for variant in test.variants:
            sent = int(await redis.get(f"abtest:stats:{variant.id}:sent") or 0)
            delivered = int(await redis.get(f"abtest:stats:{variant.id}:delivered") or 0)
            opened = int(await redis.get(f"abtest:stats:{variant.id}:opened") or 0)
            clicked = int(await redis.get(f"abtest:stats:{variant.id}:clicked") or 0)
            replied = int(await redis.get(f"abtest:stats:{variant.id}:replied") or 0)
            qualified = int(await redis.get(f"abtest:stats:{variant.id}:qualified") or 0)
            handoffs = int(await redis.get(f"abtest:stats:{variant.id}:handoffs") or 0)
            bounced = int(await redis.get(f"abtest:stats:{variant.id}:bounced") or 0)

            total_sent += sent
            is_holdout = variant.content == "__HOLDOUT__"

            stats = VariantStats(
                variant_id=variant.id,
                variant_name=variant.name,
                sent=sent,
                delivered=delivered,
                opened=opened,
                clicked=clicked,
                replied=replied,
                qualified=qualified,
                handoffs=handoffs,
                bounced=bounced,
                delivery_rate=delivered / sent if sent > 0 else 0,
                open_rate=opened / delivered if delivered > 0 else 0,
                click_rate=clicked / delivered if delivered > 0 else 0,
                reply_rate=replied / delivered if delivered > 0 else 0,
                qualified_rate=qualified / delivered if delivered > 0 else 0,
                handoff_rate=handoffs / delivered if delivered > 0 else 0,
                bounce_rate=bounced / sent if sent > 0 else 0,
                is_holdout=is_holdout,
            )

            if is_holdout:
                holdout_stats = stats
            else:
                variant_stats.append(stats)

        # Check if we can declare a winner (excluding holdout from analysis)
        can_declare, winner_id, confidence = self._analyze_winner(
            variant_stats,
            min_sample_size=test.min_sample_size,
            winner_metric=test.winner_metric,
        )

        # Calculate lift vs holdout if we have a winner and holdout
        lift_vs_holdout = None
        if winner_id and holdout_stats:
            winner_stats = next((v for v in variant_stats if v.variant_id == winner_id), None)
            if winner_stats:
                lift_vs_holdout = self._calculate_lift(
                    winner_stats, holdout_stats, test.winner_metric
                )

        return ABTestResults(
            test_id=test.test_id,
            campaign_id=test.campaign_id,
            variant_type=test.variant_type.value,
            is_active=test.is_active,
            total_sent=total_sent,
            variants=variant_stats,
            holdout=holdout_stats,
            winner_id=winner_id,
            winner_confidence=confidence,
            winner_metric=test.winner_metric,
            can_declare_winner=can_declare,
            lift_vs_holdout=lift_vs_holdout,
        )

    def _get_metric_value(self, stats: VariantStats, metric: str) -> float:
        """Get metric value from stats based on metric name."""
        if metric == "reply_rate":
            return stats.reply_rate
        elif metric == "qualified_rate":
            return stats.qualified_rate
        elif metric == "handoff_rate":
            return stats.handoff_rate
        else:
            return stats.qualified_rate  # Default

    def _calculate_lift(
        self,
        treatment: VariantStats,
        holdout: VariantStats,
        metric: str,
    ) -> float | None:
        """Calculate lift of treatment vs holdout.

        Args:
            treatment: Treatment variant stats
            holdout: Holdout group stats
            metric: Metric to compare

        Returns:
            Lift as percentage (e.g., 25.0 for 25% lift)
        """
        treatment_value = self._get_metric_value(treatment, metric)
        holdout_value = self._get_metric_value(holdout, metric)

        if holdout_value == 0:
            return None if treatment_value == 0 else 100.0

        lift = ((treatment_value - holdout_value) / holdout_value) * 100
        return round(lift, 1)

    def _analyze_winner(
        self,
        variants: list[VariantStats],
        min_sample_size: int = 100,
        winner_metric: str = "qualified_rate",
    ) -> tuple[bool, str | None, float | None]:
        """Analyze variants to determine winner.

        Uses configurable metric for comparison with minimum sample size.

        Args:
            variants: List of variant statistics (excluding holdout)
            min_sample_size: Minimum emails per variant
            winner_metric: Metric to use (reply_rate, qualified_rate, handoff_rate)

        Returns:
            Tuple of (can_declare_winner, winner_id, confidence)
        """
        if len(variants) < 2:
            return False, None, None

        # Check if all variants have minimum sample
        for v in variants:
            if v.sent < min_sample_size:
                return False, None, None

        # Sort by the selected metric
        sorted_variants = sorted(
            variants,
            key=lambda x: self._get_metric_value(x, winner_metric),
            reverse=True
        )
        best = sorted_variants[0]
        second = sorted_variants[1]

        best_value = self._get_metric_value(best, winner_metric)
        second_value = self._get_metric_value(second, winner_metric)

        # Simple confidence calculation based on difference
        if best_value == 0 and second_value == 0:
            return False, None, None

        # Calculate relative improvement
        if second_value > 0:
            improvement = (best_value - second_value) / second_value
        else:
            improvement = 1.0 if best_value > 0 else 0

        # Simple heuristic: >20% improvement with significant sample = winner
        if improvement >= 0.20 and best.sent >= min_sample_size:
            confidence = min(0.95, 0.80 + improvement * 0.5)
            return True, best.variant_id, round(confidence, 2)

        return False, None, None

    def is_holdout_variant(self, variant: Variant) -> bool:
        """Check if variant is a holdout group."""
        return variant.content == "__HOLDOUT__"

    # ========================================================================
    # Quick Subject Line Test
    # ========================================================================

    async def create_subject_test(
        self,
        campaign_id: str,
        subject_a: str,
        subject_b: str,
        name_a: str = "Subject A",
        name_b: str = "Subject B",
    ) -> ABTest:
        """Quick helper to create a subject line A/B test.

        Args:
            campaign_id: Campaign ID
            subject_a: First subject line
            subject_b: Second subject line
            name_a: Name for first variant
            name_b: Name for second variant

        Returns:
            Created ABTest
        """
        return await self.create_test(
            campaign_id=campaign_id,
            variant_type=VariantType.SUBJECT,
            variants=[
                {"name": name_a, "content": subject_a, "weight": 0.5},
                {"name": name_b, "content": subject_b, "weight": 0.5},
            ],
        )

    async def get_subject_for_lead(
        self,
        campaign_id: str,
        lead_id: str,
        default_subject: str,
    ) -> str:
        """Get subject line for a lead, considering A/B tests.

        Args:
            campaign_id: Campaign ID
            lead_id: Lead ID
            default_subject: Default subject if no test active

        Returns:
            Subject line to use
        """
        tests = await self.get_campaign_tests(campaign_id)

        # Find active subject test
        for test in tests:
            if test.variant_type == VariantType.SUBJECT and test.is_active:
                variant = await self.assign_variant(test.test_id, lead_id)
                if variant:
                    await self.record_assignment(test.test_id, lead_id, variant.id)
                    logger.debug(
                        f"[AB_TEST] Assigned subject variant | lead={lead_id} | "
                        f"variant={variant.name}"
                    )
                    return variant.content

        return default_subject


# Singleton
ab_testing_service = ABTestingService()
