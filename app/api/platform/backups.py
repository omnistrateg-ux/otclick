"""Backup management API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.signed_backup import (
    SignedBackupService,
    BackupType,
    BackupTarget,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backups", tags=["backups"])


# Request models
class CreateBackupRequest(BaseModel):
    """Create backup request."""

    target: str
    created_by: str
    backup_type: str = "full"
    metadata: dict[str, Any] | None = None


class RestoreBackupRequest(BaseModel):
    """Restore backup request."""

    restored_by: str
    verify_first: bool = True


# Endpoints
@router.post("")
async def create_backup(
    request: CreateBackupRequest,
) -> dict[str, Any]:
    """Create signed backup."""
    service = SignedBackupService()

    try:
        target = BackupTarget(request.target)
    except ValueError:
        valid = [t.value for t in BackupTarget]
        raise HTTPException(400, f"Invalid target. Valid: {valid}")

    try:
        backup_type = BackupType(request.backup_type)
    except ValueError:
        valid = [t.value for t in BackupType]
        raise HTTPException(400, f"Invalid backup type. Valid: {valid}")

    backup = await service.create_backup(
        target=target,
        created_by=request.created_by,
        backup_type=backup_type,
        metadata=request.metadata,
    )
    return backup.to_dict()


@router.get("")
async def list_backups(
    target: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """List backups."""
    service = SignedBackupService()

    t = None
    if target:
        try:
            t = BackupTarget(target)
        except ValueError:
            valid = [t.value for t in BackupTarget]
            raise HTTPException(400, f"Invalid target. Valid: {valid}")

    backups = await service.list_backups(target=t, limit=limit)
    return [b.to_dict() for b in backups]


@router.get("/restores/history")
async def get_restore_history(
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get restore history."""
    service = SignedBackupService()
    operations = await service.get_restore_history(limit=limit)
    return [o.to_dict() for o in operations]


@router.get("/{backup_id}")
async def get_backup(backup_id: str) -> dict[str, Any]:
    """Get backup by ID."""
    service = SignedBackupService()
    backup = await service.get_backup(backup_id)
    if not backup:
        raise HTTPException(404, "Backup not found")
    return backup.to_dict()


@router.post("/{backup_id}/verify")
async def verify_backup(backup_id: str) -> dict[str, Any]:
    """Verify backup integrity."""
    service = SignedBackupService()
    valid, message = await service.verify_backup(backup_id)
    return {"valid": valid, "message": message}


@router.post("/{backup_id}/restore")
async def restore_backup(
    backup_id: str,
    request: RestoreBackupRequest,
) -> dict[str, Any]:
    """Restore from backup."""
    service = SignedBackupService()

    try:
        operation = await service.restore_backup(
            backup_id=backup_id,
            restored_by=request.restored_by,
            verify_first=request.verify_first,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return operation.to_dict()


@router.delete("/{backup_id}")
async def delete_backup(
    backup_id: str,
    deleted_by: str = Query(...),
) -> dict[str, str]:
    """Delete backup."""
    service = SignedBackupService()
    deleted = await service.delete_backup(backup_id, deleted_by)
    if not deleted:
        raise HTTPException(404, "Backup not found")
    return {"status": "deleted"}


# Reference endpoints
@router.get("/reference/targets")
async def list_backup_targets() -> list[str]:
    """List available backup targets."""
    return [t.value for t in BackupTarget]


@router.get("/reference/types")
async def list_backup_types() -> list[str]:
    """List available backup types."""
    return [t.value for t in BackupType]
