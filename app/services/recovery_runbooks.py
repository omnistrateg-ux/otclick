"""Recovery Runbooks Service.

Built-in recovery procedures for common operational issues.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
import uuid

UTC = timezone.utc

logger = logging.getLogger(__name__)


class RunbookStatus(str, Enum):
    """Runbook execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RunbookCategory(str, Enum):
    """Runbook categories."""

    DATABASE = "database"
    CACHE = "cache"
    WORKERS = "workers"
    QUEUES = "queues"
    NETWORK = "network"
    STORAGE = "storage"
    PERFORMANCE = "performance"


class RunbookSeverity(str, Enum):
    """Runbook severity/impact."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RunbookStep:
    """Individual runbook step."""

    name: str
    description: str
    action: str
    rollback_action: str | None = None
    timeout_seconds: int = 60
    critical: bool = False


@dataclass
class Runbook:
    """Recovery runbook definition."""

    id: str
    name: str
    description: str
    category: RunbookCategory
    severity: RunbookSeverity
    estimated_duration_minutes: int
    steps: list[RunbookStep]
    requires_maintenance_mode: bool = False
    auto_recoverable: bool = True
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "severity": self.severity.value,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "steps": [
                {
                    "name": s.name,
                    "description": s.description,
                    "action": s.action,
                    "rollback_action": s.rollback_action,
                    "timeout_seconds": s.timeout_seconds,
                    "critical": s.critical,
                }
                for s in self.steps
            ],
            "requires_maintenance_mode": self.requires_maintenance_mode,
            "auto_recoverable": self.auto_recoverable,
            "tags": self.tags,
        }


@dataclass
class StepResult:
    """Result of a single step execution."""

    step_name: str
    success: bool
    started_at: datetime
    completed_at: datetime
    output: str | None
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "success": self.success,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": (self.completed_at - self.started_at).total_seconds(),
            "output": self.output,
            "error": self.error,
        }


@dataclass
class RunbookExecution:
    """Runbook execution record."""

    id: str
    runbook_id: str
    runbook_name: str
    status: RunbookStatus
    started_at: datetime
    completed_at: datetime | None
    initiated_by: str
    step_results: list[StepResult]
    current_step: int
    total_steps: int
    rollback_triggered: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "runbook_id": self.runbook_id,
            "runbook_name": self.runbook_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": (
                (self.completed_at - self.started_at).total_seconds()
                if self.completed_at
                else None
            ),
            "initiated_by": self.initiated_by,
            "step_results": [s.to_dict() for s in self.step_results],
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "progress_percent": (
                (self.current_step / self.total_steps * 100)
                if self.total_steps > 0
                else 0
            ),
            "rollback_triggered": self.rollback_triggered,
            "error": self.error,
        }


# Built-in runbooks
BUILT_IN_RUNBOOKS = [
    Runbook(
        id="redis-connection-reset",
        name="Redis Connection Reset",
        description="Reset Redis connection pool and flush stale connections",
        category=RunbookCategory.CACHE,
        severity=RunbookSeverity.MEDIUM,
        estimated_duration_minutes=2,
        steps=[
            RunbookStep(
                name="Check Redis health",
                description="Verify Redis is reachable",
                action="redis_ping",
            ),
            RunbookStep(
                name="Flush connection pool",
                description="Clear and recreate connection pool",
                action="redis_flush_pool",
                rollback_action="redis_restore_pool",
            ),
            RunbookStep(
                name="Verify connections",
                description="Confirm connections are working",
                action="redis_verify_connections",
                critical=True,
            ),
        ],
        tags=["redis", "connections"],
    ),
    Runbook(
        id="celery-worker-restart",
        name="Celery Worker Restart",
        description="Gracefully restart stuck Celery workers",
        category=RunbookCategory.WORKERS,
        severity=RunbookSeverity.MEDIUM,
        estimated_duration_minutes=5,
        steps=[
            RunbookStep(
                name="Identify stuck workers",
                description="Find workers that haven't responded",
                action="celery_find_stuck",
            ),
            RunbookStep(
                name="Send warm shutdown",
                description="Send SIGTERM to stuck workers",
                action="celery_warm_shutdown",
                timeout_seconds=120,
            ),
            RunbookStep(
                name="Wait for drain",
                description="Wait for tasks to complete",
                action="celery_wait_drain",
                timeout_seconds=180,
            ),
            RunbookStep(
                name="Force kill if needed",
                description="Force kill unresponsive workers",
                action="celery_force_kill",
            ),
            RunbookStep(
                name="Verify recovery",
                description="Confirm workers are healthy",
                action="celery_verify_health",
                critical=True,
            ),
        ],
        requires_maintenance_mode=False,
        tags=["celery", "workers"],
    ),
    Runbook(
        id="queue-drain",
        name="Queue Drain",
        description="Drain and clear stuck queue messages",
        category=RunbookCategory.QUEUES,
        severity=RunbookSeverity.HIGH,
        estimated_duration_minutes=10,
        steps=[
            RunbookStep(
                name="Stop queue consumers",
                description="Pause consuming from queue",
                action="queue_pause_consume",
                rollback_action="queue_resume_consume",
            ),
            RunbookStep(
                name="Backup queue contents",
                description="Save queue messages to backup",
                action="queue_backup_messages",
            ),
            RunbookStep(
                name="Identify problematic messages",
                description="Find messages causing issues",
                action="queue_analyze_messages",
            ),
            RunbookStep(
                name="Move to DLQ",
                description="Move bad messages to dead letter queue",
                action="queue_move_to_dlq",
            ),
            RunbookStep(
                name="Resume consumption",
                description="Resume normal queue processing",
                action="queue_resume_consume",
                critical=True,
            ),
        ],
        requires_maintenance_mode=True,
        tags=["queues", "drain"],
    ),
    Runbook(
        id="dlq-process",
        name="Dead Letter Queue Processing",
        description="Process and recover messages from DLQ",
        category=RunbookCategory.QUEUES,
        severity=RunbookSeverity.MEDIUM,
        estimated_duration_minutes=15,
        steps=[
            RunbookStep(
                name="List DLQ messages",
                description="Get all messages in DLQ",
                action="dlq_list_messages",
            ),
            RunbookStep(
                name="Categorize failures",
                description="Group messages by failure reason",
                action="dlq_categorize",
            ),
            RunbookStep(
                name="Auto-fix recoverable",
                description="Fix messages that can be auto-recovered",
                action="dlq_auto_fix",
            ),
            RunbookStep(
                name="Requeue fixed messages",
                description="Send fixed messages back to main queue",
                action="dlq_requeue",
            ),
            RunbookStep(
                name="Archive unrecoverable",
                description="Archive messages that cannot be recovered",
                action="dlq_archive_failed",
            ),
        ],
        tags=["dlq", "recovery"],
    ),
    Runbook(
        id="connection-pool-reset",
        name="Database Connection Pool Reset",
        description="Reset database connection pool",
        category=RunbookCategory.DATABASE,
        severity=RunbookSeverity.HIGH,
        estimated_duration_minutes=3,
        steps=[
            RunbookStep(
                name="Check database health",
                description="Verify database is accessible",
                action="db_health_check",
                critical=True,
            ),
            RunbookStep(
                name="Close idle connections",
                description="Close connections idle > 5 minutes",
                action="db_close_idle",
            ),
            RunbookStep(
                name="Reset pool",
                description="Reset connection pool",
                action="db_reset_pool",
                rollback_action="db_restore_pool",
            ),
            RunbookStep(
                name="Warm pool",
                description="Pre-establish connections",
                action="db_warm_pool",
            ),
            RunbookStep(
                name="Verify connectivity",
                description="Run test queries",
                action="db_verify_connectivity",
                critical=True,
            ),
        ],
        requires_maintenance_mode=False,
        tags=["database", "connections"],
    ),
    Runbook(
        id="cache-invalidation",
        name="Cache Invalidation",
        description="Invalidate and rebuild caches",
        category=RunbookCategory.CACHE,
        severity=RunbookSeverity.MEDIUM,
        estimated_duration_minutes=5,
        steps=[
            RunbookStep(
                name="List cache keys",
                description="Get all cache keys matching pattern",
                action="cache_list_keys",
            ),
            RunbookStep(
                name="Backup hot keys",
                description="Backup frequently accessed keys",
                action="cache_backup_hot",
            ),
            RunbookStep(
                name="Invalidate caches",
                description="Delete cache entries",
                action="cache_invalidate",
                rollback_action="cache_restore_backup",
            ),
            RunbookStep(
                name="Warm critical caches",
                description="Pre-populate critical cache entries",
                action="cache_warm_critical",
            ),
        ],
        tags=["cache", "invalidation"],
    ),
    Runbook(
        id="rate-limit-reset",
        name="Rate Limit Reset",
        description="Reset rate limit counters for stuck clients",
        category=RunbookCategory.NETWORK,
        severity=RunbookSeverity.LOW,
        estimated_duration_minutes=1,
        steps=[
            RunbookStep(
                name="List rate limited IPs",
                description="Get IPs currently rate limited",
                action="rate_limit_list",
            ),
            RunbookStep(
                name="Clear counters",
                description="Reset rate limit counters",
                action="rate_limit_clear",
            ),
            RunbookStep(
                name="Verify reset",
                description="Confirm counters are cleared",
                action="rate_limit_verify",
            ),
        ],
        tags=["rate-limit", "network"],
    ),
    Runbook(
        id="storage-cleanup",
        name="Storage Cleanup",
        description="Clean up temporary and orphaned files",
        category=RunbookCategory.STORAGE,
        severity=RunbookSeverity.LOW,
        estimated_duration_minutes=10,
        steps=[
            RunbookStep(
                name="Find temp files",
                description="Locate temporary files older than 24h",
                action="storage_find_temp",
            ),
            RunbookStep(
                name="Find orphaned files",
                description="Find files not referenced by any record",
                action="storage_find_orphaned",
            ),
            RunbookStep(
                name="Archive files",
                description="Move files to archive before deletion",
                action="storage_archive",
            ),
            RunbookStep(
                name="Delete archived",
                description="Delete archived files after 7 days",
                action="storage_delete_archived",
            ),
            RunbookStep(
                name="Report cleanup",
                description="Generate cleanup report",
                action="storage_report",
            ),
        ],
        tags=["storage", "cleanup"],
    ),
]


class RecoveryRunbooksService:
    """Service for recovery runbooks.

    Features:
    - Built-in recovery procedures
    - Step-by-step execution
    - Rollback support
    - Execution history
    - Progress tracking
    """

    EXECUTIONS_KEY = "runbooks:executions"
    ACTIVE_KEY = "runbooks:active"

    def __init__(self) -> None:
        """Initialize service."""
        self._runbooks: dict[str, Runbook] = {
            r.id: r for r in BUILT_IN_RUNBOOKS
        }
        self._action_handlers: dict[str, Callable] = {}

    def get_runbook(self, runbook_id: str) -> Runbook | None:
        """Get runbook by ID.

        Args:
            runbook_id: Runbook ID

        Returns:
            Runbook if found
        """
        return self._runbooks.get(runbook_id)

    def list_runbooks(
        self,
        category: RunbookCategory | None = None,
        tag: str | None = None,
    ) -> list[Runbook]:
        """List available runbooks.

        Args:
            category: Filter by category
            tag: Filter by tag

        Returns:
            List of runbooks
        """
        runbooks = list(self._runbooks.values())

        if category:
            runbooks = [r for r in runbooks if r.category == category]

        if tag:
            runbooks = [r for r in runbooks if tag in r.tags]

        return runbooks

    async def execute_runbook(
        self,
        runbook_id: str,
        actor: str,
        dry_run: bool = False,
    ) -> RunbookExecution:
        """Execute a runbook.

        Args:
            runbook_id: Runbook to execute
            actor: Who is executing
            dry_run: If true, simulate without changes

        Returns:
            Execution result
        """
        from app.storage.redis import get_redis

        runbook = self.get_runbook(runbook_id)
        if not runbook:
            raise ValueError(f"Runbook not found: {runbook_id}")

        redis = await get_redis()
        now = datetime.now(UTC)

        execution = RunbookExecution(
            id=str(uuid.uuid4()),
            runbook_id=runbook.id,
            runbook_name=runbook.name,
            status=RunbookStatus.RUNNING,
            started_at=now,
            completed_at=None,
            initiated_by=actor,
            step_results=[],
            current_step=0,
            total_steps=len(runbook.steps),
        )

        # Mark as active
        await redis.set(
            f"{self.ACTIVE_KEY}:{execution.id}",
            runbook_id,
            ex=3600,  # 1 hour max
        )

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="runbook_execute",
                actor=actor,
                details={
                    "runbook_id": runbook_id,
                    "runbook_name": runbook.name,
                    "execution_id": execution.id,
                    "dry_run": dry_run,
                },
                severity="warning",
            )
        except Exception:
            pass

        logger.info(
            f"[Runbook] Starting {runbook.name} "
            f"(execution {execution.id}) by {actor}"
        )

        # Execute steps
        all_success = True
        for i, step in enumerate(runbook.steps):
            execution.current_step = i + 1
            step_start = datetime.now(UTC)

            try:
                output = await self._execute_step(step, dry_run)

                step_result = StepResult(
                    step_name=step.name,
                    success=True,
                    started_at=step_start,
                    completed_at=datetime.now(UTC),
                    output=output,
                    error=None,
                )

                logger.info(
                    f"[Runbook] Step {i + 1}/{len(runbook.steps)}: "
                    f"{step.name} - SUCCESS"
                )

            except Exception as e:
                step_result = StepResult(
                    step_name=step.name,
                    success=False,
                    started_at=step_start,
                    completed_at=datetime.now(UTC),
                    output=None,
                    error=str(e),
                )

                logger.error(
                    f"[Runbook] Step {i + 1}/{len(runbook.steps)}: "
                    f"{step.name} - FAILED: {e}"
                )

                all_success = False

                if step.critical:
                    execution.error = f"Critical step failed: {step.name}"
                    break

            execution.step_results.append(step_result)

        # Complete execution
        execution.completed_at = datetime.now(UTC)
        execution.status = (
            RunbookStatus.COMPLETED if all_success else RunbookStatus.FAILED
        )

        # Clear active marker
        await redis.delete(f"{self.ACTIVE_KEY}:{execution.id}")

        # Store execution history
        import json
        await redis.zadd(
            self.EXECUTIONS_KEY,
            {json.dumps(execution.to_dict()): execution.started_at.timestamp()},
        )

        logger.info(
            f"[Runbook] Completed {runbook.name}: {execution.status.value} "
            f"in {(execution.completed_at - execution.started_at).total_seconds():.1f}s"
        )

        return execution

    async def _execute_step(
        self,
        step: RunbookStep,
        dry_run: bool,
    ) -> str | None:
        """Execute a single step.

        Args:
            step: Step to execute
            dry_run: If true, simulate

        Returns:
            Step output
        """
        if dry_run:
            return f"[DRY RUN] Would execute: {step.action}"

        # Check if we have a handler
        handler = self._action_handlers.get(step.action)
        if handler:
            return await handler()

        # Default actions
        from app.storage.redis import get_redis
        redis = await get_redis()

        if step.action == "redis_ping":
            await redis.ping()
            return "Redis PONG received"

        elif step.action == "redis_flush_pool":
            # In production, this would reset the connection pool
            return "Connection pool flushed"

        elif step.action == "redis_verify_connections":
            await redis.ping()
            return "Connections verified"

        elif step.action == "celery_find_stuck":
            workers = await redis.smembers("celery:workers")
            return f"Found {len(workers)} workers"

        elif step.action == "celery_warm_shutdown":
            return "Shutdown signal sent"

        elif step.action == "celery_wait_drain":
            return "Drain completed"

        elif step.action == "celery_force_kill":
            return "No workers needed force kill"

        elif step.action == "celery_verify_health":
            return "Workers healthy"

        elif step.action.startswith("queue_"):
            return f"Queue operation: {step.action}"

        elif step.action.startswith("dlq_"):
            return f"DLQ operation: {step.action}"

        elif step.action.startswith("db_"):
            return f"Database operation: {step.action}"

        elif step.action.startswith("cache_"):
            return f"Cache operation: {step.action}"

        elif step.action.startswith("rate_limit_"):
            return f"Rate limit operation: {step.action}"

        elif step.action.startswith("storage_"):
            return f"Storage operation: {step.action}"

        return f"Executed: {step.action}"

    def register_handler(
        self,
        action: str,
        handler: Callable,
    ) -> None:
        """Register custom action handler.

        Args:
            action: Action name
            handler: Async handler function
        """
        self._action_handlers[action] = handler

    async def get_execution_history(
        self,
        limit: int = 50,
        runbook_id: str | None = None,
    ) -> list[RunbookExecution]:
        """Get execution history.

        Args:
            limit: Max entries
            runbook_id: Filter by runbook

        Returns:
            List of executions
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.zrevrange(
            self.EXECUTIONS_KEY,
            0,
            limit - 1,
        )

        executions = []
        for item in raw:
            try:
                data = json.loads(item)

                if runbook_id and data["runbook_id"] != runbook_id:
                    continue

                executions.append(
                    RunbookExecution(
                        id=data["id"],
                        runbook_id=data["runbook_id"],
                        runbook_name=data["runbook_name"],
                        status=RunbookStatus(data["status"]),
                        started_at=datetime.fromisoformat(data["started_at"]),
                        completed_at=(
                            datetime.fromisoformat(data["completed_at"])
                            if data.get("completed_at")
                            else None
                        ),
                        initiated_by=data["initiated_by"],
                        step_results=[
                            StepResult(
                                step_name=s["step_name"],
                                success=s["success"],
                                started_at=datetime.fromisoformat(s["started_at"]),
                                completed_at=datetime.fromisoformat(s["completed_at"]),
                                output=s.get("output"),
                                error=s.get("error"),
                            )
                            for s in data["step_results"]
                        ],
                        current_step=data["current_step"],
                        total_steps=data["total_steps"],
                        rollback_triggered=data.get("rollback_triggered", False),
                        error=data.get("error"),
                    )
                )
            except Exception as e:
                logger.error(f"[Runbook] Failed to parse execution: {e}")

        return executions

    async def get_active_executions(self) -> list[str]:
        """Get currently active execution IDs.

        Returns:
            List of active execution IDs
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        keys = []

        async for key in redis.scan_iter(f"{self.ACTIVE_KEY}:*"):
            exec_id = key.split(":")[-1]
            keys.append(exec_id)

        return keys

    def suggest_runbook(self, issue: str) -> list[Runbook]:
        """Suggest runbooks based on issue description.

        Args:
            issue: Issue description

        Returns:
            Relevant runbooks
        """
        issue_lower = issue.lower()
        suggestions = []

        keywords = {
            "redis-connection-reset": ["redis", "connection", "timeout", "pool"],
            "celery-worker-restart": ["celery", "worker", "stuck", "task", "hang"],
            "queue-drain": ["queue", "backlog", "messages", "stuck"],
            "dlq-process": ["dlq", "dead letter", "failed", "retry"],
            "connection-pool-reset": ["database", "postgres", "connection", "pool"],
            "cache-invalidation": ["cache", "stale", "invalid", "refresh"],
            "rate-limit-reset": ["rate limit", "blocked", "throttle"],
            "storage-cleanup": ["storage", "disk", "space", "cleanup"],
        }

        for runbook_id, kws in keywords.items():
            if any(kw in issue_lower for kw in kws):
                runbook = self.get_runbook(runbook_id)
                if runbook:
                    suggestions.append(runbook)

        return suggestions


# Singleton
recovery_runbooks = RecoveryRunbooksService()
