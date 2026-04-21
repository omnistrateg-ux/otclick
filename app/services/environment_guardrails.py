"""Environment Guardrails Service.

Multi-environment safety rules and restrictions.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Environment types."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class ActionSeverity(str, Enum):
    """Action severity levels."""

    SAFE = "safe"  # Always allowed
    CAUTION = "caution"  # Allowed with warning
    RESTRICTED = "restricted"  # Requires confirmation
    FORBIDDEN = "forbidden"  # Never allowed


class ActionCategory(str, Enum):
    """Action categories."""

    DATA_MODIFY = "data_modify"
    DATA_DELETE = "data_delete"
    CONFIG_CHANGE = "config_change"
    OUTBOUND_EMAIL = "outbound_email"
    EXTERNAL_API = "external_api"
    DEPLOYMENT = "deployment"
    MIGRATION = "migration"
    ADMIN_OVERRIDE = "admin_override"


@dataclass
class GuardrailRule:
    """Environment guardrail rule."""

    action: ActionCategory
    severity: ActionSeverity
    description: str
    require_confirmation: bool = False
    require_reason: bool = False
    max_batch_size: int | None = None
    cooldown_seconds: int | None = None


@dataclass
class GuardrailViolation:
    """Guardrail violation record."""

    id: str
    environment: Environment
    action: ActionCategory
    severity: ActionSeverity
    actor: str
    details: dict[str, Any]
    blocked: bool
    reason: str
    occurred_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "environment": self.environment.value,
            "action": self.action.value,
            "severity": self.severity.value,
            "actor": self.actor,
            "details": self.details,
            "blocked": self.blocked,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass
class EnvironmentConfig:
    """Environment-specific configuration."""

    name: Environment
    display_name: str
    rules: dict[ActionCategory, GuardrailRule]
    max_outbound_emails_per_hour: int
    max_api_calls_per_minute: int
    allow_destructive_operations: bool
    require_approval_for_deploys: bool
    data_retention_days: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name.value,
            "display_name": self.display_name,
            "rules": {
                k.value: {
                    "severity": v.severity.value,
                    "description": v.description,
                    "require_confirmation": v.require_confirmation,
                }
                for k, v in self.rules.items()
            },
            "max_outbound_emails_per_hour": self.max_outbound_emails_per_hour,
            "max_api_calls_per_minute": self.max_api_calls_per_minute,
            "allow_destructive_operations": self.allow_destructive_operations,
            "require_approval_for_deploys": self.require_approval_for_deploys,
            "data_retention_days": self.data_retention_days,
        }


# Environment configurations
ENVIRONMENT_CONFIGS = {
    Environment.DEVELOPMENT: EnvironmentConfig(
        name=Environment.DEVELOPMENT,
        display_name="Development",
        rules={
            ActionCategory.DATA_MODIFY: GuardrailRule(
                action=ActionCategory.DATA_MODIFY,
                severity=ActionSeverity.SAFE,
                description="Data modifications allowed",
            ),
            ActionCategory.DATA_DELETE: GuardrailRule(
                action=ActionCategory.DATA_DELETE,
                severity=ActionSeverity.SAFE,
                description="Data deletions allowed",
            ),
            ActionCategory.OUTBOUND_EMAIL: GuardrailRule(
                action=ActionCategory.OUTBOUND_EMAIL,
                severity=ActionSeverity.RESTRICTED,
                description="Emails redirect to test inbox",
                require_confirmation=True,
            ),
            ActionCategory.DEPLOYMENT: GuardrailRule(
                action=ActionCategory.DEPLOYMENT,
                severity=ActionSeverity.SAFE,
                description="Deployments allowed freely",
            ),
        },
        max_outbound_emails_per_hour=10,
        max_api_calls_per_minute=1000,
        allow_destructive_operations=True,
        require_approval_for_deploys=False,
        data_retention_days=7,
    ),
    Environment.STAGING: EnvironmentConfig(
        name=Environment.STAGING,
        display_name="Staging",
        rules={
            ActionCategory.DATA_MODIFY: GuardrailRule(
                action=ActionCategory.DATA_MODIFY,
                severity=ActionSeverity.CAUTION,
                description="Data modifications logged",
            ),
            ActionCategory.DATA_DELETE: GuardrailRule(
                action=ActionCategory.DATA_DELETE,
                severity=ActionSeverity.RESTRICTED,
                description="Bulk deletions require confirmation",
                require_confirmation=True,
                max_batch_size=100,
            ),
            ActionCategory.OUTBOUND_EMAIL: GuardrailRule(
                action=ActionCategory.OUTBOUND_EMAIL,
                severity=ActionSeverity.RESTRICTED,
                description="Limited email sending",
                max_batch_size=50,
            ),
            ActionCategory.DEPLOYMENT: GuardrailRule(
                action=ActionCategory.DEPLOYMENT,
                severity=ActionSeverity.CAUTION,
                description="Deployments require tests to pass",
            ),
        },
        max_outbound_emails_per_hour=100,
        max_api_calls_per_minute=500,
        allow_destructive_operations=True,
        require_approval_for_deploys=False,
        data_retention_days=30,
    ),
    Environment.PRODUCTION: EnvironmentConfig(
        name=Environment.PRODUCTION,
        display_name="Production",
        rules={
            ActionCategory.DATA_MODIFY: GuardrailRule(
                action=ActionCategory.DATA_MODIFY,
                severity=ActionSeverity.CAUTION,
                description="All modifications audited",
                require_reason=True,
            ),
            ActionCategory.DATA_DELETE: GuardrailRule(
                action=ActionCategory.DATA_DELETE,
                severity=ActionSeverity.RESTRICTED,
                description="Deletions require approval and reason",
                require_confirmation=True,
                require_reason=True,
                max_batch_size=10,
                cooldown_seconds=300,
            ),
            ActionCategory.OUTBOUND_EMAIL: GuardrailRule(
                action=ActionCategory.OUTBOUND_EMAIL,
                severity=ActionSeverity.CAUTION,
                description="Email sending rate limited",
                max_batch_size=100,
            ),
            ActionCategory.DEPLOYMENT: GuardrailRule(
                action=ActionCategory.DEPLOYMENT,
                severity=ActionSeverity.RESTRICTED,
                description="Deployments require approval",
                require_confirmation=True,
            ),
            ActionCategory.MIGRATION: GuardrailRule(
                action=ActionCategory.MIGRATION,
                severity=ActionSeverity.RESTRICTED,
                description="Migrations require approval and backup",
                require_confirmation=True,
                require_reason=True,
            ),
            ActionCategory.ADMIN_OVERRIDE: GuardrailRule(
                action=ActionCategory.ADMIN_OVERRIDE,
                severity=ActionSeverity.RESTRICTED,
                description="Admin overrides logged to immutable journal",
                require_confirmation=True,
                require_reason=True,
            ),
        },
        max_outbound_emails_per_hour=1000,
        max_api_calls_per_minute=200,
        allow_destructive_operations=False,
        require_approval_for_deploys=True,
        data_retention_days=365,
    ),
}


class EnvironmentGuardrailsService:
    """Service for environment-specific safety guardrails.

    Features:
    - Environment detection
    - Action validation
    - Rate limiting by environment
    - Violation tracking
    """

    VIOLATIONS_KEY = "guardrails:violations"
    COOLDOWN_PREFIX = "guardrails:cooldown:"

    def __init__(self) -> None:
        """Initialize service."""
        self._current_env: Environment | None = None

    def detect_environment(self) -> Environment:
        """Detect current environment.

        Returns:
            Current environment
        """
        if self._current_env:
            return self._current_env

        env_str = os.getenv("OTCLICK_ENVIRONMENT", "development").lower()

        env_map = {
            "development": Environment.DEVELOPMENT,
            "dev": Environment.DEVELOPMENT,
            "staging": Environment.STAGING,
            "stage": Environment.STAGING,
            "production": Environment.PRODUCTION,
            "prod": Environment.PRODUCTION,
            "test": Environment.TEST,
        }

        self._current_env = env_map.get(env_str, Environment.DEVELOPMENT)
        return self._current_env

    def get_config(self, env: Environment | None = None) -> EnvironmentConfig:
        """Get environment configuration.

        Args:
            env: Environment (defaults to current)

        Returns:
            Environment config
        """
        if env is None:
            env = self.detect_environment()

        return ENVIRONMENT_CONFIGS.get(env, ENVIRONMENT_CONFIGS[Environment.DEVELOPMENT])

    async def check_action(
        self,
        action: ActionCategory,
        actor: str,
        details: dict[str, Any] | None = None,
        batch_size: int = 1,
    ) -> dict[str, Any]:
        """Check if action is allowed.

        Args:
            action: Action to check
            actor: Who is performing action
            details: Action details
            batch_size: Number of items affected

        Returns:
            Check result with allowed status
        """
        env = self.detect_environment()
        config = self.get_config(env)

        rule = config.rules.get(action)
        if not rule:
            return {
                "allowed": True,
                "severity": ActionSeverity.SAFE.value,
                "warnings": [],
            }

        warnings = []
        blocked = False
        reason = None

        # Check severity
        if rule.severity == ActionSeverity.FORBIDDEN:
            blocked = True
            reason = f"Action {action.value} forbidden in {env.value}"

        # Check batch size
        if rule.max_batch_size and batch_size > rule.max_batch_size:
            blocked = True
            reason = f"Batch size {batch_size} exceeds limit {rule.max_batch_size}"

        # Check cooldown
        if rule.cooldown_seconds:
            on_cooldown = await self._check_cooldown(action, actor)
            if on_cooldown:
                blocked = True
                reason = f"Action on cooldown, wait {rule.cooldown_seconds}s"

        # Add warnings
        if rule.severity == ActionSeverity.CAUTION:
            warnings.append(f"Caution: {rule.description}")

        if rule.severity == ActionSeverity.RESTRICTED:
            warnings.append(f"Restricted: {rule.description}")

        if rule.require_confirmation:
            warnings.append("Confirmation required")

        if rule.require_reason:
            warnings.append("Reason required")

        # Record violation if blocked
        if blocked:
            await self._record_violation(
                env=env,
                action=action,
                severity=rule.severity,
                actor=actor,
                details=details or {},
                blocked=True,
                reason=reason or "Unknown",
            )

        return {
            "allowed": not blocked,
            "severity": rule.severity.value,
            "warnings": warnings,
            "require_confirmation": rule.require_confirmation,
            "require_reason": rule.require_reason,
            "reason": reason,
        }

    async def _check_cooldown(
        self,
        action: ActionCategory,
        actor: str,
    ) -> bool:
        """Check if action is on cooldown."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        key = f"{self.COOLDOWN_PREFIX}{action.value}:{actor}"
        return await redis.exists(key)

    async def set_cooldown(
        self,
        action: ActionCategory,
        actor: str,
        seconds: int,
    ) -> None:
        """Set action cooldown."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        key = f"{self.COOLDOWN_PREFIX}{action.value}:{actor}"
        await redis.set(key, "1", ex=seconds)

    async def _record_violation(
        self,
        env: Environment,
        action: ActionCategory,
        severity: ActionSeverity,
        actor: str,
        details: dict[str, Any],
        blocked: bool,
        reason: str,
    ) -> None:
        """Record a guardrail violation."""
        from app.storage.redis import get_redis
        import json
        import uuid

        redis = await get_redis()
        now = datetime.now(UTC)

        violation = GuardrailViolation(
            id=str(uuid.uuid4()),
            environment=env,
            action=action,
            severity=severity,
            actor=actor,
            details=details,
            blocked=blocked,
            reason=reason,
            occurred_at=now,
        )

        await redis.zadd(
            self.VIOLATIONS_KEY,
            {json.dumps(violation.to_dict()): now.timestamp()},
        )

        logger.warning(
            f"[Guardrails] Violation: {action.value} by {actor} "
            f"in {env.value} - {reason}"
        )

    async def get_violations(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> list[GuardrailViolation]:
        """Get recent violations.

        Args:
            hours: Hours to look back
            limit: Max results

        Returns:
            List of violations
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)
        min_ts = (now - __import__("datetime").timedelta(hours=hours)).timestamp()

        raw = await redis.zrevrangebyscore(
            self.VIOLATIONS_KEY,
            "+inf",
            min_ts,
            start=0,
            num=limit,
        )

        violations = []
        for item in raw:
            try:
                data = json.loads(item)
                violations.append(GuardrailViolation(
                    id=data["id"],
                    environment=Environment(data["environment"]),
                    action=ActionCategory(data["action"]),
                    severity=ActionSeverity(data["severity"]),
                    actor=data["actor"],
                    details=data["details"],
                    blocked=data["blocked"],
                    reason=data["reason"],
                    occurred_at=datetime.fromisoformat(data["occurred_at"]),
                ))
            except Exception:
                continue

        return violations

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.detect_environment() == Environment.PRODUCTION

    def get_email_limit(self) -> int:
        """Get email rate limit for current environment."""
        config = self.get_config()
        return config.max_outbound_emails_per_hour

    def allows_destructive_ops(self) -> bool:
        """Check if destructive operations are allowed."""
        config = self.get_config()
        return config.allow_destructive_operations


# Singleton
environment_guardrails = EnvironmentGuardrailsService()
