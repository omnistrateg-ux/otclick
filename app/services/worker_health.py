"""Worker Health Service.

Redis and Celery deep health monitoring.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class WorkerState(str, Enum):
    """Worker states."""

    ONLINE = "online"
    OFFLINE = "offline"
    STUCK = "stuck"
    BUSY = "busy"
    IDLE = "idle"


class QueueHealth(str, Enum):
    """Queue health status."""

    HEALTHY = "healthy"
    LAGGING = "lagging"
    BACKLOGGED = "backlogged"
    STALLED = "stalled"


@dataclass
class QueueStats:
    """Queue statistics."""

    name: str
    length: int
    health: QueueHealth
    oldest_task_age_seconds: float | None
    processing_rate_per_minute: float
    avg_wait_time_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "length": self.length,
            "health": self.health.value,
            "oldest_task_age_seconds": self.oldest_task_age_seconds,
            "processing_rate_per_minute": self.processing_rate_per_minute,
            "avg_wait_time_seconds": self.avg_wait_time_seconds,
        }


@dataclass
class WorkerInfo:
    """Worker information."""

    worker_id: str
    state: WorkerState
    hostname: str
    pid: int | None
    last_heartbeat: datetime | None
    current_task: str | None
    task_started_at: datetime | None
    tasks_completed: int
    tasks_failed: int
    uptime_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "state": self.state.value,
            "hostname": self.hostname,
            "pid": self.pid,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "current_task": self.current_task,
            "task_started_at": self.task_started_at.isoformat() if self.task_started_at else None,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "uptime_seconds": self.uptime_seconds,
        }


@dataclass
class DLQStats:
    """Dead Letter Queue statistics."""

    total_messages: int
    oldest_message_age_hours: float | None
    messages_by_error: dict[str, int]
    recent_failures: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_messages": self.total_messages,
            "oldest_message_age_hours": self.oldest_message_age_hours,
            "messages_by_error": self.messages_by_error,
            "recent_failures": self.recent_failures,
        }


@dataclass
class RedisHealth:
    """Redis health details."""

    connected: bool
    response_time_ms: float
    version: str | None
    used_memory_mb: float
    max_memory_mb: float | None
    memory_usage_percent: float
    connected_clients: int
    blocked_clients: int
    keys_count: int
    expired_keys: int
    evicted_keys: int
    hit_rate_percent: float
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "response_time_ms": self.response_time_ms,
            "version": self.version,
            "used_memory_mb": self.used_memory_mb,
            "max_memory_mb": self.max_memory_mb,
            "memory_usage_percent": self.memory_usage_percent,
            "connected_clients": self.connected_clients,
            "blocked_clients": self.blocked_clients,
            "keys_count": self.keys_count,
            "expired_keys": self.expired_keys,
            "evicted_keys": self.evicted_keys,
            "hit_rate_percent": self.hit_rate_percent,
            "issues": self.issues,
        }


@dataclass
class CeleryHealth:
    """Celery health details."""

    healthy: bool
    workers_online: int
    workers_stuck: int
    total_queues: int
    queues: list[QueueStats]
    workers: list[WorkerInfo]
    dlq: DLQStats | None
    tasks_pending: int
    tasks_active: int
    tasks_reserved: int
    avg_task_duration_seconds: float
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "workers_online": self.workers_online,
            "workers_stuck": self.workers_stuck,
            "total_queues": self.total_queues,
            "queues": [q.to_dict() for q in self.queues],
            "workers": [w.to_dict() for w in self.workers],
            "dlq": self.dlq.to_dict() if self.dlq else None,
            "tasks_pending": self.tasks_pending,
            "tasks_active": self.tasks_active,
            "tasks_reserved": self.tasks_reserved,
            "avg_task_duration_seconds": self.avg_task_duration_seconds,
            "issues": self.issues,
        }


# Queue thresholds
QUEUE_THRESHOLDS = {
    "celery": {"lagging": 100, "backlogged": 500},
    "high_priority": {"lagging": 50, "backlogged": 200},
    "low_priority": {"lagging": 500, "backlogged": 2000},
    "default": {"lagging": 100, "backlogged": 500},
}

# Heartbeat timeout
HEARTBEAT_TIMEOUT_SECONDS = 60
STUCK_TASK_THRESHOLD_SECONDS = 300  # 5 minutes


class WorkerHealthService:
    """Service for Redis and Celery health monitoring.

    Features:
    - Queue lag monitoring
    - Stuck worker detection
    - Dead letter queue tracking
    - Worker heartbeats
    - Memory pressure detection
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    # ========================================================================
    # Redis Health
    # ========================================================================

    async def get_redis_health(self) -> RedisHealth:
        """Get detailed Redis health.

        Returns:
            RedisHealth
        """
        import time

        issues = []

        try:
            from app.storage.redis import get_redis

            start = time.time()
            redis = await get_redis()
            await redis.ping()
            response_time = (time.time() - start) * 1000

            # Get Redis info
            info = await redis.info()
            memory_info = await redis.info("memory")
            stats_info = await redis.info("stats")
            clients_info = await redis.info("clients")

            version = info.get("redis_version", "unknown")
            used_memory = memory_info.get("used_memory", 0)
            max_memory = memory_info.get("maxmemory", 0)
            used_memory_mb = used_memory / 1024 / 1024
            max_memory_mb = max_memory / 1024 / 1024 if max_memory else None

            if max_memory > 0:
                memory_usage = (used_memory / max_memory) * 100
                if memory_usage > 90:
                    issues.append(f"Critical memory usage: {memory_usage:.1f}%")
                elif memory_usage > 75:
                    issues.append(f"High memory usage: {memory_usage:.1f}%")
            else:
                memory_usage = 0

            connected_clients = clients_info.get("connected_clients", 0)
            blocked_clients = clients_info.get("blocked_clients", 0)

            if blocked_clients > 5:
                issues.append(f"Blocked clients: {blocked_clients}")

            # Key stats
            keys_count = sum(
                int(info.get(f"db{i}", {}).get("keys", 0) if isinstance(info.get(f"db{i}"), dict) else 0)
                for i in range(16)
            )

            expired_keys = stats_info.get("expired_keys", 0)
            evicted_keys = stats_info.get("evicted_keys", 0)

            if evicted_keys > 1000:
                issues.append(f"High eviction rate: {evicted_keys} keys evicted")

            # Hit rate
            hits = stats_info.get("keyspace_hits", 0)
            misses = stats_info.get("keyspace_misses", 0)
            if hits + misses > 0:
                hit_rate = (hits / (hits + misses)) * 100
            else:
                hit_rate = 100

            if hit_rate < 80 and hits + misses > 1000:
                issues.append(f"Low cache hit rate: {hit_rate:.1f}%")

            return RedisHealth(
                connected=True,
                response_time_ms=response_time,
                version=version,
                used_memory_mb=round(used_memory_mb, 2),
                max_memory_mb=round(max_memory_mb, 2) if max_memory_mb else None,
                memory_usage_percent=round(memory_usage, 1),
                connected_clients=connected_clients,
                blocked_clients=blocked_clients,
                keys_count=keys_count,
                expired_keys=expired_keys,
                evicted_keys=evicted_keys,
                hit_rate_percent=round(hit_rate, 1),
                issues=issues,
            )

        except Exception as e:
            logger.error(f"[Redis Health] Check failed: {str(e)}")
            return RedisHealth(
                connected=False,
                response_time_ms=0,
                version=None,
                used_memory_mb=0,
                max_memory_mb=None,
                memory_usage_percent=0,
                connected_clients=0,
                blocked_clients=0,
                keys_count=0,
                expired_keys=0,
                evicted_keys=0,
                hit_rate_percent=0,
                issues=[f"Connection failed: {str(e)}"],
            )

    # ========================================================================
    # Celery Health
    # ========================================================================

    async def get_celery_health(self) -> CeleryHealth:
        """Get detailed Celery health.

        Returns:
            CeleryHealth
        """
        from app.storage.redis import get_redis
        import json

        issues = []

        try:
            redis = await get_redis()
            now = datetime.now(UTC)

            # Get queue stats
            queues = []
            queue_names = ["celery", "high_priority", "low_priority"]
            total_pending = 0

            for queue_name in queue_names:
                length = await redis.llen(queue_name) or 0
                total_pending += length

                # Determine health
                thresholds = QUEUE_THRESHOLDS.get(queue_name, QUEUE_THRESHOLDS["default"])
                if length >= thresholds["backlogged"]:
                    health = QueueHealth.BACKLOGGED
                    issues.append(f"Queue {queue_name} backlogged: {length} tasks")
                elif length >= thresholds["lagging"]:
                    health = QueueHealth.LAGGING
                    issues.append(f"Queue {queue_name} lagging: {length} tasks")
                else:
                    health = QueueHealth.HEALTHY

                # Get oldest task age (approximate)
                oldest_age = None
                if length > 0:
                    oldest_key = f"queue:{queue_name}:oldest"
                    oldest_ts = await redis.get(oldest_key)
                    if oldest_ts:
                        oldest_age = (now - datetime.fromisoformat(oldest_ts)).total_seconds()

                # Get processing rate
                rate_key = f"queue:{queue_name}:rate"
                rate = float(await redis.get(rate_key) or 0)

                # Get avg wait time
                wait_key = f"queue:{queue_name}:avg_wait"
                avg_wait = float(await redis.get(wait_key) or 0)

                queues.append(QueueStats(
                    name=queue_name,
                    length=length,
                    health=health,
                    oldest_task_age_seconds=oldest_age,
                    processing_rate_per_minute=rate,
                    avg_wait_time_seconds=avg_wait,
                ))

            # Get worker info
            workers = []
            workers_online = 0
            workers_stuck = 0

            worker_ids = await redis.smembers("celery:workers")
            for worker_id in worker_ids:
                worker_data = await redis.get(f"celery:worker:{worker_id}")
                if not worker_data:
                    continue

                try:
                    w = json.loads(worker_data)
                    last_heartbeat = datetime.fromisoformat(w.get("last_heartbeat", now.isoformat()))
                    heartbeat_age = (now - last_heartbeat).total_seconds()

                    # Determine state
                    if heartbeat_age > HEARTBEAT_TIMEOUT_SECONDS:
                        state = WorkerState.OFFLINE
                    elif w.get("current_task"):
                        task_started = w.get("task_started_at")
                        if task_started:
                            task_age = (now - datetime.fromisoformat(task_started)).total_seconds()
                            if task_age > STUCK_TASK_THRESHOLD_SECONDS:
                                state = WorkerState.STUCK
                                workers_stuck += 1
                                issues.append(f"Worker {worker_id} stuck on task for {task_age:.0f}s")
                            else:
                                state = WorkerState.BUSY
                        else:
                            state = WorkerState.BUSY
                    else:
                        state = WorkerState.IDLE

                    if state in (WorkerState.ONLINE, WorkerState.BUSY, WorkerState.IDLE):
                        workers_online += 1

                    workers.append(WorkerInfo(
                        worker_id=worker_id,
                        state=state,
                        hostname=w.get("hostname", "unknown"),
                        pid=w.get("pid"),
                        last_heartbeat=last_heartbeat,
                        current_task=w.get("current_task"),
                        task_started_at=datetime.fromisoformat(w["task_started_at"]) if w.get("task_started_at") else None,
                        tasks_completed=w.get("tasks_completed", 0),
                        tasks_failed=w.get("tasks_failed", 0),
                        uptime_seconds=w.get("uptime_seconds", 0),
                    ))
                except (KeyError, ValueError, TypeError) as e:
                    logger.debug(f"[Worker Health] Failed to parse worker data: {e}")
                    continue

            if workers_online == 0 and total_pending > 0:
                issues.append("No workers online but tasks pending!")

            # Get DLQ stats
            dlq = await self._get_dlq_stats()
            if dlq and dlq.total_messages > 0:
                issues.append(f"Dead letter queue has {dlq.total_messages} messages")

            # Tasks stats
            tasks_active = int(await redis.get("celery:tasks:active") or 0)
            tasks_reserved = int(await redis.get("celery:tasks:reserved") or 0)
            avg_duration = float(await redis.get("celery:tasks:avg_duration") or 0)

            healthy = len([i for i in issues if "Critical" in i or "stuck" in i.lower() or "No workers" in i]) == 0

            return CeleryHealth(
                healthy=healthy,
                workers_online=workers_online,
                workers_stuck=workers_stuck,
                total_queues=len(queues),
                queues=queues,
                workers=workers,
                dlq=dlq,
                tasks_pending=total_pending,
                tasks_active=tasks_active,
                tasks_reserved=tasks_reserved,
                avg_task_duration_seconds=avg_duration,
                issues=issues,
            )

        except Exception as e:
            logger.error(f"[Celery Health] Check failed: {str(e)}")
            return CeleryHealth(
                healthy=False,
                workers_online=0,
                workers_stuck=0,
                total_queues=0,
                queues=[],
                workers=[],
                dlq=None,
                tasks_pending=0,
                tasks_active=0,
                tasks_reserved=0,
                avg_task_duration_seconds=0,
                issues=[f"Health check failed: {str(e)}"],
            )

    async def _get_dlq_stats(self) -> DLQStats | None:
        """Get Dead Letter Queue statistics."""
        from app.storage.redis import get_redis
        import json

        try:
            redis = await get_redis()

            # DLQ is stored as a list
            dlq_length = await redis.llen("celery:dlq") or 0
            if dlq_length == 0:
                return DLQStats(
                    total_messages=0,
                    oldest_message_age_hours=None,
                    messages_by_error={},
                    recent_failures=[],
                )

            # Get recent failures
            recent = await redis.lrange("celery:dlq", 0, 9)
            failures = []
            error_counts: dict[str, int] = {}
            oldest_age = None
            now = datetime.now(UTC)

            for item in recent:
                try:
                    data = json.loads(item)
                    error = data.get("error", "unknown")[:50]
                    error_counts[error] = error_counts.get(error, 0) + 1

                    failed_at = data.get("failed_at")
                    if failed_at:
                        age = (now - datetime.fromisoformat(failed_at)).total_seconds() / 3600
                        if oldest_age is None or age > oldest_age:
                            oldest_age = age

                    failures.append({
                        "task": data.get("task"),
                        "error": error,
                        "failed_at": failed_at,
                    })
                except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
                    logger.debug(f"[DLQ] Failed to parse DLQ entry: {e}")
                    continue

            return DLQStats(
                total_messages=dlq_length,
                oldest_message_age_hours=oldest_age,
                messages_by_error=error_counts,
                recent_failures=failures,
            )

        except Exception as e:
            logger.error(f"[DLQ] Stats failed: {str(e)}")
            return None

    # ========================================================================
    # Heartbeats
    # ========================================================================

    async def send_worker_heartbeat(
        self,
        worker_id: str,
        hostname: str,
        pid: int | None = None,
        current_task: str | None = None,
        task_started_at: datetime | None = None,
        tasks_completed: int = 0,
        tasks_failed: int = 0,
        uptime_seconds: float = 0,
    ) -> None:
        """Send worker heartbeat.

        Args:
            worker_id: Worker ID
            hostname: Worker hostname
            pid: Process ID
            current_task: Current task being processed
            task_started_at: When current task started
            tasks_completed: Total completed tasks
            tasks_failed: Total failed tasks
            uptime_seconds: Worker uptime
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        worker_data = {
            "worker_id": worker_id,
            "hostname": hostname,
            "pid": pid,
            "last_heartbeat": now.isoformat(),
            "current_task": current_task,
            "task_started_at": task_started_at.isoformat() if task_started_at else None,
            "tasks_completed": tasks_completed,
            "tasks_failed": tasks_failed,
            "uptime_seconds": uptime_seconds,
        }

        await redis.set(
            f"celery:worker:{worker_id}",
            json.dumps(worker_data),
            ex=HEARTBEAT_TIMEOUT_SECONDS * 2,
        )
        await redis.sadd("celery:workers", worker_id)
        await redis.expire("celery:workers", 86400)

    async def clear_stale_workers(self) -> int:
        """Clear stale worker records.

        Returns:
            Number of workers cleared
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)
        cleared = 0

        worker_ids = await redis.smembers("celery:workers")
        for worker_id in worker_ids:
            worker_data = await redis.get(f"celery:worker:{worker_id}")
            if not worker_data:
                await redis.srem("celery:workers", worker_id)
                cleared += 1
                continue

            try:
                w = json.loads(worker_data)
                last_heartbeat = datetime.fromisoformat(w.get("last_heartbeat", now.isoformat()))
                if (now - last_heartbeat).total_seconds() > HEARTBEAT_TIMEOUT_SECONDS * 3:
                    await redis.delete(f"celery:worker:{worker_id}")
                    await redis.srem("celery:workers", worker_id)
                    cleared += 1
                    logger.info(f"[Worker Health] Cleared stale worker: {worker_id}")
            except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
                logger.debug(f"[Worker Health] Failed to check worker staleness: {e}")
                continue

        return cleared

    # ========================================================================
    # DLQ Management
    # ========================================================================

    async def add_to_dlq(
        self,
        task: str,
        error: str,
        payload: dict[str, Any],
    ) -> None:
        """Add failed task to dead letter queue.

        Args:
            task: Task name
            error: Error message
            payload: Task payload
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        now = datetime.now(UTC)

        dlq_entry = {
            "task": task,
            "error": error,
            "payload": payload,
            "failed_at": now.isoformat(),
        }

        await redis.lpush("celery:dlq", json.dumps(dlq_entry))
        await redis.ltrim("celery:dlq", 0, 9999)  # Keep max 10000
        await redis.expire("celery:dlq", 86400 * 7)  # 7 days

    async def replay_dlq_task(self, index: int) -> dict[str, Any]:
        """Replay a task from DLQ.

        Args:
            index: Task index in DLQ

        Returns:
            Replay result
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Get task
        item = await redis.lindex("celery:dlq", index)
        if not item:
            return {"success": False, "error": "Task not found"}

        try:
            data = json.loads(item)

            # Queue for retry
            retry_task = {
                "task": data["task"],
                "payload": data["payload"],
                "retried_at": datetime.now(UTC).isoformat(),
                "original_error": data["error"],
            }
            await redis.lpush("jobs:retry_queue", json.dumps(retry_task))

            # Remove from DLQ
            await redis.lset("celery:dlq", index, "__DELETED__")
            await redis.lrem("celery:dlq", 1, "__DELETED__")

            logger.info(f"[DLQ] Replayed task: {data['task']}")

            return {"success": True, "task": data["task"]}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def purge_dlq(self) -> int:
        """Purge all DLQ messages.

        Returns:
            Number of messages purged
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        length = await redis.llen("celery:dlq") or 0
        await redis.delete("celery:dlq")

        logger.warning(f"[DLQ] Purged {length} messages")
        return length


# Singleton
worker_health = WorkerHealthService()
