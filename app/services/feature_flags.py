"""Feature Flags Service.

Feature toggle system with gradual rollout support.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import hashlib

UTC = timezone.utc

logger = logging.getLogger(__name__)


class FlagStatus(str, Enum):
    """Feature flag status."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    GRADUAL = "gradual"  # Percentage rollout
    TARGETED = "targeted"  # Specific users/segments


class FlagEnvironment(str, Enum):
    """Flag environment scope."""

    ALL = "all"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class FeatureFlag:
    """Feature flag definition."""

    key: str
    name: str
    description: str
    status: FlagStatus
    environments: list[FlagEnvironment]
    rollout_percentage: int = 100
    allowed_users: list[str] = field(default_factory=list)
    allowed_segments: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_by: str = "system"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "environments": [e.value for e in self.environments],
            "rollout_percentage": self.rollout_percentage,
            "allowed_users": self.allowed_users,
            "allowed_segments": self.allowed_segments,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "updated_by": self.updated_by,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureFlag":
        return cls(
            key=data["key"],
            name=data["name"],
            description=data["description"],
            status=FlagStatus(data["status"]),
            environments=[FlagEnvironment(e) for e in data["environments"]],
            rollout_percentage=data.get("rollout_percentage", 100),
            allowed_users=data.get("allowed_users", []),
            allowed_segments=data.get("allowed_segments", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            updated_by=data.get("updated_by", "system"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class FlagEvaluation:
    """Result of evaluating a feature flag."""

    flag_key: str
    enabled: bool
    reason: str
    variant: str | None = None
    user_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "flag_key": self.flag_key,
            "enabled": self.enabled,
            "reason": self.reason,
            "variant": self.variant,
            "user_id": self.user_id,
        }


@dataclass
class FlagAuditEntry:
    """Audit entry for flag changes."""

    flag_key: str
    action: str  # created, updated, deleted
    actor: str
    timestamp: datetime
    previous_value: dict[str, Any] | None
    new_value: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "flag_key": self.flag_key,
            "action": self.action,
            "actor": self.actor,
            "timestamp": self.timestamp.isoformat(),
            "previous_value": self.previous_value,
            "new_value": self.new_value,
        }


# Default feature flags
DEFAULT_FLAGS = [
    FeatureFlag(
        key="new_scoring_algorithm",
        name="New Scoring Algorithm",
        description="Use v2 scoring algorithm with ML enhancements",
        status=FlagStatus.GRADUAL,
        environments=[FlagEnvironment.ALL],
        rollout_percentage=0,
    ),
    FeatureFlag(
        key="async_enrichment",
        name="Async Enrichment Pipeline",
        description="Process enrichment asynchronously",
        status=FlagStatus.ENABLED,
        environments=[FlagEnvironment.ALL],
    ),
    FeatureFlag(
        key="email_ai_generation",
        name="AI Email Generation",
        description="Use LLM for email content generation",
        status=FlagStatus.ENABLED,
        environments=[FlagEnvironment.ALL],
    ),
    FeatureFlag(
        key="advanced_analytics",
        name="Advanced Analytics Dashboard",
        description="Show advanced analytics features",
        status=FlagStatus.TARGETED,
        environments=[FlagEnvironment.PRODUCTION],
        allowed_segments=["enterprise", "beta_testers"],
    ),
    FeatureFlag(
        key="multi_channel_outreach",
        name="Multi-Channel Outreach",
        description="Enable SMS and messenger channels",
        status=FlagStatus.DISABLED,
        environments=[FlagEnvironment.DEVELOPMENT, FlagEnvironment.STAGING],
    ),
    FeatureFlag(
        key="smart_scheduling",
        name="Smart Email Scheduling",
        description="AI-powered optimal send time",
        status=FlagStatus.GRADUAL,
        environments=[FlagEnvironment.ALL],
        rollout_percentage=25,
    ),
]


class FeatureFlagsService:
    """Service for feature flags management.

    Features:
    - Flag CRUD operations
    - Gradual rollout by percentage
    - User/segment targeting
    - Environment scoping
    - Change audit trail
    """

    FLAGS_KEY = "feature_flags:flags"
    AUDIT_KEY = "feature_flags:audit"
    EVAL_CACHE_PREFIX = "feature_flags:eval:"

    def __init__(self) -> None:
        """Initialize service."""
        self._current_env: FlagEnvironment | None = None

    def _detect_environment(self) -> FlagEnvironment:
        """Detect current environment."""
        import os

        env = os.getenv("OTCLICK_ENVIRONMENT", "development").lower()
        env_map = {
            "development": FlagEnvironment.DEVELOPMENT,
            "dev": FlagEnvironment.DEVELOPMENT,
            "staging": FlagEnvironment.STAGING,
            "stage": FlagEnvironment.STAGING,
            "production": FlagEnvironment.PRODUCTION,
            "prod": FlagEnvironment.PRODUCTION,
        }
        return env_map.get(env, FlagEnvironment.DEVELOPMENT)

    async def _ensure_defaults(self) -> None:
        """Ensure default flags exist."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        for flag in DEFAULT_FLAGS:
            exists = await redis.hexists(self.FLAGS_KEY, flag.key)
            if not exists:
                await self.create_flag(flag, actor="system")

    async def is_enabled(
        self,
        flag_key: str,
        user_id: str | None = None,
        segment: str | None = None,
        default: bool = False,
    ) -> bool:
        """Check if feature flag is enabled.

        Args:
            flag_key: Flag key
            user_id: Optional user ID for targeting
            segment: Optional segment for targeting
            default: Default value if flag not found

        Returns:
            Whether flag is enabled
        """
        evaluation = await self.evaluate(flag_key, user_id, segment)
        return evaluation.enabled if evaluation else default

    async def evaluate(
        self,
        flag_key: str,
        user_id: str | None = None,
        segment: str | None = None,
    ) -> FlagEvaluation:
        """Evaluate a feature flag.

        Args:
            flag_key: Flag key
            user_id: Optional user ID
            segment: Optional segment

        Returns:
            Evaluation result
        """
        flag = await self.get_flag(flag_key)

        if not flag:
            return FlagEvaluation(
                flag_key=flag_key,
                enabled=False,
                reason="flag_not_found",
                user_id=user_id,
            )

        # Check environment
        current_env = self._detect_environment()
        if FlagEnvironment.ALL not in flag.environments and current_env not in flag.environments:
            return FlagEvaluation(
                flag_key=flag_key,
                enabled=False,
                reason="environment_mismatch",
                user_id=user_id,
            )

        # Check status
        if flag.status == FlagStatus.DISABLED:
            return FlagEvaluation(
                flag_key=flag_key,
                enabled=False,
                reason="flag_disabled",
                user_id=user_id,
            )

        if flag.status == FlagStatus.ENABLED:
            return FlagEvaluation(
                flag_key=flag_key,
                enabled=True,
                reason="flag_enabled",
                user_id=user_id,
            )

        if flag.status == FlagStatus.TARGETED:
            # Check user
            if user_id and user_id in flag.allowed_users:
                return FlagEvaluation(
                    flag_key=flag_key,
                    enabled=True,
                    reason="user_targeted",
                    user_id=user_id,
                )

            # Check segment
            if segment and segment in flag.allowed_segments:
                return FlagEvaluation(
                    flag_key=flag_key,
                    enabled=True,
                    reason="segment_targeted",
                    user_id=user_id,
                )

            return FlagEvaluation(
                flag_key=flag_key,
                enabled=False,
                reason="not_targeted",
                user_id=user_id,
            )

        if flag.status == FlagStatus.GRADUAL:
            # Hash-based consistent rollout
            if user_id:
                hash_input = f"{flag_key}:{user_id}"
                hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
                bucket = hash_value % 100

                enabled = bucket < flag.rollout_percentage

                return FlagEvaluation(
                    flag_key=flag_key,
                    enabled=enabled,
                    reason="gradual_rollout",
                    variant=f"bucket_{bucket}",
                    user_id=user_id,
                )

            # Without user_id, use random
            import random
            enabled = random.randint(0, 99) < flag.rollout_percentage

            return FlagEvaluation(
                flag_key=flag_key,
                enabled=enabled,
                reason="gradual_rollout_random",
                user_id=user_id,
            )

        return FlagEvaluation(
            flag_key=flag_key,
            enabled=False,
            reason="unknown_status",
            user_id=user_id,
        )

    async def get_flag(self, flag_key: str) -> FeatureFlag | None:
        """Get feature flag by key.

        Args:
            flag_key: Flag key

        Returns:
            Feature flag if found
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        data = await redis.hget(self.FLAGS_KEY, flag_key)

        if not data:
            # Check defaults
            for flag in DEFAULT_FLAGS:
                if flag.key == flag_key:
                    return flag
            return None

        try:
            return FeatureFlag.from_dict(json.loads(data))
        except Exception:
            return None

    async def list_flags(self) -> list[FeatureFlag]:
        """List all feature flags.

        Returns:
            List of flags
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        all_data = await redis.hgetall(self.FLAGS_KEY)

        flags = []
        for key, data in all_data.items():
            try:
                flags.append(FeatureFlag.from_dict(json.loads(data)))
            except Exception:
                continue

        # Add any missing defaults
        existing_keys = {f.key for f in flags}
        for default in DEFAULT_FLAGS:
            if default.key not in existing_keys:
                flags.append(default)

        return sorted(flags, key=lambda f: f.key)

    async def create_flag(
        self,
        flag: FeatureFlag,
        actor: str,
    ) -> FeatureFlag:
        """Create a new feature flag.

        Args:
            flag: Flag to create
            actor: Who created it

        Returns:
            Created flag
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        flag.created_at = now
        flag.updated_at = now
        flag.updated_by = actor

        await redis.hset(self.FLAGS_KEY, flag.key, json.dumps(flag.to_dict()))

        # Audit
        await self._record_audit(
            flag_key=flag.key,
            action="created",
            actor=actor,
            previous_value=None,
            new_value=flag.to_dict(),
        )

        logger.info(f"[FeatureFlags] Created flag: {flag.key} by {actor}")

        return flag

    async def update_flag(
        self,
        flag_key: str,
        updates: dict[str, Any],
        actor: str,
    ) -> FeatureFlag | None:
        """Update a feature flag.

        Args:
            flag_key: Flag key
            updates: Fields to update
            actor: Who updated it

        Returns:
            Updated flag
        """
        from app.storage.redis import get_redis
        import json

        flag = await self.get_flag(flag_key)
        if not flag:
            return None

        redis = await get_redis()
        previous = flag.to_dict()

        # Apply updates
        if "status" in updates:
            flag.status = FlagStatus(updates["status"])
        if "rollout_percentage" in updates:
            flag.rollout_percentage = max(0, min(100, updates["rollout_percentage"]))
        if "allowed_users" in updates:
            flag.allowed_users = updates["allowed_users"]
        if "allowed_segments" in updates:
            flag.allowed_segments = updates["allowed_segments"]
        if "environments" in updates:
            flag.environments = [FlagEnvironment(e) for e in updates["environments"]]
        if "description" in updates:
            flag.description = updates["description"]
        if "metadata" in updates:
            flag.metadata.update(updates["metadata"])

        flag.updated_at = datetime.now(UTC)
        flag.updated_by = actor

        await redis.hset(self.FLAGS_KEY, flag_key, json.dumps(flag.to_dict()))

        # Audit
        await self._record_audit(
            flag_key=flag_key,
            action="updated",
            actor=actor,
            previous_value=previous,
            new_value=flag.to_dict(),
        )

        logger.info(f"[FeatureFlags] Updated flag: {flag_key} by {actor}")

        return flag

    async def delete_flag(
        self,
        flag_key: str,
        actor: str,
    ) -> bool:
        """Delete a feature flag.

        Args:
            flag_key: Flag key
            actor: Who deleted it

        Returns:
            Whether deleted
        """
        from app.storage.redis import get_redis

        flag = await self.get_flag(flag_key)
        if not flag:
            return False

        redis = await get_redis()
        await redis.hdel(self.FLAGS_KEY, flag_key)

        # Audit
        await self._record_audit(
            flag_key=flag_key,
            action="deleted",
            actor=actor,
            previous_value=flag.to_dict(),
            new_value=None,
        )

        logger.info(f"[FeatureFlags] Deleted flag: {flag_key} by {actor}")

        return True

    async def set_rollout(
        self,
        flag_key: str,
        percentage: int,
        actor: str,
    ) -> FeatureFlag | None:
        """Set rollout percentage.

        Args:
            flag_key: Flag key
            percentage: Rollout percentage (0-100)
            actor: Who set it

        Returns:
            Updated flag
        """
        return await self.update_flag(
            flag_key=flag_key,
            updates={
                "status": FlagStatus.GRADUAL.value,
                "rollout_percentage": percentage,
            },
            actor=actor,
        )

    async def _record_audit(
        self,
        flag_key: str,
        action: str,
        actor: str,
        previous_value: dict[str, Any] | None,
        new_value: dict[str, Any] | None,
    ) -> None:
        """Record audit entry."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        entry = FlagAuditEntry(
            flag_key=flag_key,
            action=action,
            actor=actor,
            timestamp=now,
            previous_value=previous_value,
            new_value=new_value,
        )

        await redis.zadd(
            self.AUDIT_KEY,
            {json.dumps(entry.to_dict()): now.timestamp()},
        )

    async def get_audit_log(
        self,
        flag_key: str | None = None,
        limit: int = 50,
    ) -> list[FlagAuditEntry]:
        """Get audit log.

        Args:
            flag_key: Filter by flag
            limit: Max entries

        Returns:
            Audit entries
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.zrevrange(self.AUDIT_KEY, 0, limit - 1)

        entries = []
        for item in raw:
            try:
                data = json.loads(item)

                if flag_key and data["flag_key"] != flag_key:
                    continue

                entries.append(FlagAuditEntry(
                    flag_key=data["flag_key"],
                    action=data["action"],
                    actor=data["actor"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    previous_value=data.get("previous_value"),
                    new_value=data.get("new_value"),
                ))
            except Exception:
                continue

        return entries


# Singleton
feature_flags = FeatureFlagsService()
