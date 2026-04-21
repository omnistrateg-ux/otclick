"""Tests for Round 6 Services.

Security, Config, Backup, Health, Jobs, Admin Ops, Data Retention.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

UTC = timezone.utc


# ============================================================================
# Security Service Tests
# ============================================================================


class TestSecurityService:
    """Tests for SecurityService."""

    def test_threat_level_enum_values(self):
        """Test ThreatLevel enum values."""
        from app.services.security import ThreatLevel

        assert ThreatLevel.NONE.value == "none"
        assert ThreatLevel.LOW.value == "low"
        assert ThreatLevel.CRITICAL.value == "critical"

    def test_security_event_type_enum_values(self):
        """Test SecurityEventType enum values."""
        from app.services.security import SecurityEventType

        assert SecurityEventType.INVALID_INPUT.value == "invalid_input"
        assert SecurityEventType.INJECTION_ATTEMPT.value == "injection_attempt"
        assert SecurityEventType.IP_BLOCKED.value == "ip_blocked"

    def test_validate_email_valid(self):
        """Test email validation with valid email."""
        from app.services.security import SecurityService

        service = SecurityService()
        result = service.validate_email("test@example.com")

        assert result.valid is True
        assert result.sanitized_value == "test@example.com"

    def test_validate_email_invalid(self):
        """Test email validation with invalid email."""
        from app.services.security import SecurityService

        service = SecurityService()
        result = service.validate_email("invalid-email")

        assert result.valid is False
        assert len(result.errors) > 0

    def test_validate_phone_valid(self):
        """Test phone validation with valid phone."""
        from app.services.security import SecurityService

        service = SecurityService()
        result = service.validate_phone("+79261234567")

        assert result.valid is True

    def test_validate_text_with_injection(self):
        """Test text validation detects injection."""
        from app.services.security import SecurityService

        service = SecurityService()
        result = service.validate_text("<script>alert('xss')</script>")

        assert result.valid is False
        assert result.threat_detected is True

    def test_generate_secure_token(self):
        """Test secure token generation."""
        from app.services.security import SecurityService

        service = SecurityService()
        token = service.generate_secure_token(32)

        assert len(token) == 64  # Hex encoded
        assert token.isalnum()

    def test_hash_sensitive_data(self):
        """Test hashing sensitive data."""
        from app.services.security import SecurityService

        service = SecurityService()
        hash1 = service.hash_sensitive_data("password123")
        hash2 = service.hash_sensitive_data("password123")

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256

    def test_verify_signature(self):
        """Test HMAC signature verification."""
        from app.services.security import SecurityService
        import hmac
        import hashlib

        service = SecurityService()
        payload = "test payload"
        secret = "secret_key"

        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        assert service.verify_signature(payload, signature, secret) is True
        assert service.verify_signature(payload, "wrong", secret) is False


# ============================================================================
# Config Validation Tests
# ============================================================================


class TestConfigValidationService:
    """Tests for ConfigValidationService."""

    def test_config_status_enum_values(self):
        """Test ConfigStatus enum values."""
        from app.services.config_validation import ConfigStatus

        assert ConfigStatus.OK.value == "ok"
        assert ConfigStatus.WARNING.value == "warning"
        assert ConfigStatus.ERROR.value == "error"
        assert ConfigStatus.MISSING.value == "missing"

    def test_config_category_enum_values(self):
        """Test ConfigCategory enum values."""
        from app.services.config_validation import ConfigCategory

        assert ConfigCategory.DATABASE.value == "database"
        assert ConfigCategory.REDIS.value == "redis"
        assert ConfigCategory.API_KEYS.value == "api_keys"

    def test_validate_all(self):
        """Test validate_all returns result."""
        from app.services.config_validation import ConfigValidationService

        service = ConfigValidationService()
        result = service.validate_all()

        assert result is not None
        assert hasattr(result, "valid")
        assert hasattr(result, "checks")
        assert result.total_checks > 0

    def test_get_config_summary(self):
        """Test get_config_summary returns summary."""
        from app.services.config_validation import ConfigValidationService

        service = ConfigValidationService()
        summary = service.get_config_summary()

        assert "valid" in summary
        assert "total_checks" in summary
        assert "by_category" in summary


# ============================================================================
# Backup Recovery Tests
# ============================================================================


class TestBackupRecoveryService:
    """Tests for BackupRecoveryService."""

    def test_backup_type_enum_values(self):
        """Test BackupType enum values."""
        from app.services.backup_recovery import BackupType

        assert BackupType.FULL.value == "full"
        assert BackupType.LEADS.value == "leads"
        assert BackupType.CONFIG.value == "config"

    def test_backup_status_enum_values(self):
        """Test BackupStatus enum values."""
        from app.services.backup_recovery import BackupStatus

        assert BackupStatus.PENDING.value == "pending"
        assert BackupStatus.COMPLETED.value == "completed"
        assert BackupStatus.FAILED.value == "failed"

    def test_backup_metadata_to_dict(self):
        """Test BackupMetadata.to_dict()."""
        from app.services.backup_recovery import BackupMetadata, BackupType, BackupStatus

        now = datetime.now(UTC)
        metadata = BackupMetadata(
            id="backup-1",
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            created_at=now,
            completed_at=now,
            size_bytes=1024,
            record_count=100,
            filename="backup.json.gz",
        )

        d = metadata.to_dict()

        assert d["id"] == "backup-1"
        assert d["backup_type"] == "full"
        assert d["status"] == "completed"
        assert d["size_bytes"] == 1024

    @pytest.mark.asyncio
    async def test_list_backups(self):
        """Test listing backups."""
        from app.services.backup_recovery import BackupRecoveryService

        mock_redis = AsyncMock()
        mock_redis.zrevrange = AsyncMock(return_value=[])

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = BackupRecoveryService()
            backups = await service.list_backups()

        assert isinstance(backups, list)


# ============================================================================
# Health Diagnostics Tests
# ============================================================================


class TestHealthDiagnosticsService:
    """Tests for HealthDiagnosticsService."""

    def test_health_status_enum_values(self):
        """Test HealthStatus enum values."""
        from app.services.health_diagnostics import HealthStatus

        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_alert_severity_enum_values(self):
        """Test AlertSeverity enum values."""
        from app.services.health_diagnostics import AlertSeverity

        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_alert_to_dict(self):
        """Test Alert.to_dict()."""
        from app.services.health_diagnostics import Alert, AlertType, AlertSeverity

        now = datetime.now(UTC)
        alert = Alert(
            id="alert-1",
            alert_type=AlertType.SLA_BREACH,
            severity=AlertSeverity.ERROR,
            title="SLA Breach",
            message="Handoff response time exceeded",
            created_at=now,
        )

        d = alert.to_dict()

        assert d["id"] == "alert-1"
        assert d["alert_type"] == "sla_breach"
        assert d["severity"] == "error"
        assert d["acknowledged"] is False

    def test_sla_definitions_exist(self):
        """Test SLA definitions are defined."""
        from app.services.health_diagnostics import SLA_DEFINITIONS

        assert len(SLA_DEFINITIONS) > 0
        assert any(s["name"] == "handoff_response_time" for s in SLA_DEFINITIONS)

    @pytest.mark.asyncio
    async def test_check_system_health(self):
        """Test checking system health."""
        from app.services.health_diagnostics import HealthDiagnosticsService

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.info = AsyncMock(return_value={"used_memory": 1024})
        mock_redis.llen = AsyncMock(return_value=0)

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = HealthDiagnosticsService()
            health = await service.check_system_health()

        assert health is not None
        assert len(health.components) > 0


# ============================================================================
# Job Management Tests
# ============================================================================


class TestJobManagementService:
    """Tests for JobManagementService."""

    def test_job_status_enum_values(self):
        """Test JobStatus enum values."""
        from app.services.job_management import JobStatus

        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.RETRYING.value == "retrying"

    def test_job_type_enum_values(self):
        """Test JobType enum values."""
        from app.services.job_management import JobType

        assert JobType.ENRICHMENT.value == "enrichment"
        assert JobType.EMAIL_SEND.value == "email_send"
        assert JobType.BACKUP.value == "backup"

    def test_failed_job_to_dict(self):
        """Test FailedJob.to_dict()."""
        from app.services.job_management import FailedJob, JobType, JobStatus

        now = datetime.now(UTC)
        job = FailedJob(
            id="job-1",
            job_type=JobType.ENRICHMENT,
            status=JobStatus.FAILED,
            created_at=now,
            failed_at=now,
            retry_count=1,
            max_retries=3,
            error_message="Connection timeout",
            error_traceback=None,
            payload={"lead_id": "123"},
        )

        d = job.to_dict()

        assert d["id"] == "job-1"
        assert d["job_type"] == "enrichment"
        assert d["retry_count"] == 1
        assert d["can_retry"] is True

    @pytest.mark.asyncio
    async def test_get_failed_jobs(self):
        """Test getting failed jobs."""
        from app.services.job_management import JobManagementService

        mock_redis = AsyncMock()
        mock_redis.zrevrangebyscore = AsyncMock(return_value=[])

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = JobManagementService()
            jobs = await service.get_failed_jobs()

        assert isinstance(jobs, list)

    @pytest.mark.asyncio
    async def test_get_job_stats(self):
        """Test getting job statistics."""
        from app.services.job_management import JobManagementService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="0")
        mock_redis.llen = AsyncMock(return_value=0)
        mock_redis.zrevrangebyscore = AsyncMock(return_value=[])

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = JobManagementService()
            stats = await service.get_job_stats(hours=24)

        assert stats.period_hours == 24
        assert hasattr(stats, "success_rate")


# ============================================================================
# Admin Ops Tests
# ============================================================================


class TestAdminOpsService:
    """Tests for AdminOpsService."""

    def test_override_type_enum_values(self):
        """Test OverrideType enum values."""
        from app.services.admin_ops import OverrideType

        assert OverrideType.STATUS_CHANGE.value == "status_change"
        assert OverrideType.SCORE_OVERRIDE.value == "score_override"
        assert OverrideType.FORCE_TRANSITION.value == "force_transition"

    def test_admin_action_type_enum_values(self):
        """Test AdminActionType enum values."""
        from app.services.admin_ops import AdminActionType

        assert AdminActionType.OVERRIDE.value == "override"
        assert AdminActionType.CLEANUP.value == "cleanup"
        assert AdminActionType.PURGE.value == "purge"

    def test_admin_action_to_dict(self):
        """Test AdminAction.to_dict()."""
        from app.services.admin_ops import AdminAction, AdminActionType, OverrideType

        now = datetime.now(UTC)
        action = AdminAction(
            id="action-1",
            action_type=AdminActionType.OVERRIDE,
            override_type=OverrideType.STATUS_CHANGE,
            actor="admin@example.com",
            target_type="lead",
            target_id="lead-1",
            description="Status override",
            before_state={"status": "new"},
            after_state={"status": "qualified"},
            performed_at=now,
            reason="Manual qualification",
        )

        d = action.to_dict()

        assert d["id"] == "action-1"
        assert d["action_type"] == "override"
        assert d["override_type"] == "status_change"
        assert d["reversible"] is True

    @pytest.mark.asyncio
    async def test_get_admin_actions(self):
        """Test getting admin actions."""
        from app.services.admin_ops import AdminOpsService

        mock_redis = AsyncMock()
        mock_redis.zrevrangebyscore = AsyncMock(return_value=[])

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = AdminOpsService()
            actions = await service.get_admin_actions()

        assert isinstance(actions, list)

    @pytest.mark.asyncio
    async def test_get_system_overview(self):
        """Test getting system overview."""
        from app.services.admin_ops import AdminOpsService

        async def mock_scan_iter(pattern):
            return
            yield

        mock_redis = AsyncMock()
        mock_redis.scan_iter = mock_scan_iter
        mock_redis.info = AsyncMock(return_value={"used_memory": 1024})
        mock_redis.zrevrangebyscore = AsyncMock(return_value=[])

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = AdminOpsService()
            overview = await service.get_system_overview()

        assert "timestamp" in overview
        assert "counts" in overview


# ============================================================================
# Data Retention Tests
# ============================================================================


class TestDataRetentionService:
    """Tests for DataRetentionService."""

    def test_data_category_enum_values(self):
        """Test DataCategory enum values."""
        from app.services.data_retention import DataCategory

        assert DataCategory.LEADS.value == "leads"
        assert DataCategory.AUDIT_LOGS.value == "audit_logs"
        assert DataCategory.TEMP_DATA.value == "temp_data"

    def test_retention_action_enum_values(self):
        """Test RetentionAction enum values."""
        from app.services.data_retention import RetentionAction

        assert RetentionAction.DELETE.value == "delete"
        assert RetentionAction.ARCHIVE.value == "archive"
        assert RetentionAction.ANONYMIZE.value == "anonymize"

    def test_default_policies_loaded(self):
        """Test default policies are loaded."""
        from app.services.data_retention import DataRetentionService, DataCategory

        service = DataRetentionService()
        policies = service.get_all_policies()

        assert len(policies) > 0
        assert any(p.category == DataCategory.AUDIT_LOGS for p in policies)

    def test_get_policy(self):
        """Test getting a policy."""
        from app.services.data_retention import DataRetentionService, DataCategory

        service = DataRetentionService()
        policy = service.get_policy(DataCategory.AUDIT_LOGS)

        assert policy is not None
        assert policy.retention_days == 365

    def test_retention_policy_to_dict(self):
        """Test RetentionPolicy.to_dict()."""
        from app.services.data_retention import RetentionPolicy, DataCategory, RetentionAction

        policy = RetentionPolicy(
            category=DataCategory.LEADS,
            retention_days=180,
            action=RetentionAction.ARCHIVE,
            enabled=True,
        )

        d = policy.to_dict()

        assert d["category"] == "leads"
        assert d["retention_days"] == 180
        assert d["action"] == "archive"

    @pytest.mark.asyncio
    async def test_get_storage_stats(self):
        """Test getting storage stats."""
        from app.services.data_retention import DataRetentionService

        async def mock_scan_iter(pattern):
            return
            yield

        mock_redis = AsyncMock()
        mock_redis.info = AsyncMock(return_value={"used_memory": 1024, "used_memory_peak": 2048})
        mock_redis.scan_iter = mock_scan_iter

        with patch("app.storage.redis.get_redis", return_value=mock_redis):
            service = DataRetentionService()
            stats = await service.get_storage_stats()

        assert "used_memory_mb" in stats
        assert "policies" in stats
