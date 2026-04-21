"""Immutable Operations Journal.

Append-only journal for critical admin actions with tamper detection.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

UTC = timezone.utc

logger = logging.getLogger(__name__)


class JournalSeverity(str, Enum):
    """Journal entry severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class JournalCategory(str, Enum):
    """Journal entry categories."""

    MAINTENANCE = "maintenance"
    SECURITY = "security"
    DATA = "data"
    CONFIG = "config"
    OVERRIDE = "override"
    RECOVERY = "recovery"
    SYSTEM = "system"


@dataclass
class JournalEntry:
    """Immutable journal entry."""

    id: str
    sequence: int
    timestamp: datetime
    action: str
    category: JournalCategory
    severity: JournalSeverity
    actor: str
    details: dict[str, Any]
    previous_hash: str
    entry_hash: str
    signature: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sequence": self.sequence,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "category": self.category.value,
            "severity": self.severity.value,
            "actor": self.actor,
            "details": self.details,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JournalEntry":
        return cls(
            id=data["id"],
            sequence=data["sequence"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action=data["action"],
            category=JournalCategory(data["category"]),
            severity=JournalSeverity(data["severity"]),
            actor=data["actor"],
            details=data["details"],
            previous_hash=data["previous_hash"],
            entry_hash=data["entry_hash"],
            signature=data.get("signature"),
        )


@dataclass
class JournalIntegrity:
    """Journal integrity verification result."""

    valid: bool
    total_entries: int
    verified_entries: int
    first_invalid_sequence: int | None
    chain_broken_at: int | None
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "total_entries": self.total_entries,
            "verified_entries": self.verified_entries,
            "first_invalid_sequence": self.first_invalid_sequence,
            "chain_broken_at": self.chain_broken_at,
            "issues": self.issues,
        }


# Action to category mapping
ACTION_CATEGORIES = {
    "enter_maintenance": JournalCategory.MAINTENANCE,
    "exit_maintenance": JournalCategory.MAINTENANCE,
    "schedule_maintenance": JournalCategory.MAINTENANCE,
    "backup_create": JournalCategory.DATA,
    "backup_restore": JournalCategory.DATA,
    "data_delete": JournalCategory.DATA,
    "data_archive": JournalCategory.DATA,
    "retention_apply": JournalCategory.DATA,
    "config_change": JournalCategory.CONFIG,
    "secret_rotate": JournalCategory.CONFIG,
    "status_override": JournalCategory.OVERRIDE,
    "score_override": JournalCategory.OVERRIDE,
    "force_transition": JournalCategory.OVERRIDE,
    "job_retry": JournalCategory.RECOVERY,
    "job_cancel": JournalCategory.RECOVERY,
    "runbook_execute": JournalCategory.RECOVERY,
    "ip_block": JournalCategory.SECURITY,
    "ip_unblock": JournalCategory.SECURITY,
    "rate_limit_change": JournalCategory.SECURITY,
    "permission_change": JournalCategory.SECURITY,
    "system_start": JournalCategory.SYSTEM,
    "system_stop": JournalCategory.SYSTEM,
    "worker_restart": JournalCategory.SYSTEM,
}


