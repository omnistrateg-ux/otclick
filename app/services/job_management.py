"""Job Management Service.

Failed job visibility, retry, and manual operations.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Types of jobs."""

    ENRICHMENT = "enrichment"
    SCORING = "scoring"
    EMAIL_SEND = "email_send"
    EMAIL_GENERATE = "email_generate"
    LEAD_TRANSITION = "lead_transition"
    HANDOFF_CREATE = "handoff_create"
    BACKUP = "backup"
    CLEANUP = "cleanup"
    SYNC = "sync"


@dataclass
class FailedJob:
    """A failed job record."""

    id: str
    job_type: JobType
    status: JobStatus
    created_at: datetime
    failed_at: datetime
    retry_count: int
    max_retries: int
    error_message: str
    error_traceback: str | None
    payload: dict[str, Any]
    result: dict[str, Any] | None = None
    last_retry_at: datetime | None = None
    can_retry: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "failed_at": self.failed_at.isoformat(),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error_message": self.error_message,
            "error_traceback": self.error_traceback,
            "payload": self.payload,
            "result": self.result,
            "last_retry_at": self.last_retry_at.isoformat() if self.last_retry_at else None,
            "can_retry": self.can_retry,
        }


@dataclass
class RetryResult:
    """Result of a retry operation."""

    job_id: str
    success: bool
    message: str
    new_job_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "success": self.success,
            "message": self.message,
            "new_job_id": self.new_job_id,
        }


@dataclass
class JobStats:
    """Job statistics."""

    period_hours: int
    total_jobs: int
    completed: int
    failed: int
    retrying: int
    pending: int
    success_rate: float
    by_type: dict[str, dict[str, int]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "period_hours": self.period_hours,
            "total_jobs": self.total_jobs,
            "completed": self.completed,
            "failed": self.failed,
            "retrying": self.retrying,
            "pending": self.pending,
            "success_rate": self.success_rate,
            "by_type": self.by_type,
        }


