"""Chaos Drills Service.

Controlled chaos engineering tests for resilience validation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
import uuid

UTC = timezone.utc

logger = logging.getLogger(__name__)


class DrillType(str, Enum):
    """Chaos drill types."""

    LATENCY_INJECTION = "latency_injection"
    ERROR_INJECTION = "error_injection"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DEPENDENCY_FAILURE = "dependency_failure"
    NETWORK_PARTITION = "network_partition"
    WORKER_KILL = "worker_kill"
    CACHE_FLUSH = "cache_flush"
    QUEUE_FLOOD = "queue_flood"


class DrillStatus(str, Enum):
    """Drill execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class DrillSeverity(str, Enum):
    """Drill impact severity."""

    LOW = "low"  # Minimal impact, safe to run
    MEDIUM = "medium"  # Some impact, use caution
    HIGH = "high"  # Significant impact, staging only
    CRITICAL = "critical"  # Major impact, manual approval


@dataclass
class DrillDefinition:
    """Chaos drill definition."""

    id: str
    name: str
    description: str
    drill_type: DrillType
    severity: DrillSeverity
    target_service: str
    duration_seconds: int
    parameters: dict[str, Any]
    rollback_steps: list[str]
    safe_for_production: bool = False
    requires_approval: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "drill_type": self.drill_type.value,
            "severity": self.severity.value,
            "target_service": self.target_service,
            "duration_seconds": self.duration_seconds,
            "parameters": self.parameters,
            "rollback_steps": self.rollback_steps,
            "safe_for_production": self.safe_for_production,
            "requires_approval": self.requires_approval,
        }


@dataclass
class DrillExecution:
    """Drill execution record."""

    id: str
    drill_id: str
    drill_name: str
    status: DrillStatus
    started_at: datetime
    ended_at: datetime | None
    initiated_by: str
    approved_by: str | None
    environment: str
    observations: list[str]
    metrics_before: dict[str, Any]
    metrics_during: dict[str, Any]
    metrics_after: dict[str, Any]
    success_criteria_met: bool | None = None
    rollback_executed: bool = False
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "drill_id": self.drill_id,
            "drill_name": self.drill_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": (
                (self.ended_at - self.started_at).total_seconds()
                if self.ended_at
                else None
            ),
            "initiated_by": self.initiated_by,
            "approved_by": self.approved_by,
            "environment": self.environment,
            "observations": self.observations,
            "metrics_before": self.metrics_before,
            "metrics_during": self.metrics_during,
            "metrics_after": self.metrics_after,
            "success_criteria_met": self.success_criteria_met,
            "rollback_executed": self.rollback_executed,
            "findings": self.findings,
        }


@dataclass
class DrillReport:
    """Drill execution report."""

    execution_id: str
    drill_name: str
    summary: str
    impact_assessment: str
    resilience_score: int  # 0-100
    recommendations: list[str]
    generated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "drill_name": self.drill_name,
            "summary": self.summary,
            "impact_assessment": self.impact_assessment,
            "resilience_score": self.resilience_score,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at.isoformat(),
        }


