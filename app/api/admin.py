"""Admin API endpoints.

RBAC, Audit Trail, and administrative functions.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.rbac import (
    RBACService,
    Role,
    Permission,
)
from app.services.audit_trail import (
    AuditTrailService,
    AuditAction,
    AuditSeverity,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateUserRequest(BaseModel):
    """Create user request."""

    user_id: str
    email: str
    name: str
    role: str
    metadata: dict[str, Any] | None = None


class UpdateRoleRequest(BaseModel):
    """Update user role request."""

    new_role: str
    actor: str


class PermissionRequest(BaseModel):
    """Grant/deny permission request."""

    permission: str
    actor: str


class AuditLogRequest(BaseModel):
    """Manual audit log request."""

    action: str
    actor_id: str
    resource_type: str
    resource_id: str
    description: str
    severity: str = "info"
    changes: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


# ============================================================================
# RBAC Endpoints
# ============================================================================


@router.post("/users")
async def create_user(
    request: CreateUserRequest,
) -> dict[str, Any]:
    """Create a new user.

    Args:
        request: User creation request

    Returns:
        Created user
    """
    service = RBACService()

    try:
        role = Role(request.role)
    except ValueError:
        valid_roles = [r.value for r in Role]
        raise HTTPException(400, f"Invalid role. Valid: {valid_roles}")

    user = await service.create_user(
        user_id=request.user_id,
        email=request.email,
        name=request.name,
        role=role,
        metadata=request.metadata,
    )

    return user.to_dict()


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
) -> dict[str, Any]:
    """Get user by ID.

    Args:
        user_id: User ID

    Returns:
        User details
    """
    service = RBACService()
    user = await service.get_user(user_id)

    if not user:
        raise HTTPException(404, f"User {user_id} not found")

    return user.to_dict()


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    request: UpdateRoleRequest,
) -> dict[str, Any]:
    """Update user's role.

    Args:
        user_id: User ID
        request: Role update request

    Returns:
        Updated user
    """
    service = RBACService()

    try:
        role = Role(request.new_role)
    except ValueError:
        valid_roles = [r.value for r in Role]
        raise HTTPException(400, f"Invalid role. Valid: {valid_roles}")

    try:
        user = await service.update_user_role(user_id, role, request.actor)
    except ValueError as e:
        raise HTTPException(404, str(e))

    return user.to_dict()


@router.post("/users/{user_id}/permissions/grant")
async def grant_permission(
    user_id: str,
    request: PermissionRequest,
) -> dict[str, Any]:
    """Grant permission to user.

    Args:
        user_id: User ID
        request: Permission request

    Returns:
        Updated user
    """
    service = RBACService()

    try:
        permission = Permission(request.permission)
    except ValueError:
        valid_perms = [p.value for p in Permission]
        raise HTTPException(400, f"Invalid permission. Valid: {valid_perms}")

    try:
        user = await service.grant_permission(user_id, permission, request.actor)
    except ValueError as e:
        raise HTTPException(404, str(e))

    return user.to_dict()


@router.post("/users/{user_id}/permissions/deny")
async def deny_permission(
    user_id: str,
    request: PermissionRequest,
) -> dict[str, Any]:
    """Deny permission from user.

    Args:
        user_id: User ID
        request: Permission request

    Returns:
        Updated user
    """
    service = RBACService()

    try:
        permission = Permission(request.permission)
    except ValueError:
        valid_perms = [p.value for p in Permission]
        raise HTTPException(400, f"Invalid permission. Valid: {valid_perms}")

    try:
        user = await service.deny_permission(user_id, permission, request.actor)
    except ValueError as e:
        raise HTTPException(404, str(e))

    return user.to_dict()


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: str,
) -> dict[str, Any]:
    """Get all permissions for a user.

    Args:
        user_id: User ID

    Returns:
        User permissions
    """
    service = RBACService()
    permissions = await service.get_user_permissions(user_id)

    return {
        "user_id": user_id,
        "permissions": [p.value for p in permissions],
        "count": len(permissions),
    }


@router.get("/users/{user_id}/check")
async def check_permission(
    user_id: str,
    permission: str,
) -> dict[str, Any]:
    """Check if user has permission.

    Args:
        user_id: User ID
        permission: Permission to check

    Returns:
        Access check result
    """
    service = RBACService()

    try:
        perm = Permission(permission)
    except ValueError:
        valid_perms = [p.value for p in Permission]
        raise HTTPException(400, f"Invalid permission. Valid: {valid_perms}")

    result = await service.check_permission(user_id, perm)
    return result.to_dict()


@router.get("/users/by-role/{role}")
async def get_users_by_role(
    role: str,
) -> list[dict[str, Any]]:
    """Get all users with a role.

    Args:
        role: Role to filter by

    Returns:
        List of users
    """
    service = RBACService()

    try:
        r = Role(role)
    except ValueError:
        valid_roles = [r.value for r in Role]
        raise HTTPException(400, f"Invalid role. Valid: {valid_roles}")

    users = await service.get_users_by_role(r)
    return [u.to_dict() for u in users]


@router.get("/managers")
async def get_managers() -> list[dict[str, Any]]:
    """Get all managers.

    Returns:
        List of managers
    """
    service = RBACService()
    managers = await service.get_managers()
    return [m.to_dict() for m in managers]


# ============================================================================
# Audit Trail Endpoints
# ============================================================================


@router.post("/audit")
async def log_audit_event(
    request: AuditLogRequest,
) -> dict[str, Any]:
    """Log an audit event.

    Args:
        request: Audit log request

    Returns:
        Created audit entry
    """
    service = AuditTrailService()

    try:
        action = AuditAction(request.action)
    except ValueError:
        valid_actions = [a.value for a in AuditAction]
        raise HTTPException(400, f"Invalid action. Valid actions: {valid_actions[:10]}...")

    try:
        severity = AuditSeverity(request.severity)
    except ValueError:
        valid_sev = [s.value for s in AuditSeverity]
        raise HTTPException(400, f"Invalid severity. Valid: {valid_sev}")

    entry = await service.log(
        action=action,
        actor_id=request.actor_id,
        resource_type=request.resource_type,
        resource_id=request.resource_id,
        description=request.description,
        severity=severity,
        changes=request.changes,
        metadata=request.metadata,
    )

    return entry.to_dict()


@router.get("/audit/{entry_id}")
async def get_audit_entry(
    entry_id: str,
) -> dict[str, Any]:
    """Get audit entry by ID.

    Args:
        entry_id: Entry ID

    Returns:
        Audit entry
    """
    service = AuditTrailService()
    entry = await service.get_entry(entry_id)

    if not entry:
        raise HTTPException(404, f"Audit entry {entry_id} not found")

    return entry.to_dict()


@router.get("/audit/resource/{resource_type}/{resource_id}")
async def get_resource_audit_history(
    resource_type: str,
    resource_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get audit history for a resource.

    Args:
        resource_type: Resource type
        resource_id: Resource ID
        limit: Max entries

    Returns:
        List of audit entries
    """
    service = AuditTrailService()
    entries = await service.get_resource_history(resource_type, resource_id, limit)
    return [e.to_dict() for e in entries]