class JobManagementService:
    """Service for job management and visibility.

    Features:
    - Failed job tracking
    - Retry operations
    - Job statistics
    - Manual job management
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Job Recording
    # ========================================================================

    async def record_failed_job(
        self,
        job_id: str,
        job_type: JobType,
        error_message: str,
        payload: dict[str, Any],
        error_traceback: str | None = None,
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> FailedJob:
        """Record a failed job.

        Args:
            job_id: Job ID
            job_type: Type of job
            error_message: Error message
            payload: Job payload
            error_traceback: Full traceback
            retry_count: Current retry count
            max_retries: Maximum retries

        Returns:
            FailedJob
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        job = FailedJob(
            id=job_id,
            job_type=job_type,
            status=JobStatus.FAILED,
            created_at=now,
            failed_at=now,
            retry_count=retry_count,
            max_retries=max_retries,
            error_message=error_message,
            error_traceback=error_traceback,
            payload=payload,
            can_retry=retry_count < max_retries,
        )

        # Store job
        await redis.set(
            f"failed_job:{job_id}",
            json.dumps(job.to_dict()),
            ex=86400 * 7,
        )

        # Add to failed jobs list
        await redis.zadd("failed_jobs:timeline", {job_id: now.timestamp()})
        await redis.expire("failed_jobs:timeline", 86400 * 7)

        # Add to type index
        await redis.lpush(f"failed_jobs:type:{job_type.value}", job_id)
        await redis.ltrim(f"failed_jobs:type:{job_type.value}", 0, 999)
        await redis.expire(f"failed_jobs:type:{job_type.value}", 86400 * 7)

        # Increment daily stats
        day = now.strftime("%Y-%m-%d")
        await redis.incr(f"job_stats:{day}:failed")
        await redis.incr(f"job_stats:{day}:failed:{job_type.value}")
        await redis.expire(f"job_stats:{day}:failed", 86400 * 30)
        await redis.expire(f"job_stats:{day}:failed:{job_type.value}", 86400 * 30)

        logger.error(
            f"[Job] Failed | id={job_id} | type={job_type.value} | "
            f"retry={retry_count}/{max_retries} | error={error_message[:100]}"
        )

        return job

    async def record_job_completion(
        self,
        job_id: str,
        job_type: JobType,
    ) -> None:
        """Record successful job completion.

        Args:
            job_id: Job ID
            job_type: Type of job
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        day = now.strftime("%Y-%m-%d")

        await redis.incr(f"job_stats:{day}:completed")
        await redis.incr(f"job_stats:{day}:completed:{job_type.value}")
        await redis.expire(f"job_stats:{day}:completed", 86400 * 30)
        await redis.expire(f"job_stats:{day}:completed:{job_type.value}", 86400 * 30)

    # ========================================================================
    # Failed Job Retrieval
    # ========================================================================

    async def get_failed_job(self, job_id: str) -> FailedJob | None:
        """Get failed job by ID.

        Args:
            job_id: Job ID

        Returns:
            FailedJob or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        data = await redis.get(f"failed_job:{job_id}")

        if not data:
            return None

        d = json.loads(data)
        return FailedJob(
            id=d["id"],
            job_type=JobType(d["job_type"]),
            status=JobStatus(d["status"]),
            created_at=datetime.fromisoformat(d["created_at"]),
            failed_at=datetime.fromisoformat(d["failed_at"]),
            retry_count=d["retry_count"],
            max_retries=d["max_retries"],
            error_message=d["error_message"],
            error_traceback=d.get("error_traceback"),
            payload=d["payload"],
            result=d.get("result"),
            last_retry_at=datetime.fromisoformat(d["last_retry_at"]) if d.get("last_retry_at") else None,
            can_retry=d.get("can_retry", True),
        )

    async def get_failed_jobs(
        self,
        job_type: JobType | None = None,
        hours: int = 24,
        limit: int = 50,
    ) -> list[FailedJob]:
        """Get failed jobs.

        Args:
            job_type: Filter by type
            hours: Hours to look back
            limit: Max results

        Returns:
            List of failed jobs
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)
        start_time = (now - timedelta(hours=hours)).timestamp()

        if job_type:
            job_ids = await redis.lrange(f"failed_jobs:type:{job_type.value}", 0, limit - 1)
        else:
            job_ids = await redis.zrevrangebyscore(
                "failed_jobs:timeline",
                now.timestamp(),
                start_time,
                start=0,
                num=limit,
            )

        jobs = []
        for job_id in job_ids:
            job = await self.get_failed_job(job_id)
            if job:
                jobs.append(job)

        return jobs

    async def get_retryable_jobs(
        self,
        limit: int = 50,
    ) -> list[FailedJob]:
        """Get jobs that can be retried.

        Args:
            limit: Max results

        Returns:
            List of retryable jobs
        """
        jobs = await self.get_failed_jobs(limit=limit * 2)
        return [j for j in jobs if j.can_retry][:limit]

    # ========================================================================
    # Retry Operations
    # ========================================================================

    async def retry_job(
        self,
        job_id: str,
        actor: str = "system",
    ) -> RetryResult:
        """Retry a failed job.

        Args:
            job_id: Job ID
            actor: Who initiated retry

        Returns:
            RetryResult
        """
        from app.storage.redis import get_redis
        from uuid import uuid4
        import json

        job = await self.get_failed_job(job_id)
        if not job:
            return RetryResult(
                job_id=job_id,
                success=False,
                message="Job not found",
            )

        if not job.can_retry:
            return RetryResult(
                job_id=job_id,
                success=False,
                message=f"Job cannot be retried (retry count: {job.retry_count}/{job.max_retries})",
            )

        redis = await get_redis()
        now = datetime.now(UTC)

        # Update job status
        job.status = JobStatus.RETRYING
        job.retry_count += 1
        job.last_retry_at = now
        job.can_retry = job.retry_count < job.max_retries

        await redis.set(
            f"failed_job:{job_id}",
            json.dumps(job.to_dict()),
            ex=86400 * 7,
        )

        # Queue retry based on job type
        new_job_id = str(uuid4())

        try:
            await self._queue_retry(job, new_job_id)

            logger.info(
                f"[Job] Retry queued | id={job_id} | new_id={new_job_id} | "
                f"type={job.job_type.value} | actor={actor}"
            )

            return RetryResult(
                job_id=job_id,
                success=True,
                message="Retry queued successfully",
                new_job_id=new_job_id,
            )

        except Exception as e:
            logger.error(f"[Job] Retry failed | id={job_id} | error={str(e)}")

            return RetryResult(
                job_id=job_id,
                success=False,
                message=f"Retry failed: {str(e)}",
            )

    async def _queue_retry(
        self,
        job: FailedJob,
        new_job_id: str,
    ) -> None:
        """Queue job for retry.

        Args:
            job: Failed job
            new_job_id: New job ID
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Create retry task
        retry_task = {
            "id": new_job_id,
            "original_job_id": job.id,
            "job_type": job.job_type.value,
            "payload": job.payload,
            "retry_count": job.retry_count,
            "created_at": datetime.now(UTC).isoformat(),
        }

        # Add to retry queue
        await redis.lpush("jobs:retry_queue", json.dumps(retry_task))
        await redis.expire("jobs:retry_queue", 86400)

    async def retry_all_failed(
        self,
        job_type: JobType | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        """Retry all failed jobs.

        Args:
            job_type: Filter by type
            actor: Who initiated

        Returns:
            Summary of retries
        """
        jobs = await self.get_retryable_jobs(limit=100)

        if job_type:
            jobs = [j for j in jobs if j.job_type == job_type]

        success = 0
        failed = 0
        results = []

        for job in jobs:
            result = await self.retry_job(job.id, actor)
            if result.success:
                success += 1
            else:
                failed += 1
            results.append(result.to_dict())

        return {
            "total": len(jobs),
            "success": success,
            "failed": failed,
            "results": results[:20],  # Limit details
        }

    async def cancel_job(
        self,
        job_id: str,
        actor: str = "system",
    ) -> bool:
        """Cancel a failed job (prevent retries).

        Args:
            job_id: Job ID
            actor: Who cancelled

        Returns:
            True if cancelled
        """
        from app.storage.redis import get_redis
        import json

        job = await self.get_failed_job(job_id)
        if not job:
            return False

        job.status = JobStatus.CANCELLED
        job.can_retry = False

        redis = await get_redis()
        await redis.set(
            f"failed_job:{job_id}",
            json.dumps(job.to_dict()),
            ex=86400 * 7,
        )

        logger.info(f"[Job] Cancelled | id={job_id} | actor={actor}")

        return True

    # ========================================================================
    # Statistics
    # ========================================================================

    async def get_job_stats(
        self,
        hours: int = 24,
    ) -> JobStats:
        """Get job statistics.

        Args:
            hours: Hours to analyze

        Returns:
            JobStats
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        completed = 0
        failed = 0
        by_type: dict[str, dict[str, int]] = {}

        # Aggregate stats
        for i in range(min(hours // 24 + 1, 7)):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")

            day_completed = int(await redis.get(f"job_stats:{day}:completed") or 0)
            day_failed = int(await redis.get(f"job_stats:{day}:failed") or 0)

            completed += day_completed
            failed += day_failed

            # By type
            for jt in JobType:
                type_completed = int(await redis.get(f"job_stats:{day}:completed:{jt.value}") or 0)
                type_failed = int(await redis.get(f"job_stats:{day}:failed:{jt.value}") or 0)

                if jt.value not in by_type:
                    by_type[jt.value] = {"completed": 0, "failed": 0}

                by_type[jt.value]["completed"] += type_completed
                by_type[jt.value]["failed"] += type_failed

        total = completed + failed
        success_rate = (completed / total * 100) if total > 0 else 100.0

        # Get current queue state
        pending = await redis.llen("jobs:retry_queue") or 0
        retrying_jobs = await self.get_failed_jobs(hours=hours, limit=1000)
        retrying = sum(1 for j in retrying_jobs if j.status == JobStatus.RETRYING)

        return JobStats(
            period_hours=hours,
            total_jobs=total,
            completed=completed,
            failed=failed,
            retrying=retrying,
            pending=pending,
            success_rate=success_rate,
            by_type=by_type,
        )

    async def get_error_summary(
        self,
        hours: int = 24,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get summary of most common errors.

        Args:
            hours: Hours to analyze
            limit: Max results

        Returns:
            List of error summaries
        """
        jobs = await self.get_failed_jobs(hours=hours, limit=500)

        # Group by error message
        error_counts: dict[str, dict[str, Any]] = {}

        for job in jobs:
            # Normalize error message
            error_key = job.error_message[:100]

            if error_key not in error_counts:
                error_counts[error_key] = {
                    "error": job.error_message,
                    "count": 0,
                    "job_types": set(),
                    "latest": job.failed_at,
                }

            error_counts[error_key]["count"] += 1
            error_counts[error_key]["job_types"].add(job.job_type.value)
            if job.failed_at > error_counts[error_key]["latest"]:
                error_counts[error_key]["latest"] = job.failed_at

        # Sort by count
        sorted_errors = sorted(
            error_counts.values(),
            key=lambda x: x["count"],
            reverse=True,
        )[:limit]

        return [
            {
                "error": e["error"],
                "count": e["count"],
                "job_types": list(e["job_types"]),
                "latest": e["latest"].isoformat(),
            }
            for e in sorted_errors
        ]


# Singleton
job_service = JobManagementService()
