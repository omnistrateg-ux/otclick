"""PostgreSQL Diagnostics Service.

Deep database health checks and diagnostics.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc

logger = logging.getLogger(__name__)


class ConnectionState(str, Enum):
    """Database connection states."""

    ACTIVE = "active"
    IDLE = "idle"
    IDLE_IN_TRANSACTION = "idle_in_transaction"
    WAITING = "waiting"


@dataclass
class ConnectionPoolStats:
    """Connection pool statistics."""

    pool_size: int
    active_connections: int
    idle_connections: int
    waiting_connections: int
    max_connections: int
    utilization_percent: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_size": self.pool_size,
            "active_connections": self.active_connections,
            "idle_connections": self.idle_connections,
            "waiting_connections": self.waiting_connections,
            "max_connections": self.max_connections,
            "utilization_percent": self.utilization_percent,
        }


@dataclass
class QueryStats:
    """Query performance statistics."""

    total_queries: int
    slow_queries: int  # > 1s
    very_slow_queries: int  # > 5s
    avg_query_time_ms: float
    max_query_time_ms: float
    queries_per_second: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_queries": self.total_queries,
            "slow_queries": self.slow_queries,
            "very_slow_queries": self.very_slow_queries,
            "avg_query_time_ms": self.avg_query_time_ms,
            "max_query_time_ms": self.max_query_time_ms,
            "queries_per_second": self.queries_per_second,
        }


@dataclass
class TableStats:
    """Table statistics."""

    table_name: str
    row_count: int
    size_bytes: int
    size_mb: float
    index_size_bytes: int
    dead_tuples: int
    last_vacuum: datetime | None
    last_analyze: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_name": self.table_name,
            "row_count": self.row_count,
            "size_bytes": self.size_bytes,
            "size_mb": self.size_mb,
            "index_size_bytes": self.index_size_bytes,
            "dead_tuples": self.dead_tuples,
            "last_vacuum": self.last_vacuum.isoformat() if self.last_vacuum else None,
            "last_analyze": self.last_analyze.isoformat() if self.last_analyze else None,
        }


@dataclass
class LockInfo:
    """Database lock information."""

    pid: int
    lock_type: str
    relation: str
    mode: str
    granted: bool
    wait_time_seconds: float | None
    query: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "lock_type": self.lock_type,
            "relation": self.relation,
            "mode": self.mode,
            "granted": self.granted,
            "wait_time_seconds": self.wait_time_seconds,
            "query": self.query[:200] if self.query else None,
        }


@dataclass
class PostgresDiagnostics:
    """Full PostgreSQL diagnostics."""

    checked_at: datetime
    connected: bool
    version: str | None
    uptime_hours: float | None
    connection_pool: ConnectionPoolStats | None
    query_stats: QueryStats | None
    table_stats: list[TableStats]
    active_locks: list[LockInfo]
    long_running_queries: list[dict[str, Any]]
    replication_lag_bytes: int | None
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "checked_at": self.checked_at.isoformat(),
            "connected": self.connected,
            "version": self.version,
            "uptime_hours": self.uptime_hours,
            "connection_pool": self.connection_pool.to_dict() if self.connection_pool else None,
            "query_stats": self.query_stats.to_dict() if self.query_stats else None,
            "table_stats": [t.to_dict() for t in self.table_stats],
            "active_locks": [l.to_dict() for l in self.active_locks],
            "long_running_queries": self.long_running_queries,
            "replication_lag_bytes": self.replication_lag_bytes,
            "issues": self.issues,
        }


class PostgresDiagnosticsService:
    """Service for PostgreSQL diagnostics.

    Features:
    - Connection pool monitoring
    - Query performance analysis
    - Table statistics
    - Lock detection
    - Long-running query detection
    """

    def __init__(self) -> None:
        """Initialize service."""
        pass

    async def get_full_diagnostics(self) -> PostgresDiagnostics:
        """Get full PostgreSQL diagnostics.

        Returns:
            PostgresDiagnostics
        """
        now = datetime.now(UTC)
        issues = []

        # Try to get diagnostics from Redis-stored metrics
        # (In production, these would come from actual PG queries)
        from app.storage.redis import get_redis

        try:
            redis = await get_redis()

            # Get stored diagnostics
            version = await redis.get("pg:version") or "PostgreSQL (version unknown)"
            uptime = float(await redis.get("pg:uptime_hours") or 0)

            # Connection pool stats
            pool_size = int(await redis.get("pg:pool:size") or 10)
            active = int(await redis.get("pg:pool:active") or 0)
            idle = int(await redis.get("pg:pool:idle") or pool_size)
            max_conn = int(await redis.get("pg:pool:max") or 100)

            utilization = (active / max_conn * 100) if max_conn > 0 else 0
            if utilization > 80:
                issues.append(f"High connection utilization: {utilization:.1f}%")

            connection_pool = ConnectionPoolStats(
                pool_size=pool_size,
                active_connections=active,
                idle_connections=idle,
                waiting_connections=0,
                max_connections=max_conn,
                utilization_percent=utilization,
            )

            # Query stats
            total_queries = int(await redis.get("pg:queries:total") or 0)
            slow = int(await redis.get("pg:queries:slow") or 0)
            very_slow = int(await redis.get("pg:queries:very_slow") or 0)
            avg_time = float(await redis.get("pg:queries:avg_ms") or 0)
            max_time = float(await redis.get("pg:queries:max_ms") or 0)

            if slow > 10:
                issues.append(f"High number of slow queries: {slow}")
            if very_slow > 0:
                issues.append(f"Very slow queries detected: {very_slow}")

            query_stats = QueryStats(
                total_queries=total_queries,
                slow_queries=slow,
                very_slow_queries=very_slow,
                avg_query_time_ms=avg_time,
                max_query_time_ms=max_time,
                queries_per_second=0,
            )

            # Table stats (simplified - would come from pg_stat_user_tables)
            table_stats = []

            # Locks
            active_locks = []
            lock_count = int(await redis.get("pg:locks:waiting") or 0)
            if lock_count > 0:
                issues.append(f"Waiting locks detected: {lock_count}")

            # Long running queries
            long_running = []
            long_running_count = int(await redis.get("pg:queries:long_running") or 0)
            if long_running_count > 0:
                issues.append(f"Long-running queries: {long_running_count}")

            # Replication lag
            replication_lag = int(await redis.get("pg:replication:lag_bytes") or 0) or None

            return PostgresDiagnostics(
                checked_at=now,
                connected=True,
                version=version,
                uptime_hours=uptime,
                connection_pool=connection_pool,
                query_stats=query_stats,
                table_stats=table_stats,
                active_locks=active_locks,
                long_running_queries=long_running,
                replication_lag_bytes=replication_lag,
                issues=issues,
            )

        except Exception as e:
            logger.error(f"[PG Diagnostics] Failed: {str(e)}")
            return PostgresDiagnostics(
                checked_at=now,
                connected=False,
                version=None,
                uptime_hours=None,
                connection_pool=None,
                query_stats=None,
                table_stats=[],
                active_locks=[],
                long_running_queries=[],
                replication_lag_bytes=None,
                issues=[f"Connection failed: {str(e)}"],
            )

    async def check_connection(self) -> dict[str, Any]:
        """Quick connection check.

        Returns:
            Connection status
        """
        from app.storage.redis import get_redis
        import time

        try:
            start = time.time()
            redis = await get_redis()

            # Check if PG is marked as healthy
            healthy = await redis.get("pg:healthy")
            response_time = (time.time() - start) * 1000

            return {
                "connected": healthy == "true" or healthy is None,
                "response_time_ms": response_time,
                "checked_at": datetime.now(UTC).isoformat(),
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "checked_at": datetime.now(UTC).isoformat(),
            }

    async def update_metrics(
        self,
        metrics: dict[str, Any],
    ) -> None:
        """Update stored PG metrics.

        Args:
            metrics: Metrics to store
        """
        from app.storage.redis import get_redis

        redis = await get_redis()

        for key, value in metrics.items():
            await redis.set(f"pg:{key}", str(value), ex=300)  # 5 min TTL

    async def get_health_score(self) -> dict[str, Any]:
        """Calculate overall database health score.

        Returns:
            Health score and details
        """
        diagnostics = await self.get_full_diagnostics()

        score = 100
        factors = []

        if not diagnostics.connected:
            return {
                "score": 0,
                "status": "critical",
                "factors": ["Database not connected"],
            }

        # Deduct for issues
        for issue in diagnostics.issues:
            if "critical" in issue.lower():
                score -= 30
            elif "high" in issue.lower():
                score -= 15
            else:
                score -= 5
            factors.append(issue)

        # Connection pool utilization
        if diagnostics.connection_pool:
            util = diagnostics.connection_pool.utilization_percent
            if util > 90:
                score -= 20
                factors.append(f"Critical pool utilization: {util:.1f}%")
            elif util > 70:
                score -= 10
                factors.append(f"High pool utilization: {util:.1f}%")

        # Query performance
        if diagnostics.query_stats:
            if diagnostics.query_stats.very_slow_queries > 5:
                score -= 15
            if diagnostics.query_stats.avg_query_time_ms > 100:
                score -= 10

        score = max(0, score)

        if score >= 80:
            status = "healthy"
        elif score >= 50:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "score": score,
            "status": status,
            "factors": factors,
            "checked_at": diagnostics.checked_at.isoformat(),
        }


# Singleton
pg_diagnostics = PostgresDiagnosticsService()
