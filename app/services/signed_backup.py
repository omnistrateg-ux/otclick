"""Signed Backup/Restore Service.

Cryptographic verification of backups.
"""

import logging
import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid
import base64

UTC = timezone.utc

logger = logging.getLogger(__name__)


class BackupType(str, Enum):
    """Types of backups."""

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"


class BackupStatus(str, Enum):
    """Backup status."""

    CREATING = "creating"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    CORRUPTED = "corrupted"
    RESTORING = "restoring"
    RESTORED = "restored"


class BackupTarget(str, Enum):
    """Backup target types."""

    DATABASE = "database"
    REDIS = "redis"
    CONFIG = "config"
    FILES = "files"
    FULL_SYSTEM = "full_system"


@dataclass
class BackupSignature:
    """Cryptographic signature for backup."""

    algorithm: str
    signature: str
    checksum: str
    signed_at: datetime
    signed_by: str
    public_key_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "signature": self.signature,
            "checksum": self.checksum,
            "signed_at": self.signed_at.isoformat(),
            "signed_by": self.signed_by,
            "public_key_id": self.public_key_id,
        }


@dataclass
class BackupManifest:
    """Backup manifest with metadata."""

    id: str
    backup_type: BackupType
    target: BackupTarget
    status: BackupStatus
    created_at: datetime
    created_by: str
    size_bytes: int
    file_count: int
    checksum: str
    signature: BackupSignature | None
    metadata: dict[str, Any]
    parent_backup_id: str | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    restore_point: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "backup_type": self.backup_type.value,
            "target": self.target.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "size_bytes": self.size_bytes,
            "file_count": self.file_count,
            "checksum": self.checksum,
            "signature": self.signature.to_dict() if self.signature else None,
            "metadata": self.metadata,
            "parent_backup_id": self.parent_backup_id,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "restore_point": self.restore_point,
        }


@dataclass
class RestoreOperation:
    """Restore operation record."""

    id: str
    backup_id: str
    target: BackupTarget
    status: BackupStatus
    started_at: datetime
    started_by: str
    completed_at: datetime | None = None
    verification_passed: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "backup_id": self.backup_id,
            "target": self.target.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "started_by": self.started_by,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "verification_passed": self.verification_passed,
            "error": self.error,
        }