# Built-in drill definitions
BUILT_IN_DRILLS = [
    DrillDefinition(
        id="redis_latency_50ms",
        name="Redis Latency Injection (50ms)",
        description="Inject 50ms latency on Redis operations",
        drill_type=DrillType.LATENCY_INJECTION,
        severity=DrillSeverity.LOW,
        target_service="redis",
        duration_seconds=60,
        parameters={"latency_ms": 50},
        rollback_steps=["Remove latency injection", "Verify normal latency"],
        safe_for_production=True,
    ),
    DrillDefinition(
        id="redis_latency_500ms",
        name="Redis Latency Injection (500ms)",
        description="Inject 500ms latency on Redis operations",
        drill_type=DrillType.LATENCY_INJECTION,
        severity=DrillSeverity.MEDIUM,
        target_service="redis",
        duration_seconds=30,
        parameters={"latency_ms": 500},
        rollback_steps=["Remove latency injection", "Verify normal latency"],
        safe_for_production=False,
    ),
    DrillDefinition(
        id="api_error_5pct",
        name="API Error Injection (5%)",
        description="Return 500 errors on 5% of API requests",
        drill_type=DrillType.ERROR_INJECTION,
        severity=DrillSeverity.LOW,
        target_service="api",
        duration_seconds=120,
        parameters={"error_rate": 0.05, "error_code": 500},
        rollback_steps=["Disable error injection", "Verify error rates normal"],
        safe_for_production=True,
    ),
    DrillDefinition(
        id="api_error_25pct",
        name="API Error Injection (25%)",
        description="Return 500 errors on 25% of API requests",
        drill_type=DrillType.ERROR_INJECTION,
        severity=DrillSeverity.MEDIUM,
        target_service="api",
        duration_seconds=60,
        parameters={"error_rate": 0.25, "error_code": 500},
        rollback_steps=["Disable error injection", "Verify error rates normal"],
        safe_for_production=False,
    ),
    DrillDefinition(
        id="worker_kill_one",
        name="Kill One Worker",
        description="Terminate one random worker process",
        drill_type=DrillType.WORKER_KILL,
        severity=DrillSeverity.LOW,
        target_service="celery",
        duration_seconds=300,
        parameters={"count": 1},
        rollback_steps=["Auto-restart handled by supervisor"],
        safe_for_production=True,
    ),
    DrillDefinition(
        id="worker_kill_half",
        name="Kill Half Workers",
        description="Terminate 50% of worker processes",
        drill_type=DrillType.WORKER_KILL,
        severity=DrillSeverity.HIGH,
        target_service="celery",
        duration_seconds=300,
        parameters={"count_percent": 50},
        rollback_steps=["Wait for supervisor restart", "Scale up if needed"],
        safe_for_production=False,
        requires_approval=True,
    ),
    DrillDefinition(
        id="cache_flush_partial",
        name="Partial Cache Flush",
        description="Flush 10% of cache entries",
        drill_type=DrillType.CACHE_FLUSH,
        severity=DrillSeverity.LOW,
        target_service="redis",
        duration_seconds=30,
        parameters={"flush_percent": 10},
        rollback_steps=["Caches self-heal on miss"],
        safe_for_production=True,
    ),
    DrillDefinition(
        id="queue_flood_100",
        name="Queue Flood (100 tasks)",
        description="Inject 100 test tasks into queue",
        drill_type=DrillType.QUEUE_FLOOD,
        severity=DrillSeverity.LOW,
        target_service="celery",
        duration_seconds=60,
        parameters={"task_count": 100, "task_type": "test_task"},
        rollback_steps=["Clear test tasks from queue"],
        safe_for_production=True,
    ),
    DrillDefinition(
        id="dependency_timeout",
        name="External API Timeout",
        description="Simulate external API timeout",
        drill_type=DrillType.DEPENDENCY_FAILURE,
        severity=DrillSeverity.MEDIUM,
        target_service="external_api",
        duration_seconds=120,
        parameters={"timeout_ms": 30000, "service": "enrichment"},
        rollback_steps=["Restore normal timeouts"],
        safe_for_production=False,
    ),
]


