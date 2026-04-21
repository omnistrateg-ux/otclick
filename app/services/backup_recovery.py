"""Backup and Recovery Service.

Data backup, export, import, and recovery operations.
"""

import gzip
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class BackupType(str, Enum):
    """Types of backups."""

    FULL = "full"  # All data
    LEADS = "leads"  # Just leads
    DEALS = "deals"  # Just deals
    CONFIG = "config"  # Configuration only
    AUDIT = "audit"  # Audit logs


class BackupStatus(str, Enum):
    """Backup status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BackupMetadata:
    """Metadata for a backup."""

    id: str
    backup_type: BackupType
    status: BackupStatus
    created_at: datetime
    completed_at: datetime | None
    size_bytes: int
    record_count: int
    filename: str | None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "backup_type": self.backup_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "size_bytes": self.size_bytes,
            "record_count": self.record_count,
            "filename": self.filename,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class RestoreResult:
    """Result of a restore operation."""

    success: bool
    restored_records: int
    skipped_records: int
    errors: list[str]
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "restored_records": self.restored_records,
            "skipped_records": self.skipped_records,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
        }


class BackupRecoveryService:
    """Service for backup and recovery operations.

    Features:
    - Create backups
    - Restore from backups
    - Export/import data
    - Backup scheduling
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Backup Operations
    # ========================================================================

    async def create_backup(
        self,
        backup_type: BackupType = BackupType.FULL,
        compress: bool = True,
    ) -> BackupMetadata:
        """Create a backup.

        Args:
            backup_type: Type of backup
            compress: Whether to compress

        Returns:
            BackupMetadata
        """
        from app.storage.redis import get_redis
        from uuid import uuid4

        redis = await get_redis()
        now = datetime.now(UTC)
        backup_id = str(uuid4())

        metadata = BackupMetadata(
            id=backup_id,
            backup_type=backup_type,
            status=BackupStatus.IN_PROGRESS,
            created_at=now,
            completed_at=None,
            size_bytes=0,
            record_count=0,
            filename=None,
        )

        # Store initial metadata
        await redis.set(
            f"backup:{backup_id}",
            json.dumps(metadata.to_dict()),
            ex=86400 * 30,
        )

        try:
            # Collect data based on type
            data = await self._collect_backup_data(backup_type)

            # Serialize
            json_data = json.dumps(data, default=str)

            if compress:
                backup_bytes = gzip.compress(json_data.encode())
                filename = f"backup_{backup_id}_{backup_type.value}.json.gz"
            else:
                backup_bytes = json_data.encode()
                filename = f"backup_{backup_id}_{backup_type.value}.json"

            # Store backup data
            await redis.set(
                f"backup:data:{backup_id}",
                backup_bytes,
                ex=86400 * 30,
            )

            # Update metadata
            metadata.status = BackupStatus.COMPLETED
            metadata.completed_at = datetime.now(UTC)
            metadata.size_bytes = len(backup_bytes)
            metadata.record_count = data.get("record_count", 0)
            metadata.filename = filename

            await redis.set(
                f"backup:{backup_id}",
                json.dumps(metadata.to_dict()),
                ex=86400 * 30,
            )

            # Add to backup list
            await redis.zadd("backups:list", {backup_id: now.timestamp()})
            await redis.expire("backups:list", 86400 * 30)

            logger.info(
                f"[Backup] Created | id={backup_id} | type={backup_type.value} | "
                f"records={metadata.record_count} | size={metadata.size_bytes}"
            )

        except Exception as e:
            metadata.status = BackupStatus.FAILED
            metadata.error = str(e)
            metadata.completed_at = datetime.now(UTC)

            await redis.set(
                f"backup:{backup_id}",
                json.dumps(metadata.to_dict()),
                ex=86400 * 7,
            )

            logger.error(f"[Backup] Failed | id={backup_id} | error={str(e)}")

        return metadata

    async def _collect_backup_data(
        self,
        backup_type: BackupType,
    ) -> dict[str, Any]:
        """Collect data for backup.

        Args:
            backup_type: Type of backup

        Returns:
            Backup data dict
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        data = {
            "backup_type": backup_type.value,
            "created_at": datetime.now(UTC).isoformat(),
            "version": "1.0",
        }

        record_count = 0

        if backup_type in (BackupType.FULL, BackupType.LEADS):
            # Export leads
            leads = {}
            async for key in redis.scan_iter("lead:*"):
                if not key.startswith("lead:"):
                    continue
                value = await redis.get(key)
                if value:
                    leads[key] = value
                    record_count += 1
            data["leads"] = leads

        if backup_type in (BackupType.FULL, BackupType.DEALS):
            # Export deals
            deals = {}
            async for key in redis.scan_iter("deal:*"):
                value = await redis.get(key)
                if value:
                    deals[key] = value
                    record_count += 1
            data["deals"] = deals

        if backup_type in (BackupType.FULL, BackupType.CONFIG):
            # Export config
            configs = {}
            async for key in redis.scan_iter("config:*"):
                value = await redis.get(key)
                if value:
                    configs[key] = value
                    record_count += 1
            data["configs"] = configs

            # Export manager configs
            manager_configs = {}
            async for key in redis.scan_iter("manager:config:*"):
                value = await redis.get(key)
                if value:
                    manager_configs[key] = value
                    record_count += 1
            data["manager_configs"] = manager_configs

        if backup_type == BackupType.AUDIT:
            # Export recent audit logs
            audit_ids = await redis.zrevrange("audit:timeline", 0, 10000)
            audits = {}
            for audit_id in audit_ids:
                value = await redis.get(f"audit:{audit_id}")
                if value:
                    audits[audit_id] = value
                    record_count += 1
            data["audits"] = audits

        data["record_count"] = record_count
        return data

    async def restore_backup(
        self,
        backup_id: str,
        overwrite: bool = False,
    ) -> RestoreResult:
        """Restore from a backup.

        Args:
            backup_id: Backup ID
            overwrite: Whether to overwrite existing data

        Returns:
            RestoreResult
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        start_time = datetime.now(UTC)

        restored = 0
        skipped = 0
        errors = []

        try:
            # Get backup data
            backup_bytes = await redis.get(f"backup:data:{backup_id}")
            if not backup_bytes:
                return RestoreResult(
                    success=False,
                    restored_records=0,
                    skipped_records=0,
                    errors=["Backup not found"],
                    duration_seconds=0,
                )

            # Decompress if needed
            try:
                json_data = gzip.decompress(backup_bytes).decode()
            except (gzip.BadGzipFile, OSError, UnicodeDecodeError):
                # Not gzip compressed, treat as raw JSON
                json_data = backup_bytes.decode() if isinstance(backup_bytes, bytes) else backup_bytes

            data = json.loads(json_data)

            # Restore leads
            if "leads" in data:
                for key, value in data["leads"].items():
                    if not overwrite:
                        exists = await redis.exists(key)
                        if exists:
                            skipped += 1
                            continue
                    await redis.set(key, value, ex=86400 * 365)
                    restored += 1

            # Restore deals
            if "deals" in data:
                for key, value in data["deals"].items():
                    if not overwrite:
                        exists = await redis.exists(key)
                        if exists:
                            skipped += 1
                            continue
                    await redis.set(key, value, ex=86400 * 365)
                    restored += 1

            # Restore configs
            if "configs" in data:
                for key, value in data["configs"].items():
                    await redis.set(key, value, ex=86400 * 365)
                    restored += 1

            if "manager_configs" in data:
                for key, value in data["manager_configs"].items():
                    await redis.set(key, value, ex=86400 * 365)
                    restored += 1

            logger.info(
                f"[Backup] Restored | id={backup_id} | "
                f"restored={restored} | skipped={skipped}"
            )

        except Exception as e:
            errors.append(str(e))
            logger.error(f"[Backup] Restore failed | id={backup_id} | error={str(e)}")

        duration = (datetime.now(UTC) - start_time).total_seconds()

        return RestoreResult(
            success=len(errors) == 0,
            restored_records=restored,
            skipped_records=skipped,
            errors=errors,
            duration_seconds=duration,
        )

    async def get_backup(self, backup_id: str) -> BackupMetadata | None:
        """Get backup metadata.

        Args:
            backup_id: Backup ID

        Returns:
            BackupMetadata or None
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        data = await redis.get(f"backup:{backup_id}")

        if not data:
            return None

        d = json.loads(data)
        return BackupMetadata(
            id=d["id"],
            backup_type=BackupType(d["backup_type"]),
            status=BackupStatus(d["status"]),
            created_at=datetime.fromisoformat(d["created_at"]),
            completed_at=datetime.fromisoformat(d["completed_at"]) if d.get("completed_at") else None,
            size_bytes=d["size_bytes"],
            record_count=d["record_count"],
            filename=d.get("filename"),
            error=d.get("error"),
            metadata=d.get("metadata", {}),
        )

    async def list_backups(
        self,
        limit: int = 20,
    ) -> list[BackupMetadata]:
        """List recent backups.

        Args:
            limit: Max results

        Returns:
            List of backups
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        backup_ids = await redis.zrevrange("backups:list", 0, limit - 1)

        backups = []
        for backup_id in backup_ids:
            backup = await self.get_backup(backup_id)
            if backup:
                backups.append(backup)

        return backups

    async def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup.

        Args:
            backup_id: Backup ID

        Returns:
            True if deleted
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        exists = await redis.exists(f"backup:{backup_id}")
        if not exists:
            return False

        await redis.delete(f"backup:{backup_id}")
        await redis.delete(f"backup:data:{backup_id}")
        await redis.zrem("backups:list", backup_id)

        logger.info(f"[Backup] Deleted | id={backup_id}")
        return True

    # ========================================================================
    # Export/Import
    # ========================================================================

    async def export_leads(
        self,
        lead_ids: list[str] | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Export leads to JSON.

        Args:
            lead_ids: Specific lead IDs
            status: Filter by status

        Returns:
            Export data
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        leads = []

        if lead_ids:
            for lead_id in lead_ids:
                data = await redis.get(f"lead:{lead_id}")
                if data:
                    lead = json.loads(data)
                    if status and lead.get("status") != status:
                        continue
                    leads.append(lead)
        else:
            async for key in redis.scan_iter("lead:*"):
                data = await redis.get(key)
                if data:
                    lead = json.loads(data)
                    if status and lead.get("status") != status:
                        continue
                    leads.append(lead)

        return {
            "exported_at": datetime.now(UTC).isoformat(),
            "count": len(leads),
            "leads": leads,
        }

    async def import_leads(
        self,
        data: dict[str, Any],
        skip_existing: bool = True,
    ) -> dict[str, Any]:
        """Import leads from JSON.

        Args:
            data: Import data
            skip_existing: Skip if lead exists

        Returns:
            Import result
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        imported = 0
        skipped = 0
        errors = []

        leads = data.get("leads", [])

        for lead in leads:
            try:
                lead_id = lead.get("id")
                if not lead_id:
                    errors.append("Lead missing ID")
                    continue

                if skip_existing:
                    exists = await redis.exists(f"lead:{lead_id}")
                    if exists:
                        skipped += 1
                        continue

                await redis.set(
                    f"lead:{lead_id}",
                    json.dumps(lead),
                    ex=86400 * 365,
                )
                imported += 1

            except Exception as e:
                errors.append(f"Error importing lead: {str(e)}")

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:10],  # Limit errors
            "total_errors": len(errors),
        }


# Singleton
backup_service = BackupRecoveryService()
