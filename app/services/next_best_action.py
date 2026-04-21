"""Next Best Action Engine.

Context-aware action recommendations.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class ActionPriority(str, Enum):
    """Action priority levels."""

    CRITICAL = "critical"  # Do immediately
    HIGH = "high"  # Do today
    MEDIUM = "medium"  # Do this week
    LOW = "low"  # Do when time permits


class ActionCategory(str, Enum):
    """Categories of actions."""

    OUTREACH = "outreach"  # Sending messages
    FOLLOWUP = "followup"  # Following up
    RESPONSE = "response"  # Responding to replies
    HANDOFF = "handoff"  # Manager handoff actions
    MEETING = "meeting"  # Meeting-related
    DEAL = "deal"  # Deal progression
    ADMIN = "admin"  # Administrative tasks


@dataclass
class RecommendedAction:
    """A recommended action."""

    id: str
    action_type: str
    category: ActionCategory
    priority: ActionPriority
    title: str
    description: str
    resource_type: str
    resource_id: str
    score: float  # 0-100, higher = more urgent
    reasoning: str
    due_by: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action_type": self.action_type,
            "category": self.category.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "score": self.score,
            "reasoning": self.reasoning,
            "due_by": self.due_by.isoformat() if self.due_by else None,
            "metadata": self.metadata,
        }


@dataclass
class ActionContext:
    """Context for generating recommendations."""

    user_id: str
    role: str
    current_workload: int = 0
    time_of_day: str = "business_hours"  # morning, afternoon, evening
    day_of_week: int = 0  # 0 = Monday
    recent_actions: list[str] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)


class NextBestActionEngine:
    """Engine for recommending next best actions.

    Features:
    - Context-aware recommendations
    - Priority scoring
    - Time-sensitive actions
    - Workload balancing
    """

    def __init__(self) -> None:
        """Initialize engine."""
        pass

    # ========================================================================
    # Recommendation Generation
    # ========================================================================

    async def get_recommendations(
        self,
        user_id: str,
        role: str = "sales_rep",
        limit: int = 10,
        categories: list[ActionCategory] | None = None,
    ) -> list[RecommendedAction]:
        """Get recommended actions for a user.

        Args:
            user_id: User to get recommendations for
            role: User's role
            limit: Max recommendations
            categories: Filter by categories

        Returns:
            List of recommended actions
        """
        now = datetime.now(UTC)
        recommendations = []

        # Build context
        context = ActionContext(
            user_id=user_id,
            role=role,
            time_of_day=self._get_time_of_day(now),
            day_of_week=now.weekday(),
        )

        # Gather recommendations from various sources
        if role in ("manager", "sales_rep", "admin"):
            recommendations.extend(await self._get_handoff_actions(context))

        if role in ("sales_rep", "marketing", "admin"):
            recommendations.extend(await self._get_outreach_actions(context))

        if role in ("manager", "sales_rep", "admin"):
            recommendations.extend(await self._get_deal_actions(context))

        recommendations.extend(await self._get_response_actions(context))
        recommendations.extend(await self._get_followup_actions(context))

        # Filter by category
        if categories:
            recommendations = [
                r for r in recommendations
                if r.category in categories
            ]

        # Sort by score (highest first)
        recommendations.sort(key=lambda r: r.score, reverse=True)

        # Limit results
        return recommendations[:limit]

    async def _get_handoff_actions(
        self,
        context: ActionContext,
    ) -> list[RecommendedAction]:
        """Get handoff-related actions.

        Args:
            context: Action context

        Returns:
            Handoff recommendations
        """
        from app.storage.redis import get_redis
        import json
        from uuid import uuid4

        redis = await get_redis()
        recommendations = []
        now = datetime.now(UTC)

        # Check for pending handoffs assigned to user
        pending_key = f"handoffs:pending:{context.user_id}"
        handoff_ids = await redis.lrange(pending_key, 0, 20)

        for handoff_id in handoff_ids:
            handoff_data = await redis.get(f"handoff:{handoff_id}")
            if not handoff_data:
                continue

            handoff = json.loads(handoff_data)

            # Check SLA
            created_at = datetime.fromisoformat(handoff["created_at"])
            sla_deadline = handoff.get("sla_deadline")

            if sla_deadline:
                deadline = datetime.fromisoformat(sla_deadline)
                hours_until_sla = (deadline - now).total_seconds() / 3600
            else:
                hours_until_sla = 24  # Default

            # Calculate priority and score
            if hours_until_sla < 1:
                priority = ActionPriority.CRITICAL
                score = 95
                reasoning = "SLA deadline in less than 1 hour"
            elif hours_until_sla < 4:
                priority = ActionPriority.HIGH
                score = 85
                reasoning = f"SLA deadline in {hours_until_sla:.1f} hours"
            else:
                priority = ActionPriority.MEDIUM
                score = 60
                reasoning = "Pending handoff awaiting action"

            # Boost score for high-value leads
            lead_score = handoff.get("lead_score", 0)
            if lead_score >= 80:
                score += 10
                reasoning += "; high-value lead"

            recommendations.append(
                RecommendedAction(
                    id=str(uuid4()),
                    action_type="review_handoff",
                    category=ActionCategory.HANDOFF,
                    priority=priority,
                    title=f"Review Handoff: {handoff.get('account_id', 'Unknown')}",
                    description="Review and take action on pending handoff",
                    resource_type="handoff",
                    resource_id=handoff_id,
                    score=min(100, score),
                    reasoning=reasoning,
                    due_by=datetime.fromisoformat(sla_deadline) if sla_deadline else None,
                    metadata={
                        "lead_score": lead_score,
                        "hours_until_sla": hours_until_sla,
                    },
                )
            )

        return recommendations

    async def _get_outreach_actions(
        self,
        context: ActionContext,
    ) -> list[RecommendedAction]:
        """Get outreach-related actions.

        Args:
            context: Action context

        Returns:
            Outreach recommendations
        """
        from app.storage.redis import get_redis
        import json
        from uuid import uuid4

        redis = await get_redis()
        recommendations = []
        now = datetime.now(UTC)

        # Get accounts due for next touch
        due_key = "outreach:due"
        due_accounts = await redis.zrangebyscore(
            due_key,
            "-inf",
            now.timestamp(),
            start=0,
            num=20,
        )

        for lead_id in due_accounts:
            state_data = await redis.get(f"outreach:state:{lead_id}")
            if not state_data:
                continue

            state = json.loads(state_data)
            touch_count = state.get("touch_count", 0)

            # Calculate priority
            if touch_count == 0:
                priority = ActionPriority.HIGH
                score = 75
                reasoning = "New lead ready for first outreach"
            elif touch_count < 3:
                priority = ActionPriority.MEDIUM
                score = 65
                reasoning = f"Follow-up #{touch_count + 1} is due"
            else:
                priority = ActionPriority.LOW
                score = 45
                reasoning = f"Touch #{touch_count + 1} in sequence"

            # Boost for high-scoring leads
            lead_score = state.get("lead_score", 0)
            if lead_score >= 80:
                score += 15
                priority = ActionPriority.HIGH
                reasoning += "; high-value lead"
            elif lead_score >= 60:
                score += 5

            recommendations.append(
                RecommendedAction(
                    id=str(uuid4()),
                    action_type="send_outreach",
                    category=ActionCategory.OUTREACH,
                    priority=priority,
                    title=f"Send Outreach: {state.get('company_name', 'Unknown')}",
                    description=f"Send touch #{touch_count + 1} in outreach sequence",
                    resource_type="lead",
                    resource_id=lead_id,
                    score=min(100, score),
                    reasoning=reasoning,
                    metadata={
                        "touch_number": touch_count + 1,
                        "lead_score": lead_score,
                    },
                )
            )

        return recommendations

    async def _get_deal_actions(
        self,
        context: ActionContext,
    ) -> list[RecommendedAction]:
        """Get deal-related actions.

        Args:
            context: Action context

        Returns:
            Deal recommendations
        """
        from app.storage.redis import get_redis
        import json
        from uuid import uuid4

        redis = await get_redis()
        recommendations = []
        now = datetime.now(UTC)

        # Get deals owned by user
        deal_ids = await redis.smembers(f"deals:owner:{context.user_id}")

        for deal_id in list(deal_ids)[:20]:
            deal_data = await redis.get(f"deal:{deal_id}")
            if not deal_data:
                continue

            deal = json.loads(deal_data)
            stage = deal.get("stage", "")
            last_activity = deal.get("last_activity_at")
            deal_value = deal.get("value", 0)

            if last_activity:
                last_activity_dt = datetime.fromisoformat(last_activity)
                days_since_activity = (now - last_activity_dt).days
            else:
                days_since_activity = 7

            # Stale deals need attention
            if days_since_activity >= 7:
                priority = ActionPriority.HIGH
                score = 80
                reasoning = f"No activity in {days_since_activity} days"
            elif days_since_activity >= 3:
                priority = ActionPriority.MEDIUM
                score = 60
                reasoning = f"Deal may be going stale ({days_since_activity} days)"
            else:
                continue  # Skip recent deals

            # Boost for high-value deals
            if deal_value >= 100000:
                score += 15
                reasoning += "; high-value deal"
            elif deal_value >= 50000:
                score += 5

            # Action depends on stage
            if stage == "proposal_sent":
                action_type = "follow_up_proposal"
                title = f"Follow Up on Proposal: {deal.get('account_name', 'Unknown')}"
            elif stage == "meeting_scheduled":
                action_type = "confirm_meeting"
                title = f"Confirm Meeting: {deal.get('account_name', 'Unknown')}"
            else:
                action_type = "progress_deal"
                title = f"Progress Deal: {deal.get('account_name', 'Unknown')}"

            recommendations.append(
                RecommendedAction(
                    id=str(uuid4()),
                    action_type=action_type,
                    category=ActionCategory.DEAL,
                    priority=priority,
                    title=title,
                    description=f"Take action to move {stage} deal forward",
                    resource_type="deal",
                    resource_id=deal_id,
                    score=min(100, score),
                    reasoning=reasoning,
                    metadata={
                        "stage": stage,
                        "value": deal_value,
                        "days_since_activity": days_since_activity,
                    },
                )
            )

        return recommendations

    async def _get_response_actions(
        self,
        context: ActionContext,
    ) -> list[RecommendedAction]:
        """Get response-related actions (replies needing attention).

        Args:
            context: Action context

        Returns:
            Response recommendations
        """
        from app.storage.redis import get_redis
        import json
        from uuid import uuid4

        redis = await get_redis()
        recommendations = []
        now = datetime.now(UTC)

        # Get unprocessed replies
        reply_ids = await redis.lrange("replies:unprocessed", 0, 20)

        for reply_id in reply_ids:
            reply_data = await redis.get(f"reply:{reply_id}")
            if not reply_data:
                continue

            reply = json.loads(reply_data)
            received_at = datetime.fromisoformat(reply.get("received_at", now.isoformat()))
            hours_waiting = (now - received_at).total_seconds() / 3600

            # Replies should be handled quickly
            if hours_waiting < 1:
                priority = ActionPriority.HIGH
                score = 90
                reasoning = "Fresh reply - respond quickly for best engagement"
            elif hours_waiting < 4:
                priority = ActionPriority.HIGH
                score = 85
                reasoning = f"Reply waiting {hours_waiting:.1f} hours"
            elif hours_waiting < 24:
                priority = ActionPriority.MEDIUM
                score = 70
                reasoning = f"Reply waiting {hours_waiting:.1f} hours - respond today"
            else:
                priority = ActionPriority.LOW
                score = 50
                reasoning = f"Reply waiting {hours_waiting:.0f} hours - may be too late"

            # Check sentiment
            sentiment = reply.get("sentiment", "neutral")
            if sentiment == "positive":
                score += 10
                reasoning += "; positive sentiment"
            elif sentiment == "negative":
                score += 5
                reasoning += "; needs careful response"

            recommendations.append(
                RecommendedAction(
                    id=str(uuid4()),
                    action_type="respond_to_reply",
                    category=ActionCategory.RESPONSE,
                    priority=priority,
                    title=f"Respond to Reply: {reply.get('from_name', 'Unknown')}",
                    description="Review and respond to incoming reply",
                    resource_type="reply",
                    resource_id=reply_id,
                    score=min(100, score),
                    reasoning=reasoning,
                    metadata={
                        "sentiment": sentiment,
                        "hours_waiting": hours_waiting,
                        "lead_id": reply.get("lead_id"),
                    },
                )
            )

        return recommendations

    async def _get_followup_actions(
        self,
        context: ActionContext,
    ) -> list[RecommendedAction]:
        """Get scheduled follow-up actions.

        Args:
            context: Action context

        Returns:
            Follow-up recommendations
        """
        from app.storage.redis import get_redis
        import json
        from uuid import uuid4

        redis = await get_redis()
        recommendations = []
        now = datetime.now(UTC)

        # Get follow-ups due today
        followup_key = f"followups:{context.user_id}"
        followups = await redis.zrangebyscore(
            followup_key,
            "-inf",
            (now + timedelta(hours=24)).timestamp(),
            start=0,
            num=20,
        )

        for followup_id in followups:
            followup_data = await redis.get(f"followup:{followup_id}")
            if not followup_data:
                continue

            followup = json.loads(followup_data)
            due_at = datetime.fromisoformat(followup.get("due_at", now.isoformat()))
            hours_until = (due_at - now).total_seconds() / 3600

            if hours_until < 0:
                # Overdue
                priority = ActionPriority.HIGH
                score = 80
                reasoning = f"Follow-up overdue by {abs(hours_until):.1f} hours"
            elif hours_until < 2:
                priority = ActionPriority.HIGH
                score = 75
                reasoning = "Follow-up due soon"
            elif hours_until < 8:
                priority = ActionPriority.MEDIUM
                score = 60
                reasoning = "Follow-up scheduled for today"
            else:
                priority = ActionPriority.LOW
                score = 40
                reasoning = "Upcoming follow-up"

            recommendations.append(
                RecommendedAction(
                    id=str(uuid4()),
                    action_type="execute_followup",
                    category=ActionCategory.FOLLOWUP,
                    priority=priority,
                    title=f"Follow Up: {followup.get('subject', 'Scheduled task')}",
                    description=followup.get("description", "Execute scheduled follow-up"),
                    resource_type=followup.get("resource_type", "lead"),
                    resource_id=followup.get("resource_id", ""),
                    score=min(100, score),
                    reasoning=reasoning,
                    due_by=due_at,
                    metadata={
                        "followup_type": followup.get("type"),
                    },
                )
            )

        return recommendations

    # ========================================================================
    # Helpers
    # ========================================================================

    def _get_time_of_day(self, dt: datetime) -> str:
        """Get time of day category."""
        hour = dt.hour
        if 6 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"

    async def get_action_stats(
        self,
        user_id: str,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get action statistics for a user.

        Args:
            user_id: User ID
            days: Days to analyze

        Returns:
            Action statistics
        """
        recommendations = await self.get_recommendations(user_id, limit=100)

        by_category = {}
        by_priority = {}

        for r in recommendations:
            cat = r.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

            pri = r.priority.value
            by_priority[pri] = by_priority.get(pri, 0) + 1

        return {
            "total_pending": len(recommendations),
            "by_category": by_category,
            "by_priority": by_priority,
            "critical_count": by_priority.get("critical", 0),
            "high_count": by_priority.get("high", 0),
        }


# Singleton
nba_engine = NextBestActionEngine()
