"""Tests for Round 7 Services.

Postgres Diagnostics, Worker Health, Maintenance Mode, Ops Journal, Recovery Runbooks.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

UTC = timezone.utc


# ============================================================================
# PostgreSQL Diagnostics Tests
# ============================================================================


class TestPostgresDiagnosticsService:
    """Tests for PostgresDiagnosticsService."""

    def test_connection_state_enum_values(self):
        """Test ConnectionState enum values."""
        from app.services.postgres_diagnostics import ConnectionState

        assert ConnectionState.ACTIVE.value == "active"
        assert ConnectionState.IDLE.value == "idle"
        assert ConnectionState.WAITING.value == "waiting"

    def test_connection_pool_stats_to_dict(self):
        """Test ConnectionPoolStats.to_dict()."""
        from app.services.postgres_diagnostics import ConnectionPoolStats

        stats = ConnectionPoolStats(
            pool_size=10,
            active_connections=3,
            idle_connections=7,
            waiting_connections=0,
            max_connections=100,
            utilization_percent=3.0,
        )

        d = stats.to_dict()

        assert d["pool_size"] == 10
        assert d["active_connections"] == 3
        assert d["utilization_percent"] == 3.0

    def test_query_stats_to_dict(self):
        """Test QueryStats.to_dict()."""
        from app.services.postgres_diagnostics import QueryStats

        stats = QueryStats(
            total_queries=1000,
            slow_queries=5,
            very_slow_queries=1,
            avg_query_time_ms=15.5,
            max_query_time_ms=500.0,
            queries_per_second=50.0,
        )

        d = stats.to_dict()

        assert d["total_queries"] == 1000
        assert d["slow_queries"] == 5
        assert d["avg_query_time_ms"] == 15.5

    def test_table_stats_to_dict(self):
        """Test TableStats.to_dict()."""
        from app.services.postgres_diagnostics import TableStats

        now = datetime.now(UTC)
        stats = TableStats(
            table_name="leads",
            row_count=10000,
            size_bytes=1024000,
            size_mb=1.0,
            index_size_bytes=512000,
            dead_tuples=100,
            last_vacuum=now,
            last_analyze=now,
        )

        d = stats.to_dict()

        assert d["table_name"] == "leads"
        assert d["row_count"] == 10000
        assert d["last_vacuum"] is not None

    def test_lock_info_to_dict(self):
        """Test LockInfo.to_dict()."""
        from app.services.postgres_diagnostics import LockInfo

        lock = LockInfo(
            pid=12345,
            lock_type="relation",
            relation="leads",
            mode="AccessShareLock",
            granted=True,
            wait_time_seconds=None,
            query="SELECT * FROM leads",
        )

        d = lock.to_dict()

        assert d["pid"] == 12345
        assert d["granted"] is True

    @pytest.mark.asyncio
    async def test_get_full_diagnostics(self):
        """Test getting full diagnostics."""
        from app.services.postgres_diagnostics import PostgresDiagnosticsService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = PostgresDiagnosticsService()
            diagnostics = await service.get_full_diagnostics()

        assert diagnostics is not None
        assert diagnostics.connected is True
        assert diagnostics.connection_pool is not None

    @pytest.mark.asyncio
    async def test_check_connection(self):
        """Test connection check."""
        from app.services.postgres_diagnostics import PostgresDiagnosticsService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="true")

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = PostgresDiagnosticsService()
            result = await service.check_connection()

        assert "connected" in result
        assert "response_time_ms" in result

    @pytest.mark.asyncio
    async def test_get_health_score(self):
        """Test health score calculation."""
        from app.services.postgres_diagnostics import PostgresDiagnosticsService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = PostgresDiagnosticsService()
            result = await service.get_health_score()

        assert "score" in result
        assert "status" in result
        assert result["score"] >= 0


# ============================================================================
# Worker Health Tests
# ============================================================================


class TestWorkerHealthService:
    """Tests for WorkerHealthService."""

    def test_worker_state_enum_values(self):
        """Test WorkerState enum values."""
        from app.services.worker_health import WorkerState

        assert WorkerState.ONLINE.value == "online"
        assert WorkerState.OFFLINE.value == "offline"
        assert WorkerState.STUCK.value == "stuck"
        assert WorkerState.BUSY.value == "busy"

    def test_queue_stats_to_dict(self):
        """Test QueueStats.to_dict()."""
        from app.services.worker_health import QueueStats, QueueHealth

        stats = QueueStats(
            name="celery",
            length=10,
            health=QueueHealth.HEALTHY,
            oldest_task_age_seconds=30.0,
            processing_rate_per_minute=100.0,
            avg_wait_time_seconds=5.0,
        )

        d = stats.to_dict()

        assert d["name"] == "celery"
        assert d["length"] == 10
        assert d["health"] == "healthy"

    def test_worker_info_to_dict(self):
        """Test WorkerInfo.to_dict()."""
        from app.services.worker_health import WorkerInfo, WorkerState

        now = datetime.now(UTC)
        info = WorkerInfo(
            worker_id="worker-1",
            state=WorkerState.ONLINE,
            hostname="localhost",
            pid=12345,
            last_heartbeat=now,
            current_task=None,
            task_started_at=None,
            tasks_completed=100,
            tasks_failed=2,
            uptime_seconds=3600.0,
        )

        d = info.to_dict()

        assert d["worker_id"] == "worker-1"
        assert d["state"] == "online"
        assert d["pid"] == 12345

    def test_dlq_stats_to_dict(self):
        """Test DLQStats.to_dict()."""
        from app.services.worker_health import DLQStats

        stats = DLQStats(
            total_messages=5,
            oldest_message_age_hours=1.0,
            messages_by_error={"timeout": 3, "connection": 2},
            recent_failures=[],
        )

        d = stats.to_dict()

        assert d["total_messages"] == 5
        assert "timeout" in d["messages_by_error"]

    def test_redis_health_to_dict(self):
        """Test RedisHealth.to_dict()."""
        from app.services.worker_health import RedisHealth

        health = RedisHealth(
            connected=True,
            response_time_ms=5.0,
            version="7.0.0",
            used_memory_mb=100.0,
            max_memory_mb=1000.0,
            memory_usage_percent=10.0,
            connected_clients=10,
            blocked_clients=0,
            keys_count=5000,
            expired_keys=100,
            evicted_keys=0,
            hit_rate_percent=95.0,
            issues=[],
        )

        d = health.to_dict()

        assert d["connected"] is True
        assert d["version"] == "7.0.0"
        assert d["hit_rate_percent"] == 95.0

    @pytest.mark.asyncio
    async def test_get_redis_health(self):
        """Test getting Redis health."""
        from app.services.worker_health import WorkerHealthService

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.info = AsyncMock(return_value={
            "redis_version": "7.0.0",
            "uptime_in_seconds": 86400,
            "used_memory": 104857600,
            "maxmemory": 1073741824,
            "connected_clients": 10,
            "blocked_clients": 0,
            "instantaneous_ops_per_sec": 1000,
            "keyspace_hits": 95,
            "keyspace_misses": 5,
        })
        mock_redis.dbsize = AsyncMock(return_value=5000)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = WorkerHealthService()
            health = await service.get_redis_health()

        assert health.connected is True
        assert health.version == "7.0.0"

    @pytest.mark.asyncio
    async def test_get_celery_health(self):
        """Test getting Celery health."""
        from app.services.worker_health import WorkerHealthService

        mock_redis = AsyncMock()
        mock_redis.smembers = AsyncMock(return_value=set())
        mock_redis.llen = AsyncMock(return_value=0)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.zcard = AsyncMock(return_value=0)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = WorkerHealthService()
            health = await service.get_celery_health()

        assert health is not None
        assert health.healthy is True

    @pytest.mark.asyncio
    async def test_send_worker_heartbeat(self):
        """Test sending worker heartbeat."""
        from app.services.worker_health import WorkerHealthService

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = WorkerHealthService()
            await service.send_worker_heartbeat(
                worker_id="worker-1",
                hostname="localhost",
                pid=12345,
            )

        mock_redis.set.assert_called()
        mock_redis.sadd.assert_called()


# ============================================================================
# Maintenance Mode Tests
# ============================================================================


class TestMaintenanceModeService:
    """Tests for MaintenanceModeService."""

    def test_system_state_enum_values(self):
        """Test SystemState enum values."""
        from app.services.maintenance_mode import SystemState

        assert SystemState.RUNNING.value == "running"
        assert SystemState.MAINTENANCE.value == "maintenance"
        assert SystemState.DEGRADED.value == "degraded"

    def test_readiness_state_enum_values(self):
        """Test ReadinessState enum values."""
        from app.services.maintenance_mode import ReadinessState

        assert ReadinessState.READY.value == "ready"
        assert ReadinessState.NOT_READY.value == "not_ready"
        assert ReadinessState.DRAINING.value == "draining"

    def test_maintenance_window_to_dict(self):
        """Test MaintenanceWindow.to_dict()."""
        from app.services.maintenance_mode import MaintenanceWindow

        now = datetime.now(UTC)
        window = MaintenanceWindow(
            id="window-1",
            reason="Database upgrade",
            scheduled_by="admin@example.com",
            scheduled_at=now,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            affected_services=["api", "workers"],
            notify_users=True,
            auto_recover=True,
        )

        d = window.to_dict()

        assert d["id"] == "window-1"
        assert d["reason"] == "Database upgrade"
        assert len(d["affected_services"]) == 2

    def test_system_status_to_dict(self):
        """Test SystemStatus.to_dict()."""
        from app.services.maintenance_mode import (
            SystemStatus, SystemState, ReadinessState
        )

        now = datetime.now(UTC)
        status = SystemStatus(
            state=SystemState.RUNNING,
            readiness=ReadinessState.READY,
            maintenance_mode=False,
            maintenance_reason=None,
            maintenance_started_at=None,
            maintenance_by=None,
            services_healthy={"redis": True, "postgres": True},
            active_connections=10,
            pending_requests=5,
            checked_at=now,
        )

        d = status.to_dict()

        assert d["state"] == "running"
        assert d["readiness"] == "ready"
        assert d["maintenance_mode"] is False

    def test_drain_status_to_dict(self):
        """Test DrainStatus.to_dict()."""
        from app.services.maintenance_mode import DrainStatus

        now = datetime.now(UTC)
        status = DrainStatus(
            is_draining=True,
            drain_started_at=now,
            initial_connections=100,
            current_connections=50,
            drain_timeout_seconds=300,
            estimated_completion=now + timedelta(minutes=2),
        )

        d = status.to_dict()

        assert d["is_draining"] is True
        assert d["initial_connections"] == 100
        assert d["current_connections"] == 50

    @pytest.mark.asyncio
    async def test_enter_maintenance_mode(self):
        """Test entering maintenance mode."""
        from app.services.maintenance_mode import MaintenanceModeService

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(return_value="0")

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = MaintenanceModeService()
            result = await service.enter_maintenance_mode(
                reason="Testing",
                actor="admin",
            )

        assert result["status"] == "maintenance_mode_active"
        assert result["reason"] == "Testing"

    @pytest.mark.asyncio
    async def test_exit_maintenance_mode(self):
        """Test exiting maintenance mode."""
        from app.services.maintenance_mode import MaintenanceModeService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock()

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = MaintenanceModeService()
            result = await service.exit_maintenance_mode(actor="admin")

        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting system status."""
        from app.services.maintenance_mode import MaintenanceModeService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = MaintenanceModeService()
            status = await service.get_status()

        assert status.maintenance_mode is False

    @pytest.mark.asyncio
    async def test_is_ready_when_not_maintenance(self):
        """Test readiness when not in maintenance."""
        from app.services.maintenance_mode import MaintenanceModeService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = MaintenanceModeService()
            ready = await service.is_ready()

        assert ready is True

    @pytest.mark.asyncio
    async def test_is_live(self):
        """Test liveness check."""
        from app.services.maintenance_mode import MaintenanceModeService

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = MaintenanceModeService()
            live = await service.is_live()

        assert live is True


