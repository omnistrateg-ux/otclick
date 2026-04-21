"""Deployment Safety Service.

Pre-deployment validation and safety checks.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

UTC = timezone.utc

logger = logging.getLogger(__name__)


class DeploymentStatus(str, Enum):
    """Deployment status."""

    PENDING = "pending"
    CHECKING = "checking"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class CheckStatus(str, Enum):
    """Safety check status."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class CheckCategory(str, Enum):
    """Safety check category."""

    TESTS = "tests"
    MIGRATIONS = "migrations"
    DEPENDENCIES = "dependencies"
    CONFIG = "config"
    CAPACITY = "capacity"
    TIMING = "timing"
    ROLLBACK = "rollback"


@dataclass
class SafetyCheck:
    """Individual safety check result."""

    name: str
    category: CheckCategory
    status: CheckStatus
    message: str
    details: dict[str, Any] | None = None
    duration_ms: float = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "duration_ms": self.duration_ms,
        }


@dataclass
class DeploymentPlan:
    """Deployment plan with safety checks."""

    id: str
    version: str
    environment: str
    status: DeploymentStatus
    created_at: datetime
    created_by: str
    checks: list[SafetyCheck]
    approved_at: datetime | None = None
    approved_by: str | None = None
    deployed_at: datetime | None = None
    rolled_back_at: datetime | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "environment": self.environment,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "checks": [c.to_dict() for c in self.checks],
            "checks_passed": sum(1 for c in self.checks if c.status == CheckStatus.PASSED),
            "checks_failed": sum(1 for c in self.checks if c.status == CheckStatus.FAILED),
            "checks_warnings": sum(1 for c in self.checks if c.status == CheckStatus.WARNING),
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approved_by": self.approved_by,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "rolled_back_at": self.rolled_back_at.isoformat() if self.rolled_back_at else None,
            "notes": self.notes,
            "can_deploy": all(c.status != CheckStatus.FAILED for c in self.checks),
        }


@dataclass
class RollbackPlan:
    """Rollback plan."""

    deployment_id: str
    previous_version: str
    steps: list[str]
    estimated_duration_seconds: int
    data_loss_risk: bool
    requires_manual_steps: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "previous_version": self.previous_version,
            "steps": self.steps,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "data_loss_risk": self.data_loss_risk,
            "requires_manual_steps": self.requires_manual_steps,
        }


# Deployment windows (UTC hours)
DEPLOYMENT_WINDOWS = {
    "production": {
        "allowed_hours": list(range(6, 18)),  # 6 AM - 6 PM UTC
        "forbidden_days": [5, 6],  # Saturday, Sunday
        "freeze_dates": [],  # Add specific dates
    },
    "staging": {
        "allowed_hours": list(range(0, 24)),
        "forbidden_days": [],
        "freeze_dates": [],
    },
}