class ChaosDrillsService:
    """Service for chaos engineering drills.

    Features:
    - Drill definition management
    - Controlled execution
    - Metrics collection
    - Auto-rollback
    - Impact assessment
    """

    DRILLS_KEY = "chaos:drills"
    EXECUTIONS_KEY = "chaos:executions"
    ACTIVE_KEY = "chaos:active"
    FINDINGS_KEY = "chaos:findings"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    def get_drill(self, drill_id: str) -> DrillDefinition | None:
        """Get drill by ID.

        Args:
            drill_id: Drill ID

        Returns:
            Drill if found
        """
        for drill in BUILT_IN_DRILLS:
            if drill.id == drill_id:
                return drill
        return None

    def list_drills(
        self,
        drill_type: DrillType | None = None,
        safe_for_production: bool | None = None,
    ) -> list[DrillDefinition]:
        """List available drills.

        Args:
            drill_type: Filter by type
            safe_for_production: Filter by production safety

        Returns:
            List of drills
        """
        drills = BUILT_IN_DRILLS.copy()

        if drill_type:
            drills = [d for d in drills if d.drill_type == drill_type]

        if safe_for_production is not None:
            drills = [d for d in drills if d.safe_for_production == safe_for_production]

        return drills

    async def start_drill(
        self,
        drill_id: str,
        initiated_by: str,
        approved_by: str | None = None,
        environment: str = "staging",
    ) -> DrillExecution:
        """Start a chaos drill.

        Args:
            drill_id: Drill to execute
            initiated_by: Who started it
            approved_by: Who approved (if required)
            environment: Target environment

        Returns:
            Drill execution
        """
        from app.storage.redis import get_redis
        import json

        drill = self.get_drill(drill_id)
        if not drill:
            raise ValueError(f"Drill not found: {drill_id}")

        # Safety checks
        if environment == "production" and not drill.safe_for_production:
            raise ValueError(f"Drill {drill_id} not safe for production")

        if drill.requires_approval and not approved_by:
            raise ValueError(f"Drill {drill_id} requires approval")

        redis = await get_redis()
        now = datetime.now(UTC)

        # Check for active drill
        active = await redis.get(self.ACTIVE_KEY)
        if active:
            raise ValueError("Another drill is currently running")

        # Collect baseline metrics
        metrics_before = await self._collect_metrics()

        execution = DrillExecution(
            id=str(uuid.uuid4())[:8],
            drill_id=drill.id,
            drill_name=drill.name,
            status=DrillStatus.RUNNING,
            started_at=now,
            ended_at=None,
            initiated_by=initiated_by,
            approved_by=approved_by,
            environment=environment,
            observations=[],
            metrics_before=metrics_before,
            metrics_during={},
            metrics_after={},
        )

        # Mark as active
        await redis.set(
            self.ACTIVE_KEY,
            json.dumps({"execution_id": execution.id, "drill_id": drill_id}),
            ex=drill.duration_seconds + 60,  # Buffer
        )

        # Execute drill
        await self._execute_drill(drill, execution)

        # Store execution
        await self._store_execution(execution)

        # Record in ops journal
        try:
            from app.services.ops_journal import ops_journal
            await ops_journal.record(
                action="chaos_drill_started",
                actor=initiated_by,
                details={
                    "drill_id": drill_id,
                    "drill_name": drill.name,
                    "execution_id": execution.id,
                    "environment": environment,
                },
                severity="warning",
            )
        except Exception:
            pass

        logger.warning(
            f"[Chaos] Started drill: {drill.name} "
            f"(execution {execution.id}) by {initiated_by}"
        )

        return execution

    async def _execute_drill(
        self,
        drill: DrillDefinition,
        execution: DrillExecution,
    ) -> None:
        """Execute the drill logic."""
        from app.storage.redis import get_redis
        import asyncio

        redis = await get_redis()

        # Set chaos injection flag
        chaos_key = f"chaos:inject:{drill.drill_type.value}"
        await redis.set(
            chaos_key,
            str(drill.parameters),
            ex=drill.duration_seconds + 10,
        )

        execution.observations.append(
            f"Started {drill.drill_type.value} injection"
        )

        # Wait for duration (in background)
        # In production, this would be handled by a background task
        # For now, simulate completion

        # Collect during metrics
        execution.metrics_during = await self._collect_metrics()

        # Auto-complete after duration
        await asyncio.sleep(min(drill.duration_seconds, 5))  # Cap for testing

        # Remove injection
        await redis.delete(chaos_key)

        execution.observations.append("Injection removed")

        # Collect after metrics
        execution.metrics_after = await self._collect_metrics()

        # Complete execution
        await self._complete_drill(execution)

    async def _complete_drill(
        self,
        execution: DrillExecution,
    ) -> None:
        """Complete drill execution."""
        from app.storage.redis import get_redis

        redis = await get_redis()
        now = datetime.now(UTC)

        execution.ended_at = now
        execution.status = DrillStatus.COMPLETED

        # Analyze results
        execution.findings = await self._analyze_findings(execution)
        execution.success_criteria_met = len([
            f for f in execution.findings if "FAIL" in f
        ]) == 0

        # Clear active marker
        await redis.delete(self.ACTIVE_KEY)

        # Update stored execution
        await self._store_execution(execution)

        logger.info(
            f"[Chaos] Completed drill: {execution.drill_name} "
            f"- {'PASSED' if execution.success_criteria_met else 'FINDINGS'}"
        )

    async def _collect_metrics(self) -> dict[str, Any]:
        """Collect current system metrics."""
        from app.storage.redis import get_redis

        redis = await get_redis()

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "error_rate": float(await redis.get("metrics:error_rate") or 0),
            "latency_p99": float(await redis.get("metrics:latency_p99") or 0),
            "queue_depth": int(await redis.get("metrics:queue_depth") or 0),
            "active_connections": int(await redis.get("metrics:connections") or 0),
        }

    async def _analyze_findings(
        self,
        execution: DrillExecution,
    ) -> list[str]:
        """Analyze drill results for findings."""
        findings = []

        # Compare before/after metrics
        before = execution.metrics_before
        after = execution.metrics_after

        # Error rate spike
        if after.get("error_rate", 0) > before.get("error_rate", 0) * 5:
            findings.append(
                f"FAIL: Error rate spiked from "
                f"{before.get('error_rate', 0):.2f}% to {after.get('error_rate', 0):.2f}%"
            )

        # Latency spike
        if after.get("latency_p99", 0) > before.get("latency_p99", 0) * 3:
            findings.append(
                f"WARNING: P99 latency increased significantly"
            )

        # Queue buildup
        if after.get("queue_depth", 0) > before.get("queue_depth", 0) + 100:
            findings.append(
                f"WARNING: Queue depth increased during drill"
            )

        # Recovery check
        if after.get("error_rate", 0) <= before.get("error_rate", 0) * 1.1:
            findings.append("PASS: System recovered to baseline error rate")

        if not findings:
            findings.append("PASS: No significant impact observed")

        return findings

    async def _store_execution(self, execution: DrillExecution) -> None:
        """Store execution record."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        await redis.zadd(
            self.EXECUTIONS_KEY,
            {json.dumps(execution.to_dict()): execution.started_at.timestamp()},
        )

    async def stop_drill(
        self,
        execution_id: str,
        actor: str,
        reason: str = "Manual stop",
    ) -> DrillExecution | None:
        """Stop a running drill.

        Args:
            execution_id: Execution to stop
            actor: Who stopped it
            reason: Reason for stopping

        Returns:
            Updated execution
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        # Check if active
        active_data = await redis.get(self.ACTIVE_KEY)
        if not active_data:
            return None

        active = json.loads(active_data)
        if active["execution_id"] != execution_id:
            return None

        # Get execution
        execution = await self.get_execution(execution_id)
        if not execution:
            return None

        drill = self.get_drill(execution.drill_id)
        if drill:
            # Clear injection
            chaos_key = f"chaos:inject:{drill.drill_type.value}"
            await redis.delete(chaos_key)

        # Update execution
        execution.ended_at = datetime.now(UTC)
        execution.status = DrillStatus.CANCELLED
        execution.observations.append(f"Stopped by {actor}: {reason}")
        execution.rollback_executed = True

        # Clear active
        await redis.delete(self.ACTIVE_KEY)

        await self._store_execution(execution)

        logger.warning(f"[Chaos] Drill {execution_id} stopped by {actor}: {reason}")

        return execution

    async def get_execution(self, execution_id: str) -> DrillExecution | None:
        """Get execution by ID."""
        history = await self.get_execution_history(limit=100)
        for exec in history:
            if exec.id == execution_id:
                return exec
        return None

    async def get_execution_history(
        self,
        drill_id: str | None = None,
        limit: int = 50,
    ) -> list[DrillExecution]:
        """Get drill execution history.

        Args:
            drill_id: Filter by drill
            limit: Max results

        Returns:
            List of executions
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.zrevrange(self.EXECUTIONS_KEY, 0, limit - 1)

        executions = []
        for item in raw:
            try:
                data = json.loads(item)

                if drill_id and data["drill_id"] != drill_id:
                    continue

                executions.append(DrillExecution(
                    id=data["id"],
                    drill_id=data["drill_id"],
                    drill_name=data["drill_name"],
                    status=DrillStatus(data["status"]),
                    started_at=datetime.fromisoformat(data["started_at"]),
                    ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
                    initiated_by=data["initiated_by"],
                    approved_by=data.get("approved_by"),
                    environment=data["environment"],
                    observations=data.get("observations", []),
                    metrics_before=data.get("metrics_before", {}),
                    metrics_during=data.get("metrics_during", {}),
                    metrics_after=data.get("metrics_after", {}),
                    success_criteria_met=data.get("success_criteria_met"),
                    rollback_executed=data.get("rollback_executed", False),
                    findings=data.get("findings", []),
                ))
            except Exception:
                continue

        return executions

    async def generate_report(
        self,
        execution_id: str,
    ) -> DrillReport | None:
        """Generate drill report.

        Args:
            execution_id: Execution to report on

        Returns:
            Drill report
        """
        execution = await self.get_execution(execution_id)
        if not execution:
            return None

        # Generate summary
        passed = sum(1 for f in execution.findings if "PASS" in f)
        failed = sum(1 for f in execution.findings if "FAIL" in f)
        warnings = sum(1 for f in execution.findings if "WARNING" in f)

        if execution.success_criteria_met:
            summary = f"Drill completed successfully. {passed} checks passed."
        else:
            summary = f"Drill revealed issues. {failed} failures, {warnings} warnings."

        # Impact assessment
        if failed > 0:
            impact = "HIGH: Critical resilience gaps identified"
        elif warnings > 0:
            impact = "MEDIUM: Some degradation observed"
        else:
            impact = "LOW: System handled chaos gracefully"

        # Resilience score
        total_checks = passed + failed + warnings
        if total_checks > 0:
            score = int((passed / total_checks) * 100)
        else:
            score = 100

        # Recommendations
        recommendations = []
        if failed > 0:
            recommendations.append("Investigate failure modes and add circuit breakers")
        if warnings > 0:
            recommendations.append("Review timeout and retry configurations")
        if score < 70:
            recommendations.append("Schedule follow-up drills after fixes")
        if score >= 90:
            recommendations.append("Consider more aggressive chaos scenarios")

        return DrillReport(
            execution_id=execution_id,
            drill_name=execution.drill_name,
            summary=summary,
            impact_assessment=impact,
            resilience_score=score,
            recommendations=recommendations,
            generated_at=datetime.now(UTC),
        )

    async def get_active_drill(self) -> dict[str, Any] | None:
        """Get currently active drill.

        Returns:
            Active drill info or None
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        active = await redis.get(self.ACTIVE_KEY)

        if active:
            return json.loads(active)
        return None


# Singleton
chaos_drills = ChaosDrillsService()
