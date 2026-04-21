"""Capacity Planning Service.

Manager capacity modeling and workload forecasting.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class CapacityStatus(str, Enum):
    """Manager capacity status."""

    AVAILABLE = "available"  # Has capacity
    BUSY = "busy"  # At capacity but can handle urgent
    OVERLOADED = "overloaded"  # Over capacity
    UNAVAILABLE = "unavailable"  # Out of office


@dataclass
class ManagerCapacity:
    """Capacity information for a manager."""

    manager_id: str
    name: str
    status: CapacityStatus
    max_handoffs: int  # Max concurrent handoffs
    current_handoffs: int
    max_deals: int  # Max concurrent deals
    current_deals: int
    capacity_percent: float  # 0-100
    available_slots: int
    skills: list[str] = field(default_factory=list)
    segments: list[str] = field(default_factory=list)  # Preferred segments
    avg_response_time_hours: float = 0.0
    avg_close_time_days: float = 0.0
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manager_id": self.manager_id,
            "name": self.name,
            "status": self.status.value,
            "max_handoffs": self.max_handoffs,
            "current_handoffs": self.current_handoffs,
            "max_deals": self.max_deals,
            "current_deals": self.current_deals,
            "capacity_percent": self.capacity_percent,
            "available_slots": self.available_slots,
            "skills": self.skills,
            "segments": self.segments,
            "avg_response_time_hours": self.avg_response_time_hours,
            "avg_close_time_days": self.avg_close_time_days,
            "is_active": self.is_active,
            "metadata": self.metadata,
        }


@dataclass
class WorkloadForecast:
    """Workload forecast for a period."""

    period_days: int
    expected_handoffs: int
    expected_deals: int
    current_capacity: int
    forecasted_capacity_needed: int
    capacity_gap: int  # Negative = understaffed
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "period_days": self.period_days,
            "expected_handoffs": self.expected_handoffs,
            "expected_deals": self.expected_deals,
            "current_capacity": self.current_capacity,
            "forecasted_capacity_needed": self.forecasted_capacity_needed,
            "capacity_gap": self.capacity_gap,
            "recommendations": self.recommendations,
        }


@dataclass
class TeamCapacity:
    """Team-wide capacity summary."""

    total_managers: int
    active_managers: int
    total_capacity: int
    used_capacity: int
    available_capacity: int
    utilization_percent: float
    by_status: dict[str, int]
    bottlenecks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_managers": self.total_managers,
            "active_managers": self.active_managers,
            "total_capacity": self.total_capacity,
            "used_capacity": self.used_capacity,
            "available_capacity": self.available_capacity,
            "utilization_percent": self.utilization_percent,
            "by_status": self.by_status,
            "bottlenecks": self.bottlenecks,
        }


# Default capacity settings
DEFAULT_MAX_HANDOFFS = 15
DEFAULT_MAX_DEALS = 25


class CapacityPlanningService:
    """Service for capacity planning and workload forecasting.

    Features:
    - Manager capacity tracking
    - Workload forecasting
    - Optimal assignment recommendations
    - Team utilization analytics
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Manager Capacity
    # ========================================================================

    async def get_manager_capacity(
        self,
        manager_id: str,
    ) -> ManagerCapacity | None:
        """Get capacity for a manager.

        Args:
            manager_id: Manager ID

        Returns:
            ManagerCapacity or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Get manager config
        config_data = await redis.get(f"manager:config:{manager_id}")
        if config_data:
            config = json.loads(config_data)
        else:
            config = {
                "name": manager_id,
                "max_handoffs": DEFAULT_MAX_HANDOFFS,
                "max_deals": DEFAULT_MAX_DEALS,
                "skills": [],
                "segments": [],
                "is_active": True,
            }

        # Count current workload
        current_handoffs = await redis.scard(f"handoffs:assigned:{manager_id}") or 0
        current_deals = await redis.scard(f"deals:owner:{manager_id}") or 0

        # Calculate capacity
        max_total = config["max_handoffs"] + config["max_deals"]
        current_total = current_handoffs + current_deals

        if max_total > 0:
            capacity_percent = (current_total / max_total) * 100
        else:
            capacity_percent = 0

        available_slots = max(0, config["max_handoffs"] - current_handoffs)

        # Determine status
        if not config.get("is_active", True):
            status = CapacityStatus.UNAVAILABLE
        elif capacity_percent >= 100:
            status = CapacityStatus.OVERLOADED
        elif capacity_percent >= 80:
            status = CapacityStatus.BUSY
        else:
            status = CapacityStatus.AVAILABLE

        # Get performance metrics
        avg_response = float(await redis.get(f"metrics:manager:{manager_id}:avg_response_hours") or 0)
        avg_close = float(await redis.get(f"metrics:manager:{manager_id}:avg_close_days") or 0)

        return ManagerCapacity(
            manager_id=manager_id,
            name=config.get("name", manager_id),
            status=status,
            max_handoffs=config["max_handoffs"],
            current_handoffs=current_handoffs,
            max_deals=config["max_deals"],
            current_deals=current_deals,
            capacity_percent=min(100, capacity_percent),
            available_slots=available_slots,
            skills=config.get("skills", []),
            segments=config.get("segments", []),
            avg_response_time_hours=avg_response,
            avg_close_time_days=avg_close,
            is_active=config.get("is_active", True),
        )

    async def set_manager_config(
        self,
        manager_id: str,
        name: str | None = None,
        max_handoffs: int | None = None,
        max_deals: int | None = None,
        skills: list[str] | None = None,
        segments: list[str] | None = None,
        is_active: bool | None = None,
    ) -> ManagerCapacity:
        """Configure a manager's capacity settings.

        Args:
            manager_id: Manager ID
            name: Display name
            max_handoffs: Max concurrent handoffs
            max_deals: Max concurrent deals
            skills: Manager skills
            segments: Preferred segments
            is_active: Whether manager is active

        Returns:
            Updated ManagerCapacity
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Get existing config
        config_data = await redis.get(f"manager:config:{manager_id}")
        if config_data:
            config = json.loads(config_data)
        else:
            config = {
                "name": manager_id,
                "max_handoffs": DEFAULT_MAX_HANDOFFS,
                "max_deals": DEFAULT_MAX_DEALS,
                "skills": [],
                "segments": [],
                "is_active": True,
            }

        # Update fields
        if name is not None:
            config["name"] = name
        if max_handoffs is not None:
            config["max_handoffs"] = max_handoffs
        if max_deals is not None:
            config["max_deals"] = max_deals
        if skills is not None:
            config["skills"] = skills
        if segments is not None:
            config["segments"] = segments
        if is_active is not None:
            config["is_active"] = is_active

        # Save
        await redis.set(
            f"manager:config:{manager_id}",
            json.dumps(config),
            ex=86400 * 365,
        )

        # Add to managers set
        await redis.sadd("managers:all", manager_id)

        logger.info(f"[Capacity] Config updated | manager={manager_id}")

        return await self.get_manager_capacity(manager_id)

    async def set_manager_unavailable(
        self,
        manager_id: str,
        until: datetime | None = None,
        reason: str | None = None,
    ) -> ManagerCapacity:
        """Mark manager as unavailable.

        Args:
            manager_id: Manager ID
            until: When they return
            reason: Why unavailable

        Returns:
            Updated ManagerCapacity
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Update config
        capacity = await self.set_manager_config(manager_id, is_active=False)

        # Store unavailability details
        unavail = {
            "manager_id": manager_id,
            "until": until.isoformat() if until else None,
            "reason": reason,
            "set_at": datetime.now(UTC).isoformat(),
        }
        await redis.set(
            f"manager:unavailable:{manager_id}",
            json.dumps(unavail),
            ex=86400 * 30,
        )

        logger.info(f"[Capacity] Manager unavailable | manager={manager_id} | reason={reason}")

        return capacity

    # ========================================================================
    # Team Capacity
    # ========================================================================

    async def get_team_capacity(self) -> TeamCapacity:
        """Get team-wide capacity summary.

        Returns:
            TeamCapacity
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Get all managers
        manager_ids = await redis.smembers("managers:all")

        total_managers = 0
        active_managers = 0
        total_capacity = 0
        used_capacity = 0
        by_status = {}
        bottlenecks = []

        for manager_id in manager_ids:
            capacity = await self.get_manager_capacity(manager_id)
            if not capacity:
                continue

            total_managers += 1

            if capacity.is_active:
                active_managers += 1
                total_capacity += capacity.max_handoffs
                used_capacity += capacity.current_handoffs

            # Count by status
            status = capacity.status.value
            by_status[status] = by_status.get(status, 0) + 1

            # Identify bottlenecks
            if capacity.status == CapacityStatus.OVERLOADED:
                bottlenecks.append(f"{capacity.name} is overloaded ({capacity.current_handoffs}/{capacity.max_handoffs} handoffs)")
            elif capacity.avg_response_time_hours > 4:
                bottlenecks.append(f"{capacity.name} has slow response time ({capacity.avg_response_time_hours:.1f}h avg)")

        available_capacity = total_capacity - used_capacity
        if total_capacity > 0:
            utilization_percent = (used_capacity / total_capacity) * 100
        else:
            utilization_percent = 0

        return TeamCapacity(
            total_managers=total_managers,
            active_managers=active_managers,
            total_capacity=total_capacity,
            used_capacity=used_capacity,
            available_capacity=available_capacity,
            utilization_percent=utilization_percent,
            by_status=by_status,
            bottlenecks=bottlenecks,
        )

    async def get_available_managers(
        self,
        segment: str | None = None,
        skill: str | None = None,
    ) -> list[ManagerCapacity]:
        """Get managers with available capacity.

        Args:
            segment: Filter by segment preference
            skill: Filter by required skill

        Returns:
            List of available managers
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        manager_ids = await redis.smembers("managers:all")

        available = []

        for manager_id in manager_ids:
            capacity = await self.get_manager_capacity(manager_id)
            if not capacity:
                continue

            if capacity.status in (CapacityStatus.UNAVAILABLE, CapacityStatus.OVERLOADED):
                continue

            if segment and segment not in capacity.segments and capacity.segments:
                continue

            if skill and skill not in capacity.skills:
                continue

            available.append(capacity)

        # Sort by available capacity (most available first)
        available.sort(key=lambda c: c.available_slots, reverse=True)

        return available

    async def get_best_assignee(
        self,
        segment: str | None = None,
        skill: str | None = None,
        exclude: list[str] | None = None,
    ) -> str | None:
        """Get the best manager to assign work to.

        Args:
            segment: Preferred segment
            skill: Required skill
            exclude: Manager IDs to exclude

        Returns:
            Best manager ID or None
        """
        available = await self.get_available_managers(segment, skill)

        if exclude:
            available = [m for m in available if m.manager_id not in exclude]

        if not available:
            return None

        # Score managers
        best = None
        best_score = -1

        for manager in available:
            score = 0

            # Prefer managers with more capacity
            score += manager.available_slots * 10

            # Prefer managers with segment match
            if segment and segment in manager.segments:
                score += 20

            # Prefer managers with skill match
            if skill and skill in manager.skills:
                score += 15

            # Penalize slow responders
            if manager.avg_response_time_hours > 4:
                score -= 10
            elif manager.avg_response_time_hours < 2:
                score += 5

            if score > best_score:
                best_score = score
                best = manager.manager_id

        return best

    # ========================================================================
    # Workload Forecasting
    # ========================================================================

    async def forecast_workload(
        self,
        days: int = 7,
    ) -> WorkloadForecast:
        """Forecast workload for coming period.

        Args:
            days: Days to forecast

        Returns:
            WorkloadForecast
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Get historical data for forecasting
        total_handoffs = 0
        total_deals = 0

        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            handoffs = int(await redis.get(f"stats:daily:{day}:handoffs") or 0)
            deals = int(await redis.get(f"stats:daily:{day}:new_deals") or 0)
            total_handoffs += handoffs
            total_deals += deals

        # Calculate daily averages
        avg_handoffs_per_day = total_handoffs / max(days, 1)
        avg_deals_per_day = total_deals / max(days, 1)

        # Forecast for period
        expected_handoffs = int(avg_handoffs_per_day * days * 1.1)  # 10% buffer
        expected_deals = int(avg_deals_per_day * days * 1.1)

        # Get current capacity
        team = await self.get_team_capacity()
        current_capacity = team.available_capacity

        # Calculate capacity needed
        # Assume each handoff takes ~2 hours and manager works 40h/week
        handoff_capacity_needed = expected_handoffs
        forecasted_capacity_needed = handoff_capacity_needed

        capacity_gap = current_capacity - forecasted_capacity_needed

        # Generate recommendations
        recommendations = []

        if capacity_gap < 0:
            recommendations.append(
                f"Warning: Expected {abs(capacity_gap)} more handoffs than current capacity"
            )
            recommendations.append(
                "Consider: redistributing workload, temporary staff, or overtime"
            )
        elif capacity_gap < 5:
            recommendations.append(
                "Capacity is tight - monitor closely"
            )
        else:
            recommendations.append(
                f"Capacity looks healthy with {capacity_gap} slots buffer"
            )

        if team.utilization_percent > 80:
            recommendations.append(
                f"Team utilization is high ({team.utilization_percent:.0f}%) - risk of burnout"
            )

        if team.bottlenecks:
            recommendations.append(
                f"Address bottlenecks: {'; '.join(team.bottlenecks[:2])}"
            )

        return WorkloadForecast(
            period_days=days,
            expected_handoffs=expected_handoffs,
            expected_deals=expected_deals,
            current_capacity=current_capacity,
            forecasted_capacity_needed=forecasted_capacity_needed,
            capacity_gap=capacity_gap,
            recommendations=recommendations,
        )

    async def get_capacity_timeline(
        self,
        days: int = 14,
    ) -> list[dict[str, Any]]:
        """Get capacity utilization timeline.

        Args:
            days: Days of history

        Returns:
            List of daily capacity snapshots
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        timeline = []

        for i in range(days - 1, -1, -1):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")

            # Get historical data
            total_capacity = int(await redis.get(f"stats:daily:{day}:total_capacity") or 0)
            used_capacity = int(await redis.get(f"stats:daily:{day}:used_capacity") or 0)
            handoffs = int(await redis.get(f"stats:daily:{day}:handoffs") or 0)
            deals_created = int(await redis.get(f"stats:daily:{day}:new_deals") or 0)

            if total_capacity > 0:
                utilization = (used_capacity / total_capacity) * 100
            else:
                utilization = 0

            timeline.append({
                "date": day,
                "total_capacity": total_capacity,
                "used_capacity": used_capacity,
                "utilization_percent": utilization,
                "handoffs": handoffs,
                "deals_created": deals_created,
            })

        return timeline

    async def record_daily_snapshot(self) -> None:
        """Record current capacity as daily snapshot.

        Called by scheduled job.
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        day = now.strftime("%Y-%m-%d")

        team = await self.get_team_capacity()

        await redis.set(f"stats:daily:{day}:total_capacity", team.total_capacity, ex=86400 * 90)
        await redis.set(f"stats:daily:{day}:used_capacity", team.used_capacity, ex=86400 * 90)

        logger.info(
            f"[Capacity] Daily snapshot | date={day} | "
            f"total={team.total_capacity} | used={team.used_capacity}"
        )


# Singleton
capacity_service = CapacityPlanningService()