@router.get("/audit/actor/{actor_id}")
async def get_actor_audit_history(
    actor_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get audit history for an actor.

    Args:
        actor_id: Actor ID
        limit: Max entries

    Returns:
        List of audit entries
    """
    service = AuditTrailService()
    entries = await service.get_actor_history(actor_id, limit)
    return [e.to_dict() for e in entries]


@router.get("/audit/search")
async def search_audit(
    action: str = Query(default=None),
    actor_id: str = Query(default=None),
    resource_type: str = Query(default=None),
    severity: str = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Search audit entries.

    Args:
        action: Filter by action
        actor_id: Filter by actor
        resource_type: Filter by resource type
        severity: Filter by severity
        limit: Max results

    Returns:
        Matching audit entries
    """
    service = AuditTrailService()

    action_enum = None
    if action:
        try:
            action_enum = AuditAction(action)
        except ValueError:
            raise HTTPException(400, f"Invalid action: {action}")

    severity_enum = None
    if severity:
        try:
            severity_enum = AuditSeverity(severity)
        except ValueError:
            raise HTTPException(400, f"Invalid severity: {severity}")

    entries = await service.search(
        action=action_enum,
        actor_id=actor_id,
        resource_type=resource_type,
        severity=severity_enum,
        limit=limit,
    )

    return [e.to_dict() for e in entries]


@router.get("/audit/summary")
async def get_audit_summary(
    days: int = Query(default=7, ge=1, le=90),
) -> dict[str, Any]:
    """Get audit summary.

    Args:
        days: Days to analyze

    Returns:
        Audit summary
    """
    service = AuditTrailService()
    summary = await service.get_summary(days)
    return summary.to_dict()


# ============================================================================
# Reference Data
# ============================================================================


@router.get("/roles")
async def get_roles() -> list[dict[str, str]]:
    """Get all available roles.

    Returns:
        List of roles
    """
    return [{"role": r.value} for r in Role]


@router.get("/permissions")
async def get_permissions() -> list[dict[str, str]]:
    """Get all available permissions.

    Returns:
        List of permissions
    """
    return [{"permission": p.value} for p in Permission]


@router.get("/audit-actions")
async def get_audit_actions() -> list[dict[str, str]]:
    """Get all audit action types.

    Returns:
        List of actions
    """
    return [{"action": a.value} for a in AuditAction]
