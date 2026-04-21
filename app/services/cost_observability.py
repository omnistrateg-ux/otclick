"""Cost Observability Service.

Track and monitor operational costs.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class CostCategory(str, Enum):
    """Cost categories."""

    LLM_API = "llm_api"
    EMAIL_SENDING = "email_sending"
    STORAGE = "storage"
    COMPUTE = "compute"
    EXTERNAL_API = "external_api"
    DATABASE = "database"
    CDN = "cdn"
    OTHER = "other"


class CostPeriod(str, Enum):
    """Cost aggregation periods."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class CostEntry:
    """Individual cost entry."""

    category: CostCategory
    amount_usd: float
    quantity: int
    unit: str
    description: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "amount_usd": self.amount_usd,
            "quantity": self.quantity,
            "unit": self.unit,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class CostSummary:
    """Cost summary for a period."""

    period: CostPeriod
    start_date: datetime
    end_date: datetime
    total_usd: float
    by_category: dict[str, float]
    entry_count: int
    top_costs: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "total_usd": round(self.total_usd, 4),
            "by_category": {k: round(v, 4) for k, v in self.by_category.items()},
            "entry_count": self.entry_count,
            "top_costs": self.top_costs,
        }


@dataclass
class CostBudget:
    """Cost budget definition."""

    category: CostCategory | None  # None = total
    period: CostPeriod
    budget_usd: float
    alert_threshold_percent: int = 80
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value if self.category else "total",
            "period": self.period.value,
            "budget_usd": self.budget_usd,
            "alert_threshold_percent": self.alert_threshold_percent,
            "enabled": self.enabled,
        }


@dataclass
class BudgetStatus:
    """Budget status."""

    budget: CostBudget
    spent_usd: float
    remaining_usd: float
    percent_used: float
    on_track: bool
    projected_overage: float | None
    alert_triggered: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "budget": self.budget.to_dict(),
            "spent_usd": round(self.spent_usd, 4),
            "remaining_usd": round(self.remaining_usd, 4),
            "percent_used": round(self.percent_used, 1),
            "on_track": self.on_track,
            "projected_overage": round(self.projected_overage, 4) if self.projected_overage else None,
            "alert_triggered": self.alert_triggered,
        }


# Default pricing (approximate)
DEFAULT_PRICING = {
    CostCategory.LLM_API: {
        "claude_input_1k": 0.003,
        "claude_output_1k": 0.015,
        "gpt4_input_1k": 0.01,
        "gpt4_output_1k": 0.03,
    },
    CostCategory.EMAIL_SENDING: {
        "email": 0.0001,  # per email
        "bounce": 0.0001,
    },
    CostCategory.STORAGE: {
        "gb_month": 0.023,  # S3 standard
        "requests_1k": 0.0004,
    },
    CostCategory.EXTERNAL_API: {
        "enrichment_lookup": 0.01,
        "validation": 0.001,
    },
}

# Default budgets
DEFAULT_BUDGETS = [
    CostBudget(
        category=None,
        period=CostPeriod.MONTHLY,
        budget_usd=1000.0,
        alert_threshold_percent=80,
    ),
    CostBudget(
        category=CostCategory.LLM_API,
        period=CostPeriod.DAILY,
        budget_usd=50.0,
        alert_threshold_percent=90,
    ),
    CostBudget(
        category=CostCategory.EMAIL_SENDING,
        period=CostPeriod.DAILY,
        budget_usd=10.0,
        alert_threshold_percent=80,
    ),
]