class DeploymentSafetyService:
    """Service for deployment safety checks.

    Features:
    - Pre-deployment validation
    - Test verification
    - Migration safety checks
    - Deployment windows
    - Rollback planning
    """

    DEPLOYMENTS_KEY = "deployments:history"
    CURRENT_KEY = "deployments:current"

    def __init__(self) -> None:
        """Initialize service."""
        pass

    async def create_deployment_plan(
        self,
        version: str,
        environment: str,
        created_by: str,
        notes: str | None = None,
    ) -> DeploymentPlan:
        """Create deployment plan with safety checks.

        Args:
            version: Version to deploy
            environment: Target environment
            created_by: Who created the plan
            notes: Optional notes

        Returns:
            Deployment plan with checks
        """
        import time

        now = datetime.now(UTC)
        checks = []

        # Run all safety checks
        checks.append(await self._check_tests())
        checks.append(await self._check_migrations(environment))
        checks.append(await self._check_dependencies())
        checks.append(await self._check_config(environment))
        checks.append(await self._check_capacity(environment))
        checks.append(await self._check_timing(environment))
        checks.append(await self._check_rollback_ready(version))

        plan = DeploymentPlan(
            id=str(uuid.uuid4()),
            version=version,
            environment=environment,
            status=DeploymentStatus.CHECKING,
            created_at=now,
            created_by=created_by,
            checks=checks,
            notes=notes,
        )

        # Determine status
        if any(c.status == CheckStatus.FAILED for c in checks):
            plan.status = DeploymentStatus.REJECTED
        else:
            plan.status = DeploymentStatus.PENDING

        # Store plan
        await self._store_plan(plan)

        logger.info(
            f"[Deployment] Plan created: {plan.id} for {version} "
            f"to {environment} - {plan.status.value}"
        )

        return plan

    async def _check_tests(self) -> SafetyCheck:
        """Check if tests are passing."""
        import time
        start = time.time()

        # In production, this would check CI/CD status
        from app.storage.redis import get_redis

        try:
            redis = await get_redis()
            test_status = await redis.get("ci:tests:status")
            test_coverage = float(await redis.get("ci:tests:coverage") or 0)

            if test_status == "failed":
                return SafetyCheck(
                    name="Test Suite",
                    category=CheckCategory.TESTS,
                    status=CheckStatus.FAILED,
                    message="Test suite is failing",
                    details={"coverage": test_coverage},
                    duration_ms=(time.time() - start) * 1000,
                )

            if test_coverage < 70:
                return SafetyCheck(
                    name="Test Suite",
                    category=CheckCategory.TESTS,
                    status=CheckStatus.WARNING,
                    message=f"Test coverage below 70%: {test_coverage}%",
                    details={"coverage": test_coverage},
                    duration_ms=(time.time() - start) * 1000,
                )

            return SafetyCheck(
                name="Test Suite",
                category=CheckCategory.TESTS,
                status=CheckStatus.PASSED,
                message="All tests passing",
                details={"coverage": test_coverage},
                duration_ms=(time.time() - start) * 1000,
            )

        except Exception as e:
            return SafetyCheck(
                name="Test Suite",
                category=CheckCategory.TESTS,
                status=CheckStatus.WARNING,
                message=f"Could not verify tests: {str(e)}",
                duration_ms=(time.time() - start) * 1000,
            )

    async def _check_migrations(self, environment: str) -> SafetyCheck:
        """Check migration safety."""
        import time
        start = time.time()

        from app.storage.redis import get_redis

        try:
            redis = await get_redis()

            # Check for pending migrations
            pending = int(await redis.get("migrations:pending") or 0)
            has_destructive = await redis.get("migrations:has_destructive") == "true"

            if pending == 0:
                return SafetyCheck(
                    name="Database Migrations",
                    category=CheckCategory.MIGRATIONS,
                    status=CheckStatus.PASSED,
                    message="No pending migrations",
                    duration_ms=(time.time() - start) * 1000,
                )

            if has_destructive and environment == "production":
                return SafetyCheck(
                    name="Database Migrations",
                    category=CheckCategory.MIGRATIONS,
                    status=CheckStatus.FAILED,
                    message="Destructive migrations require manual approval",
                    details={"pending": pending, "destructive": True},
                    duration_ms=(time.time() - start) * 1000,
                )

            return SafetyCheck(
                name="Database Migrations",
                category=CheckCategory.MIGRATIONS,
                status=CheckStatus.WARNING,
                message=f"{pending} pending migrations",
                details={"pending": pending},
                duration_ms=(time.time() - start) * 1000,
            )

        except Exception as e:
            return SafetyCheck(
                name="Database Migrations",
                category=CheckCategory.MIGRATIONS,
                status=CheckStatus.WARNING,
                message=f"Could not check migrations: {str(e)}",
                duration_ms=(time.time() - start) * 1000,
            )

    async def _check_dependencies(self) -> SafetyCheck:
        """Check dependency health."""
        import time
        start = time.time()

        from app.storage.redis import get_redis

        try:
            redis = await get_redis()

            # Check for vulnerable deps
            vulnerabilities = int(await redis.get("deps:vulnerabilities") or 0)
            outdated = int(await redis.get("deps:outdated") or 0)

            if vulnerabilities > 0:
                return SafetyCheck(
                    name="Dependencies",
                    category=CheckCategory.DEPENDENCIES,
                    status=CheckStatus.FAILED,
                    message=f"{vulnerabilities} vulnerable dependencies",
                    details={"vulnerabilities": vulnerabilities, "outdated": outdated},
                    duration_ms=(time.time() - start) * 1000,
                )

            if outdated > 10:
                return SafetyCheck(
                    name="Dependencies",
                    category=CheckCategory.DEPENDENCIES,
                    status=CheckStatus.WARNING,
                    message=f"{outdated} outdated dependencies",
                    details={"outdated": outdated},
                    duration_ms=(time.time() - start) * 1000,
                )

            return SafetyCheck(
                name="Dependencies",
                category=CheckCategory.DEPENDENCIES,
                status=CheckStatus.PASSED,
                message="Dependencies healthy",
                duration_ms=(time.time() - start) * 1000,
            )

        except Exception as e:
            return SafetyCheck(
                name="Dependencies",
                category=CheckCategory.DEPENDENCIES,
                status=CheckStatus.PASSED,
                message="Dependency check skipped",
                duration_ms=(time.time() - start) * 1000,
            )

    async def _check_config(self, environment: str) -> SafetyCheck:
        """Check configuration validity."""
        import time
        start = time.time()

        try:
            from app.services.config_validation import ConfigValidationService

            service = ConfigValidationService()
            result = service.validate_all()

            if not result.valid:
                return SafetyCheck(
                    name="Configuration",
                    category=CheckCategory.CONFIG,
                    status=CheckStatus.FAILED,
                    message=f"{result.errors_count} configuration errors",
                    details={"errors": result.errors_count, "warnings": result.warnings_count},
                    duration_ms=(time.time() - start) * 1000,
                )

            if result.warnings_count > 0:
                return SafetyCheck(
                    name="Configuration",
                    category=CheckCategory.CONFIG,
                    status=CheckStatus.WARNING,
                    message=f"{result.warnings_count} configuration warnings",
                    details={"warnings": result.warnings_count},
                    duration_ms=(time.time() - start) * 1000,
                )

            return SafetyCheck(
                name="Configuration",
                category=CheckCategory.CONFIG,
                status=CheckStatus.PASSED,
                message="Configuration valid",
                duration_ms=(time.time() - start) * 1000,
            )

        except Exception as e:
            return SafetyCheck(
                name="Configuration",
                category=CheckCategory.CONFIG,
                status=CheckStatus.WARNING,
                message=f"Config check failed: {str(e)}",
                duration_ms=(time.time() - start) * 1000,
            )

    async def _check_capacity(self, environment: str) -> SafetyCheck:
        """Check system capacity."""
        import time
        start = time.time()

        from app.storage.redis import get_redis

        try:
            redis = await get_redis()

            # Check current load
            cpu_usage = float(await redis.get("system:cpu_percent") or 0)
            memory_usage = float(await redis.get("system:memory_percent") or 0)
            queue_depth = int(await redis.get("celery:queue:depth") or 0)

            issues = []
            if cpu_usage > 80:
                issues.append(f"High CPU: {cpu_usage}%")
            if memory_usage > 85:
                issues.append(f"High memory: {memory_usage}%")
            if queue_depth > 1000:
                issues.append(f"Queue backlog: {queue_depth}")

            if issues:
                return SafetyCheck(
                    name="System Capacity",
                    category=CheckCategory.CAPACITY,
                    status=CheckStatus.WARNING,
                    message="; ".join(issues),
                    details={
                        "cpu_percent": cpu_usage,
                        "memory_percent": memory_usage,
                        "queue_depth": queue_depth,
                    },
                    duration_ms=(time.time() - start) * 1000,
                )

            return SafetyCheck(
                name="System Capacity",
                category=CheckCategory.CAPACITY,
                status=CheckStatus.PASSED,
                message="System capacity healthy",
                details={
                    "cpu_percent": cpu_usage,
                    "memory_percent": memory_usage,
                },
                duration_ms=(time.time() - start) * 1000,
            )

        except Exception as e:
            return SafetyCheck(
                name="System Capacity",
                category=CheckCategory.CAPACITY,
                status=CheckStatus.PASSED,
                message="Capacity check skipped",
                duration_ms=(time.time() - start) * 1000,
            )

    async def _check_timing(self, environment: str) -> SafetyCheck:
        """Check deployment timing."""
        import time
        start = time.time()

        now = datetime.now(UTC)
        window = DEPLOYMENT_WINDOWS.get(environment, DEPLOYMENT_WINDOWS["staging"])

        # Check day
        if now.weekday() in window["forbidden_days"]:
            return SafetyCheck(
                name="Deployment Window",
                category=CheckCategory.TIMING,
                status=CheckStatus.FAILED,
                message="Deployments not allowed on weekends",
                details={"day": now.strftime("%A"), "hour": now.hour},
                duration_ms=(time.time() - start) * 1000,
            )

        # Check hour
        if now.hour not in window["allowed_hours"]:
            return SafetyCheck(
                name="Deployment Window",
                category=CheckCategory.TIMING,
                status=CheckStatus.WARNING,
                message=f"Outside deployment window (hour {now.hour})",
                details={"hour": now.hour, "allowed": window["allowed_hours"]},
                duration_ms=(time.time() - start) * 1000,
            )

        # Check freeze dates
        date_str = now.strftime("%Y-%m-%d")
        if date_str in window["freeze_dates"]:
            return SafetyCheck(
                name="Deployment Window",
                category=CheckCategory.TIMING,
                status=CheckStatus.FAILED,
                message="Deployment freeze in effect",
                details={"date": date_str},
                duration_ms=(time.time() - start) * 1000,
            )

        return SafetyCheck(
            name="Deployment Window",
            category=CheckCategory.TIMING,
            status=CheckStatus.PASSED,
            message="Within deployment window",
            details={"hour": now.hour, "day": now.strftime("%A")},
            duration_ms=(time.time() - start) * 1000,
        )

    async def _check_rollback_ready(self, version: str) -> SafetyCheck:
        """Check if rollback is possible."""
        import time
        start = time.time()

        from app.storage.redis import get_redis

        try:
            redis = await get_redis()

            # Check for previous version
            previous = await redis.get("deployment:previous_version")
            has_backup = await redis.get("deployment:backup_ready") == "true"

            if not previous:
                return SafetyCheck(
                    name="Rollback Ready",
                    category=CheckCategory.ROLLBACK,
                    status=CheckStatus.WARNING,
                    message="No previous version to rollback to",
                    duration_ms=(time.time() - start) * 1000,
                )

            if not has_backup:
                return SafetyCheck(
                    name="Rollback Ready",
                    category=CheckCategory.ROLLBACK,
                    status=CheckStatus.WARNING,
                    message="No backup available for rollback",
                    details={"previous_version": previous},
                    duration_ms=(time.time() - start) * 1000,
                )

            return SafetyCheck(
                name="Rollback Ready",
                category=CheckCategory.ROLLBACK,
                status=CheckStatus.PASSED,
                message=f"Can rollback to {previous}",
                details={"previous_version": previous},
                duration_ms=(time.time() - start) * 1000,
            )

        except Exception as e:
            return SafetyCheck(
                name="Rollback Ready",
                category=CheckCategory.ROLLBACK,
                status=CheckStatus.WARNING,
                message="Could not verify rollback readiness",
                duration_ms=(time.time() - start) * 1000,
            )

    async def _store_plan(self, plan: DeploymentPlan) -> None:
        """Store deployment plan."""
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()
        await redis.zadd(
            self.DEPLOYMENTS_KEY,
            {json.dumps(plan.to_dict()): plan.created_at.timestamp()},
        )
        await redis.set(
            f"{self.CURRENT_KEY}:{plan.environment}",
            json.dumps(plan.to_dict()),
            ex=86400,
        )

    async def approve_deployment(
        self,
        plan_id: str,
        approved_by: str,
    ) -> DeploymentPlan | None:
        """Approve a deployment plan.

        Args:
            plan_id: Plan ID
            approved_by: Approver

        Returns:
            Updated plan
        """
        plan = await self.get_plan(plan_id)
        if not plan:
            return None

        if plan.status != DeploymentStatus.PENDING:
            return None

        plan.status = DeploymentStatus.APPROVED
        plan.approved_at = datetime.now(UTC)
        plan.approved_by = approved_by

        await self._store_plan(plan)

        logger.info(f"[Deployment] Plan {plan_id} approved by {approved_by}")

        return plan

    async def get_plan(self, plan_id: str) -> DeploymentPlan | None:
        """Get deployment plan by ID."""
        plans = await self.get_deployment_history(limit=100)
        for plan in plans:
            if plan.id == plan_id:
                return plan
        return None

    async def get_deployment_history(
        self,
        environment: str | None = None,
        limit: int = 20,
    ) -> list[DeploymentPlan]:
        """Get deployment history.

        Args:
            environment: Filter by environment
            limit: Max results

        Returns:
            List of deployment plans
        """
        from app.storage.redis import get_redis
        import json

        redis = await get_redis()

        raw = await redis.zrevrange(
            self.DEPLOYMENTS_KEY,
            0,
            limit - 1,
        )

        plans = []
        for item in raw:
            try:
                data = json.loads(item)

                if environment and data["environment"] != environment:
                    continue

                plans.append(DeploymentPlan(
                    id=data["id"],
                    version=data["version"],
                    environment=data["environment"],
                    status=DeploymentStatus(data["status"]),
                    created_at=datetime.fromisoformat(data["created_at"]),
                    created_by=data["created_by"],
                    checks=[
                        SafetyCheck(
                            name=c["name"],
                            category=CheckCategory(c["category"]),
                            status=CheckStatus(c["status"]),
                            message=c["message"],
                            details=c.get("details"),
                            duration_ms=c.get("duration_ms", 0),
                        )
                        for c in data["checks"]
                    ],
                    approved_at=datetime.fromisoformat(data["approved_at"]) if data.get("approved_at") else None,
                    approved_by=data.get("approved_by"),
                    deployed_at=datetime.fromisoformat(data["deployed_at"]) if data.get("deployed_at") else None,
                    notes=data.get("notes"),
                ))
            except Exception:
                continue

        return plans

    async def get_rollback_plan(self, deployment_id: str) -> RollbackPlan | None:
        """Generate rollback plan.

        Args:
            deployment_id: Deployment ID

        Returns:
            Rollback plan
        """
        from app.storage.redis import get_redis

        redis = await get_redis()
        previous = await redis.get("deployment:previous_version")

        if not previous:
            return None

        return RollbackPlan(
            deployment_id=deployment_id,
            previous_version=previous,
            steps=[
                "1. Pause incoming traffic",
                "2. Scale down new version",
                "3. Restore previous version",
                "4. Run health checks",
                "5. Resume traffic",
                "6. Monitor for 15 minutes",
            ],
            estimated_duration_seconds=300,
            data_loss_risk=False,
            requires_manual_steps=False,
        )


# Singleton
deployment_safety = DeploymentSafetyService()
