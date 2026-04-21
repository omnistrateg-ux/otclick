"""Sender/Domain Warm-up Service.

Gradually increases sending limits for new senders and domains to build reputation.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.config.settings import settings

UTC = timezone.utc

logger = logging.getLogger(__name__)


class WarmupPhase(str, Enum):
    """Warm-up phase."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    COMPLETED = "completed"
    PAUSED = "paused"  # Paused due to issues


@dataclass
class WarmupStatus:
    """Warm-up status for a sender or domain."""

    entity: str
    entity_type: str  # "sender" or "domain"
    phase: WarmupPhase
    started_at: datetime | None
    current_day: int
    current_daily_limit: int
    max_daily_limit: int
    sent_today: int
    remaining_today: int
    days_to_full: int
    progress_percent: float
    health_score: float | None = None
    pause_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "entity_type": self.entity_type,
            "phase": self.phase.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "current_day": self.current_day,
            "current_daily_limit": self.current_daily_limit,
            "max_daily_limit": self.max_daily_limit,
            "sent_today": self.sent_today,
            "remaining_today": self.remaining_today,
            "days_to_full": self.days_to_full,
            "progress_percent": self.progress_percent,
            "health_score": self.health_score,
            "pause_reason": self.pause_reason,
        }


@dataclass
class WarmupConfig:
    """Warm-up configuration."""

    initial_daily_limit: int
    max_daily_limit: int
    increment_percent: int
    days_to_full: int

    @classmethod
    def from_settings(cls) -> "WarmupConfig":
        """Create config from settings."""
        return cls(
            initial_daily_limit=settings.warmup_initial_daily_limit,
            max_daily_limit=settings.warmup_max_daily_limit,
            increment_percent=settings.warmup_increment_percent,
            days_to_full=settings.warmup_days_to_full,
        )