class SignedBackupService:
    """Service for signed backup/restore operations.

    Features:
    - Create backups with signatures
    - Verify backup integrity
    - Restore with verification
    - Chain of custody tracking
    """

    BACKUPS_KEY = "backups:manifests"
    RESTORES_KEY = "backups:restores"
    SIGNING_KEY = "backups:signing_key"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    async def _get_signing_key(self) -> bytes:
        """Get or create signing key.

        In production, this would use a proper key management system.
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        key = await redis.get(self.SIGNING_KEY)
        if key:
            return base64.b64decode(key)

        # Generate new key (in production, use proper KMS)
        import secrets
        new_key = secrets.token_bytes(32)
        await redis.set(self.SIGNING_KEY, base64.b64encode(new_key).decode())

        return new_key

    def _compute_checksum(self, data: bytes) -> str:
        """Compute SHA-256 checksum."""
        return hashlib.sha256(data).hexdigest()

    def _sign_data(
        self,
        data: bytes,
        key: bytes,
    ) -> str:
        """Sign data with HMAC-SHA256."""
        signature = hmac.new(key, data, hashlib.sha256)
        return base64.b64encode(signature.digest()).decode()

    def _verify_signature(
        self,
        data: bytes,
        signature: str,
        key: bytes,
    ) -> bool:
        """Verify HMAC signature."""
        expected = hmac.new(key, data, hashlib.sha256)
        expected_sig = base64.b64encode(expected.digest()).decode()
        return hmac.compare_digest(signature, expected_sig)

    async def create_backup(
        self,
        target: BackupTarget,
        created_by: str,
        backup_type: BackupType = BackupType.FULL,
        metadata: dict[str, Any] | None = None,
        parent_backup_id: str | None = None,
    ) -> BackupManifest:
        """Create a new backup with signature.

        Args:
            target: What to backup
            created_by: Who initiated
            backup_type: Type of backup
            metadata: Additional metadata
            parent_backup_id: Parent for incremental

        Returns:
            Backup manifest
        """
        from app.storage.redis import get_redis
        from datetime import timedelta
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        backup_id = str(uuid.uuid4())[:12]

        # Simulate backup data collection
        # In production, this would actually collect the data
        simulated_data = json.dumps({
            "backup_id": backup_id,
            "target": target.value,
            "timestamp": now.isoformat(),
            "metadata": metadata or {},
        }).encode()

        # Compute checksum
        checksum = self._compute_checksum(simulated_data)

        # Sign the backup
        signing_key = await self._get_signing_key()
        signature_value = self._sign_data(simulated_data, signing_key)

        signature = BackupSignature(
            algorithm="HMAC-SHA256",
            signature=signature_value,
            checksum=checksum,
            signed_at=now,
            signed_by="system",
            public_key_id=None,
        )

        manifest = BackupManifest(
            id=backup_id,
            backup_type=backup_type,
            target=target,
            status=BackupStatus.VERIFIED,
            created_at=now,
            created_by=created_by,
            size_bytes=len(simulated_data),
            file_count=1,
            checksum=checksum,
            signature=signature,
            metadata=metadata or {},
            parent_backup_id=parent_backup_id,
            completed_at=now,
            expires_at=now + timedelta(days=30),
            restore_point=f"{target.value}:{now.isoformat()}",
        )

        # Store manifest
        await redis.hset(
            self.BACKUPS_KEY,
            backup_id,
            json.dumps(manifest.to_dict()),
        )

        # Store backup data (in production, would go to object storage)
        await redis.set(
            f"backup:data:{backup_id}",
            simulated_data,
            ex=30 * 24 * 3600,  # 30 days
        )

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="backup_created",
                actor=created_by,
                details={
                    "backup_id": backup_id,
                    "target": target.value,
                    "type": backup_type.value,
                    "size_bytes": len(simulated_data),
                },
                severity="info",
            )
        except Exception:
            pass

        logger.info(f"[SignedBackup] Created backup {backup_id} for {target.value}")

        return manifest

    async def verify_backup(
        self,
        backup_id: str,
    ) -> tuple[bool, str]:
        """Verify backup integrity.

        Args:
            backup_id: Backup ID

        Returns:
            (valid, message) tuple
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Get manifest
        manifest = await self.get_backup(backup_id)
        if not manifest:
            return False, "Backup not found"

        if not manifest.signature:
            return False, "Backup has no signature"

        # Get backup data
        data = await redis.get(f"backup:data:{backup_id}")
        if not data:
            return False, "Backup data not found"

        if isinstance(data, str):
            data = data.encode()

        # Verify checksum
        computed_checksum = self._compute_checksum(data)
        if computed_checksum != manifest.checksum:
            # Update status
            manifest.status = BackupStatus.CORRUPTED
            await redis.hset(
                self.BACKUPS_KEY,
                backup_id,
                json.dumps(manifest.to_dict()),
            )
            return False, f"Checksum mismatch: expected {manifest.checksum}, got {computed_checksum}"

        # Verify signature
        signing_key = await self._get_signing_key()
        if not self._verify_signature(data, manifest.signature.signature, signing_key):
            manifest.status = BackupStatus.CORRUPTED
            await redis.hset(
                self.BACKUPS_KEY,
                backup_id,
                json.dumps(manifest.to_dict()),
            )
            return False, "Signature verification failed"

        logger.info(f"[SignedBackup] Backup {backup_id} verified successfully")

        return True, "Backup verified successfully"

    async def restore_backup(
        self,
        backup_id: str,
        restored_by: str,
        verify_first: bool = True,
    ) -> RestoreOperation:
        """Restore from backup.

        Args:
            backup_id: Backup ID
            restored_by: Who is restoring
            verify_first: Verify before restore

        Returns:
            Restore operation

        Raises:
            ValueError: If verification fails
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        manifest = await self.get_backup(backup_id)
        if not manifest:
            raise ValueError("Backup not found")

        operation = RestoreOperation(
            id=str(uuid.uuid4())[:8],
            backup_id=backup_id,
            target=manifest.target,
            status=BackupStatus.RESTORING,
            started_at=now,
            started_by=restored_by,
        )

        # Verify if required
        if verify_first:
            valid, message = await self.verify_backup(backup_id)
            if not valid:
                operation.status = BackupStatus.FAILED
                operation.error = f"Verification failed: {message}"
                operation.completed_at = datetime.now(UTC)

                await redis.lpush(
                    self.RESTORES_KEY,
                    json.dumps(operation.to_dict()),
                )

                raise ValueError(message)

            operation.verification_passed = True

        # Simulate restore (in production, would actually restore data)
        # ...

        operation.status = BackupStatus.RESTORED
        operation.completed_at = datetime.now(UTC)

        # Store operation
        await redis.lpush(
            self.RESTORES_KEY,
            json.dumps(operation.to_dict()),
        )

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="backup_restored",
                actor=restored_by,
                details={
                    "backup_id": backup_id,
                    "restore_id": operation.id,
                    "target": manifest.target.value,
                    "verification_passed": operation.verification_passed,
                },
                severity="warning",
            )
        except Exception:
            pass

        logger.info(f"[SignedBackup] Restored backup {backup_id}")

        return operation

    async def get_backup(self, backup_id: str) -> BackupManifest | None:
        """Get backup manifest.

        Args:
            backup_id: Backup ID

        Returns:
            Manifest or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hget(self.BACKUPS_KEY, backup_id)
        if not raw:
            return None

        data = json.loads(raw)

        signature = None
        if data.get("signature"):
            sig_data = data["signature"]
            signature = BackupSignature(
                algorithm=sig_data["algorithm"],
                signature=sig_data["signature"],
                checksum=sig_data["checksum"],
                signed_at=datetime.fromisoformat(sig_data["signed_at"]),
                signed_by=sig_data["signed_by"],
                public_key_id=sig_data.get("public_key_id"),
            )

        return BackupManifest(
            id=data["id"],
            backup_type=BackupType(data["backup_type"]),
            target=BackupTarget(data["target"]),
            status=BackupStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by=data["created_by"],
            size_bytes=data["size_bytes"],
            file_count=data["file_count"],
            checksum=data["checksum"],
            signature=signature,
            metadata=data.get("metadata", {}),
            parent_backup_id=data.get("parent_backup_id"),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            restore_point=data.get("restore_point"),
        )

    async def list_backups(
        self,
        target: BackupTarget | None = None,
        limit: int = 50,
    ) -> list[BackupManifest]:
        """List backups.

        Args:
            target: Filter by target
            limit: Max results

        Returns:
            List of manifests
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.hgetall(self.BACKUPS_KEY)
        backups = []

        for data_str in raw.values():
            try:
                data = json.loads(data_str)

                if target and data["target"] != target.value:
                    continue

                signature = None
                if data.get("signature"):
                    sig_data = data["signature"]
                    signature = BackupSignature(
                        algorithm=sig_data["algorithm"],
                        signature=sig_data["signature"],
                        checksum=sig_data["checksum"],
                        signed_at=datetime.fromisoformat(sig_data["signed_at"]),
                        signed_by=sig_data["signed_by"],
                        public_key_id=sig_data.get("public_key_id"),
                    )

                backups.append(BackupManifest(
                    id=data["id"],
                    backup_type=BackupType(data["backup_type"]),
                    target=BackupTarget(data["target"]),
                    status=BackupStatus(data["status"]),
                    created_at=datetime.fromisoformat(data["created_at"]),
                    created_by=data["created_by"],
                    size_bytes=data["size_bytes"],
                    file_count=data["file_count"],
                    checksum=data["checksum"],
                    signature=signature,
                    metadata=data.get("metadata", {}),
                    parent_backup_id=data.get("parent_backup_id"),
                    completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
                    expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
                    restore_point=data.get("restore_point"),
                ))
            except Exception:
                continue

        # Sort by created_at (newest first)
        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups[:limit]

    async def delete_backup(
        self,
        backup_id: str,
        deleted_by: str,
    ) -> bool:
        """Delete a backup.

        Args:
            backup_id: Backup ID
            deleted_by: Who deleted

        Returns:
            True if deleted
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Get backup first
        manifest = await self.get_backup(backup_id)
        if not manifest:
            return False

        # Delete manifest and data
        await redis.hdel(self.BACKUPS_KEY, backup_id)
        await redis.delete(f"backup:data:{backup_id}")

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="backup_deleted",
                actor=deleted_by,
                details={
                    "backup_id": backup_id,
                    "target": manifest.target.value,
                },
                severity="warning",
            )
        except Exception:
            pass

        logger.info(f"[SignedBackup] Deleted backup {backup_id}")

        return True

    async def get_restore_history(
        self,
        limit: int = 50,
    ) -> list[RestoreOperation]:
        """Get restore operation history.

        Args:
            limit: Max results

        Returns:
            List of operations
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.lrange(self.RESTORES_KEY, 0, limit - 1)
        operations = []

        for item in raw:
            try:
                data = json.loads(item)
                operations.append(RestoreOperation(
                    id=data["id"],
                    backup_id=data["backup_id"],
                    target=BackupTarget(data["target"]),
                    status=BackupStatus(data["status"]),
                    started_at=datetime.fromisoformat(data["started_at"]),
                    started_by=data["started_by"],
                    completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
                    verification_passed=data.get("verification_passed", False),
                    error=data.get("error"),
                ))
            except Exception:
                continue

        return operations


# Singleton
signed_backup = SignedBackupService()