class CostObservabilityService:
    """Service for cost tracking and observability.

    Features:
    - Cost entry recording
    - Budget tracking
    - Alerts on thresholds
    - Cost projections
    - Category breakdown
    """

    COSTS_KEY = "costs:entries"
    BUDGETS_KEY = "costs:budgets"
    ALERTS_KEY = "costs:alerts"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    async def record_cost(
        self,
        category: CostCategory,
        amount_usd: float,
        quantity: int = 1,
        unit: str = "unit",
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CostEntry:
        """Record a cost entry.

        Args:
            category: Cost category
            amount_usd: Cost in USD
            quantity: Number of units
            unit: Unit name
            description: Description
            metadata: Additional metadata

        Returns:
            Created cost entry
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        entry = CostEntry(
            category=category,
            amount_usd=amount_usd,
            quantity=quantity,
            unit=unit,
            description=description,
            timestamp=now,
            metadata=metadata or {},
        )

        # Store entry
        await redis.zadd(
            self.COSTS_KEY,
            {json.dumps(entry.to_dict()): now.timestamp()},
        )

        # Update running totals
        day_key = f"costs:daily:{now.strftime('%Y-%m-%d')}"
        month_key = f"costs:monthly:{now.strftime('%Y-%m')}"

        await redis.hincrbyfloat(day_key, category.value, amount_usd)
        await redis.hincrbyfloat(day_key, "total", amount_usd)
        await redis.expire(day_key, 86400 * 35)  # 35 days

        await redis.hincrbyfloat(month_key, category.value, amount_usd)
        await redis.hincrbyfloat(month_key, "total", amount_usd)
        await redis.expire(month_key, 86400 * 400)  # ~13 months

        # Check budgets
        await self._check_budgets(category, now)

        return entry

    async def record_llm_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        request_id: str | None = None,
    ) -> CostEntry:
        """Record LLM API usage.

        Args:
            model: Model name
            input_tokens: Input tokens
            output_tokens: Output tokens
            request_id: Optional request ID

        Returns:
            Cost entry
        """
        # Calculate cost based on model
        pricing = DEFAULT_PRICING[CostCategory.LLM_API]

        if "claude" in model.lower():
            input_cost = (input_tokens / 1000) * pricing["claude_input_1k"]
            output_cost = (output_tokens / 1000) * pricing["claude_output_1k"]
        else:
            input_cost = (input_tokens / 1000) * pricing["gpt4_input_1k"]
            output_cost = (output_tokens / 1000) * pricing["gpt4_output_1k"]

        total_cost = input_cost + output_cost

        return await self.record_cost(
            category=CostCategory.LLM_API,
            amount_usd=total_cost,
            quantity=input_tokens + output_tokens,
            unit="tokens",
            description=f"{model} API call",
            metadata={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "request_id": request_id,
            },
        )

    async def record_email_send(
        self,
        count: int = 1,
        bounces: int = 0,
    ) -> CostEntry:
        """Record email sending cost.

        Args:
            count: Emails sent
            bounces: Bounce count

        Returns:
            Cost entry
        """
        pricing = DEFAULT_PRICING[CostCategory.EMAIL_SENDING]
        cost = (count * pricing["email"]) + (bounces * pricing["bounce"])

        return await self.record_cost(
            category=CostCategory.EMAIL_SENDING,
            amount_usd=cost,
            quantity=count,
            unit="emails",
            description=f"Sent {count} emails ({bounces} bounces)",
            metadata={"sent": count, "bounces": bounces},
        )

    async def get_summary(
        self,
        period: CostPeriod,
        date: datetime | None = None,
    ) -> CostSummary:
        """Get cost summary for a period.

        Args:
            period: Period type
            date: Date within period (defaults to now)

        Returns:
            Cost summary
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = date or datetime.now(UTC)

        # Determine period bounds
        if period == CostPeriod.HOURLY:
            start = now.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
            key = f"costs:hourly:{start.strftime('%Y-%m-%d-%H')}"
        elif period == CostPeriod.DAILY:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            key = f"costs:daily:{start.strftime('%Y-%m-%d')}"
        elif period == CostPeriod.WEEKLY:
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(weeks=1)
            key = f"costs:weekly:{start.strftime('%Y-%W')}"
        else:  # Monthly
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                end = start.replace(year=now.year + 1, month=1)
            else:
                end = start.replace(month=now.month + 1)
            key = f"costs:monthly:{start.strftime('%Y-%m')}"

        # Get totals
        totals = await redis.hgetall(key)

        by_category = {}
        total = 0.0

        for cat, amount in totals.items():
            if cat == "total":
                total = float(amount)
            else:
                by_category[cat] = float(amount)

        # Get top costs from entries
        min_ts = start.timestamp()
        max_ts = end.timestamp()

        raw = await redis.zrangebyscore(
            self.COSTS_KEY,
            min_ts,
            max_ts,
            start=0,
            num=100,
        )

        entry_count = len(raw)
        top_costs = []

        import json
        entries = []
        for item in raw:
            try:
                entries.append(json.loads(item))
            except Exception:
                continue

        # Sort by amount and get top 10
        entries.sort(key=lambda e: e["amount_usd"], reverse=True)
        top_costs = entries[:10]

        return CostSummary(
            period=period,
            start_date=start,
            end_date=end,
            total_usd=total,
            by_category=by_category,
            entry_count=entry_count,
            top_costs=top_costs,
        )

    async def get_budget_status(
        self,
        category: CostCategory | None = None,
    ) -> list[BudgetStatus]:
        """Get budget status.

        Args:
            category: Filter by category

        Returns:
            List of budget statuses
        """
        budgets = await self.get_budgets()
        statuses = []

        for budget in budgets:
            if category is not None and budget.category != category:
                continue

            if not budget.enabled:
                continue

            # Get spent amount
            summary = await self.get_summary(budget.period)

            if budget.category:
                spent = summary.by_category.get(budget.category.value, 0.0)
            else:
                spent = summary.total_usd

            remaining = max(0, budget.budget_usd - spent)
            percent_used = (spent / budget.budget_usd * 100) if budget.budget_usd > 0 else 0

            # Calculate if on track
            now = datetime.now(UTC)
            if budget.period == CostPeriod.DAILY:
                elapsed = now.hour / 24
            elif budget.period == CostPeriod.MONTHLY:
                elapsed = now.day / 30
            else:
                elapsed = 0.5

            expected_spend = budget.budget_usd * elapsed
            on_track = spent <= expected_spend * 1.1  # 10% buffer

            # Project overage
            projected_overage = None
            if elapsed > 0:
                projected_total = spent / elapsed
                if projected_total > budget.budget_usd:
                    projected_overage = projected_total - budget.budget_usd

            alert_triggered = percent_used >= budget.alert_threshold_percent

            statuses.append(BudgetStatus(
                budget=budget,
                spent_usd=spent,
                remaining_usd=remaining,
                percent_used=percent_used,
                on_track=on_track,
                projected_overage=projected_overage,
                alert_triggered=alert_triggered,
            ))

        return statuses

    async def get_budgets(self) -> list[CostBudget]:
        """Get all budgets.

        Returns:
            List of budgets
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        raw = await redis.lrange(self.BUDGETS_KEY, 0, -1)

        if not raw:
            return DEFAULT_BUDGETS

        budgets = []
        for item in raw:
            try:
                data = json.loads(item)
                cat = CostCategory(data["category"]) if data["category"] != "total" else None
                budgets.append(CostBudget(
                    category=cat,
                    period=CostPeriod(data["period"]),
                    budget_usd=data["budget_usd"],
                    alert_threshold_percent=data.get("alert_threshold_percent", 80),
                    enabled=data.get("enabled", True),
                ))
            except Exception:
                continue

        return budgets or DEFAULT_BUDGETS

    async def set_budget(
        self,
        budget: CostBudget,
    ) -> CostBudget:
        """Set or update a budget.

        Args:
            budget: Budget to set

        Returns:
            Updated budget
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Get existing budgets
        budgets = await self.get_budgets()

        # Replace or add
        updated = False
        for i, b in enumerate(budgets):
            if b.category == budget.category and b.period == budget.period:
                budgets[i] = budget
                updated = True
                break

        if not updated:
            budgets.append(budget)

        # Store
        await redis.delete(self.BUDGETS_KEY)
        for b in budgets:
            await redis.rpush(self.BUDGETS_KEY, json.dumps(b.to_dict()))

        logger.info(
            f"[Costs] Budget set: {budget.category.value if budget.category else 'total'} "
            f"${budget.budget_usd}/{budget.period.value}"
        )

        return budget

    async def _check_budgets(
        self,
        category: CostCategory,
        timestamp: datetime,
    ) -> None:
        """Check budgets and create alerts if needed."""
        from app.storage.redis import get_redis
        import json

        statuses = await self.get_budget_status(category)

        redis = await get_redis()

        for status in statuses:
            if status.alert_triggered:
                alert_key = (
                    f"{status.budget.category.value if status.budget.category else 'total'}"
                    f":{status.budget.period.value}:{timestamp.strftime('%Y-%m-%d')}"
                )

                # Check if alert already sent today
                if await redis.sismember(self.ALERTS_KEY, alert_key):
                    continue

                await redis.sadd(self.ALERTS_KEY, alert_key)
                await redis.expire(self.ALERTS_KEY, 86400 * 2)

                logger.warning(
                    f"[Costs] Budget alert: {status.budget.category.value if status.budget.category else 'total'} "
                    f"at {status.percent_used:.1f}% (${status.spent_usd:.2f}/${status.budget.budget_usd:.2f})"
                )

    async def get_cost_trend(
        self,
        category: CostCategory | None = None,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get cost trend over time.

        Args:
            category: Filter by category
            days: Number of days

        Returns:
            Daily cost data
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        trend = []
        now = datetime.now(UTC)

        for i in range(days):
            date = now - timedelta(days=i)
            key = f"costs:daily:{date.strftime('%Y-%m-%d')}"
            totals = await redis.hgetall(key)

            if category:
                amount = float(totals.get(category.value, 0))
            else:
                amount = float(totals.get("total", 0))

            trend.append({
                "date": date.strftime("%Y-%m-%d"),
                "amount_usd": round(amount, 4),
            })

        trend.reverse()
        return trend


# Singleton
cost_observability = CostObservabilityService()