class WarmupService:
    """Manages sender and domain warm-up.

    Features:
    - Gradual limit increase for new senders/domains
    - Auto-pause on health issues
    - Integration with reputation scoring
    - Progress tracking
    """

    def __init__(self, config: WarmupConfig | None = None) -> None:
        """Initialize warm-up service.

        Args:
            config: Warm-up configuration (uses settings if not provided)
        """
        self.config = config or WarmupConfig.from_settings()

    # ========================================================================
    # Warm-up Management
    # ========================================================================

    async def start_warmup(
        self,
        entity: str,
        entity_type: str = "sender",
        custom_config: dict[str, Any] | None = None,
    ) -> WarmupStatus:
        """Start warm-up for a sender or domain.

        Args:
            entity: Email address or domain
            entity_type: "sender" or "domain"
            custom_config: Override default config

        Returns:
            WarmupStatus
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        entity = entity.lower().strip()
        key = f"warmup:{entity_type}:{entity}"

        # Check if already warming
        existing = await redis.hgetall(key)
        if existing and existing.get("phase") == WarmupPhase.WARMING.value:
            logger.info(f"[WARMUP] Already warming | {entity_type}={entity}")
            return await self.get_warmup_status(entity, entity_type)

        # Initialize warm-up
        now = datetime.now(UTC)
        config = self.config

        if custom_config:
            config = WarmupConfig(
                initial_daily_limit=custom_config.get("initial_daily_limit", config.initial_daily_limit),
                max_daily_limit=custom_config.get("max_daily_limit", config.max_daily_limit),
                increment_percent=custom_config.get("increment_percent", config.increment_percent),
                days_to_full=custom_config.get("days_to_full", config.days_to_full),
            )

        warmup_data = {
            "entity": entity,
            "entity_type": entity_type,
            "phase": WarmupPhase.WARMING.value,
            "started_at": now.isoformat(),
            "initial_daily_limit": str(config.initial_daily_limit),
            "max_daily_limit": str(config.max_daily_limit),
            "increment_percent": str(config.increment_percent),
            "days_to_full": str(config.days_to_full),
        }

        await redis.hset(key, mapping=warmup_data)
        await redis.expire(key, 86400 * 60)  # 60 days TTL

        logger.info(
            f"[WARMUP] Started | {entity_type}={entity} | "
            f"initial_limit={config.initial_daily_limit} | "
            f"max_limit={config.max_daily_limit}"
        )

        return await self.get_warmup_status(entity, entity_type)

    async def get_warmup_status(
        self,
        entity: str,
        entity_type: str = "sender",
    ) -> WarmupStatus:
        """Get warm-up status for a sender or domain.

        Args:
            entity: Email or domain
            entity_type: "sender" or "domain"

        Returns:
            WarmupStatus
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        entity = entity.lower().strip()
        key = f"warmup:{entity_type}:{entity}"
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        data = await redis.hgetall(key)

        if not data:
            # Not in warm-up - return "not started" or "completed" based on history
            sent_key = f"throttle:{entity_type}:{entity}:{today}"
            sent_today = int(await redis.get(sent_key) or 0)

            # If has significant history, assume completed
            total_sent = await self._get_total_sent(redis, entity, entity_type, days=30)

            if total_sent > self.config.max_daily_limit * 7:
                # Sent more than a week's worth at max - assume warmed up
                return WarmupStatus(
                    entity=entity,
                    entity_type=entity_type,
                    phase=WarmupPhase.COMPLETED,
                    started_at=None,
                    current_day=0,
                    current_daily_limit=self.config.max_daily_limit,
                    max_daily_limit=self.config.max_daily_limit,
                    sent_today=sent_today,
                    remaining_today=max(0, self.config.max_daily_limit - sent_today),
                    days_to_full=0,
                    progress_percent=100.0,
                )
            else:
                return WarmupStatus(
                    entity=entity,
                    entity_type=entity_type,
                    phase=WarmupPhase.NOT_STARTED,
                    started_at=None,
                    current_day=0,
                    current_daily_limit=self.config.initial_daily_limit,
                    max_daily_limit=self.config.max_daily_limit,
                    sent_today=sent_today,
                    remaining_today=max(0, self.config.initial_daily_limit - sent_today),
                    days_to_full=self.config.days_to_full,
                    progress_percent=0.0,
                )

        # Parse warm-up data
        phase = WarmupPhase(data.get("phase", WarmupPhase.NOT_STARTED.value))
        started_at_str = data.get("started_at")
        started_at = datetime.fromisoformat(started_at_str) if started_at_str else None

        initial_limit = int(data.get("initial_daily_limit", self.config.initial_daily_limit))
        max_limit = int(data.get("max_daily_limit", self.config.max_daily_limit))
        increment_pct = int(data.get("increment_percent", self.config.increment_percent))
        days_to_full = int(data.get("days_to_full", self.config.days_to_full))
        pause_reason = data.get("pause_reason")

        # Calculate current day and limit
        current_day = 0
        if started_at:
            current_day = (datetime.now(UTC) - started_at).days + 1

        current_limit = self._calculate_daily_limit(
            current_day, initial_limit, max_limit, increment_pct
        )

        # Check if warm-up is complete
        if current_limit >= max_limit and phase == WarmupPhase.WARMING:
            phase = WarmupPhase.COMPLETED
            await redis.hset(key, "phase", WarmupPhase.COMPLETED.value)

        # Get today's sent count
        sent_key = f"throttle:{entity_type}:{entity}:{today}"
        sent_today = int(await redis.get(sent_key) or 0)

        # Calculate progress
        if days_to_full > 0:
            progress = min(100.0, (current_day / days_to_full) * 100)
        else:
            progress = 100.0 if phase == WarmupPhase.COMPLETED else 0.0

        return WarmupStatus(
            entity=entity,
            entity_type=entity_type,
            phase=phase,
            started_at=started_at,
            current_day=current_day,
            current_daily_limit=current_limit,
            max_daily_limit=max_limit,
            sent_today=sent_today,
            remaining_today=max(0, current_limit - sent_today),
            days_to_full=max(0, days_to_full - current_day),
            progress_percent=round(progress, 1),
            pause_reason=pause_reason,
        )

    async def get_current_limit(
        self,
        entity: str,
        entity_type: str = "sender",
    ) -> int:
        """Get current daily limit for a sender/domain considering warm-up.

        Args:
            entity: Email or domain
            entity_type: "sender" or "domain"

        Returns:
            Current daily limit
        """
        if not settings.warmup_enabled:
            return self.config.max_daily_limit

        status = await self.get_warmup_status(entity, entity_type)

        if status.phase == WarmupPhase.PAUSED:
            return 0  # No sending allowed when paused

        return status.current_daily_limit

    async def can_send(
        self,
        entity: str,
        entity_type: str = "sender",
    ) -> tuple[bool, str | None]:
        """Check if sender/domain can send based on warm-up limits.

        Args:
            entity: Email or domain
            entity_type: "sender" or "domain"

        Returns:
            Tuple of (can_send, reason_if_blocked)
        """
        status = await self.get_warmup_status(entity, entity_type)

        if status.phase == WarmupPhase.PAUSED:
            return False, f"warmup_paused:{status.pause_reason}"

        if status.remaining_today <= 0:
            return False, f"warmup_limit_reached:{status.sent_today}/{status.current_daily_limit}"

        return True, None

    async def pause_warmup(
        self,
        entity: str,
        entity_type: str = "sender",
        reason: str = "manual",
    ) -> bool:
        """Pause warm-up for a sender/domain.

        Args:
            entity: Email or domain
            entity_type: "sender" or "domain"
            reason: Pause reason

        Returns:
            True if paused successfully
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        entity = entity.lower().strip()
        key = f"warmup:{entity_type}:{entity}"

        exists = await redis.exists(key)
        if not exists:
            return False

        await redis.hset(key, mapping={
            "phase": WarmupPhase.PAUSED.value,
            "pause_reason": reason,
            "paused_at": datetime.now(UTC).isoformat(),
        })

        logger.warning(f"[WARMUP] Paused | {entity_type}={entity} | reason={reason}")
        return True

    async def resume_warmup(
        self,
        entity: str,
        entity_type: str = "sender",
    ) -> bool:
        """Resume warm-up for a sender/domain.

        Args:
            entity: Email or domain
            entity_type: "sender" or "domain"

        Returns:
            True if resumed successfully
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        entity = entity.lower().strip()
        key = f"warmup:{entity_type}:{entity}"

        exists = await redis.exists(key)
        if not exists:
            return False

        await redis.hset(key, mapping={
            "phase": WarmupPhase.WARMING.value,
            "pause_reason": "",
        })
        await redis.hdel(key, "paused_at")

        logger.info(f"[WARMUP] Resumed | {entity_type}={entity}")
        return True

    async def auto_pause_on_issues(
        self,
        entity: str,
        entity_type: str = "sender",
        bounce_rate: float = 0.0,
        complaint_rate: float = 0.0,
    ) -> bool:
        """Auto-pause warm-up if health issues detected.

        Args:
            entity: Email or domain
            entity_type: "sender" or "domain"
            bounce_rate: Current bounce rate
            complaint_rate: Current complaint rate

        Returns:
            True if paused due to issues
        """
        # Pause thresholds during warm-up are stricter
        warmup_bounce_threshold = settings.bounce_rate_warning  # 5%
        warmup_complaint_threshold = settings.complaint_rate_warning  # 0.1%

        if bounce_rate >= warmup_bounce_threshold:
            await self.pause_warmup(
                entity, entity_type,
                reason=f"high_bounce_rate:{bounce_rate:.2%}"
            )
            return True

        if complaint_rate >= warmup_complaint_threshold:
            await self.pause_warmup(
                entity, entity_type,
                reason=f"high_complaint_rate:{complaint_rate:.2%}"
            )
            return True

        return False

    def _calculate_daily_limit(
        self,
        day: int,
        initial: int,
        maximum: int,
        increment_pct: int,
    ) -> int:
        """Calculate daily limit based on warm-up day.

        Uses compound growth: limit = initial * (1 + increment_pct/100) ^ (day-1)

        Args:
            day: Current warm-up day (1-indexed)
            initial: Initial daily limit
            maximum: Maximum daily limit
            increment_pct: Daily increment percentage

        Returns:
            Current daily limit
        """
        if day <= 0:
            return initial

        growth_factor = 1 + (increment_pct / 100)
        limit = initial * (growth_factor ** (day - 1))

        return min(int(limit), maximum)

    async def _get_total_sent(
        self,
        redis: Any,
        entity: str,
        entity_type: str,
        days: int = 30,
    ) -> int:
        """Get total emails sent by entity over past days."""
        total = 0
        now = datetime.now(UTC)

        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            key = f"throttle:{entity_type}:{entity}:{day}"
            count = int(await redis.get(key) or 0)
            total += count

        return total

    async def get_all_warmup_entities(
        self,
        entity_type: str | None = None,
    ) -> list[WarmupStatus]:
        """Get all entities currently in warm-up.

        Args:
            entity_type: Filter by type ("sender" or "domain")

        Returns:
            List of WarmupStatus
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        results = []

        pattern = f"warmup:{entity_type or '*'}:*"
        async for key in redis.scan_iter(pattern):
            parts = key.split(":")
            if len(parts) >= 3:
                etype = parts[1]
                entity = ":".join(parts[2:])  # Handle emails with colons
                status = await self.get_warmup_status(entity, etype)
                if status.phase in (WarmupPhase.WARMING, WarmupPhase.PAUSED):
                    results.append(status)

        return results


# Singleton
warmup_service = WarmupService()
