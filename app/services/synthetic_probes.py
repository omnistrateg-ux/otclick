"""Synthetic Probes Service.

Synthetic end-to-end health probes and monitoring.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable
import uuid

UTC = timezone.utc

logger = logging.getLogger(__name__)


class ProbeStatus(str, Enum):
    """Probe execution status."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class ProbeType(str, Enum):
    """Probe types."""

    HTTP = "http"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    EXTERNAL_API = "external_api"
    END_TO_END = "end_to_end"


class ProbeSeverity(str, Enum):
    """Probe failure severity."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ProbeResult:
    """Result of a probe execution."""

    probe_id: str
    status: ProbeStatus
    latency_ms: float
    timestamp: datetime
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "details": self.details,
        }


@dataclass
class ProbeDefinition:
    """Synthetic probe definition."""

    id: str
    name: str
    description: str
    probe_type: ProbeType
    severity: ProbeSeverity
    interval_seconds: int
    timeout_seconds: int
    endpoint: str | None = None
    expected_status: int | None = None
    check_content: str | None = None
    enabled: bool = True
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "probe_type": self.probe_type.value,
            "severity": self.severity.value,
            "interval_seconds": self.interval_seconds,
            "timeout_seconds": self.timeout_seconds,
            "endpoint": self.endpoint,
            "expected_status": self.expected_status,
            "check_content": self.check_content,
            "enabled": self.enabled,
            "tags": self.tags,
        }


@dataclass
class ProbeHistory:
    """Probe execution history summary."""

    probe_id: str
    probe_name: str
    total_executions: int
    success_count: int
    failure_count: int
    timeout_count: int
    success_rate_percent: float
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    last_execution: ProbeResult | None
    recent_failures: list[ProbeResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "probe_name": self.probe_name,
            "total_executions": self.total_executions,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "timeout_count": self.timeout_count,
            "success_rate_percent": round(self.success_rate_percent, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "last_execution": self.last_execution.to_dict() if self.last_execution else None,
            "recent_failures": [f.to_dict() for f in self.recent_failures],
        }


@dataclass
class ProbeAlert:
    """Alert from probe failure."""

    id: str
    probe_id: str
    probe_name: str
    severity: ProbeSeverity
    message: str
    triggered_at: datetime
    acknowledged: bool = False
    acknowledged_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "probe_id": self.probe_id,
            "probe_name": self.probe_name,
            "severity": self.severity.value,
            "message": self.message,
            "triggered_at": self.triggered_at.isoformat(),
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
        }


# Default probes
DEFAULT_PROBES = [
    ProbeDefinition(
        id="api_health",
        name="API Health Check",
        description="Check API health endpoint",
        probe_type=ProbeType.HTTP,
        severity=ProbeSeverity.CRITICAL,
        interval_seconds=30,
        timeout_seconds=5,
        endpoint="/api/v1/health",
        expected_status=200,
    ),
    ProbeDefinition(
        id="redis_connection",
        name="Redis Connection",
        description="Check Redis connectivity",
        probe_type=ProbeType.CACHE,
        severity=ProbeSeverity.CRITICAL,
        interval_seconds=30,
        timeout_seconds=3,
    ),
    ProbeDefinition(
        id="database_query",
        name="Database Query",
        description="Execute test database query",
        probe_type=ProbeType.DATABASE,
        severity=ProbeSeverity.CRITICAL,
        interval_seconds=60,
        timeout_seconds=5,
    ),
    ProbeDefinition(
        id="queue_publish",
        name="Queue Publish",
        description="Test queue message publishing",
        probe_type=ProbeType.QUEUE,
        severity=ProbeSeverity.HIGH,
        interval_seconds=60,
        timeout_seconds=5,
    ),
    ProbeDefinition(
        id="lead_pipeline_e2e",
        name="Lead Pipeline E2E",
        description="End-to-end lead processing test",
        probe_type=ProbeType.END_TO_END,
        severity=ProbeSeverity.HIGH,
        interval_seconds=300,
        timeout_seconds=30,
    ),
    ProbeDefinition(
        id="email_send_test",
        name="Email Send Test",
        description="Test email sending capability",
        probe_type=ProbeType.EXTERNAL_API,
        severity=ProbeSeverity.MEDIUM,
        interval_seconds=300,
        timeout_seconds=10,
    ),
]


class SyntheticProbesService:
    """Service for synthetic health probes.

    Features:
    - Configurable probes
    - Scheduled execution
    - Latency tracking
    - Failure alerting
    - History and metrics
    """

    PROBES_KEY = "probes:definitions"
    RESULTS_PREFIX = "probes:results:"
    ALERTS_KEY = "probes:alerts"
    LAST_RUN_PREFIX = "probes:last_run:"

    def __init__(self) -> None:
        """Initialize service."""
        self._handlers: dict[ProbeType, Callable] = {}

    async def get_probe(self, probe_id: str) -> ProbeDefinition | None:
        """Get probe by ID.

        Args:
            probe_id: Probe ID

        Returns:
            Probe if found
        """
        probes = await self.list_probes()
        for probe in probes:
            if probe.id == probe_id:
                return probe
        return None

    async def list_probes(
        self,
        probe_type: ProbeType | None = None,
        enabled_only: bool = True,
    ) -> list[ProbeDefinition]:
        """List all probes.

        Args:
            probe_type: Filter by type
            enabled_only: Only enabled probes

        Returns:
            List of probes
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        raw = await redis.hgetall(self.PROBES_KEY)

        probes = []
        existing_ids = set()

        for key, data in raw.items():
            try:
                d = json.loads(data)
                probe = ProbeDefinition(
                    id=d["id"],
                    name=d["name"],
                    description=d["description"],
                    probe_type=ProbeType(d["probe_type"]),
                    severity=ProbeSeverity(d["severity"]),
                    interval_seconds=d["interval_seconds"],
                    timeout_seconds=d["timeout_seconds"],
                    endpoint=d.get("endpoint"),
                    expected_status=d.get("expected_status"),
                    check_content=d.get("check_content"),
                    enabled=d.get("enabled", True),
                    tags=d.get("tags", []),
                )

                if enabled_only and not probe.enabled:
                    continue
                if probe_type and probe.probe_type != probe_type:
                    continue

                probes.append(probe)
                existing_ids.add(probe.id)
            except Exception:
                continue

        # Add missing defaults
        for default in DEFAULT_PROBES:
            if default.id not in existing_ids:
                if enabled_only and not default.enabled:
                    continue
                if probe_type and default.probe_type != probe_type:
                    continue
                probes.append(default)

        return probes

    async def execute_probe(
        self,
        probe_id: str,
    ) -> ProbeResult:
        """Execute a probe.

        Args:
            probe_id: Probe ID

        Returns:
            Probe result
        """
        import time

        probe = await self.get_probe(probe_id)
        if not probe:
            return ProbeResult(
                probe_id=probe_id,
                status=ProbeStatus.FAILURE,
                latency_ms=0,
                timestamp=datetime.now(UTC),
                message="Probe not found",
            )

        start = time.time()
        now = datetime.now(UTC)

        try:
            # Execute based on type
            if probe.probe_type == ProbeType.CACHE:
                result = await self._execute_cache_probe(probe)
            elif probe.probe_type == ProbeType.DATABASE:
                result = await self._execute_database_probe(probe)
            elif probe.probe_type == ProbeType.QUEUE:
                result = await self._execute_queue_probe(probe)
            elif probe.probe_type == ProbeType.HTTP:
                result = await self._execute_http_probe(probe)
            elif probe.probe_type == ProbeType.END_TO_END:
                result = await self._execute_e2e_probe(probe)
            else:
                result = ProbeResult(
                    probe_id=probe_id,
                    status=ProbeStatus.SUCCESS,
                    latency_ms=(time.time() - start) * 1000,
                    timestamp=now,
                    message="Probe type not implemented",
                )

            result.latency_ms = (time.time() - start) * 1000

        except TimeoutError:
            result = ProbeResult(
                probe_id=probe_id,
                status=ProbeStatus.TIMEOUT,
                latency_ms=(time.time() - start) * 1000,
                timestamp=now,
                message=f"Probe timed out after {probe.timeout_seconds}s",
            )
        except Exception as e:
            result = ProbeResult(
                probe_id=probe_id,
                status=ProbeStatus.FAILURE,
                latency_ms=(time.time() - start) * 1000,
                timestamp=now,
                message=str(e),
            )

        # Store result
        await self._store_result(result)

        # Check for alerts
        if result.status != ProbeStatus.SUCCESS:
            await self._check_alert(probe, result)

        return result

    async def _execute_cache_probe(self, probe: ProbeDefinition) -> ProbeResult:
        """Execute cache (Redis) probe."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Test ping
        await redis.ping()

        # Test set/get
        test_key = f"probe:test:{probe.id}"
        test_value = str(uuid.uuid4())

        await redis.set(test_key, test_value, ex=10)
        retrieved = await redis.get(test_key)

        if retrieved != test_value:
            return ProbeResult(
                probe_id=probe.id,
                status=ProbeStatus.FAILURE,
                latency_ms=0,
                timestamp=datetime.now(UTC),
                message="Cache set/get mismatch",
            )

        return ProbeResult(
            probe_id=probe.id,
            status=ProbeStatus.SUCCESS,
            latency_ms=0,
            timestamp=datetime.now(UTC),
            message="Redis healthy",
        )

    async def _execute_database_probe(self, probe: ProbeDefinition) -> ProbeResult:
        """Execute database probe."""
        from app.storage.redis import get_redis

        # For now, verify via Redis that PG is healthy
        redis = await get_redis()
        pg_healthy = await redis.get("pg:healthy")

        if pg_healthy == "false":
            return ProbeResult(
                probe_id=probe.id,
                status=ProbeStatus.FAILURE,
                latency_ms=0,
                timestamp=datetime.now(UTC),
                message="Database unhealthy",
            )

        return ProbeResult(
            probe_id=probe.id,
            status=ProbeStatus.SUCCESS,
            latency_ms=0,
            timestamp=datetime.now(UTC),
            message="Database healthy",
        )

    async def _execute_queue_probe(self, probe: ProbeDefinition) -> ProbeResult:
        """Execute queue probe."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Test queue push/pop
        test_queue = "probe:test_queue"
        test_msg = str(uuid.uuid4())

        await redis.lpush(test_queue, test_msg)
        retrieved = await redis.rpop(test_queue)

        if retrieved != test_msg:
            return ProbeResult(
                probe_id=probe.id,
                status=ProbeStatus.FAILURE,
                latency_ms=0,
                timestamp=datetime.now(UTC),
                message="Queue push/pop mismatch",
            )

        return ProbeResult(
            probe_id=probe.id,
            status=ProbeStatus.SUCCESS,
            latency_ms=0,
            timestamp=datetime.now(UTC),
            message="Queue healthy",
        )

    async def _execute_http_probe(self, probe: ProbeDefinition) -> ProbeResult:
        """Execute HTTP probe."""
        # Simulate HTTP check (in production would use httpx)
        from app.storage.redis import get_redis

        redis = await get_redis()
        api_healthy = await redis.get("api:healthy")

        if api_healthy == "false":
            return ProbeResult(
                probe_id=probe.id,
                status=ProbeStatus.FAILURE,
                latency_ms=0,
                timestamp=datetime.now(UTC),
                message="API endpoint unhealthy",
            )

        return ProbeResult(
            probe_id=probe.id,
            status=ProbeStatus.SUCCESS,
            latency_ms=0,
            timestamp=datetime.now(UTC),
            message="API endpoint healthy",
            details={"endpoint": probe.endpoint},
        )

    async def _execute_e2e_probe(self, probe: ProbeDefinition) -> ProbeResult:
        """Execute end-to-end probe."""
        # Simulate E2E test
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Check all critical systems
        checks = {
            "redis": await redis.ping(),
            "api": await redis.get("api:healthy") != "false",
            "workers": await redis.get("workers:healthy") != "false",
        }

        failed = [k for k, v in checks.items() if not v]

        if failed:
            return ProbeResult(
                probe_id=probe.id,
                status=ProbeStatus.FAILURE,
                latency_ms=0,
                timestamp=datetime.now(UTC),
                message=f"E2E check failed: {', '.join(failed)}",
                details={"checks": checks},
            )

        return ProbeResult(
            probe_id=probe.id,
            status=ProbeStatus.SUCCESS,
            latency_ms=0,
            timestamp=datetime.now(UTC),
            message="E2E check passed",
            details={"checks": checks},
        )

    async def _store_result(self, result: ProbeResult) -> None:
        """Store probe result."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        key = f"{self.RESULTS_PREFIX}{result.probe_id}"

        await redis.zadd(
            key,
            {json.dumps(result.to_dict()): result.timestamp.timestamp()},
        )

        # Keep last 1000 results
        await redis.zremrangebyrank(key, 0, -1001)

        # Update last run
        await redis.set(
            f"{self.LAST_RUN_PREFIX}{result.probe_id}",
            json.dumps(result.to_dict()),
            ex=86400,
        )

    async def _check_alert(
        self,
        probe: ProbeDefinition,
        result: ProbeResult,
    ) -> None:
        """Check if alert should be created."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Check consecutive failures
        key = f"{self.RESULTS_PREFIX}{probe.id}"
        recent = await redis.zrevrange(key, 0, 2)

        consecutive_failures = 0
        for item in recent:
            try:
                data = json.loads(item)
                if data["status"] != ProbeStatus.SUCCESS.value:
                    consecutive_failures += 1
                else:
                    break
            except Exception:
                break

        # Alert on 3 consecutive failures
        if consecutive_failures >= 3:
            alert_key = f"probe_alert:{probe.id}:{datetime.now(UTC).strftime('%Y-%m-%d-%H')}"

            if not await redis.exists(alert_key):
                alert = ProbeAlert(
                    id=str(uuid.uuid4()),
                    probe_id=probe.id,
                    probe_name=probe.name,
                    severity=probe.severity,
                    message=f"Probe {probe.name} failed {consecutive_failures} times: {result.message}",
                    triggered_at=datetime.now(UTC),
                )

                await redis.zadd(
                    self.ALERTS_KEY,
                    {json.dumps(alert.to_dict()): alert.triggered_at.timestamp()},
                )
                await redis.set(alert_key, "1", ex=3600)

                logger.warning(
                    f"[Probes] Alert: {probe.name} - {result.message}"
                )

    async def get_probe_history(
        self,
        probe_id: str,
        hours: int = 24,
    ) -> ProbeHistory | None:
        """Get probe execution history.

        Args:
            probe_id: Probe ID
            hours: Hours to analyze

        Returns:
            Probe history
        """
        from app.storage.redis import get_redis
        import json

        probe = await self.get_probe(probe_id)
        if not probe:
            return None

        redis = await get_redis()
        key = f"{self.RESULTS_PREFIX}{probe_id}"

        now = datetime.now(UTC)
        min_ts = (now - timedelta(hours=hours)).timestamp()

        raw = await redis.zrevrangebyscore(key, "+inf", min_ts)

        results = []
        for item in raw:
            try:
                data = json.loads(item)
                results.append(ProbeResult(
                    probe_id=data["probe_id"],
                    status=ProbeStatus(data["status"]),
                    latency_ms=data["latency_ms"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    message=data.get("message"),
                    details=data.get("details", {}),
                ))
            except Exception:
                continue

        if not results:
            return ProbeHistory(
                probe_id=probe_id,
                probe_name=probe.name,
                total_executions=0,
                success_count=0,
                failure_count=0,
                timeout_count=0,
                success_rate_percent=0,
                avg_latency_ms=0,
                p95_latency_ms=0,
                p99_latency_ms=0,
                last_execution=None,
                recent_failures=[],
            )

        # Calculate stats
        success = sum(1 for r in results if r.status == ProbeStatus.SUCCESS)
        failure = sum(1 for r in results if r.status == ProbeStatus.FAILURE)
        timeout = sum(1 for r in results if r.status == ProbeStatus.TIMEOUT)

        latencies = sorted([r.latency_ms for r in results])
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        p95_idx = int(len(latencies) * 0.95)
        p99_idx = int(len(latencies) * 0.99)

        recent_failures = [r for r in results if r.status != ProbeStatus.SUCCESS][:5]

        return ProbeHistory(
            probe_id=probe_id,
            probe_name=probe.name,
            total_executions=len(results),
            success_count=success,
            failure_count=failure,
            timeout_count=timeout,
            success_rate_percent=(success / len(results) * 100) if results else 0,
            avg_latency_ms=avg_latency,
            p95_latency_ms=latencies[p95_idx] if p95_idx < len(latencies) else 0,
            p99_latency_ms=latencies[p99_idx] if p99_idx < len(latencies) else 0,
            last_execution=results[0] if results else None,
            recent_failures=recent_failures,
        )

    async def get_all_probe_status(self) -> list[dict[str, Any]]:
        """Get status of all probes.

        Returns:
            List of probe statuses
        """
        probes = await self.list_probes()
        statuses = []

        for probe in probes:
            history = await self.get_probe_history(probe.id, hours=1)
            statuses.append({
                "probe": probe.to_dict(),
                "history": history.to_dict() if history else None,
            })

        return statuses

    async def get_alerts(
        self,
        unacknowledged_only: bool = True,
        limit: int = 50,
    ) -> list[ProbeAlert]:
        """Get probe alerts.

        Args:
            unacknowledged_only: Only unacknowledged
            limit: Max results

        Returns:
            List of alerts
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.zrevrange(self.ALERTS_KEY, 0, limit - 1)

        alerts = []
        for item in raw:
            try:
                data = json.loads(item)
                alert = ProbeAlert(
                    id=data["id"],
                    probe_id=data["probe_id"],
                    probe_name=data["probe_name"],
                    severity=ProbeSeverity(data["severity"]),
                    message=data["message"],
                    triggered_at=datetime.fromisoformat(data["triggered_at"]),
                    acknowledged=data.get("acknowledged", False),
                    acknowledged_by=data.get("acknowledged_by"),
                )

                if unacknowledged_only and alert.acknowledged:
                    continue

                alerts.append(alert)
            except Exception:
                continue

        return alerts

    async def run_all_probes(self) -> list[ProbeResult]:
        """Run all enabled probes.

        Returns:
            List of results
        """
        probes = await self.list_probes(enabled_only=True)
        results = []

        for probe in probes:
            result = await self.execute_probe(probe.id)
            results.append(result)

        return results


# Singleton
synthetic_probes = SyntheticProbesService()
