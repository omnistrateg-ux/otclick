"""Operations API endpoints.

Health, security, backup, jobs, admin operations.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.security import (
    SecurityService,
    SecurityEventType,
    ThreatLevel,
)
from app.services.config_validation import ConfigValidationService, ConfigCategory
from app.services.backup_recovery import BackupRecoveryService, BackupType
from app.services.health_diagnostics import (
    HealthDiagnosticsService,
    ComponentType,
    AlertType,
    AlertSeverity,
)
from app.services.job_management import JobManagementService, JobType
from app.services.admin_ops import AdminOpsService
from app.services.data_retention import DataRetentionService, DataCategory, RetentionAction
from app.services.postgres_diagnostics import PostgresDiagnosticsService
from app.services.worker_health import WorkerHealthService
from app.services.maintenance_mode import MaintenanceModeService, SystemState
from app.services.ops_journal import OpsJournalService, JournalCategory, JournalSeverity
from app.services.recovery_runbooks import RecoveryRunbooksService, RunbookCategory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["ops"])


# ============================================================================
# Request/Response Models
# ============================================================================


class BlockIPRequest(BaseModel):
    """Block IP request."""

    ip: str
    reason: str
    duration_hours: int = 24
    actor: str = "admin"


class CreateAlertRequest(BaseModel):
    """Create alert request."""

    alert_type: str
    severity: str
    title: str
    message: str
    metadata: dict[str, Any] | None = None


class RetryJobRequest(BaseModel):
    """Retry job request."""

    actor: str = "admin"


class OverrideStatusRequest(BaseModel):
    """Override status request."""

    new_status: str
    actor: str
    reason: str


class OverrideScoreRequest(BaseModel):
    """Override score request."""

    new_score: float
    actor: str
    reason: str


class ReassignHandoffRequest(BaseModel):
    """Reassign handoff request."""

    new_assignee: str
    actor: str
    reason: str


class UnblockLeadRequest(BaseModel):
    """Unblock lead request."""

    actor: str
    reason: str


class BulkStatusRequest(BaseModel):
    """Bulk status update request."""

    lead_ids: list[str]
    new_status: str
    actor: str
    reason: str


class UpdatePolicyRequest(BaseModel):
    """Update retention policy request."""

    retention_days: int | None = None
    action: str | None = None
    enabled: bool | None = None


class CreateBackupRequest(BaseModel):
    """Create backup request."""

    backup_type: str = "full"
    compress: bool = True


class RestoreBackupRequest(BaseModel):
    """Restore backup request."""

    overwrite: bool = False


class EnterMaintenanceRequest(BaseModel):
    """Enter maintenance mode request."""

    reason: str
    actor: str
    drain_connections: bool = True
    notify: bool = True


class ExitMaintenanceRequest(BaseModel):
    """Exit maintenance mode request."""

    actor: str


class ScheduleMaintenanceRequest(BaseModel):
    """Schedule maintenance window request."""

    reason: str
    scheduled_by: str
    start_time: str  # ISO format
    end_time: str | None = None
    affected_services: list[str] = []
    notify_users: bool = True
    auto_recover: bool = True


class ExecuteRunbookRequest(BaseModel):
    """Execute runbook request."""

    actor: str
    dry_run: bool = False


# ============================================================================
# Health Endpoints
# ============================================================================


@router.get("/health")
async def get_system_health() -> dict[str, Any]:
    """Get system health status.

    Returns:
        System health
    """
    service = HealthDiagnosticsService()
    health = await service.check_system_health()
    return health.to_dict()


@router.get("/health/{component}")
async def get_component_health(
    component: str,
) -> dict[str, Any]:
    """Get health of specific component.

    Args:
        component: Component type

    Returns:
        Component health
    """
    service = HealthDiagnosticsService()

    try:
        comp_type = ComponentType(component)
    except ValueError:
        valid = [c.value for c in ComponentType]
        raise HTTPException(400, f"Invalid component. Valid: {valid}")

    health = await service.check_component(comp_type)
    return health.to_dict()


@router.get("/config/validate")
async def validate_config() -> dict[str, Any]:
    """Validate all configuration.

    Returns:
        Validation result
    """
    service = ConfigValidationService()
    result = service.validate_all()
    return result.to_dict()


@router.get("/config/summary")
async def get_config_summary() -> dict[str, Any]:
    """Get configuration summary.

    Returns:
        Config summary
    """
    service = ConfigValidationService()
    return service.get_config_summary()


# ============================================================================
# SLA and Alerts
# ============================================================================


@router.get("/sla")
async def get_sla_status() -> list[dict[str, Any]]:
    """Get SLA metrics status.

    Returns:
        List of SLA metrics
    """
    service = HealthDiagnosticsService()
    metrics = await service.get_sla_status()
    return [m.to_dict() for m in metrics]


@router.post("/sla/check-breaches")
async def check_sla_breaches() -> list[dict[str, Any]]:
    """Check for SLA breaches.

    Returns:
        List of breach alerts
    """
    service = HealthDiagnosticsService()
    alerts = await service.check_sla_breaches()
    return [a.to_dict() for a in alerts]


@router.get("/alerts")
async def get_active_alerts(
    severity: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get active alerts.

    Args:
        severity: Filter by severity
        limit: Max results

    Returns:
        List of alerts
    """
    service = HealthDiagnosticsService()

    sev = None
    if severity:
        try:
            sev = AlertSeverity(severity)
        except ValueError:
            valid = [s.value for s in AlertSeverity]
            raise HTTPException(400, f"Invalid severity. Valid: {valid}")

    alerts = await service.get_active_alerts(severity=sev, limit=limit)
    return [a.to_dict() for a in alerts]


