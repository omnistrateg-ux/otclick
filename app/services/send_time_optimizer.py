"""Send-Time Optimization Service.

Optimizes email send times based on segment engagement patterns.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


# Default optimal windows by segment (Moscow timezone, UTC+3)
# Format: list of (hour_start, hour_end, weight)
DEFAULT_SEND_WINDOWS = {
    "retail": [
        (9, 11, 1.0),   # Morning peak
        (14, 16, 0.8),  # After lunch
    ],
    "horeca": [
        (10, 12, 1.0),  # Late morning (before rush)
        (15, 17, 0.7),  # Afternoon lull
    ],
    "it": [
        (10, 12, 1.0),  # Mid-morning
        (14, 16, 0.9),  # Early afternoon
    ],
    "manufacturing": [
        (8, 10, 1.0),   # Early morning
        (13, 15, 0.8),  # After lunch
    ],
    "logistics": [
        (7, 9, 0.9),    # Very early
        (11, 13, 1.0),  # Before lunch
    ],
    "healthcare": [
        (8, 10, 1.0),   # Morning shift change
        (14, 16, 0.7),  # Afternoon
    ],
    "default": [
        (9, 11, 1.0),   # Standard morning
        (14, 16, 0.8),  # Standard afternoon
    ],
}

# Days with typically lower engagement
LOW_ENGAGEMENT_DAYS = {
    0,  # Monday - people catching up
    4,  # Friday - weekend mode
}

# Best days for B2B outreach
HIGH_ENGAGEMENT_DAYS = {
    1,  # Tuesday
    2,  # Wednesday
    3,  # Thursday
}


@dataclass
class SendTimeRecommendation:
    """Recommended send time."""

    recommended_time: datetime
    segment: str
    confidence: float  # 0.0-1.0
    reason: str
    alternative_times: list[datetime]
    window_start: int  # Hour
    window_end: int  # Hour
    day_quality: str  # "high", "medium", "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommended_time": self.recommended_time.isoformat(),
            "segment": self.segment,
            "confidence": self.confidence,
            "reason": self.reason,
            "alternative_times": [t.isoformat() for t in self.alternative_times],
            "window_start": self.window_start,
            "window_end": self.window_end,
            "day_quality": self.day_quality,
        }


@dataclass
class SegmentSendStats:
    """Send time statistics for a segment."""

    segment: str
    total_sent: int
    total_opened: int
    total_replied: int
    best_hour: int
    best_day: int
    hourly_open_rates: dict[int, float]
    daily_open_rates: dict[int, float]
    hourly_reply_rates: dict[int, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment": self.segment,
            "total_sent": self.total_sent,
            "total_opened": self.total_opened,
            "total_replied": self.total_replied,
            "best_hour": self.best_hour,
            "best_day": self.best_day,
            "hourly_open_rates": self.hourly_open_rates,
            "daily_open_rates": self.daily_open_rates,
            "hourly_reply_rates": self.hourly_reply_rates,
        }


class SendTimeOptimizer:
    """Optimizes email send times based on segment engagement.

    Features:
    - Segment-specific optimal windows
    - Learning from historical engagement
    - Day-of-week optimization
    - Timezone-aware recommendations
    """

    def __init__(self, timezone_offset: int = 3) -> None:
        """Initialize optimizer.

        Args:
            timezone_offset: Hours offset from UTC (default: 3 for Moscow)
        """
        self.tz_offset = timezone_offset

    def get_optimal_send_time(
        self,
        segment: str,
        earliest: datetime | None = None,
        latest: datetime | None = None,
    ) -> SendTimeRecommendation:
        """Get optimal send time for a segment.

        Args:
            segment: Lead segment (retail, horeca, it, etc.)
            earliest: Earliest acceptable send time (default: now)
            latest: Latest acceptable send time (default: now + 7 days)

        Returns:
            SendTimeRecommendation
        """
        now = datetime.now(UTC)
        earliest = earliest or now
        latest = latest or (now + timedelta(days=7))

        # Normalize segment
        segment_lower = segment.lower().strip()
        if segment_lower not in DEFAULT_SEND_WINDOWS:
            segment_lower = "default"

        windows = DEFAULT_SEND_WINDOWS[segment_lower]

        # Find next optimal slot
        recommended, alternatives, window = self._find_next_optimal_slot(
            earliest, latest, windows
        )

        # Determine day quality
        day_of_week = recommended.weekday()
        if day_of_week in HIGH_ENGAGEMENT_DAYS:
            day_quality = "high"
            confidence = 0.85
        elif day_of_week in LOW_ENGAGEMENT_DAYS:
            day_quality = "low"
            confidence = 0.60
        else:
            day_quality = "medium"
            confidence = 0.75

        # Adjust confidence based on window weight
        confidence *= window[2]

        reason = self._generate_reason(segment_lower, recommended, day_quality)

        return SendTimeRecommendation(
            recommended_time=recommended,
            segment=segment_lower,
            confidence=round(confidence, 2),
            reason=reason,
            alternative_times=alternatives[:3],
            window_start=window[0],
            window_end=window[1],
            day_quality=day_quality,
        )

    def _find_next_optimal_slot(
        self,
        earliest: datetime,
        latest: datetime,
        windows: list[tuple[int, int, float]],
    ) -> tuple[datetime, list[datetime], tuple[int, int, float]]:
        """Find next optimal send slot within range.

        Args:
            earliest: Earliest acceptable time
            latest: Latest acceptable time
            windows: List of (hour_start, hour_end, weight) tuples

        Returns:
            Tuple of (recommended_time, alternatives, selected_window)
        """
        candidates = []

        current = earliest
        while current <= latest:
            local_hour = (current.hour + self.tz_offset) % 24
            day_of_week = current.weekday()

            for window in windows:
                hour_start, hour_end, weight = window

                # Adjust for weekend (skip)
                if day_of_week >= 5:
                    continue

                # Check if current time is in this window
                if hour_start <= local_hour < hour_end:
                    # Score based on window weight and day quality
                    day_mult = 1.2 if day_of_week in HIGH_ENGAGEMENT_DAYS else 1.0
                    day_mult = 0.8 if day_of_week in LOW_ENGAGEMENT_DAYS else day_mult
                    score = weight * day_mult

                    candidates.append((current, score, window))

                # Also find next occurrence of this window
                if local_hour < hour_start:
                    # Window is later today
                    hours_until = hour_start - local_hour
                    next_slot = current + timedelta(hours=hours_until)
                    if next_slot <= latest:
                        day_mult = 1.2 if next_slot.weekday() in HIGH_ENGAGEMENT_DAYS else 1.0
                        score = weight * day_mult
                        candidates.append((next_slot, score, window))

            # Move to next day's start
            current = (current + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        if not candidates:
            # Fallback to earliest time
            default_window = windows[0] if windows else (9, 11, 1.0)
            return earliest, [], default_window

        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)

        recommended = candidates[0][0]
        selected_window = candidates[0][2]
        alternatives = [c[0] for c in candidates[1:4]]

        return recommended, alternatives, selected_window

    def _generate_reason(
        self,
        segment: str,
        time: datetime,
        day_quality: str,
    ) -> str:
        """Generate human-readable reason for recommendation."""
        local_hour = (time.hour + self.tz_offset) % 24
        day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][
            time.weekday()
        ]

        reasons = []

        if segment != "default":
            reasons.append(f"Optimal window for {segment} segment")

        if day_quality == "high":
            reasons.append(f"{day_name} has high B2B engagement")
        elif day_quality == "low":
            reasons.append(f"{day_name} has lower engagement")

        if 9 <= local_hour <= 11:
            reasons.append("Morning decision-making window")
        elif 14 <= local_hour <= 16:
            reasons.append("Post-lunch review period")

        return "; ".join(reasons) if reasons else "Default optimal window"

    # ========================================================================
    # Learning from Historical Data
    # ========================================================================

    async def record_send(
        self,
        segment: str,
        sent_at: datetime,
        opened: bool = False,
        replied: bool = False,
    ) -> None:
        """Record send for learning.

        Args:
            segment: Lead segment
            sent_at: When email was sent
            opened: Whether email was opened
            replied: Whether reply was received
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        segment = segment.lower().strip()
        local_hour = (sent_at.hour + self.tz_offset) % 24
        day_of_week = sent_at.weekday()

        pipe = redis.pipeline()

        # Track sent by hour
        pipe.incr(f"sendtime:{segment}:hour:{local_hour}:sent")
        if opened:
            pipe.incr(f"sendtime:{segment}:hour:{local_hour}:opened")
        if replied:
            pipe.incr(f"sendtime:{segment}:hour:{local_hour}:replied")

        # Track sent by day
        pipe.incr(f"sendtime:{segment}:day:{day_of_week}:sent")
        if opened:
            pipe.incr(f"sendtime:{segment}:day:{day_of_week}:opened")
        if replied:
            pipe.incr(f"sendtime:{segment}:day:{day_of_week}:replied")

        # Set TTL (90 days)
        for key in [
            f"sendtime:{segment}:hour:{local_hour}:sent",
            f"sendtime:{segment}:hour:{local_hour}:opened",
            f"sendtime:{segment}:hour:{local_hour}:replied",
            f"sendtime:{segment}:day:{day_of_week}:sent",
            f"sendtime:{segment}:day:{day_of_week}:opened",
            f"sendtime:{segment}:day:{day_of_week}:replied",
        ]:
            pipe.expire(key, 86400 * 90)

        await pipe.execute()

    async def get_segment_stats(self, segment: str) -> SegmentSendStats:
        """Get send time statistics for a segment.

        Args:
            segment: Segment to analyze

        Returns:
            SegmentSendStats
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        segment = segment.lower().strip()

        total_sent = 0
        total_opened = 0
        total_replied = 0
        hourly_open_rates = {}
        hourly_reply_rates = {}
        daily_open_rates = {}

        # Collect hourly stats
        best_hour = 9
        best_hour_rate = 0.0

        for hour in range(24):
            sent = int(await redis.get(f"sendtime:{segment}:hour:{hour}:sent") or 0)
            opened = int(await redis.get(f"sendtime:{segment}:hour:{hour}:opened") or 0)
            replied = int(await redis.get(f"sendtime:{segment}:hour:{hour}:replied") or 0)

            total_sent += sent
            total_opened += opened
            total_replied += replied

            open_rate = opened / sent if sent > 0 else 0
            reply_rate = replied / sent if sent > 0 else 0

            hourly_open_rates[hour] = round(open_rate, 3)
            hourly_reply_rates[hour] = round(reply_rate, 3)

            if open_rate > best_hour_rate and sent >= 10:
                best_hour_rate = open_rate
                best_hour = hour

        # Collect daily stats
        best_day = 2  # Wednesday default
        best_day_rate = 0.0

        for day in range(7):
            sent = int(await redis.get(f"sendtime:{segment}:day:{day}:sent") or 0)
            opened = int(await redis.get(f"sendtime:{segment}:day:{day}:opened") or 0)

            open_rate = opened / sent if sent > 0 else 0
            daily_open_rates[day] = round(open_rate, 3)

            if open_rate > best_day_rate and sent >= 10:
                best_day_rate = open_rate
                best_day = day

        return SegmentSendStats(
            segment=segment,
            total_sent=total_sent,
            total_opened=total_opened,
            total_replied=total_replied,
            best_hour=best_hour,
            best_day=best_day,
            hourly_open_rates=hourly_open_rates,
            daily_open_rates=daily_open_rates,
            hourly_reply_rates=hourly_reply_rates,
        )

    async def get_learned_optimal_time(
        self,
        segment: str,
        earliest: datetime | None = None,
        latest: datetime | None = None,
        min_data_points: int = 50,
    ) -> SendTimeRecommendation:
        """Get optimal send time using learned data.

        Falls back to defaults if insufficient data.

        Args:
            segment: Lead segment
            earliest: Earliest acceptable time
            latest: Latest acceptable time
            min_data_points: Minimum sends to use learned data

        Returns:
            SendTimeRecommendation
        """
        stats = await self.get_segment_stats(segment)

        if stats.total_sent < min_data_points:
            # Not enough data, use defaults
            return self.get_optimal_send_time(segment, earliest, latest)

        # Build windows from learned data
        # Find hours with above-average open rates
        avg_open_rate = stats.total_opened / stats.total_sent if stats.total_sent > 0 else 0

        learned_windows = []
        for hour, rate in stats.hourly_open_rates.items():
            if rate > avg_open_rate * 1.1:  # 10% above average
                weight = min(1.0, rate / avg_open_rate) if avg_open_rate > 0 else 0.5
                learned_windows.append((hour, hour + 1, weight))

        if not learned_windows:
            # No clear winners, use defaults
            return self.get_optimal_send_time(segment, earliest, latest)

        # Sort by weight
        learned_windows.sort(key=lambda x: x[2], reverse=True)

        now = datetime.now(UTC)
        earliest = earliest or now
        latest = latest or (now + timedelta(days=7))

        recommended, alternatives, window = self._find_next_optimal_slot(
            earliest, latest, learned_windows
        )

        day_of_week = recommended.weekday()
        day_quality = "high" if day_of_week in HIGH_ENGAGEMENT_DAYS else "medium"
        day_quality = "low" if day_of_week in LOW_ENGAGEMENT_DAYS else day_quality

        confidence = 0.90 * window[2]  # Higher confidence for learned data

        return SendTimeRecommendation(
            recommended_time=recommended,
            segment=segment,
            confidence=round(confidence, 2),
            reason=f"Based on {stats.total_sent} historical sends; best hour: {stats.best_hour}:00",
            alternative_times=alternatives[:3],
            window_start=window[0],
            window_end=window[1],
            day_quality=day_quality,
        )


# Singleton
send_time_optimizer = SendTimeOptimizer()
