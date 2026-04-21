"""Role-Based Access Control Service.

RBAC for users, managers, and system actions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """User roles."""

    ADMIN = "admin"  # Full access
    MANAGER = "manager"  # Sales manager
    SALES_REP = "sales_rep"  # Sales representative
    MARKETING = "marketing"  # Marketing team
    VIEWER = "viewer"  # Read-only access
    SYSTEM = "system"  # System/automation


class Permission(str, Enum):
    """System permissions."""

    # Lead permissions
    LEAD_VIEW = "lead:view"
    LEAD_CREATE = "lead:create"
    LEAD_EDIT = "lead:edit"
    LEAD_DELETE = "lead:delete"
    LEAD_TRANSITION = "lead:transition"

    # Deal permissions
    DEAL_VIEW = "deal:view"
    DEAL_CREATE = "deal:create"
    DEAL_EDIT = "deal:edit"
    DEAL_CLOSE = "deal:close"
    DEAL_REASSIGN = "deal:reassign"

    # Handoff permissions
    HANDOFF_VIEW = "handoff:view"
    HANDOFF_ACCEPT = "handoff:accept"
    HANDOFF_REJECT = "handoff:reject"
    HANDOFF_REASSIGN = "handoff:reassign"

    # Campaign permissions
    CAMPAIGN_VIEW = "campaign:view"
    CAMPAIGN_CREATE = "campaign:create"
    CAMPAIGN_EDIT = "campaign:edit"
    CAMPAIGN_SEND = "campaign:send"
    CAMPAIGN_PAUSE = "campaign:pause"

    # Analytics permissions
    ANALYTICS_VIEW = "analytics:view"
    ANALYTICS_EXPORT = "analytics:export"

    # Admin permissions
    USER_MANAGE = "user:manage"
    ROLE_ASSIGN = "role:assign"
    SETTINGS_MANAGE = "settings:manage"
    AUDIT_VIEW = "audit:view"

    # Feedback permissions
    FEEDBACK_SUBMIT = "feedback:submit"
    FEEDBACK_VIEW_ALL = "feedback:view_all"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),  # All permissions

    Role.MANAGER: {
        Permission.LEAD_VIEW,
        Permission.LEAD_CREATE,
        Permission.LEAD_EDIT,
        Permission.LEAD_TRANSITION,
        Permission.DEAL_VIEW,
        Permission.DEAL_CREATE,
        Permission.DEAL_EDIT,
        Permission.DEAL_CLOSE,
        Permission.DEAL_REASSIGN,
        Permission.HANDOFF_VIEW,
        Permission.HANDOFF_ACCEPT,
        Permission.HANDOFF_REJECT,
        Permission.HANDOFF_REASSIGN,
        Permission.CAMPAIGN_VIEW,
        Permission.ANALYTICS_VIEW,
        Permission.ANALYTICS_EXPORT,
        Permission.FEEDBACK_SUBMIT,
        Permission.FEEDBACK_VIEW_ALL,
        Permission.AUDIT_VIEW,
    },

    Role.SALES_REP: {
        Permission.LEAD_VIEW,
        Permission.LEAD_EDIT,
        Permission.LEAD_TRANSITION,
        Permission.DEAL_VIEW,
        Permission.DEAL_CREATE,
        Permission.DEAL_EDIT,
        Permission.HANDOFF_VIEW,
        Permission.HANDOFF_ACCEPT,
        Permission.HANDOFF_REJECT,
        Permission.CAMPAIGN_VIEW,
        Permission.ANALYTICS_VIEW,
        Permission.FEEDBACK_SUBMIT,
    },

    Role.MARKETING: {
        Permission.LEAD_VIEW,
        Permission.LEAD_CREATE,
        Permission.CAMPAIGN_VIEW,
        Permission.CAMPAIGN_CREATE,
        Permission.CAMPAIGN_EDIT,
        Permission.CAMPAIGN_SEND,
        Permission.CAMPAIGN_PAUSE,
        Permission.ANALYTICS_VIEW,
        Permission.ANALYTICS_EXPORT,
    },

    Role.VIEWER: {
        Permission.LEAD_VIEW,
        Permission.DEAL_VIEW,
        Permission.HANDOFF_VIEW,
        Permission.CAMPAIGN_VIEW,
        Permission.ANALYTICS_VIEW,
    },

    Role.SYSTEM: set(Permission),  # All permissions for automation
}


@dataclass
class User:
    """User with role and permissions."""

    id: str
    email: str
    name: str
    role: Role
    is_active: bool = True
    created_at: datetime | None = None
    last_login: datetime | None = None
    custom_permissions: set[Permission] = field(default_factory=set)
    denied_permissions: set[Permission] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role.value,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "custom_permissions": [p.value for p in self.custom_permissions],
            "denied_permissions": [p.value for p in self.denied_permissions],
            "metadata": self.metadata,
        }


@dataclass
class AccessCheckResult:
    """Result of an access check."""

    allowed: bool
    user_id: str
    permission: str
    role: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "user_id": self.user_id,
            "permission": self.permission,
            "role": self.role,
            "reason": self.reason,
        }


class RBACService:
    """Role-Based Access Control service.

    Features:
    - Role management
    - Permission checking
    - Custom permission grants/denials
    - Access logging
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # User Management
    # ========================================================================

    async def create_user(
        self,
        user_id: str,
        email: str,
        name: str,
        role: Role,
        metadata: dict[str, Any] | None = None,
    ) -> User:
        """Create a new user.

        Args:
            user_id: User ID
            email: Email address
            name: Display name
            role: User role
            metadata: Additional metadata

        Returns:
            Created User
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        user = User(
            id=user_id,
            email=email,
            name=name,
            role=role,
            is_active=True,
            created_at=now,
            metadata=metadata or {},
        )

        key = f"user:{user_id}"
        await redis.set(key, json.dumps(user.to_dict()), ex=86400 * 365)

        # Index by email
        await redis.set(f"user:email:{email.lower()}", user_id, ex=86400 * 365)

        # Index by role
        await redis.sadd(f"users:role:{role.value}", user_id)
        await redis.expire(f"users:role:{role.value}", 86400 * 365)

        logger.info(f"[RBAC] User created | id={user_id} | role={role.value}")

        return user

    async def get_user(self, user_id: str) -> User | None:
        """Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        data = await redis.get(f"user:{user_id}")

        if not data:
            return None

        d = json.loads(data)
        return User(
            id=d["id"],
            email=d["email"],
            name=d["name"],
            role=Role(d["role"]),
            is_active=d.get("is_active", True),
            created_at=datetime.fromisoformat(d["created_at"]) if d.get("created_at") else None,
            last_login=datetime.fromisoformat(d["last_login"]) if d.get("last_login") else None,
            custom_permissions={Permission(p) for p in d.get("custom_permissions", [])},
            denied_permissions={Permission(p) for p in d.get("denied_permissions", [])},
            metadata=d.get("metadata", {}),
        )

    async def update_user_role(
        self,
        user_id: str,
        new_role: Role,
        actor: str,
    ) -> User:
        """Update user's role.

        Args:
            user_id: User ID
            new_role: New role
            actor: Who made the change

        Returns:
            Updated User
        """
        from app.storage.redis import get_redis
        import json

        user = await self.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        old_role = user.role
        user.role = new_role

        redis = await get_redis()

        # Update user
        await redis.set(f"user:{user_id}", json.dumps(user.to_dict()), ex=86400 * 365)

        # Update role indices
        await redis.srem(f"users:role:{old_role.value}", user_id)
        await redis.sadd(f"users:role:{new_role.value}", user_id)

        logger.info(
            f"[RBAC] Role updated | user={user_id} | "
            f"{old_role.value} -> {new_role.value} | actor={actor}"
        )

        return user

    async def grant_permission(
        self,
        user_id: str,
        permission: Permission,
        actor: str,
    ) -> User:
        """Grant additional permission to user.

        Args:
            user_id: User ID
            permission: Permission to grant
            actor: Who granted it

        Returns:
            Updated User
        """
        from app.storage.redis import get_redis
        import json

        user = await self.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        user.custom_permissions.add(permission)
        user.denied_permissions.discard(permission)

        redis = await get_redis()
        await redis.set(f"user:{user_id}", json.dumps(user.to_dict()), ex=86400 * 365)

        logger.info(
            f"[RBAC] Permission granted | user={user_id} | "
            f"permission={permission.value} | actor={actor}"
        )

        return user

    async def deny_permission(
        self,
        user_id: str,
        permission: Permission,
        actor: str,
    ) -> User:
        """Deny specific permission from user.

        Args:
            user_id: User ID
            permission: Permission to deny
            actor: Who denied it

        Returns:
            Updated User
        """
        from app.storage.redis import get_redis
        import json

        user = await self.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        user.denied_permissions.add(permission)
        user.custom_permissions.discard(permission)

        redis = await get_redis()
        await redis.set(f"user:{user_id}", json.dumps(user.to_dict()), ex=86400 * 365)

        logger.info(
            f"[RBAC] Permission denied | user={user_id} | "
            f"permission={permission.value} | actor={actor}"
        )

        return user

    # ========================================================================
    # Permission Checking
    # ========================================================================

    async def check_permission(
        self,
        user_id: str,
        permission: Permission,
        resource_id: str | None = None,
    ) -> AccessCheckResult:
        """Check if user has permission.

        Args:
            user_id: User ID
            permission: Permission to check
            resource_id: Optional resource ID for resource-level checks

        Returns:
            AccessCheckResult
        """
        user = await self.get_user(user_id)

        if not user:
            return AccessCheckResult(
                allowed=False,
                user_id=user_id,
                permission=permission.value,
                role="unknown",
                reason="user_not_found",
            )

        if not user.is_active:
            return AccessCheckResult(
                allowed=False,
                user_id=user_id,
                permission=permission.value,
                role=user.role.value,
                reason="user_inactive",
            )

        # Check denied permissions first
        if permission in user.denied_permissions:
            return AccessCheckResult(
                allowed=False,
                user_id=user_id,
                permission=permission.value,
                role=user.role.value,
                reason="permission_denied",
            )

        # Check custom permissions
        if permission in user.custom_permissions:
            return AccessCheckResult(
                allowed=True,
                user_id=user_id,
                permission=permission.value,
                role=user.role.value,
                reason="custom_grant",
            )

        # Check role permissions
        role_permissions = ROLE_PERMISSIONS.get(user.role, set())
        if permission in role_permissions:
            return AccessCheckResult(
                allowed=True,
                user_id=user_id,
                permission=permission.value,
                role=user.role.value,
                reason="role_permission",
            )

        return AccessCheckResult(
            allowed=False,
            user_id=user_id,
            permission=permission.value,
            role=user.role.value,
            reason="no_permission",
        )

    async def has_permission(
        self,
        user_id: str,
        permission: Permission,
    ) -> bool:
        """Quick check if user has permission.

        Args:
            user_id: User ID
            permission: Permission to check

        Returns:
            True if allowed
        """
        result = await self.check_permission(user_id, permission)
        return result.allowed

    async def get_user_permissions(
        self,
        user_id: str,
    ) -> set[Permission]:
        """Get all permissions for a user.

        Args:
            user_id: User ID

        Returns:
            Set of permissions
        """
        user = await self.get_user(user_id)
        if not user or not user.is_active:
            return set()

        # Start with role permissions
        permissions = ROLE_PERMISSIONS.get(user.role, set()).copy()

        # Add custom permissions
        permissions.update(user.custom_permissions)

        # Remove denied permissions
        permissions -= user.denied_permissions

        return permissions

    # ========================================================================
    # Role Queries
    # ========================================================================

    async def get_users_by_role(
        self,
        role: Role,
    ) -> list[User]:
        """Get all users with a role.

        Args:
            role: Role to filter by

        Returns:
            List of users
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        user_ids = await redis.smembers(f"users:role:{role.value}")

        users = []
        for user_id in user_ids:
            user = await self.get_user(user_id)
            if user:
                users.append(user)

        return users

    async def get_managers(self) -> list[User]:
        """Get all managers (MANAGER and SALES_REP roles).

        Returns:
            List of manager users
        """
        managers = await self.get_users_by_role(Role.MANAGER)
        sales_reps = await self.get_users_by_role(Role.SALES_REP)
        return managers + sales_reps


# Singleton
rbac = RBACService()