@router.post("/alerts")
async def create_alert(
    request: CreateAlertRequest,
) -> dict[str, Any]:
    """Create a new alert.

    Args:
        request: Alert request

    Returns:
        Created alert
    """
    service = HealthDiagnosticsService()

    try:
        alert_type = AlertType(request.alert_type)
    except ValueError:
        valid = [t.value for t in AlertType]
        raise HTTPException(400, f"Invalid alert type. Valid: {valid}")

    try:
        severity = AlertSeverity(request.severity)
    except ValueError:
        valid = [s.value for s in AlertSeverity]
        raise HTTPException(400, f"Invalid severity. Valid: {valid}")

    alert = await service.create_alert(
        alert_type=alert_type,
        severity=severity,
        title=request.title,
        message=request.message,
        metadata=request.metadata,
    )

    return alert.to_dict()


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str,
) -> dict[str, Any]:
    """Acknowledge an alert.

    Args:
        alert_id: Alert ID
        acknowledged_by: User acknowledging

    Returns:
        Updated alert
    """
    service = HealthDiagnosticsService()
    alert = await service.acknowledge_alert(alert_id, acknowledged_by)

    if not alert:
        raise HTTPException(404, f"Alert {alert_id} not found")

    return alert.to_dict()


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
) -> dict[str, Any]:
    """Resolve an alert.

    Args:
        alert_id: Alert ID

    Returns:
        Updated alert
    """
    service = HealthDiagnosticsService()
    alert = await service.resolve_alert(alert_id)

    if not alert:
        raise HTTPException(404, f"Alert {alert_id} not found")

    return alert.to_dict()


@router.get("/alerts/unacknowledged/count")
async def get_unacknowledged_count() -> dict[str, int]:
    """Get count of unacknowledged alerts.

    Returns:
        Count
    """
    service = HealthDiagnosticsService()
    count = await service.get_unacknowledged_count()
    return {"count": count}


# ============================================================================
# Security
# ============================================================================


