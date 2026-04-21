"""Centralized Policy Engine.

Defines and enforces policies across the system.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid
import re

UTC = timezone.utc

logger = logging.getLogger(__name__)


class PolicyType(str, Enum):
    """Types of policies."""

    RATE_LIMIT = "rate_limit"
    ACCESS_CONTROL = "access_control"
    DATA_RETENTION = "data_retention"
    OUTBOUND_LIMIT = "outbound_limit"
    RESOURCE_QUOTA = "resource_quota"
    COMPLIANCE = "compliance"
    SECURITY = "security"
    COST_LIMIT = "cost_limit"


class PolicyScope(str, Enum):
    """Scope of policy application."""

    GLOBAL = "global"
    TENANT = "tenant"
    USER = "user"
    SERVICE = "service"
    ENDPOINT = "endpoint"


class PolicyAction(str, Enum):
    """Action when policy violated."""

    DENY = "deny"
    WARN = "warn"
    LOG = "log"
    THROTTLE = "throttle"
    ALERT = "alert"


class EvaluationResult(str, Enum):
    """Policy evaluation result."""

    ALLOW = "allow"
    DENY = "deny"
    WARN = "warn"


@dataclass
class Policy:
    """Policy definition."""

    id: str
    name: str
    policy_type: PolicyType
    scope: PolicyScope
    rules: dict[str, Any]
    action: PolicyAction
    priority: int
    enabled: bool
    created_at: datetime
    updated_at: datetime
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "policy_type": self.policy_type.value,
            "scope": self.scope.value,
            "rules": self.rules,
            "action": self.action.value,
            "priority": self.priority,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "description": self.description,
            "metadata": self.metadata,
        }


@dataclass
class PolicyEvaluation:
    """Result of policy evaluation."""

    policy_id: str
    policy_name: str
    result: EvaluationResult
    action: PolicyAction
    reason: str
    evaluated_at: datetime
    context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "result": self.result.value,
            "action": self.action.value,
            "reason": self.reason,
            "evaluated_at": self.evaluated_at.isoformat(),
            "context": self.context,
        }


@dataclass
class PolicyViolation:
    """Record of policy violation."""

    id: str
    policy_id: str
    policy_name: str
    violated_at: datetime
    context: dict[str, Any]
    action_taken: PolicyAction
    severity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "violated_at": self.violated_at.isoformat(),
            "context": self.context,
            "action_taken": self.action_taken.value,
            "severity": self.severity,
        }


class PolicyEngineService:
    """Service for centralized policy management.

    Features:
    - Policy CRUD
    - Policy evaluation
    - Violation tracking
    - Priority-based enforcement
    """

    POLICIES_KEY = "policies:definitions"
    VIOLATIONS_KEY = "policies:violations"
    EVALUATIONS_KEY = "policies:evaluations"

    # Default policies
    DEFAULT_POLICIES = [
        {
            "name": "daily_email_limit",
            "policy_type": PolicyType.OUTBOUND_LIMIT,
            "scope": PolicyScope.GLOBAL,
            "rules": {"max_emails_per_day": 500, "per_domain_limit": 50},
            "action": PolicyAction.DENY,
            "priority": 100,
            "description": "Limit daily outbound emails",
        },
        {
            "name": "rate_limit_api",
            "policy_type": PolicyType.RATE_LIMIT,
            "scope": PolicyScope.ENDPOINT,
            "rules": {"requests_per_minute": 100, "burst_limit": 20},
            "action": PolicyAction.THROTTLE,
            "priority": 90,
            "description": "API rate limiting",
        },
        {
            "name": "data_retention_leads",
            "policy_type": PolicyType.DATA_RETENTION,
            "scope": PolicyScope.GLOBAL,
            "rules": {"max_age_days": 365, "archive_after_days": 90},
            "action": PolicyAction.LOG,
            "priority": 50,
            "description": "Lead data retention policy",
        },
        {
            "name": "cost_budget_llm",
            "policy_type": PolicyType.COST_LIMIT,
            "scope": PolicyScope.SERVICE,
            "rules": {"daily_budget_usd": 100, "monthly_budget_usd": 2000},
            "action": PolicyAction.ALERT,
            "priority": 80,
            "description": "LLM cost budget",
        },
        {
            "name": "pii_protection",
            "policy_type": PolicyType.COMPLIANCE,
            "scope": PolicyScope.GLOBAL,
            "rules": {"mask_pii": True, "allowed_fields": ["name", "email", "company"]},
            "action": PolicyAction.DENY,
            "priority": 100,
            "description": "PII protection policy",
        },
    ]

    def __init__(self) -> None:
        """Initialize service."""
        pass

    async def initialize_defaults(self) -> int:
        """Initialize default policies.

        Returns:
            Number of policies created
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)
        created = 0

        for policy_def in self.DEFAULT_POLICIES:
            # Check if exists
            existing = await redis.hget(self.POLICIES_KEY, policy_def["name"])
            if existing:
                continue

            policy = Policy(
                id=str(uuid.uuid4())[:8],
                name=policy_def["name"],
                policy_type=policy_def["policy_type"],
                scope=policy_def["scope"],
                rules=policy_def["rules"],
                action=policy_def["action"],
                priority=policy_def["priority"],
                enabled=True,
                created_at=now,
                updated_at=now,
                description=policy_def.get("description", ""),
            )

            await redis.hset(
                self.POLICIES_KEY,
                policy.name,
                json.dumps(policy.to_dict()),
            )
            created += 1

        logger.info(f"[PolicyEngine] Initialized {created} default policies")
        return created

    async def create_policy(
        self,
        name: str,
        policy_type: PolicyType,
        scope: PolicyScope,
        rules: dict[str, Any],
        action: PolicyAction = PolicyAction.DENY,
        priority: int = 50,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Policy:
        """Create a new policy.

        Args:
            name: Policy name (unique)
            policy_type: Type of policy
            scope: Policy scope
            rules: Policy rules
            action: Action on violation
            priority: Priority (higher = evaluated first)
            description: Policy description
            metadata: Additional metadata

        Returns:
            Created policy
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        policy = Policy(
            id=str(uuid.uuid4())[:8],
            name=name,
            policy_type=policy_type,
            scope=scope,
            rules=rules,
            action=action,
            priority=priority,
            enabled=True,
            created_at=now,
            updated_at=now,
            description=description,
            metadata=metadata or {},
        )

        await redis.hset(
            self.POLICIES_KEY,
            name,
            json.dumps(policy.to_dict()),
        )

        logger.info(f"[PolicyEngine] Created policy: {name}")
        return policy

    async def get_policy(self, name: str) -> Policy | None:
        """Get policy by name.

        Args:
            name: Policy name

        Returns:
            Policy or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hget(self.POLICIES_KEY, name)
        if not raw:
            return None

        data = json.loads(raw)

        return Policy(
            id=data["id"],
            name=data["name"],
            policy_type=PolicyType(data["policy_type"]),
            scope=PolicyScope(data["scope"]),
            rules=data["rules"],
            action=PolicyAction(data["action"]),
            priority=data["priority"],
            enabled=data["enabled"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
        )

    async def list_policies(
        self,
        policy_type: PolicyType | None = None,
        enabled_only: bool = True,
    ) -> list[Policy]:
        """List all policies.

        Args:
            policy_type: Filter by type
            enabled_only: Only enabled policies

        Returns:
            List of policies
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hgetall(self.POLICIES_KEY)
        policies = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)

                if policy_type and data["policy_type"] != policy_type.value:
                    continue

                if enabled_only and not data["enabled"]:
                    continue

                policies.append(Policy(
                    id=data["id"],
                    name=data["name"],
                    policy_type=PolicyType(data["policy_type"]),
                    scope=PolicyScope(data["scope"]),
                    rules=data["rules"],
                    action=PolicyAction(data["action"]),
                    priority=data["priority"],
                    enabled=data["enabled"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    updated_at=datetime.fromisoformat(data["updated_at"]),
                    description=data.get("description", ""),
                    metadata=data.get("metadata", {}),
                ))
            except Exception:
                continue

        # Sort by priority (highest first)
        policies.sort(key=lambda p: p.priority, reverse=True)
        return policies

    async def update_policy(
        self,
        name: str,
        rules: dict[str, Any] | None = None,
        action: PolicyAction | None = None,
        enabled: bool | None = None,
        priority: int | None = None,
    ) -> Policy | None:
        """Update a policy.

        Args:
            name: Policy name
            rules: New rules
            action: New action
            enabled: Enable/disable
            priority: New priority

        Returns:
            Updated policy or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        policy = await self.get_policy(name)
        if not policy:
            return None

        if rules is not None:
            policy.rules = rules
        if action is not None:
            policy.action = action
        if enabled is not None:
            policy.enabled = enabled
        if priority is not None:
            policy.priority = priority

        policy.updated_at = datetime.now(UTC)

        await redis.hset(
            self.POLICIES_KEY,
            name,
            json.dumps(policy.to_dict()),
        )

        logger.info(f"[PolicyEngine] Updated policy: {name}")
        return policy

    async def delete_policy(self, name: str) -> bool:
        """Delete a policy.

        Args:
            name: Policy name

        Returns:
            True if deleted
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        result = await redis.hdel(self.POLICIES_KEY, name)

        if result:
            logger.info(f"[PolicyEngine] Deleted policy: {name}")

        return result > 0

    async def evaluate(
        self,
        context: dict[str, Any],
        policy_types: list[PolicyType] | None = None,
    ) -> list[PolicyEvaluation]:
        """Evaluate policies against context.

        Args:
            context: Evaluation context (action, resource, user, etc.)
            policy_types: Filter by policy types

        Returns:
            List of evaluation results
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        policies = await self.list_policies(enabled_only=True)
        evaluations = []

        for policy in policies:
            if policy_types and policy.policy_type not in policy_types:
                continue

            result, reason = self._evaluate_policy(policy, context)

            evaluation = PolicyEvaluation(
                policy_id=policy.id,
                policy_name=policy.name,
                result=result,
                action=policy.action,
                reason=reason,
                evaluated_at=now,
                context=context,
            )
            evaluations.append(evaluation)

            # Record violation
            if result == EvaluationResult.DENY:
                await self._record_violation(policy, context, now)

        # Store evaluations
        for eval in evaluations:
            await redis.lpush(
                self.EVALUATIONS_KEY,
                json.dumps(eval.to_dict()),
            )
        await redis.ltrim(self.EVALUATIONS_KEY, 0, 9999)

        return evaluations

    def _evaluate_policy(
        self,
        policy: Policy,
        context: dict[str, Any],
    ) -> tuple[EvaluationResult, str]:
        """Evaluate a single policy.

        Args:
            policy: Policy to evaluate
            context: Evaluation context

        Returns:
            Result and reason
        """
        rules = policy.rules

        if policy.policy_type == PolicyType.RATE_LIMIT:
            current = context.get("request_count", 0)
            limit = rules.get("requests_per_minute", 100)
            if current >= limit:
                return EvaluationResult.DENY, f"Rate limit exceeded: {current}/{limit}"

        elif policy.policy_type == PolicyType.OUTBOUND_LIMIT:
            daily_count = context.get("emails_sent_today", 0)
            daily_limit = rules.get("max_emails_per_day", 500)
            if daily_count >= daily_limit:
                return EvaluationResult.DENY, f"Daily email limit: {daily_count}/{daily_limit}"

            domain_count = context.get("domain_emails_today", 0)
            domain_limit = rules.get("per_domain_limit", 50)
            if domain_count >= domain_limit:
                return EvaluationResult.DENY, f"Domain limit: {domain_count}/{domain_limit}"

        elif policy.policy_type == PolicyType.COST_LIMIT:
            daily_cost = context.get("daily_cost_usd", 0)
            daily_budget = rules.get("daily_budget_usd", 100)
            if daily_cost >= daily_budget:
                return EvaluationResult.WARN, f"Daily budget exceeded: ${daily_cost}/${daily_budget}"

        elif policy.policy_type == PolicyType.RESOURCE_QUOTA:
            usage = context.get("resource_usage", 0)
            quota = rules.get("quota", 100)
            if usage >= quota:
                return EvaluationResult.DENY, f"Quota exceeded: {usage}/{quota}"

        elif policy.policy_type == PolicyType.COMPLIANCE:
            if rules.get("mask_pii"):
                fields = context.get("fields", [])
                allowed = set(rules.get("allowed_fields", []))
                forbidden = set(fields) - allowed
                if forbidden:
                    return EvaluationResult.DENY, f"PII fields not allowed: {forbidden}"

        return EvaluationResult.ALLOW, "Policy check passed"

    async def _record_violation(
        self,
        policy: Policy,
        context: dict[str, Any],
        timestamp: datetime,
    ) -> None:
        """Record policy violation."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        violation = PolicyViolation(
            id=str(uuid.uuid4())[:8],
            policy_id=policy.id,
            policy_name=policy.name,
            violated_at=timestamp,
            context=context,
            action_taken=policy.action,
            severity="high" if policy.priority >= 80 else "medium",
        )

        await redis.zadd(
            self.VIOLATIONS_KEY,
            {json.dumps(violation.to_dict()): timestamp.timestamp()},
        )

        logger.warning(f"[PolicyEngine] Violation: {policy.name}")

    async def get_violations(
        self,
        limit: int = 100,
        policy_name: str | None = None,
    ) -> list[PolicyViolation]:
        """Get recent violations.

        Args:
            limit: Max violations
            policy_name: Filter by policy

        Returns:
            List of violations
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.zrevrange(self.VIOLATIONS_KEY, 0, limit - 1)
        violations = []

        for item in raw:
            try:
                data = json.loads(item)

                if policy_name and data["policy_name"] != policy_name:
                    continue

                violations.append(PolicyViolation(
                    id=data["id"],
                    policy_id=data["policy_id"],
                    policy_name=data["policy_name"],
                    violated_at=datetime.fromisoformat(data["violated_at"]),
                    context=data["context"],
                    action_taken=PolicyAction(data["action_taken"]),
                    severity=data["severity"],
                ))
            except Exception:
                continue

        return violations

    async def check_and_enforce(
        self,
        action: str,
        resource: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Check policies and enforce.

        Convenience method for policy enforcement.

        Args:
            action: Action being performed
            resource: Resource being accessed
            context: Additional context

        Returns:
            (allowed, reason) tuple
        """
        full_context = {
            "action": action,
            "resource": resource,
            **(context or {}),
        }

        evaluations = await self.evaluate(full_context)

        # Check for denials
        for eval in evaluations:
            if eval.result == EvaluationResult.DENY:
                return False, eval.reason

        return True, "All policies passed"


# Singleton
policy_engine = PolicyEngineService()