class OpsJournalService:
    """Service for immutable operations journal.

    Features:
    - Append-only entries
    - Hash chain for tamper detection
    - Severity-based categorization
    - Integrity verification
    - Searchable by time, actor, action
    """

    JOURNAL_KEY = "ops:journal:entries"
    SEQUENCE_KEY = "ops:journal:sequence"
    LAST_HASH_KEY = "ops:journal:last_hash"
    GENESIS_HASH = "0" * 64  # Genesis block hash

    def __init__(self) -> None:
        """Initialize service."""
        pass

    def _compute_hash(
        self,
        sequence: int,
        timestamp: datetime,
        action: str,
        actor: str,
        details: dict[str, Any],
        previous_hash: str,
    ) -> str:
        """Compute entry hash.

        Args:
            sequence: Entry sequence number
            timestamp: Entry timestamp
            action: Action name
            actor: Who performed action
            details: Action details
            previous_hash: Previous entry hash

        Returns:
            SHA256 hash
        """
        content = json.dumps(
            {
                "sequence": sequence,
                "timestamp": timestamp.isoformat(),
                "action": action,
                "actor": actor,
                "details": details,
                "previous_hash": previous_hash,
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    async def record(
        self,
        action: str,
        actor: str,
        details: dict[str, Any] | None = None,
        severity: str = "info",
        category: str | None = None,
    ) -> JournalEntry:
        """Record an action in the journal.

        Args:
            action: Action name
            actor: Who performed action
            details: Action details
            severity: Severity level
            category: Optional category override

        Returns:
            Created journal entry
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        # Atomic sequence increment
        sequence = await redis.incr(self.SEQUENCE_KEY)

        # Get previous hash
        previous_hash = await redis.get(self.LAST_HASH_KEY) or self.GENESIS_HASH

        # Determine category
        if category:
            cat = JournalCategory(category)
        else:
            cat = ACTION_CATEGORIES.get(action, JournalCategory.SYSTEM)

        # Compute hash
        entry_hash = self._compute_hash(
            sequence=sequence,
            timestamp=now,
            action=action,
            actor=actor,
            details=details or {},
            previous_hash=previous_hash,
        )

        # Create entry
        entry = JournalEntry(
            id=str(uuid.uuid4()),
            sequence=sequence,
            timestamp=now,
            action=action,
            category=cat,
            severity=JournalSeverity(severity),
            actor=actor,
            details=details or {},
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )

        # Store entry
        await redis.zadd(
            self.JOURNAL_KEY,
            {json.dumps(entry.to_dict()): sequence},
        )

        # Update last hash
        await redis.set(self.LAST_HASH_KEY, entry_hash)

        logger.info(
            f"[OpsJournal] #{sequence} {action} by {actor} [{severity}]"
        )

        return entry

    async def get_entries(
        self,
        start_sequence: int | None = None,
        end_sequence: int | None = None,
        limit: int = 100,
        actor: str | None = None,
        action: str | None = None,
        category: JournalCategory | None = None,
        severity: JournalSeverity | None = None,
    ) -> list[JournalEntry]:
        """Get journal entries with filtering.

        Args:
            start_sequence: Start sequence (inclusive)
            end_sequence: End sequence (inclusive)
            limit: Max entries
            actor: Filter by actor
            action: Filter by action
            category: Filter by category
            severity: Filter by severity

        Returns:
            List of journal entries
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        min_score = start_sequence if start_sequence else "-inf"
        max_score = end_sequence if end_sequence else "+inf"

        raw = await redis.zrevrangebyscore(
            self.JOURNAL_KEY,
            max_score,
            min_score,
            start=0,
            num=limit * 2,  # Get extra for filtering
        )

        entries = []
        for item in raw:
            try:
                data = json.loads(item)
                entry = JournalEntry.from_dict(data)

                # Apply filters
                if actor and entry.actor != actor:
                    continue
                if action and entry.action != action:
                    continue
                if category and entry.category != category:
                    continue
                if severity and entry.severity != severity:
                    continue

                entries.append(entry)

                if len(entries) >= limit:
                    break
            except Exception as e:
                logger.error(f"[OpsJournal] Failed to parse entry: {e}")

        return entries

    async def get_entry(self, entry_id: str) -> JournalEntry | None:
        """Get entry by ID.

        Args:
            entry_id: Entry ID

        Returns:
            Entry if found
        """
        entries = await self.get_entries(limit=1000)
        for entry in entries:
            if entry.id == entry_id:
                return entry
        return None

    async def verify_integrity(self) -> JournalIntegrity:
        """Verify journal integrity.

        Returns:
            Integrity verification result
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Get all entries in order
        raw = await redis.zrangebyscore(
            self.JOURNAL_KEY,
            "-inf",
            "+inf",
        )

        if not raw:
            return JournalIntegrity(
                valid=True,
                total_entries=0,
                verified_entries=0,
                first_invalid_sequence=None,
                chain_broken_at=None,
                issues=[],
            )

        issues = []
        verified = 0
        first_invalid = None
        chain_broken = None
        expected_hash = self.GENESIS_HASH

        for item in raw:
            try:
                data = json.loads(item)
                entry = JournalEntry.from_dict(data)

                # Verify hash chain
                if entry.previous_hash != expected_hash:
                    if chain_broken is None:
                        chain_broken = entry.sequence
                    issues.append(
                        f"Chain broken at #{entry.sequence}: "
                        f"expected {expected_hash[:8]}..., "
                        f"got {entry.previous_hash[:8]}..."
                    )

                # Verify entry hash
                computed = self._compute_hash(
                    sequence=entry.sequence,
                    timestamp=entry.timestamp,
                    action=entry.action,
                    actor=entry.actor,
                    details=entry.details,
                    previous_hash=entry.previous_hash,
                )

                if computed != entry.entry_hash:
                    if first_invalid is None:
                        first_invalid = entry.sequence
                    issues.append(
                        f"Invalid hash at #{entry.sequence}: "
                        f"computed {computed[:8]}..., "
                        f"stored {entry.entry_hash[:8]}..."
                    )
                else:
                    verified += 1

                expected_hash = entry.entry_hash

            except Exception as e:
                issues.append(f"Parse error: {e}")

        return JournalIntegrity(
            valid=len(issues) == 0,
            total_entries=len(raw),
            verified_entries=verified,
            first_invalid_sequence=first_invalid,
            chain_broken_at=chain_broken,
            issues=issues,
        )

    async def get_stats(self) -> dict[str, Any]:
        """Get journal statistics.

        Returns:
            Journal statistics
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        total = await redis.zcard(self.JOURNAL_KEY)
        last_sequence = int(await redis.get(self.SEQUENCE_KEY) or 0)
        last_hash = await redis.get(self.LAST_HASH_KEY)

        # Count by category
        entries = await self.get_entries(limit=1000)
        by_category = {}
        by_severity = {}
        by_actor = {}

        for entry in entries:
            by_category[entry.category.value] = (
                by_category.get(entry.category.value, 0) + 1
            )
            by_severity[entry.severity.value] = (
                by_severity.get(entry.severity.value, 0) + 1
            )
            by_actor[entry.actor] = by_actor.get(entry.actor, 0) + 1

        return {
            "total_entries": total,
            "last_sequence": last_sequence,
            "last_hash": last_hash[:16] + "..." if last_hash else None,
            "by_category": by_category,
            "by_severity": by_severity,
            "by_actor": by_actor,
        }

    async def export_entries(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Export journal entries for audit.

        Args:
            start_date: Start date filter
            end_date: End date filter

        Returns:
            List of entry dicts
        """
        entries = await self.get_entries(limit=10000)

        result = []
        for entry in entries:
            if start_date and entry.timestamp < start_date:
                continue
            if end_date and entry.timestamp > end_date:
                continue
            result.append(entry.to_dict())

        return result


# Singleton
ops_journal = OpsJournalService()