# ============================================================================
# Ops Journal Tests
# ============================================================================


class TestOpsJournalService:
    """Tests for OpsJournalService."""

    def test_journal_severity_enum_values(self):
        """Test JournalSeverity enum values."""
        from app.services.ops_journal import JournalSeverity

        assert JournalSeverity.INFO.value == "info"
        assert JournalSeverity.WARNING.value == "warning"
        assert JournalSeverity.CRITICAL.value == "critical"

    def test_journal_category_enum_values(self):
        """Test JournalCategory enum values."""
        from app.services.ops_journal import JournalCategory

        assert JournalCategory.MAINTENANCE.value == "maintenance"
        assert JournalCategory.SECURITY.value == "security"
        assert JournalCategory.RECOVERY.value == "recovery"

    def test_journal_entry_to_dict(self):
        """Test JournalEntry.to_dict()."""
        from app.services.ops_journal import (
            JournalEntry, JournalCategory, JournalSeverity
        )

        now = datetime.now(UTC)
        entry = JournalEntry(
            id="entry-1",
            sequence=1,
            timestamp=now,
            action="enter_maintenance",
            category=JournalCategory.MAINTENANCE,
            severity=JournalSeverity.CRITICAL,
            actor="admin@example.com",
            details={"reason": "upgrade"},
            previous_hash="0" * 64,
            entry_hash="a" * 64,
        )

        d = entry.to_dict()

        assert d["id"] == "entry-1"
        assert d["sequence"] == 1
        assert d["action"] == "enter_maintenance"
        assert d["category"] == "maintenance"

    def test_journal_entry_from_dict(self):
        """Test JournalEntry.from_dict()."""
        from app.services.ops_journal import JournalEntry

        now = datetime.now(UTC)
        data = {
            "id": "entry-1",
            "sequence": 1,
            "timestamp": now.isoformat(),
            "action": "test",
            "category": "system",
            "severity": "info",
            "actor": "admin",
            "details": {},
            "previous_hash": "0" * 64,
            "entry_hash": "a" * 64,
        }

        entry = JournalEntry.from_dict(data)

        assert entry.id == "entry-1"
        assert entry.sequence == 1

    def test_journal_integrity_to_dict(self):
        """Test JournalIntegrity.to_dict()."""
        from app.services.ops_journal import JournalIntegrity

        integrity = JournalIntegrity(
            valid=True,
            total_entries=100,
            verified_entries=100,
            first_invalid_sequence=None,
            chain_broken_at=None,
            issues=[],
        )

        d = integrity.to_dict()

        assert d["valid"] is True
        assert d["total_entries"] == 100
        assert d["verified_entries"] == 100

    @pytest.mark.asyncio
    async def test_record_action(self):
        """Test recording an action."""
        from app.services.ops_journal import OpsJournalService

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.zadd = AsyncMock()
        mock_redis.set = AsyncMock()

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = OpsJournalService()
            entry = await service.record(
                action="test_action",
                actor="admin",
                details={"key": "value"},
            )

        assert entry.sequence == 1
        assert entry.action == "test_action"
        assert entry.actor == "admin"

    @pytest.mark.asyncio
    async def test_get_entries(self):
        """Test getting journal entries."""
        from app.services.ops_journal import OpsJournalService

        mock_redis = AsyncMock()
        mock_redis.zrevrangebyscore = AsyncMock(return_value=[])

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = OpsJournalService()
            entries = await service.get_entries()

        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_verify_integrity_empty(self):
        """Test verifying integrity of empty journal."""
        from app.services.ops_journal import OpsJournalService

        mock_redis = AsyncMock()
        mock_redis.zrangebyscore = AsyncMock(return_value=[])

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = OpsJournalService()
            result = await service.verify_integrity()

        assert result.valid is True
        assert result.total_entries == 0

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting journal stats."""
        from app.services.ops_journal import OpsJournalService

        mock_redis = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=0)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.zrevrangebyscore = AsyncMock(return_value=[])

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = OpsJournalService()
            stats = await service.get_stats()

        assert "total_entries" in stats
        assert "last_sequence" in stats


# ============================================================================
# Recovery Runbooks Tests
# ============================================================================


class TestRecoveryRunbooksService:
    """Tests for RecoveryRunbooksService."""

    def test_runbook_status_enum_values(self):
        """Test RunbookStatus enum values."""
        from app.services.recovery_runbooks import RunbookStatus

        assert RunbookStatus.PENDING.value == "pending"
        assert RunbookStatus.RUNNING.value == "running"
        assert RunbookStatus.COMPLETED.value == "completed"
        assert RunbookStatus.FAILED.value == "failed"

    def test_runbook_category_enum_values(self):
        """Test RunbookCategory enum values."""
        from app.services.recovery_runbooks import RunbookCategory

        assert RunbookCategory.DATABASE.value == "database"
        assert RunbookCategory.CACHE.value == "cache"
        assert RunbookCategory.WORKERS.value == "workers"
        assert RunbookCategory.QUEUES.value == "queues"

    def test_runbook_to_dict(self):
        """Test Runbook.to_dict()."""
        from app.services.recovery_runbooks import (
            Runbook, RunbookStep, RunbookCategory, RunbookSeverity
        )

        runbook = Runbook(
            id="test-runbook",
            name="Test Runbook",
            description="Test description",
            category=RunbookCategory.CACHE,
            severity=RunbookSeverity.LOW,
            estimated_duration_minutes=5,
            steps=[
                RunbookStep(
                    name="Step 1",
                    description="First step",
                    action="test_action",
                )
            ],
            tags=["test"],
        )

        d = runbook.to_dict()

        assert d["id"] == "test-runbook"
        assert d["name"] == "Test Runbook"
        assert len(d["steps"]) == 1

    def test_step_result_to_dict(self):
        """Test StepResult.to_dict()."""
        from app.services.recovery_runbooks import StepResult

        now = datetime.now(UTC)
        result = StepResult(
            step_name="Test Step",
            success=True,
            started_at=now,
            completed_at=now + timedelta(seconds=5),
            output="Success",
            error=None,
        )

        d = result.to_dict()

        assert d["step_name"] == "Test Step"
        assert d["success"] is True
        assert d["duration_seconds"] == 5.0

    def test_runbook_execution_to_dict(self):
        """Test RunbookExecution.to_dict()."""
        from app.services.recovery_runbooks import RunbookExecution, RunbookStatus

        now = datetime.now(UTC)
        execution = RunbookExecution(
            id="exec-1",
            runbook_id="test-runbook",
            runbook_name="Test Runbook",
            status=RunbookStatus.COMPLETED,
            started_at=now,
            completed_at=now + timedelta(minutes=2),
            initiated_by="admin",
            step_results=[],
            current_step=3,
            total_steps=3,
        )

        d = execution.to_dict()

        assert d["id"] == "exec-1"
        assert d["status"] == "completed"
        assert d["progress_percent"] == 100.0

    def test_list_runbooks(self):
        """Test listing runbooks."""
        from app.services.recovery_runbooks import RecoveryRunbooksService

        service = RecoveryRunbooksService()
        runbooks = service.list_runbooks()

        assert len(runbooks) > 0
        assert any(r.id == "redis-connection-reset" for r in runbooks)

    def test_list_runbooks_by_category(self):
        """Test listing runbooks by category."""
        from app.services.recovery_runbooks import (
            RecoveryRunbooksService, RunbookCategory
        )

        service = RecoveryRunbooksService()
        runbooks = service.list_runbooks(category=RunbookCategory.CACHE)

        assert all(r.category == RunbookCategory.CACHE for r in runbooks)

    def test_list_runbooks_by_tag(self):
        """Test listing runbooks by tag."""
        from app.services.recovery_runbooks import RecoveryRunbooksService

        service = RecoveryRunbooksService()
        runbooks = service.list_runbooks(tag="redis")

        assert all("redis" in r.tags for r in runbooks)

    def test_get_runbook(self):
        """Test getting runbook by ID."""
        from app.services.recovery_runbooks import RecoveryRunbooksService

        service = RecoveryRunbooksService()
        runbook = service.get_runbook("redis-connection-reset")

        assert runbook is not None
        assert runbook.id == "redis-connection-reset"

    def test_get_runbook_not_found(self):
        """Test getting non-existent runbook."""
        from app.services.recovery_runbooks import RecoveryRunbooksService

        service = RecoveryRunbooksService()
        runbook = service.get_runbook("non-existent")

        assert runbook is None

    def test_suggest_runbook(self):
        """Test suggesting runbooks."""
        from app.services.recovery_runbooks import RecoveryRunbooksService

        service = RecoveryRunbooksService()

        # Redis issue
        suggestions = service.suggest_runbook("redis connection timeout")
        assert any(r.id == "redis-connection-reset" for r in suggestions)

        # Celery issue
        suggestions = service.suggest_runbook("celery worker stuck")
        assert any(r.id == "celery-worker-restart" for r in suggestions)

        # DLQ issue
        suggestions = service.suggest_runbook("messages in dead letter queue")
        assert any(r.id == "dlq-process" for r in suggestions)

    @pytest.mark.asyncio
    async def test_execute_runbook_dry_run(self):
        """Test executing runbook in dry run mode."""
        from app.services.recovery_runbooks import RecoveryRunbooksService

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_redis.zadd = AsyncMock()
        mock_redis.ping = AsyncMock()

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = RecoveryRunbooksService()
            execution = await service.execute_runbook(
                runbook_id="redis-connection-reset",
                actor="admin",
                dry_run=True,
            )

        assert execution.status.value == "completed"
        assert all(r.success for r in execution.step_results)
        assert all("[DRY RUN]" in (r.output or "") for r in execution.step_results)

    @pytest.mark.asyncio
    async def test_execute_runbook_not_found(self):
        """Test executing non-existent runbook."""
        from app.services.recovery_runbooks import RecoveryRunbooksService

        service = RecoveryRunbooksService()

        with pytest.raises(ValueError):
            await service.execute_runbook(
                runbook_id="non-existent",
                actor="admin",
            )

    @pytest.mark.asyncio
    async def test_get_execution_history(self):
        """Test getting execution history."""
        from app.services.recovery_runbooks import RecoveryRunbooksService

        mock_redis = AsyncMock()
        mock_redis.zrevrange = AsyncMock(return_value=[])

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = RecoveryRunbooksService()
            history = await service.get_execution_history()

        assert isinstance(history, list)

    @pytest.mark.asyncio
    async def test_get_active_executions(self):
        """Test getting active executions."""
        from app.services.recovery_runbooks import RecoveryRunbooksService

        async def mock_scan_iter(pattern):
            return
            yield

        mock_redis = AsyncMock()
        mock_redis.scan_iter = mock_scan_iter

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = RecoveryRunbooksService()
            active = await service.get_active_executions()

        assert isinstance(active, list)
