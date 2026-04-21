"""Data Retention and Cleanup Service.

TTL management, data purging, and archival.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class DataCategory(str, Enum):
    """Categories of data for retention."""

    LEADS = "leads"
    DEALS = "deals"
    HANDOFFS = "handoffs"
    EMAILS = "emails"
    AUDIT_LOGS = "audit_logs"
    SECURITY_EVENTS = "security_events"
    METRICS = "metrics"
    BACKUPS = "backups"
    TEMP_DATA = "temp_data"


class RetentionAction(str, Enum):
    """What to do with expired data."""

    DELETE = "delete"
    ARCHIVE = "archive"
    ANONYMIZE = "anonymize"


@dataclass
class RetentionPolicy:
    """Data retention policy."""

    category: DataCategory
    retention_days: int
    action: RetentionAction
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "retention_days": self.retention_days,
            "action": self.action.value,
            "enabled": self.enabled,
            "description": self.description,
        }


@dataclass
class RetentionReport:
    """Report from a retention run."""

    run_id: str
    started_at: datetime
    completed_at: datetime
    policies_applied: int
    records_processed: int
    records_deleted: int
    records_archived: int
    records_anonymized: int
    errors: list[str]
    by_category: dict[str, dict[str, int]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "policies_applied": self.policies_applied,
            "records_processed": self.records_processed,
            "records_deleted": self.records_deleted,
            "records_archived": self.records_archived,
            "records_anonymized": self.records_anonymized,
            "errors": self.errors,
            "by_category": self.by_category,
        }


# Default retention policies
DEFAULT_POLICIES = [
    RetentionPolicy(
        category=DataCategory.AUDIT_LOGS,
        retention_days=365,
        action=RetentionAction.DELETE,
        description="Audit logs older than 1 year",
    ),
    RetentionPolicy(
        category=DataCategory.SECURITY_EVENTS,
        retention_days=90,
        action=RetentionAction.DELETE,
        description="Security events older than 90 days",
    ),
    RetentionPolicy(
        category=DataCategory.METRICS,
        retention_days=30,
        action=RetentionAction.DELETE,
        description="Daily metrics older than 30 days",
    ),
    RetentionPolicy(
        category=DataCategory.BACKUPS,
        retention_days=30,
        action=RetentionAction.DELETE,
        description="Backups older than 30 days",
    ),
    RetentionPolicy(
        category=DataCategory.TEMP_DATA,
        retention_days=1,
        action=RetentionAction.DELETE,
        description="Temporary data older than 1 day",
    ),
    RetentionPolicy(
        category=DataCategory.EMAILS,
        retention_days=180,
        action=RetentionAction.ANONYMIZE,
        description="Email content anonymized after 180 days",
    ),
]


class DataRetentionService:
    """Service for data retention and cleanup.

    Features:
    - Configurable retention policies
    - Automatic cleanup
    - Data anonymization
    - Retention reports
    """

    def __init__(self) -> None:
        """Initialize service."""
        self._policies: dict[DataCategory, RetentionPolicy] = {}
        self._load_default_policies()

    def _load_default_policies(self) -> None:
        """Load default retention policies."""
        for policy in DEFAULT_POLICIES:
            self._policies[policy.category] = policy

    # ========================================================================
    # Policy Management
    # ========================================================================

    def get_policy(self, category: DataCategory) -> RetentionPolicy | None:
        """Get retention policy for category.

        Args:
            category: Data category

        Returns:
            RetentionPolicy or None
        """
        return self._policies.get(category)

    def get_all_policies(self) -> list[RetentionPolicy]:
        """Get all retention policies.

        Returns:
            List of policies
        """
        return list(self._policies.values())

    async def update_policy(
        self,
        category: DataCategory,
        retention_days: int | None = None,
        action: RetentionAction | None = None,
        enabled: bool | None = None,
    ) -> RetentionPolicy:
        """Update a retention policy.

        Args:
            category: Category to update
            retention_days: New retention period
            action: New retention action
            enabled: Enable/disable

        Returns:
            Updated policy
        """
        from app.storage.redis import get_redis
        import json

        policy = self._policies.get(category)
        if not policy:
            policy = RetentionPolicy(
                category=category,
                retention_days=retention_days or 90,
                action=action or RetentionAction.DELETE,
            )

        if retention_days is not None:
            policy.retention_days = retention_days
        if action is not None:
            policy.action = action
        if enabled is not None:
            policy.enabled = enabled

        self._policies[category] = policy

        # Persist to Redis
        redis = await get_redis()
        await redis.set(
            f"retention:policy:{category.value}",
            json.dumps(policy.to_dict()),
            ex=86400 * 365,
        )

        logger.info(
            f"[Retention] Policy updated | category={category.value} | "
            f"days={policy.retention_days} | action={policy.action.value}"
        )

        return policy

    # ========================================================================
    # Retention Execution
    # ========================================================================

    async def run_retention(
        self,
        categories: list[DataCategory] | None = None,
        dry_run: bool = False,
    ) -> RetentionReport:
        """Run retention for specified categories.

        Args:
            categories: Categories to process (all if None)
            dry_run: Don't actually delete

        Returns:
            RetentionReport
        """
        from uuid import uuid4

        run_id = str(uuid4())
        started_at = datetime.now(UTC)

        if categories is None:
            categories = list(self._policies.keys())

        records_processed = 0
        records_deleted = 0
        records_archived = 0
        records_anonymized = 0
        errors = []
        by_category = {}
        policies_applied = 0

        for category in categories:
            policy = self._policies.get(category)
            if not policy or not policy.enabled:
                continue

            policies_applied += 1

            try:
                result = await self._apply_policy(policy, dry_run)

                by_category[category.value] = result
                records_processed += result["processed"]
                records_deleted += result["deleted"]
                records_archived += result["archived"]
                records_anonymized += result["anonymized"]

            except Exception as e:
                errors.append(f"{category.value}: {str(e)}")
                logger.error(f"[Retention] Error | category={category.value} | error={str(e)}")

        completed_at = datetime.now(UTC)

        report = RetentionReport(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            policies_applied=policies_applied,
            records_processed=records_processed,
            records_deleted=records_deleted,
            records_archived=records_archived,
            records_anonymized=records_anonymized,
            errors=errors,
            by_category=by_category,
        )

        # Store report
        await self._store_report(report)

        logger.info(
            f"[Retention] Run completed | run_id={run_id} | "
            f"processed={records_processed} | deleted={records_deleted} | "
            f"dry_run={dry_run}"
        )

        return report

    async def _apply_policy(
        self,
        policy: RetentionPolicy,
        dry_run: bool,
    ) -> dict[str, int]:
        """Apply a single retention policy.

        Args:
            policy: Policy to apply
            dry_run: Don't actually modify

        Returns:
            Result counts
        """
        cutoff = datetime.now(UTC) - timedelta(days=policy.retention_days)

        if policy.category == DataCategory.AUDIT_LOGS:
            return await self._cleanup_audit_logs(cutoff, policy.action, dry_run)
        elif policy.category == DataCategory.SECURITY_EVENTS:
            return await self._cleanup_security_events(cutoff, policy.action, dry_run)
        elif policy.category == DataCategory.METRICS:
            return await self._cleanup_metrics(cutoff, dry_run)
        elif policy.category == DataCategory.BACKUPS:
            return await self._cleanup_backups(cutoff, dry_run)
        elif policy.category == DataCategory.TEMP_DATA:
            return await self._cleanup_temp_data(cutoff, dry_run)
        elif policy.category == DataCategory.EMAILS:
            return await self._anonymize_emails(cutoff, dry_run)
        else:
            return {"processed": 0, "deleted": 0, "archived": 0, "anonymized": 0}

    async def _cleanup_audit_logs(
        self,
        cutoff: datetime,
        action: RetentionAction,
        dry_run: bool,
    ) -> dict[str, int]:
        """Clean up audit logs."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        old_entries = await redis.zrangebyscore(
            "audit:timeline",
            "-inf",
            cutoff.timestamp(),
        )

        processed = len(old_entries)
        deleted = 0

        if not dry_run and action == RetentionAction.DELETE:
            for entry_id in old_entries:
                await redis.delete(f"audit:{entry_id}")
                deleted += 1
            await redis.zremrangebyscore("audit:timeline", "-inf", cutoff.timestamp())

        return {"processed": processed, "deleted": deleted, "archived": 0, "anonymized": 0}

    async def _cleanup_security_events(
        self,
        cutoff: datetime,
        action: RetentionAction,
        dry_run: bool,
    ) -> dict[str, int]:
        """Clean up security events."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        old_events = await redis.zrangebyscore(
            "security:timeline",
            "-inf",
            cutoff.timestamp(),
        )

        processed = len(old_events)
        deleted = 0

        if not dry_run and action == RetentionAction.DELETE:
            for event_id in old_events:
                await redis.delete(f"security:event:{event_id}")
                deleted += 1
            await redis.zremrangebyscore("security:timeline", "-inf", cutoff.timestamp())

        return {"processed": processed, "deleted": deleted, "archived": 0, "anonymized": 0}

    async def _cleanup_metrics(
        self,
        cutoff: datetime,
        dry_run: bool,
    ) -> dict[str, int]:
        """Clean up old metrics."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        processed = 0
        deleted = 0

        # Find and delete old stats keys
        patterns = ["stats:daily:*", "sla:history:*", "job_stats:*"]

        for pattern in patterns:
            async for key in redis.scan_iter(pattern):
                # Extract date from key if possible
                parts = key.split(":")
                for part in parts:
                    if len(part) == 10 and part[4] == "-":  # YYYY-MM-DD
                        try:
                            key_date = datetime.strptime(part, "%Y-%m-%d").replace(tzinfo=UTC)
                            if key_date < cutoff:
                                processed += 1
                                if not dry_run:
                                    await redis.delete(key)
                                    deleted += 1
                        except ValueError:
                            # Part doesn't match date format, skip
                            pass
                        break

        return {"processed": processed, "deleted": deleted, "archived": 0, "anonymized": 0}

    async def _cleanup_backups(
        self,
        cutoff: datetime,
        dry_run: bool,
    ) -> dict[str, int]:
        """Clean up old backups."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        old_backups = await redis.zrangebyscore(
            "backups:list",
            "-inf",
            cutoff.timestamp(),
        )

        processed = len(old_backups)
        deleted = 0

        if not dry_run:
            for backup_id in old_backups:
                await redis.delete(f"backup:{backup_id}")
                await redis.delete(f"backup:data:{backup_id}")
                deleted += 1
            await redis.zremrangebyscore("backups:list", "-inf", cutoff.timestamp())

        return {"processed": processed, "deleted": deleted, "archived": 0, "anonymized": 0}

    async def _cleanup_temp_data(
        self,
        cutoff: datetime,
        dry_run: bool,
    ) -> dict[str, int]:
        """Clean up temporary data."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        processed = 0
        deleted = 0

        # Clean temp keys
        patterns = ["temp:*", "cache:*", "session:*"]

        for pattern in patterns:
            async for key in redis.scan_iter(pattern):
                processed += 1
                if not dry_run:
                    await redis.delete(key)
                    deleted += 1

        return {"processed": processed, "deleted": deleted, "archived": 0, "anonymized": 0}

    async def _anonymize_emails(
        self,
        cutoff: datetime,
        dry_run: bool,
    ) -> dict[str, int]:
        """Anonymize old email content."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        processed = 0
        anonymized = 0

        async for key in redis.scan_iter("email:*"):
            data = await redis.get(key)
            if not data:
                continue

            try:
                email = json.loads(data)
                sent_at = email.get("sent_at")

                if sent_at:
                    sent_date = datetime.fromisoformat(sent_at)
                    if sent_date < cutoff:
                        processed += 1

                        if not dry_run:
                            # Anonymize content
                            email["subject"] = "[REDACTED]"
                            email["body"] = "[REDACTED - Data retention policy]"
                            email["to_email"] = self._anonymize_email(email.get("to_email", ""))
                            email["anonymized_at"] = datetime.now(UTC).isoformat()

                            await redis.set(key, json.dumps(email))
                            anonymized += 1

            except Exception:
                continue

        return {"processed": processed, "deleted": 0, "archived": 0, "anonymized": anonymized}

    def _anonymize_email(self, email: str) -> str:
        """Anonymize an email address."""
        if not email or "@" not in email:
            return "[REDACTED]"

        local, domain = email.split("@", 1)
        return f"{local[:2]}***@{domain}"

    # ========================================================================
    # Reporting
    # ========================================================================

    async def _store_report(self, report: RetentionReport) -> None:
        """Store retention report."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        await redis.set(
            f"retention:report:{report.run_id}",
            json.dumps(report.to_dict()),
            ex=86400 * 90,
        )

        await redis.zadd(
            "retention:reports",
            {report.run_id: report.started_at.timestamp()},
        )
        await redis.expire("retention:reports", 86400 * 90)

    async def get_report(self, run_id: str) -> RetentionReport | None:
        """Get retention report by ID."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        data = await redis.get(f"retention:report:{run_id}")

        if not data:
            return None

        d = json.loads(data)
        return RetentionReport(
            run_id=d["run_id"],
            started_at=datetime.fromisoformat(d["started_at"]),
            completed_at=datetime.fromisoformat(d["completed_at"]),
            policies_applied=d["policies_applied"],
            records_processed=d["records_processed"],
            records_deleted=d["records_deleted"],
            records_archived=d["records_archived"],
            records_anonymized=d["records_anonymized"],
            errors=d["errors"],
            by_category=d["by_category"],
        )

    async def get_recent_reports(
        self,
        limit: int = 10,
    ) -> list[RetentionReport]:
        """Get recent retention reports.

        Args:
            limit: Max results

        Returns:
            List of reports
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        report_ids = await redis.zrevrange("retention:reports", 0, limit - 1)

        reports = []
        for run_id in report_ids:
            report = await self.get_report(run_id)
            if report:
                reports.append(report)

        return reports

    async def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics.

        Returns:
            Storage stats
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Get Redis info
        try:
            info = await redis.info("memory")
            used_memory = info.get("used_memory", 0)
            peak_memory = info.get("used_memory_peak", 0)
        except Exception as e:
            logger.debug(f"[Data Retention] Failed to get Redis memory info: {e}")
            used_memory = 0
            peak_memory = 0

        # Count keys by type
        key_counts = {
            "leads": 0,
            "deals": 0,
            "handoffs": 0,
            "audits": 0,
            "backups": 0,
            "alerts": 0,
        }

        for key_type in key_counts:
            async for _ in redis.scan_iter(f"{key_type.rstrip('s')}:*"):
                key_counts[key_type] += 1

        return {
            "used_memory_bytes": used_memory,
            "used_memory_mb": round(used_memory / 1024 / 1024, 2),
            "peak_memory_mb": round(peak_memory / 1024 / 1024, 2),
            "key_counts": key_counts,
            "policies": [p.to_dict() for p in self.get_all_policies()],
        }


# Singleton
retention_service = DataRetentionService()