@router.get("/security/events")
async def get_security_events(
    hours: int = Query(default=24, ge=1, le=168),
    event_type: str = Query(default=None),
    min_threat_level: str = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Get security events.

    Args:
        hours: Hours to look back
        event_type: Filter by type
        min_threat_level: Minimum threat level
        limit: Max results

    Returns:
        List of events
    """
    service = SecurityService()

    et = None
    if event_type:
        try:
            et = SecurityEventType(event_type)
        except ValueError:
            valid = [t.value for t in SecurityEventType]
            raise HTTPException(400, f"Invalid event type. Valid: {valid}")

    mtl = None
    if min_threat_level:
        try:
            mtl = ThreatLevel(min_threat_level)
        except ValueError:
            valid = [l.value for l in ThreatLevel]
            raise HTTPException(400, f"Invalid threat level. Valid: {valid}")

    events = await service.get_security_events(
        hours=hours,
        event_type=et,
        min_threat_level=mtl,
        limit=limit,
    )

    return [e.to_dict() for e in events]


@router.post("/security/block-ip")
async def block_ip(
    request: BlockIPRequest,
) -> dict[str, str]:
    """Block an IP address.

    Args:
        request: Block request

    Returns:
        Success message
    """
    service = SecurityService()

    await service.block_ip(
        ip=request.ip,
        reason=request.reason,
        duration_hours=request.duration_hours,
        actor=request.actor,
    )

    return {"message": f"IP {request.ip} blocked for {request.duration_hours} hours"}


@router.delete("/security/block-ip/{ip}")
async def unblock_ip(
    ip: str,
    actor: str = Query(default="admin"),
) -> dict[str, str]:
    """Unblock an IP address.

    Args:
        ip: IP to unblock
        actor: Who unblocked

    Returns:
        Success message
    """
    service = SecurityService()
    await service.unblock_ip(ip, actor)
    return {"message": f"IP {ip} unblocked"}


@router.get("/security/blocked-ip/{ip}")
async def check_ip_blocked(
    ip: str,
) -> dict[str, bool]:
    """Check if IP is blocked.

    Args:
        ip: IP to check

    Returns:
        Blocked status
    """
    service = SecurityService()
    blocked = await service.is_ip_blocked(ip)
    return {"blocked": blocked}


# ============================================================================
# Jobs
# ============================================================================


@router.get("/jobs/failed")
async def get_failed_jobs(
    job_type: str = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get failed jobs.

    Args:
        job_type: Filter by type
        hours: Hours to look back
        limit: Max results

    Returns:
        List of failed jobs
    """
    service = JobManagementService()

    jt = None
    if job_type:
        try:
            jt = JobType(job_type)
        except ValueError:
            valid = [t.value for t in JobType]
            raise HTTPException(400, f"Invalid job type. Valid: {valid}")

    jobs = await service.get_failed_jobs(job_type=jt, hours=hours, limit=limit)
    return [j.to_dict() for j in jobs]


@router.get("/jobs/failed/{job_id}")
async def get_failed_job(
    job_id: str,
) -> dict[str, Any]:
    """Get failed job by ID.

    Args:
        job_id: Job ID

    Returns:
        Job details
    """
    service = JobManagementService()
    job = await service.get_failed_job(job_id)

    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    return job.to_dict()


@router.post("/jobs/failed/{job_id}/retry")
async def retry_job(
    job_id: str,
    request: RetryJobRequest,
) -> dict[str, Any]:
    """Retry a failed job.

    Args:
        job_id: Job ID
        request: Retry request

    Returns:
        Retry result
    """
    service = JobManagementService()
    result = await service.retry_job(job_id, request.actor)
    return result.to_dict()


@router.post("/jobs/failed/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    actor: str = Query(default="admin"),
) -> dict[str, bool]:
    """Cancel a failed job.

    Args:
        job_id: Job ID
        actor: Who cancelled

    Returns:
        Success status
    """
    service = JobManagementService()
    success = await service.cancel_job(job_id, actor)

    if not success:
        raise HTTPException(404, f"Job {job_id} not found")

    return {"cancelled": True}


@router.post("/jobs/retry-all")
async def retry_all_failed(
    job_type: str = Query(default=None),
    actor: str = Query(default="admin"),
) -> dict[str, Any]:
    """Retry all failed jobs.

    Args:
        job_type: Filter by type
        actor: Who initiated

    Returns:
        Retry summary
    """
    service = JobManagementService()

    jt = None
    if job_type:
        try:
            jt = JobType(job_type)
        except ValueError:
            valid = [t.value for t in JobType]
            raise HTTPException(400, f"Invalid job type. Valid: {valid}")

    return await service.retry_all_failed(job_type=jt, actor=actor)


@router.get("/jobs/stats")
async def get_job_stats(
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    """Get job statistics.

    Args:
        hours: Hours to analyze

    Returns:
        Job stats
    """
    service = JobManagementService()
    stats = await service.get_job_stats(hours)
    return stats.to_dict()


@router.get("/jobs/errors")
async def get_error_summary(
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[dict[str, Any]]:
    """Get error summary.

    Args:
        hours: Hours to analyze
        limit: Max results

    Returns:
        Error summary
    """
    service = JobManagementService()
    return await service.get_error_summary(hours, limit)


# ============================================================================
# Admin Operations
# ============================================================================


@router.post("/admin/leads/{lead_id}/override-status")
async def override_lead_status(
    lead_id: str,
    request: OverrideStatusRequest,
) -> dict[str, Any]:
    """Override lead status.

    Args:
        lead_id: Lead ID
        request: Override request

    Returns:
        Admin action
    """
    service = AdminOpsService()

    try:
        action = await service.override_lead_status(
            lead_id=lead_id,
            new_status=request.new_status,
            actor=request.actor,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    return action.to_dict()


@router.post("/admin/leads/{lead_id}/override-score")
async def override_lead_score(
    lead_id: str,
    request: OverrideScoreRequest,
) -> dict[str, Any]:
    """Override lead score.

    Args:
        lead_id: Lead ID
        request: Override request

    Returns:
        Admin action
    """
    service = AdminOpsService()

    try:
        action = await service.override_lead_score(
            lead_id=lead_id,
            new_score=request.new_score,
            actor=request.actor,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    return action.to_dict()


@router.post("/admin/leads/{lead_id}/unblock")
async def unblock_lead(
    lead_id: str,
    request: UnblockLeadRequest,
) -> dict[str, Any]:
    """Unblock a stuck lead.

    Args:
        lead_id: Lead ID
        request: Unblock request

    Returns:
        Admin action
    """
    service = AdminOpsService()

    try:
        action = await service.unblock_lead(
            lead_id=lead_id,
            actor=request.actor,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    return action.to_dict()


@router.post("/admin/handoffs/{handoff_id}/reassign")
async def force_reassign_handoff(
    handoff_id: str,
    request: ReassignHandoffRequest,
) -> dict[str, Any]:
    """Force reassign a handoff.

    Args:
        handoff_id: Handoff ID
        request: Reassign request

    Returns:
        Admin action
    """
    service = AdminOpsService()

    try:
        action = await service.force_handoff_assignment(
            handoff_id=handoff_id,
            new_assignee=request.new_assignee,
            actor=request.actor,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    return action.to_dict()


@router.post("/admin/leads/bulk-status")
async def bulk_update_status(
    request: BulkStatusRequest,
) -> dict[str, Any]:
    """Bulk update lead statuses.

    Args:
        request: Bulk update request

    Returns:
        Update summary
    """
    service = AdminOpsService()
    return await service.bulk_status_update(
        lead_ids=request.lead_ids,
        new_status=request.new_status,
        actor=request.actor,
        reason=request.reason,
    )


@router.delete("/admin/leads/{lead_id}")
async def purge_lead(
    lead_id: str,
    actor: str = Query(...),
    reason: str = Query(...),
) -> dict[str, Any]:
    """Permanently delete a lead.

    Args:
        lead_id: Lead ID
        actor: Who deleted
        reason: Reason for deletion

    Returns:
        Admin action
    """
    service = AdminOpsService()

    try:
        action = await service.purge_lead(lead_id, actor, reason)
    except ValueError as e:
        raise HTTPException(404, str(e))

    return action.to_dict()


@router.get("/admin/actions")
async def get_admin_actions(
    actor: str = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get admin actions.

    Args:
        actor: Filter by actor
        hours: Hours to look back
        limit: Max results

    Returns:
        List of actions
    """
    service = AdminOpsService()
    actions = await service.get_admin_actions(actor=actor, hours=hours, limit=limit)
    return [a.to_dict() for a in actions]


@router.get("/admin/overview")
async def get_system_overview() -> dict[str, Any]:
    """Get system overview.

    Returns:
        System overview
    """
    service = AdminOpsService()
    return await service.get_system_overview()


# ============================================================================
# Backup and Recovery
# ============================================================================


@router.post("/backup")
async def create_backup(
    request: CreateBackupRequest,
) -> dict[str, Any]:
    """Create a backup.

    Args:
        request: Backup request

    Returns:
        Backup metadata
    """
    service = BackupRecoveryService()

    try:
        backup_type = BackupType(request.backup_type)
    except ValueError:
        valid = [t.value for t in BackupType]
        raise HTTPException(400, f"Invalid backup type. Valid: {valid}")

    backup = await service.create_backup(backup_type, request.compress)
    return backup.to_dict()


@router.get("/backup")
async def list_backups(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """List backups.

    Args:
        limit: Max results

    Returns:
        List of backups
    """
    service = BackupRecoveryService()
    backups = await service.list_backups(limit)
    return [b.to_dict() for b in backups]


@router.get("/backup/{backup_id}")
async def get_backup(
    backup_id: str,
) -> dict[str, Any]:
    """Get backup by ID.

    Args:
        backup_id: Backup ID

    Returns:
        Backup metadata
    """
    service = BackupRecoveryService()
    backup = await service.get_backup(backup_id)

    if not backup:
        raise HTTPException(404, f"Backup {backup_id} not found")

    return backup.to_dict()


@router.post("/backup/{backup_id}/restore")
async def restore_backup(
    backup_id: str,
    request: RestoreBackupRequest,
) -> dict[str, Any]:
    """Restore from backup.

    Args:
        backup_id: Backup ID
        request: Restore request

    Returns:
        Restore result
    """
    service = BackupRecoveryService()
    result = await service.restore_backup(backup_id, request.overwrite)
    return result.to_dict()


@router.delete("/backup/{backup_id}")
async def delete_backup(
    backup_id: str,
) -> dict[str, bool]:
    """Delete a backup.

    Args:
        backup_id: Backup ID

    Returns:
        Success status
    """
    service = BackupRecoveryService()
    success = await service.delete_backup(backup_id)

    if not success:
        raise HTTPException(404, f"Backup {backup_id} not found")

    return {"deleted": True}


# ============================================================================
# Data Retention
# ============================================================================


@router.get("/retention/policies")
async def get_retention_policies() -> list[dict[str, Any]]:
    """Get all retention policies.

    Returns:
        List of policies
    """
    service = DataRetentionService()
    policies = service.get_all_policies()
    return [p.to_dict() for p in policies]


@router.put("/retention/policies/{category}")
async def update_retention_policy(
    category: str,
    request: UpdatePolicyRequest,
) -> dict[str, Any]:
    """Update a retention policy.

    Args:
        category: Data category
        request: Update request

    Returns:
        Updated policy
    """
    service = DataRetentionService()

    try:
        cat = DataCategory(category)
    except ValueError:
        valid = [c.value for c in DataCategory]
        raise HTTPException(400, f"Invalid category. Valid: {valid}")

    action = None
    if request.action:
        try:
            action = RetentionAction(request.action)
        except ValueError:
            valid = [a.value for a in RetentionAction]
            raise HTTPException(400, f"Invalid action. Valid: {valid}")

    policy = await service.update_policy(
        category=cat,
        retention_days=request.retention_days,
        action=action,
        enabled=request.enabled,
    )

    return policy.to_dict()


@router.post("/retention/run")
async def run_retention(
    categories: str = Query(default=None),
    dry_run: bool = Query(default=True),
) -> dict[str, Any]:
    """Run data retention.

    Args:
        categories: Comma-separated categories
        dry_run: Don't actually delete

    Returns:
        Retention report
    """
    service = DataRetentionService()

    cat_list = None
    if categories:
        cat_list = []
        for cat in categories.split(","):
            try:
                cat_list.append(DataCategory(cat.strip()))
            except ValueError:
                valid = [c.value for c in DataCategory]
                raise HTTPException(400, f"Invalid category: {cat}. Valid: {valid}")

    report = await service.run_retention(categories=cat_list, dry_run=dry_run)
    return report.to_dict()


@router.get("/retention/reports")
async def get_retention_reports(
    limit: int = Query(default=10, ge=1, le=50),
) -> list[dict[str, Any]]:
    """Get recent retention reports.

    Args:
        limit: Max results

    Returns:
        List of reports
    """
    service = DataRetentionService()
    reports = await service.get_recent_reports(limit)
    return [r.to_dict() for r in reports]


@router.get("/retention/storage")
async def get_storage_stats() -> dict[str, Any]:
    """Get storage statistics.

    Returns:
        Storage stats
    """
    service = DataRetentionService()
    return await service.get_storage_stats()


# ============================================================================
# Reference Data
# ============================================================================


@router.get("/job-types")
async def get_job_types() -> list[dict[str, str]]:
    """Get all job types."""
    return [{"type": t.value} for t in JobType]


@router.get("/backup-types")
async def get_backup_types() -> list[dict[str, str]]:
    """Get all backup types."""
    return [{"type": t.value} for t in BackupType]


@router.get("/data-categories")
async def get_data_categories() -> list[dict[str, str]]:
    """Get all data categories."""
    return [{"category": c.value} for c in DataCategory]


# ============================================================================
# PostgreSQL Diagnostics (Round 7)
# ============================================================================


@router.get("/postgres/diagnostics")
async def get_postgres_diagnostics() -> dict[str, Any]:
    """Get full PostgreSQL diagnostics.

    Returns:
        PostgreSQL diagnostics
    """
    service = PostgresDiagnosticsService()
    diagnostics = await service.get_full_diagnostics()
    return diagnostics.to_dict()


@router.get("/postgres/connection")
async def check_postgres_connection() -> dict[str, Any]:
    """Quick PostgreSQL connection check.

    Returns:
        Connection status
    """
    service = PostgresDiagnosticsService()
    return await service.check_connection()


@router.get("/postgres/health-score")
async def get_postgres_health_score() -> dict[str, Any]:
    """Get PostgreSQL health score.

    Returns:
        Health score and factors
    """
    service = PostgresDiagnosticsService()
    return await service.get_health_score()


# ============================================================================
# Redis/Celery Worker Health (Round 7)
# ============================================================================


@router.get("/workers/health")
async def get_worker_health() -> dict[str, Any]:
    """Get Celery worker health.

    Returns:
        Worker health status
    """
    service = WorkerHealthService()
    health = await service.get_celery_health()
    return health.to_dict()


@router.get("/workers/redis")
async def get_redis_health() -> dict[str, Any]:
    """Get Redis health.

    Returns:
        Redis health status
    """
    service = WorkerHealthService()
    health = await service.get_redis_health()
    return health.to_dict()


@router.get("/workers/queues")
async def get_queue_health(
    queue: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get queue statistics.

    Args:
        queue: Filter by queue name

    Returns:
        Queue stats
    """
    service = WorkerHealthService()
    health = await service.get_celery_health()

    if queue:
        return [q.to_dict() for q in health.queues if q.name == queue]
    return [q.to_dict() for q in health.queues]


@router.get("/workers/dlq")
async def get_dlq_status() -> dict[str, Any]:
    """Get dead letter queue status.

    Returns:
        DLQ stats
    """
    service = WorkerHealthService()
    health = await service.get_celery_health()

    if health.dlq:
        return health.dlq.to_dict()
    return {"size": 0, "oldest_message_age_seconds": None, "newest_message_age_seconds": None}


@router.get("/workers/stuck")
async def get_stuck_workers() -> list[dict[str, Any]]:
    """Get stuck workers.

    Returns:
        List of stuck workers
    """
    service = WorkerHealthService()
    health = await service.get_celery_health()

    stuck = [w.to_dict() for w in health.workers if w.stuck]
    return stuck


@router.post("/workers/heartbeat")
async def send_heartbeat(
    worker_id: str,
    hostname: str = Query(default="unknown"),
    pid: int = Query(default=None),
) -> dict[str, Any]:
    """Record worker heartbeat.

    Args:
        worker_id: Worker ID
        hostname: Worker hostname
        pid: Process ID

    Returns:
        Heartbeat confirmation
    """
    service = WorkerHealthService()
    await service.send_worker_heartbeat(
        worker_id=worker_id,
        hostname=hostname,
        pid=pid,
    )
    return {"worker_id": worker_id, "heartbeat": "recorded"}


@router.get("/workers/full-status")
async def get_full_worker_status() -> dict[str, Any]:
    """Get combined Redis and Celery status.

    Returns:
        Full infrastructure status
    """
    service = WorkerHealthService()
    redis_health = await service.get_redis_health()
    celery_health = await service.get_celery_health()
    return {
        "redis": redis_health.to_dict(),
        "celery": celery_health.to_dict(),
    }


# ============================================================================
# Maintenance Mode (Round 7)
# ============================================================================


@router.get("/maintenance/status")
async def get_maintenance_status() -> dict[str, Any]:
    """Get current maintenance status.

    Returns:
        System status
    """
    service = MaintenanceModeService()
    status = await service.get_status()
    return status.to_dict()


@router.post("/maintenance/enter")
async def enter_maintenance_mode(
    request: EnterMaintenanceRequest,
) -> dict[str, Any]:
    """Enter maintenance mode.

    Args:
        request: Maintenance request

    Returns:
        Maintenance status
    """
    service = MaintenanceModeService()
    return await service.enter_maintenance_mode(
        reason=request.reason,
        actor=request.actor,
        drain_connections=request.drain_connections,
        notify=request.notify,
    )


@router.post("/maintenance/exit")
async def exit_maintenance_mode(
    request: ExitMaintenanceRequest,
) -> dict[str, Any]:
    """Exit maintenance mode.

    Args:
        request: Exit request

    Returns:
        Exit status
    """
    service = MaintenanceModeService()
    return await service.exit_maintenance_mode(actor=request.actor)


@router.get("/maintenance/drain")
async def get_drain_status() -> dict[str, Any]:
    """Get connection drain status.

    Returns:
        Drain status
    """
    service = MaintenanceModeService()
    status = await service.get_drain_status()
    return status.to_dict()


@router.get("/maintenance/ready")
async def check_readiness() -> dict[str, bool]:
    """Check system readiness (k8s probe).

    Returns:
        Ready status
    """
    service = MaintenanceModeService()
    ready = await service.is_ready()
    return {"ready": ready}


@router.get("/maintenance/live")
async def check_liveness() -> dict[str, bool]:
    """Check system liveness (k8s probe).

    Returns:
        Live status
    """
    service = MaintenanceModeService()
    live = await service.is_live()
    return {"live": live}


@router.post("/maintenance/schedule")
async def schedule_maintenance(
    request: ScheduleMaintenanceRequest,
) -> dict[str, Any]:
    """Schedule a maintenance window.

    Args:
        request: Schedule request

    Returns:
        Window ID
    """
    from datetime import datetime
    from app.services.maintenance_mode import MaintenanceWindow
    import uuid

    service = MaintenanceModeService()

    try:
        start = datetime.fromisoformat(request.start_time)
        end = datetime.fromisoformat(request.end_time) if request.end_time else None
    except ValueError:
        raise HTTPException(400, "Invalid datetime format. Use ISO format.")

    window = MaintenanceWindow(
        id=str(uuid.uuid4()),
        reason=request.reason,
        scheduled_by=request.scheduled_by,
        scheduled_at=datetime.now(__import__("datetime").timezone.utc),
        start_time=start,
        end_time=end,
        affected_services=request.affected_services,
        notify_users=request.notify_users,
        auto_recover=request.auto_recover,
    )

    window_id = await service.schedule_maintenance(window)
    return {"window_id": window_id, "scheduled": window.to_dict()}


@router.get("/maintenance/windows")
async def get_scheduled_windows(
    include_past: bool = Query(default=False),
) -> list[dict[str, Any]]:
    """Get scheduled maintenance windows.

    Args:
        include_past: Include past windows

    Returns:
        List of windows
    """
    service = MaintenanceModeService()
    windows = await service.get_scheduled_windows(include_past)
    return [w.to_dict() for w in windows]


# ============================================================================
# Operations Journal (Round 7)
# ============================================================================


@router.get("/journal")
async def get_journal_entries(
    limit: int = Query(default=50, ge=1, le=500),
    actor: str = Query(default=None),
    action: str = Query(default=None),
    category: str = Query(default=None),
    severity: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get journal entries.

    Args:
        limit: Max entries
        actor: Filter by actor
        action: Filter by action
        category: Filter by category
        severity: Filter by severity

    Returns:
        List of journal entries
    """
    service = OpsJournalService()

    cat = None
    if category:
        try:
            cat = JournalCategory(category)
        except ValueError:
            valid = [c.value for c in JournalCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    sev = None
    if severity:
        try:
            sev = JournalSeverity(severity)
        except ValueError:
            valid = [s.value for s in JournalSeverity]
            raise HTTPException(400, f"Invalid severity. Valid: {valid}")

    entries = await service.get_entries(
        limit=limit,
        actor=actor,
        action=action,
        category=cat,
        severity=sev,
    )
    return [e.to_dict() for e in entries]


@router.get("/journal/{entry_id}")
async def get_journal_entry(
    entry_id: str,
) -> dict[str, Any]:
    """Get journal entry by ID.

    Args:
        entry_id: Entry ID

    Returns:
        Journal entry
    """
    service = OpsJournalService()
    entry = await service.get_entry(entry_id)

    if not entry:
        raise HTTPException(404, f"Entry {entry_id} not found")

    return entry.to_dict()


@router.get("/journal/verify")
async def verify_journal_integrity() -> dict[str, Any]:
    """Verify journal integrity.

    Returns:
        Integrity verification result
    """
    service = OpsJournalService()
    result = await service.verify_integrity()
    return result.to_dict()


@router.get("/journal/stats")
async def get_journal_stats() -> dict[str, Any]:
    """Get journal statistics.

    Returns:
        Journal stats
    """
    service = OpsJournalService()
    return await service.get_stats()


@router.get("/journal/export")
async def export_journal(
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Export journal entries.

    Args:
        start_date: Start date (ISO format)
        end_date: End date (ISO format)

    Returns:
        Exported entries
    """
    from datetime import datetime

    service = OpsJournalService()

    start = None
    end = None

    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(400, "Invalid start_date format")

    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(400, "Invalid end_date format")

    return await service.export_entries(start_date=start, end_date=end)


# ============================================================================
# Recovery Runbooks (Round 7)
# ============================================================================


@router.get("/runbooks")
async def list_runbooks(
    category: str = Query(default=None),
    tag: str = Query(default=None),
) -> list[dict[str, Any]]:
    """List available runbooks.

    Args:
        category: Filter by category
        tag: Filter by tag

    Returns:
        List of runbooks
    """
    service = RecoveryRunbooksService()

    cat = None
    if category:
        try:
            cat = RunbookCategory(category)
        except ValueError:
            valid = [c.value for c in RunbookCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    runbooks = service.list_runbooks(category=cat, tag=tag)
    return [r.to_dict() for r in runbooks]


@router.get("/runbooks/{runbook_id}")
async def get_runbook(
    runbook_id: str,
) -> dict[str, Any]:
    """Get runbook by ID.

    Args:
        runbook_id: Runbook ID

    Returns:
        Runbook details
    """
    service = RecoveryRunbooksService()
    runbook = service.get_runbook(runbook_id)

    if not runbook:
        raise HTTPException(404, f"Runbook {runbook_id} not found")

    return runbook.to_dict()


@router.post("/runbooks/{runbook_id}/execute")
async def execute_runbook(
    runbook_id: str,
    request: ExecuteRunbookRequest,
) -> dict[str, Any]:
    """Execute a runbook.

    Args:
        runbook_id: Runbook ID
        request: Execute request

    Returns:
        Execution result
    """
    service = RecoveryRunbooksService()

    try:
        execution = await service.execute_runbook(
            runbook_id=runbook_id,
            actor=request.actor,
            dry_run=request.dry_run,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    return execution.to_dict()


@router.get("/runbooks/executions/history")
async def get_execution_history(
    limit: int = Query(default=50, ge=1, le=200),
    runbook_id: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get runbook execution history.

    Args:
        limit: Max entries
        runbook_id: Filter by runbook

    Returns:
        Execution history
    """
    service = RecoveryRunbooksService()
    executions = await service.get_execution_history(limit=limit, runbook_id=runbook_id)
    return [e.to_dict() for e in executions]


@router.get("/runbooks/executions/active")
async def get_active_executions() -> list[str]:
    """Get currently active runbook executions.

    Returns:
        Active execution IDs
    """
    service = RecoveryRunbooksService()
    return await service.get_active_executions()


@router.get("/runbooks/suggest")
async def suggest_runbook(
    issue: str = Query(..., min_length=3),
) -> list[dict[str, Any]]:
    """Suggest runbooks for an issue.

    Args:
        issue: Issue description

    Returns:
        Suggested runbooks
    """
    service = RecoveryRunbooksService()
    suggestions = service.suggest_runbook(issue)
    return [r.to_dict() for r in suggestions]


# ============================================================================
# Reference Data (Round 7)
# ============================================================================


@router.get("/runbook-categories")
async def get_runbook_categories() -> list[dict[str, str]]:
    """Get all runbook categories."""
    return [{"category": c.value} for c in RunbookCategory]


@router.get("/journal-categories")
async def get_journal_categories() -> list[dict[str, str]]:
    """Get all journal categories."""
    return [{"category": c.value} for c in JournalCategory]


@router.get("/journal-severities")
async def get_journal_severities() -> list[dict[str, str]]:
    """Get all journal severities."""
    return [{"severity": s.value} for s in JournalSeverity]
