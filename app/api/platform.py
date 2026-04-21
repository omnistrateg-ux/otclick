"""Platform Operations API endpoints.

Environment guardrails, deployment safety, feature flags, costs, SLOs,
incidents, synthetic probes, chaos drills, control plane, policies,
approval gates, backups, dependency graph, root cause, drift detection,
change impact analysis.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.environment_guardrails import (
    EnvironmentGuardrailsService,
    ActionCategory,
    Environment,
)
from app.services.deployment_safety import DeploymentSafetyService
from app.services.feature_flags import FeatureFlagsService, FlagStatus
from app.services.cost_observability import CostObservabilityService, CostCategory, CostPeriod
from app.services.slo_budgets import SLOBudgetsService, SLOType
from app.services.incident_timeline import (
    IncidentTimelineService,
    IncidentSeverity,
    IncidentStatus,
    TimelineEventType,
)
from app.services.synthetic_probes import SyntheticProbesService, ProbeType
from app.services.chaos_drills import ChaosDrillsService, DrillType
from app.services.control_plane import (
    ControlPlaneService,
    ControlAction,
    ControlScope,
)
from app.services.policy_engine import (
    PolicyEngineService,
    PolicyType,
    PolicyScope,
    PolicyAction,
)
from app.services.approval_gates import (
    ApprovalGatesService,
    ActionCategory as ApprovalCategory,
    RiskLevel,
)
from app.services.signed_backup import (
    SignedBackupService,
    BackupType,
    BackupTarget,
)
from app.services.dependency_graph import (
    DependencyGraphService,
    NodeType,
    DependencyType,
    HealthStatus,
)
from app.services.root_cause_helper import (
    RootCauseHelperService,
    SymptomCategory,
)
from app.services.drift_detection import (
    DriftDetectionService,
    DriftType,
    DriftSeverity,
)
from app.services.change_impact import (
    ChangeImpactService,
    ChangeType,
    RiskLevel as ImpactRiskLevel,
)
from app.services.ops_cockpit import (
    OpsCockpitService,
    ActionPriority as CockpitActionPriority,
    ActionCategory as CockpitActionCategory,
)
from app.services.ops_assistant import (
    OpsAssistantService,
    TriageSeverity,
    TriageCategory,
    RemediationStatus,
    RunbookSafetyLevel,
    EscalationLevel,
    HandoffStatus,
)
from app.services.decision_safety import (
    DecisionSafetyService,
    ConfidenceLevel,
    AutoRemediationMode,
    RollbackUrgency,
    ReviewStatus,
    PolicyLearningType,
    ProdGuardLevel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platform", tags=["platform"])


# ============================================================================
# Request Models
# ============================================================================


class CheckActionRequest(BaseModel):
    """Check action request."""
    action: str
    actor: str
    details: dict[str, Any] | None = None
    batch_size: int = 1


class CreateDeploymentRequest(BaseModel):
    """Create deployment request."""
    version: str
    environment: str
    created_by: str
    notes: str | None = None


class ApproveDeploymentRequest(BaseModel):
    """Approve deployment request."""
    approved_by: str


class UpdateFlagRequest(BaseModel):
    """Update flag request."""
    status: str | None = None
    rollout_percentage: int | None = None
    allowed_users: list[str] | None = None
    allowed_segments: list[str] | None = None
    actor: str


class SetBudgetRequest(BaseModel):
    """Set budget request."""
    category: str | None = None
    period: str
    budget_usd: float
    alert_threshold_percent: int = 80


class CreateSLORequest(BaseModel):
    """Create SLO request."""
    id: str
    name: str
    description: str
    slo_type: str
    target_percent: float
    window_days: int
    measurement_query: str
    service: str


class RecordSLOMetricRequest(BaseModel):
    """Record SLO metric request."""
    good_events: int
    total_events: int


class CreateIncidentRequest(BaseModel):
    """Create incident request."""
    title: str
    description: str
    severity: str
    created_by: str
    affected_services: list[str] | None = None
    assignee: str | None = None
    tags: list[str] | None = None


class UpdateIncidentStatusRequest(BaseModel):
    """Update incident status request."""
    status: str
    actor: str
    comment: str | None = None


class ResolveIncidentRequest(BaseModel):
    """Resolve incident request."""
    actor: str
    resolution_summary: str


class AddTimelineEventRequest(BaseModel):
    """Add timeline event request."""
    event_type: str
    actor: str
    content: str
    metadata: dict[str, Any] | None = None


class StartDrillRequest(BaseModel):
    """Start drill request."""
    initiated_by: str
    approved_by: str | None = None
    environment: str = "staging"


class StopDrillRequest(BaseModel):
    """Stop drill request."""
    actor: str
    reason: str = "Manual stop"


# Round 9 Request Models

class IssueCommandRequest(BaseModel):
    """Issue control command request."""
    action: str
    issued_by: str
    scope: str = "global"
    target: str | None = None
    parameters: dict[str, Any] | None = None


class ClearEmergencyRequest(BaseModel):
    """Clear emergency request."""
    cleared_by: str


class CreatePolicyRequest(BaseModel):
    """Create policy request."""
    name: str
    policy_type: str
    scope: str
    rules: dict[str, Any]
    action: str = "deny"
    priority: int = 50
    description: str = ""


class UpdatePolicyRequest(BaseModel):
    """Update policy request."""
    rules: dict[str, Any] | None = None
    action: str | None = None
    enabled: bool | None = None
    priority: int | None = None


class EvaluatePolicyRequest(BaseModel):
    """Evaluate policy request."""
    context: dict[str, Any]
    policy_types: list[str] | None = None


class RequestApprovalRequest(BaseModel):
    """Request approval request."""
    action: str
    category: str
    requester: str
    reason: str = ""
    context: dict[str, Any] | None = None


class ApprovalDecisionRequest(BaseModel):
    """Approval decision request."""
    actor: str
    role: str = ""
    reason: str | None = None


class CreateBackupRequest(BaseModel):
    """Create backup request."""
    target: str
    created_by: str
    backup_type: str = "full"
    metadata: dict[str, Any] | None = None


class RestoreBackupRequest(BaseModel):
    """Restore backup request."""
    restored_by: str
    verify_first: bool = True


class RegisterNodeRequest(BaseModel):
    """Register dependency node request."""
    name: str
    node_type: str
    version: str | None = None
    metadata: dict[str, Any] | None = None


class AddDependencyRequest(BaseModel):
    """Add dependency request."""
    source: str
    target: str
    dependency_type: str = "required"
    description: str = ""


class UpdateNodeHealthRequest(BaseModel):
    """Update node health request."""
    health: str


class RecordSymptomRequest(BaseModel):
    """Record symptom request."""
    category: str
    description: str
    severity: str = "medium"
    metrics: dict[str, Any] | None = None


class AnalyzeErrorRequest(BaseModel):
    """Analyze error request."""
    error_message: str
    stack_trace: str | None = None
    context: dict[str, Any] | None = None


class CaptureBaselineRequest(BaseModel):
    """Capture drift baseline request."""
    resource: str
    drift_type: str
    state_data: dict[str, Any]
    captured_by: str = "system"


class CheckDriftRequest(BaseModel):
    """Check drift request."""
    resource: str
    current_state: dict[str, Any]
    critical_keys: list[str] | None = None


class AnalyzeChangeRequest(BaseModel):
    """Analyze change impact request."""
    change_type: str
    title: str
    description: str
    requested_by: str
    target_components: list[str] | None = None
    metadata: dict[str, Any] | None = None


# Round 11 Request Models

class TriageIncidentRequest(BaseModel):
    """Triage incident request."""
    incident_id: str
    title: str
    description: str
    metadata: dict[str, Any] | None = None


class GeneratePlanRequest(BaseModel):
    """Generate remediation plan request."""
    incident_id: str
    created_by: str = "ops_assistant"


class AdvancePlanRequest(BaseModel):
    """Advance plan step request."""
    actor: str


class ExecuteRunbookRequest(BaseModel):
    """Execute runbook request."""
    executed_by: str
    parameters: dict[str, Any] | None = None
    approval_id: str | None = None


class CreateNoteRequest(BaseModel):
    """Create operator note request."""
    author: str
    content: str
    shift: str = "day"
    incident_ids: list[str] | None = None
    action_items: list[str] | None = None
    tags: list[str] | None = None


class CreateHandoffRequest(BaseModel):
    """Create shift handoff request."""
    from_operator: str
    to_operator: str
    shift_start: str
    shift_end: str


class AcknowledgeHandoffRequest(BaseModel):
    """Acknowledge handoff request."""
    acknowledged_by: str


class RecordFixRequest(BaseModel):
    """Record fix request."""
    incident_id: str
    fix_description: str
    runbook_id: str | None = None
    resolution_minutes: float = 30
    tags: list[str] | None = None


# Round 12 Request Models

class CalculateConfidenceRequest(BaseModel):
    """Calculate confidence request."""
    recommendation_type: str
    recommendation_id: str
    context: dict[str, Any]


class EvaluateRemediationRequest(BaseModel):
    """Evaluate auto-remediation request."""
    incident_id: str
    runbook_id: str
    context: dict[str, Any]


class SetRemediationModeRequest(BaseModel):
    """Set remediation mode request."""
    mode: str
    set_by: str


class GenerateRollbackRequest(BaseModel):
    """Generate rollback suggestion request."""
    action_id: str
    action_type: str
    action_details: dict[str, Any]


class GenerateReviewRequest(BaseModel):
    """Generate post-incident review request."""
    incident_id: str
    created_by: str


class LearnPoliciesRequest(BaseModel):
    """Learn policies from incident request."""
    incident_id: str


class ApprovePolicyRequest(BaseModel):
    """Approve learned policy request."""
    approved_by: str


class CheckGuardRequest(BaseModel):
    """Check guard request."""
    action: str
    actor: str
    context: dict[str, Any]
    bypass_reason: str | None = None


class ToggleGuardRequest(BaseModel):
    """Toggle guard request."""
    active: bool
    toggled_by: str


# ============================================================================
# Environment Guardrails
# ============================================================================


@router.get("/guardrails/environment")
async def get_current_environment() -> dict[str, Any]:
    """Get current environment info."""
    service = EnvironmentGuardrailsService()
    env = service.detect_environment()
    config = service.get_config(env)
    return config.to_dict()


@router.post("/guardrails/check")
async def check_action(
    request: CheckActionRequest,
) -> dict[str, Any]:
    """Check if action is allowed.

    Args:
        request: Action check request

    Returns:
        Check result
    """
    service = EnvironmentGuardrailsService()

    try:
        action = ActionCategory(request.action)
    except ValueError:
        valid = [a.value for a in ActionCategory]
        raise HTTPException(400, f"Invalid action. Valid: {valid}")

    return await service.check_action(
        action=action,
        actor=request.actor,
        details=request.details,
        batch_size=request.batch_size,
    )


@router.get("/guardrails/violations")
async def get_violations(
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Get guardrail violations."""
    service = EnvironmentGuardrailsService()
    violations = await service.get_violations(hours=hours, limit=limit)
    return [v.to_dict() for v in violations]


# ============================================================================
# Deployment Safety
# ============================================================================


@router.post("/deployments")
async def create_deployment(
    request: CreateDeploymentRequest,
) -> dict[str, Any]:
    """Create deployment plan with safety checks."""
    service = DeploymentSafetyService()
    plan = await service.create_deployment_plan(
        version=request.version,
        environment=request.environment,
        created_by=request.created_by,
        notes=request.notes,
    )
    return plan.to_dict()


@router.get("/deployments")
async def list_deployments(
    environment: str = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """List deployment plans."""
    service = DeploymentSafetyService()
    plans = await service.get_deployment_history(environment=environment, limit=limit)
    return [p.to_dict() for p in plans]


@router.get("/deployments/{plan_id}")
async def get_deployment(plan_id: str) -> dict[str, Any]:
    """Get deployment plan by ID."""
    service = DeploymentSafetyService()
    plan = await service.get_plan(plan_id)
    if not plan:
        raise HTTPException(404, "Deployment plan not found")
    return plan.to_dict()


@router.post("/deployments/{plan_id}/approve")
async def approve_deployment(
    plan_id: str,
    request: ApproveDeploymentRequest,
) -> dict[str, Any]:
    """Approve deployment plan."""
    service = DeploymentSafetyService()
    plan = await service.approve_deployment(plan_id, request.approved_by)
    if not plan:
        raise HTTPException(404, "Deployment plan not found or not pending")
    return plan.to_dict()


@router.get("/deployments/{plan_id}/rollback")
async def get_rollback_plan(plan_id: str) -> dict[str, Any]:
    """Get rollback plan for deployment."""
    service = DeploymentSafetyService()
    rollback = await service.get_rollback_plan(plan_id)
    if not rollback:
        raise HTTPException(404, "No rollback plan available")
    return rollback.to_dict()


# ============================================================================
# Feature Flags
# ============================================================================


@router.get("/flags")
async def list_flags() -> list[dict[str, Any]]:
    """List all feature flags."""
    service = FeatureFlagsService()
    flags = await service.list_flags()
    return [f.to_dict() for f in flags]


@router.get("/flags/{flag_key}")
async def get_flag(flag_key: str) -> dict[str, Any]:
    """Get feature flag by key."""
    service = FeatureFlagsService()
    flag = await service.get_flag(flag_key)
    if not flag:
        raise HTTPException(404, f"Flag {flag_key} not found")
    return flag.to_dict()


@router.get("/flags/{flag_key}/evaluate")
async def evaluate_flag(
    flag_key: str,
    user_id: str = Query(default=None),
    segment: str = Query(default=None),
) -> dict[str, Any]:
    """Evaluate feature flag."""
    service = FeatureFlagsService()
    evaluation = await service.evaluate(flag_key, user_id, segment)
    return evaluation.to_dict()


@router.put("/flags/{flag_key}")
async def update_flag(
    flag_key: str,
    request: UpdateFlagRequest,
) -> dict[str, Any]:
    """Update feature flag."""
    service = FeatureFlagsService()

    updates = {}
    if request.status:
        updates["status"] = request.status
    if request.rollout_percentage is not None:
        updates["rollout_percentage"] = request.rollout_percentage
    if request.allowed_users is not None:
        updates["allowed_users"] = request.allowed_users
    if request.allowed_segments is not None:
        updates["allowed_segments"] = request.allowed_segments

    flag = await service.update_flag(flag_key, updates, request.actor)
    if not flag:
        raise HTTPException(404, f"Flag {flag_key} not found")
    return flag.to_dict()


@router.get("/flags/audit")
async def get_flag_audit(
    flag_key: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get flag audit log."""
    service = FeatureFlagsService()
    entries = await service.get_audit_log(flag_key=flag_key, limit=limit)
    return [e.to_dict() for e in entries]


# ============================================================================
# Cost Observability
# ============================================================================


@router.get("/costs/summary")
async def get_cost_summary(
    period: str = Query(default="daily"),
) -> dict[str, Any]:
    """Get cost summary for period."""
    service = CostObservabilityService()

    try:
        p = CostPeriod(period)
    except ValueError:
        valid = [p.value for p in CostPeriod]
        raise HTTPException(400, f"Invalid period. Valid: {valid}")

    summary = await service.get_summary(p)
    return summary.to_dict()


@router.get("/costs/budgets")
async def get_budget_status(
    category: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get budget status."""
    service = CostObservabilityService()

    cat = None
    if category:
        try:
            cat = CostCategory(category)
        except ValueError:
            valid = [c.value for c in CostCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    statuses = await service.get_budget_status(cat)
    return [s.to_dict() for s in statuses]


@router.post("/costs/budgets")
async def set_budget(
    request: SetBudgetRequest,
) -> dict[str, Any]:
    """Set cost budget."""
    from app.services.cost_observability import CostBudget

    service = CostObservabilityService()

    cat = None
    if request.category:
        try:
            cat = CostCategory(request.category)
        except ValueError:
            valid = [c.value for c in CostCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    try:
        period = CostPeriod(request.period)
    except ValueError:
        valid = [p.value for p in CostPeriod]
        raise HTTPException(400, f"Invalid period. Valid: {valid}")

    budget = CostBudget(
        category=cat,
        period=period,
        budget_usd=request.budget_usd,
        alert_threshold_percent=request.alert_threshold_percent,
    )

    result = await service.set_budget(budget)
    return result.to_dict()


@router.get("/costs/trend")
async def get_cost_trend(
    category: str = Query(default=None),
    days: int = Query(default=30, ge=1, le=90),
) -> list[dict[str, Any]]:
    """Get cost trend."""
    service = CostObservabilityService()

    cat = None
    if category:
        try:
            cat = CostCategory(category)
        except ValueError:
            valid = [c.value for c in CostCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    return await service.get_cost_trend(category=cat, days=days)


# ============================================================================
# SLO and Error Budgets
# ============================================================================


@router.get("/slos")
async def list_slos(
    service_filter: str = Query(default=None, alias="service"),
) -> list[dict[str, Any]]:
    """List SLOs."""
    slo_service = SLOBudgetsService()
    slos = await slo_service.list_slos(service=service_filter)
    return [s.to_dict() for s in slos]


@router.post("/slos")
async def create_slo(
    request: CreateSLORequest,
) -> dict[str, Any]:
    """Create SLO."""
    from app.services.slo_budgets import SLO

    slo_service = SLOBudgetsService()

    try:
        slo_type = SLOType(request.slo_type)
    except ValueError:
        valid = [t.value for t in SLOType]
        raise HTTPException(400, f"Invalid SLO type. Valid: {valid}")

    slo = SLO(
        id=request.id,
        name=request.name,
        description=request.description,
        slo_type=slo_type,
        target_percent=request.target_percent,
        window_days=request.window_days,
        measurement_query=request.measurement_query,
        service=request.service,
    )

    result = await slo_service.create_slo(slo)
    return result.to_dict()


@router.get("/slos/{slo_id}/budget")
async def get_error_budget(slo_id: str) -> dict[str, Any]:
    """Get error budget for SLO."""
    slo_service = SLOBudgetsService()
    budget = await slo_service.get_error_budget(slo_id)
    if not budget:
        raise HTTPException(404, f"SLO {slo_id} not found")
    return budget.to_dict()


@router.post("/slos/{slo_id}/metrics")
async def record_slo_metric(
    slo_id: str,
    request: RecordSLOMetricRequest,
) -> dict[str, str]:
    """Record SLO metric data."""
    slo_service = SLOBudgetsService()
    await slo_service.record_metric(
        slo_id=slo_id,
        good_events=request.good_events,
        total_events=request.total_events,
    )
    return {"status": "recorded"}


@router.get("/slos/budgets")
async def get_all_budgets() -> list[dict[str, Any]]:
    """Get all error budgets."""
    slo_service = SLOBudgetsService()
    budgets = await slo_service.get_all_budgets()
    return [b.to_dict() for b in budgets]


@router.get("/slos/report")
async def generate_slo_report(
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, Any]:
    """Generate SLO report."""
    slo_service = SLOBudgetsService()
    report = await slo_service.generate_report(period_days=days)
    return report.to_dict()


# ============================================================================
# Incident Timeline
# ============================================================================


@router.post("/incidents")
async def create_incident(
    request: CreateIncidentRequest,
) -> dict[str, Any]:
    """Create new incident."""
    inc_service = IncidentTimelineService()

    try:
        severity = IncidentSeverity(request.severity)
    except ValueError:
        valid = [s.value for s in IncidentSeverity]
        raise HTTPException(400, f"Invalid severity. Valid: {valid}")

    incident = await inc_service.create_incident(
        title=request.title,
        description=request.description,
        severity=severity,
        created_by=request.created_by,
        affected_services=request.affected_services,
        assignee=request.assignee,
        tags=request.tags,
    )
    return incident.to_dict()


@router.get("/incidents")
async def list_incidents(
    status: str = Query(default=None),
    severity: str = Query(default=None),
    active_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """List incidents."""
    inc_service = IncidentTimelineService()

    st = None
    if status:
        try:
            st = IncidentStatus(status)
        except ValueError:
            valid = [s.value for s in IncidentStatus]
            raise HTTPException(400, f"Invalid status. Valid: {valid}")

    sev = None
    if severity:
        try:
            sev = IncidentSeverity(severity)
        except ValueError:
            valid = [s.value for s in IncidentSeverity]
            raise HTTPException(400, f"Invalid severity. Valid: {valid}")

    incidents = await inc_service.list_incidents(
        status=st,
        severity=sev,
        active_only=active_only,
        limit=limit,
    )
    return [i.to_dict() for i in incidents]


@router.get("/incidents/active")
async def get_active_incidents() -> list[dict[str, Any]]:
    """Get active incidents."""
    inc_service = IncidentTimelineService()
    incidents = await inc_service.get_active_incidents()
    return [i.to_dict() for i in incidents]


@router.get("/incidents/stats")
async def get_incident_stats(
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, Any]:
    """Get incident statistics."""
    inc_service = IncidentTimelineService()
    stats = await inc_service.get_stats(days=days)
    return stats.to_dict()


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str) -> dict[str, Any]:
    """Get incident by ID."""
    inc_service = IncidentTimelineService()
    incident = await inc_service.get_incident(incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    return incident.to_dict()


@router.post("/incidents/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    request: UpdateIncidentStatusRequest,
) -> dict[str, Any]:
    """Update incident status."""
    inc_service = IncidentTimelineService()

    try:
        status = IncidentStatus(request.status)
    except ValueError:
        valid = [s.value for s in IncidentStatus]
        raise HTTPException(400, f"Invalid status. Valid: {valid}")

    incident = await inc_service.update_status(
        incident_id=incident_id,
        new_status=status,
        actor=request.actor,
        comment=request.comment,
    )
    if not incident:
        raise HTTPException(404, "Incident not found")
    return incident.to_dict()


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    request: ResolveIncidentRequest,
) -> dict[str, Any]:
    """Resolve incident."""
    inc_service = IncidentTimelineService()
    incident = await inc_service.resolve_incident(
        incident_id=incident_id,
        actor=request.actor,
        resolution_summary=request.resolution_summary,
    )
    if not incident:
        raise HTTPException(404, "Incident not found")
    return incident.to_dict()


@router.post("/incidents/{incident_id}/timeline")
async def add_timeline_event(
    incident_id: str,
    request: AddTimelineEventRequest,
) -> dict[str, Any]:
    """Add event to incident timeline."""
    inc_service = IncidentTimelineService()

    try:
        event_type = TimelineEventType(request.event_type)
    except ValueError:
        valid = [t.value for t in TimelineEventType]
        raise HTTPException(400, f"Invalid event type. Valid: {valid}")

    incident = await inc_service.add_timeline_event(
        incident_id=incident_id,
        event_type=event_type,
        actor=request.actor,
        content=request.content,
        metadata=request.metadata,
    )
    if not incident:
        raise HTTPException(404, "Incident not found")
    return incident.to_dict()


# ============================================================================
# Synthetic Probes
# ============================================================================


@router.get("/probes")
async def list_probes(
    probe_type: str = Query(default=None),
) -> list[dict[str, Any]]:
    """List synthetic probes."""
    probe_service = SyntheticProbesService()

    pt = None
    if probe_type:
        try:
            pt = ProbeType(probe_type)
        except ValueError:
            valid = [t.value for t in ProbeType]
            raise HTTPException(400, f"Invalid probe type. Valid: {valid}")

    probes = await probe_service.list_probes(probe_type=pt)
    return [p.to_dict() for p in probes]


@router.get("/probes/status")
async def get_all_probe_status() -> list[dict[str, Any]]:
    """Get status of all probes."""
    probe_service = SyntheticProbesService()
    return await probe_service.get_all_probe_status()


@router.post("/probes/{probe_id}/execute")
async def execute_probe(probe_id: str) -> dict[str, Any]:
    """Execute a probe."""
    probe_service = SyntheticProbesService()
    result = await probe_service.execute_probe(probe_id)
    return result.to_dict()


@router.post("/probes/run-all")
async def run_all_probes() -> list[dict[str, Any]]:
    """Run all enabled probes."""
    probe_service = SyntheticProbesService()
    results = await probe_service.run_all_probes()
    return [r.to_dict() for r in results]


@router.get("/probes/{probe_id}/history")
async def get_probe_history(
    probe_id: str,
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    """Get probe execution history."""
    probe_service = SyntheticProbesService()
    history = await probe_service.get_probe_history(probe_id, hours)
    if not history:
        raise HTTPException(404, "Probe not found")
    return history.to_dict()


@router.get("/probes/alerts")
async def get_probe_alerts(
    unacknowledged_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get probe alerts."""
    probe_service = SyntheticProbesService()
    alerts = await probe_service.get_alerts(
        unacknowledged_only=unacknowledged_only,
        limit=limit,
    )
    return [a.to_dict() for a in alerts]


# ============================================================================
# Chaos Drills
# ============================================================================


@router.get("/chaos/drills")
async def list_drills(
    drill_type: str = Query(default=None),
    safe_for_production: bool = Query(default=None),
) -> list[dict[str, Any]]:
    """List available chaos drills."""
    drill_service = ChaosDrillsService()

    dt = None
    if drill_type:
        try:
            dt = DrillType(drill_type)
        except ValueError:
            valid = [t.value for t in DrillType]
            raise HTTPException(400, f"Invalid drill type. Valid: {valid}")

    drills = drill_service.list_drills(
        drill_type=dt,
        safe_for_production=safe_for_production,
    )
    return [d.to_dict() for d in drills]


@router.get("/chaos/drills/{drill_id}")
async def get_drill(drill_id: str) -> dict[str, Any]:
    """Get drill by ID."""
    drill_service = ChaosDrillsService()
    drill = drill_service.get_drill(drill_id)
    if not drill:
        raise HTTPException(404, "Drill not found")
    return drill.to_dict()


@router.post("/chaos/drills/{drill_id}/start")
async def start_drill(
    drill_id: str,
    request: StartDrillRequest,
) -> dict[str, Any]:
    """Start a chaos drill."""
    drill_service = ChaosDrillsService()

    try:
        execution = await drill_service.start_drill(
            drill_id=drill_id,
            initiated_by=request.initiated_by,
            approved_by=request.approved_by,
            environment=request.environment,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return execution.to_dict()


@router.post("/chaos/executions/{execution_id}/stop")
async def stop_drill(
    execution_id: str,
    request: StopDrillRequest,
) -> dict[str, Any]:
    """Stop a running drill."""
    drill_service = ChaosDrillsService()
    execution = await drill_service.stop_drill(
        execution_id=execution_id,
        actor=request.actor,
        reason=request.reason,
    )
    if not execution:
        raise HTTPException(404, "Execution not found or not running")
    return execution.to_dict()


@router.get("/chaos/active")
async def get_active_drill() -> dict[str, Any] | None:
    """Get currently active drill."""
    drill_service = ChaosDrillsService()
    return await drill_service.get_active_drill()


@router.get("/chaos/executions")
async def get_drill_history(
    drill_id: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get drill execution history."""
    drill_service = ChaosDrillsService()
    executions = await drill_service.get_execution_history(drill_id=drill_id, limit=limit)
    return [e.to_dict() for e in executions]


@router.get("/chaos/executions/{execution_id}")
async def get_drill_execution(execution_id: str) -> dict[str, Any]:
    """Get drill execution by ID."""
    drill_service = ChaosDrillsService()
    execution = await drill_service.get_execution(execution_id)
    if not execution:
        raise HTTPException(404, "Execution not found")
    return execution.to_dict()


@router.get("/chaos/executions/{execution_id}/report")
async def get_drill_report(execution_id: str) -> dict[str, Any]:
    """Generate drill report."""
    drill_service = ChaosDrillsService()
    report = await drill_service.generate_report(execution_id)
    if not report:
        raise HTTPException(404, "Execution not found")
    return report.to_dict()


# ============================================================================
# Reference Data
# ============================================================================


@router.get("/reference/action-categories")
async def get_action_categories() -> list[dict[str, str]]:
    """Get action categories."""
    return [{"category": c.value} for c in ActionCategory]


@router.get("/reference/cost-categories")
async def get_cost_categories() -> list[dict[str, str]]:
    """Get cost categories."""
    return [{"category": c.value} for c in CostCategory]


@router.get("/reference/slo-types")
async def get_slo_types() -> list[dict[str, str]]:
    """Get SLO types."""
    return [{"type": t.value} for t in SLOType]


@router.get("/reference/incident-severities")
async def get_incident_severities() -> list[dict[str, str]]:
    """Get incident severities."""
    return [{"severity": s.value} for s in IncidentSeverity]


@router.get("/reference/drill-types")
async def get_drill_types() -> list[dict[str, str]]:
    """Get drill types."""
    return [{"type": t.value} for t in DrillType]


# ============================================================================
# Control Plane (Round 9)
# ============================================================================


@router.get("/control/state")
async def get_system_state() -> dict[str, Any]:
    """Get current system state."""
    service = ControlPlaneService()
    state = await service.get_system_state()
    return state.to_dict()


@router.post("/control/command")
async def issue_command(
    request: IssueCommandRequest,
) -> dict[str, Any]:
    """Issue control command."""
    service = ControlPlaneService()

    try:
        action = ControlAction(request.action)
    except ValueError:
        valid = [a.value for a in ControlAction]
        raise HTTPException(400, f"Invalid action. Valid: {valid}")

    try:
        scope = ControlScope(request.scope)
    except ValueError:
        valid = [s.value for s in ControlScope]
        raise HTTPException(400, f"Invalid scope. Valid: {valid}")

    command = await service.issue_command(
        action=action,
        issued_by=request.issued_by,
        scope=scope,
        target=request.target,
        parameters=request.parameters,
    )
    return command.to_dict()


@router.get("/control/commands")
async def get_command_history(
    action: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get command history."""
    service = ControlPlaneService()

    act = None
    if action:
        try:
            act = ControlAction(action)
        except ValueError:
            valid = [a.value for a in ControlAction]
            raise HTTPException(400, f"Invalid action. Valid: {valid}")

    commands = await service.get_command_history(limit=limit, action=act)
    return [c.to_dict() for c in commands]


@router.get("/control/metrics")
async def get_control_metrics() -> dict[str, Any]:
    """Get control plane metrics."""
    service = ControlPlaneService()
    metrics = await service.get_metrics()
    return metrics.to_dict()


@router.post("/control/emergency/clear")
async def clear_emergency(
    request: ClearEmergencyRequest,
) -> dict[str, Any]:
    """Clear emergency mode."""
    service = ControlPlaneService()
    result = await service.clear_emergency(request.cleared_by)
    return result


# ============================================================================
# Policy Engine (Round 9)
# ============================================================================


@router.get("/policies")
async def list_policies(
    policy_type: str = Query(default=None),
    enabled_only: bool = Query(default=True),
) -> list[dict[str, Any]]:
    """List policies."""
    service = PolicyEngineService()

    pt = None
    if policy_type:
        try:
            pt = PolicyType(policy_type)
        except ValueError:
            valid = [t.value for t in PolicyType]
            raise HTTPException(400, f"Invalid policy type. Valid: {valid}")

    policies = await service.list_policies(policy_type=pt, enabled_only=enabled_only)
    return [p.to_dict() for p in policies]


@router.post("/policies")
async def create_policy(
    request: CreatePolicyRequest,
) -> dict[str, Any]:
    """Create policy."""
    service = PolicyEngineService()

    try:
        policy_type = PolicyType(request.policy_type)
    except ValueError:
        valid = [t.value for t in PolicyType]
        raise HTTPException(400, f"Invalid policy type. Valid: {valid}")

    try:
        scope = PolicyScope(request.scope)
    except ValueError:
        valid = [s.value for s in PolicyScope]
        raise HTTPException(400, f"Invalid scope. Valid: {valid}")

    try:
        action = PolicyAction(request.action)
    except ValueError:
        valid = [a.value for a in PolicyAction]
        raise HTTPException(400, f"Invalid action. Valid: {valid}")

    policy = await service.create_policy(
        name=request.name,
        policy_type=policy_type,
        scope=scope,
        rules=request.rules,
        action=action,
        priority=request.priority,
        description=request.description,
    )
    return policy.to_dict()


@router.get("/policies/{name}")
async def get_policy(name: str) -> dict[str, Any]:
    """Get policy by name."""
    service = PolicyEngineService()
    policy = await service.get_policy(name)
    if not policy:
        raise HTTPException(404, "Policy not found")
    return policy.to_dict()


@router.put("/policies/{name}")
async def update_policy(
    name: str,
    request: UpdatePolicyRequest,
) -> dict[str, Any]:
    """Update policy."""
    service = PolicyEngineService()

    action = None
    if request.action:
        try:
            action = PolicyAction(request.action)
        except ValueError:
            valid = [a.value for a in PolicyAction]
            raise HTTPException(400, f"Invalid action. Valid: {valid}")

    policy = await service.update_policy(
        name=name,
        rules=request.rules,
        action=action,
        enabled=request.enabled,
        priority=request.priority,
    )
    if not policy:
        raise HTTPException(404, "Policy not found")
    return policy.to_dict()


@router.delete("/policies/{name}")
async def delete_policy(name: str) -> dict[str, str]:
    """Delete policy."""
    service = PolicyEngineService()
    deleted = await service.delete_policy(name)
    if not deleted:
        raise HTTPException(404, "Policy not found")
    return {"status": "deleted"}


@router.post("/policies/evaluate")
async def evaluate_policies(
    request: EvaluatePolicyRequest,
) -> list[dict[str, Any]]:
    """Evaluate policies against context."""
    service = PolicyEngineService()

    policy_types = None
    if request.policy_types:
        policy_types = []
        for pt in request.policy_types:
            try:
                policy_types.append(PolicyType(pt))
            except ValueError:
                valid = [t.value for t in PolicyType]
                raise HTTPException(400, f"Invalid policy type: {pt}. Valid: {valid}")

    evaluations = await service.evaluate(
        context=request.context,
        policy_types=policy_types,
    )
    return [e.to_dict() for e in evaluations]


@router.get("/policies/violations")
async def get_policy_violations(
    policy_name: str = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Get policy violations."""
    service = PolicyEngineService()
    violations = await service.get_violations(limit=limit, policy_name=policy_name)
    return [v.to_dict() for v in violations]


@router.post("/policies/initialize")
async def initialize_default_policies() -> dict[str, int]:
    """Initialize default policies."""
    service = PolicyEngineService()
    count = await service.initialize_defaults()
    return {"policies_created": count}


# ============================================================================
# Approval Gates (Round 9)
# ============================================================================


@router.get("/approvals/rules")
async def list_approval_rules() -> list[dict[str, Any]]:
    """List approval rules."""
    service = ApprovalGatesService()
    rules = await service.list_rules()
    return [r.to_dict() for r in rules]


@router.post("/approvals/request")
async def request_approval(
    request: RequestApprovalRequest,
) -> dict[str, Any]:
    """Request approval for action."""
    service = ApprovalGatesService()

    try:
        category = ApprovalCategory(request.category)
    except ValueError:
        valid = [c.value for c in ApprovalCategory]
        raise HTTPException(400, f"Invalid category. Valid: {valid}")

    try:
        approval = await service.request_approval(
            action=request.action,
            category=category,
            requester=request.requester,
            reason=request.reason,
            context=request.context,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return approval.to_dict()


@router.get("/approvals/pending")
async def list_pending_approvals(
    category: str = Query(default=None),
) -> list[dict[str, Any]]:
    """List pending approvals."""
    service = ApprovalGatesService()

    cat = None
    if category:
        try:
            cat = ApprovalCategory(category)
        except ValueError:
            valid = [c.value for c in ApprovalCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    requests = await service.list_pending(category=cat)
    return [r.to_dict() for r in requests]


@router.get("/approvals/{request_id}")
async def get_approval_request(request_id: str) -> dict[str, Any]:
    """Get approval request."""
    service = ApprovalGatesService()
    request = await service.get_request(request_id)
    if not request:
        raise HTTPException(404, "Request not found")
    return request.to_dict()


@router.post("/approvals/{request_id}/approve")
async def approve_request(
    request_id: str,
    request: ApprovalDecisionRequest,
) -> dict[str, Any]:
    """Approve a request."""
    service = ApprovalGatesService()
    approval = await service.approve(
        request_id=request_id,
        approver=request.actor,
        approver_role=request.role,
        reason=request.reason,
    )
    if not approval:
        raise HTTPException(404, "Request not found")
    return approval.to_dict()


@router.post("/approvals/{request_id}/reject")
async def reject_request(
    request_id: str,
    request: ApprovalDecisionRequest,
) -> dict[str, Any]:
    """Reject a request."""
    service = ApprovalGatesService()

    if not request.reason:
        raise HTTPException(400, "Reason required for rejection")

    approval = await service.reject(
        request_id=request_id,
        rejector=request.actor,
        reason=request.reason,
    )
    if not approval:
        raise HTTPException(404, "Request not found")
    return approval.to_dict()


@router.get("/approvals/{request_id}/check")
async def check_approval_status(request_id: str) -> dict[str, Any]:
    """Check approval status."""
    service = ApprovalGatesService()
    approved, message = await service.check_approval(request_id)
    return {"approved": approved, "message": message}


@router.post("/approvals/initialize")
async def initialize_approval_rules() -> dict[str, int]:
    """Initialize default approval rules."""
    service = ApprovalGatesService()
    count = await service.initialize_defaults()
    return {"rules_created": count}


# ============================================================================
# Signed Backup/Restore (Round 9)
# ============================================================================


@router.post("/backups")
async def create_backup(
    request: CreateBackupRequest,
) -> dict[str, Any]:
    """Create signed backup."""
    service = SignedBackupService()

    try:
        target = BackupTarget(request.target)
    except ValueError:
        valid = [t.value for t in BackupTarget]
        raise HTTPException(400, f"Invalid target. Valid: {valid}")

    try:
        backup_type = BackupType(request.backup_type)
    except ValueError:
        valid = [t.value for t in BackupType]
        raise HTTPException(400, f"Invalid backup type. Valid: {valid}")

    backup = await service.create_backup(
        target=target,
        created_by=request.created_by,
        backup_type=backup_type,
        metadata=request.metadata,
    )
    return backup.to_dict()


@router.get("/backups")
async def list_backups(
    target: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """List backups."""
    service = SignedBackupService()

    t = None
    if target:
        try:
            t = BackupTarget(target)
        except ValueError:
            valid = [t.value for t in BackupTarget]
            raise HTTPException(400, f"Invalid target. Valid: {valid}")

    backups = await service.list_backups(target=t, limit=limit)
    return [b.to_dict() for b in backups]


@router.get("/backups/{backup_id}")
async def get_backup(backup_id: str) -> dict[str, Any]:
    """Get backup by ID."""
    service = SignedBackupService()
    backup = await service.get_backup(backup_id)
    if not backup:
        raise HTTPException(404, "Backup not found")
    return backup.to_dict()


@router.post("/backups/{backup_id}/verify")
async def verify_backup(backup_id: str) -> dict[str, Any]:
    """Verify backup integrity."""
    service = SignedBackupService()
    valid, message = await service.verify_backup(backup_id)
    return {"valid": valid, "message": message}


@router.post("/backups/{backup_id}/restore")
async def restore_backup(
    backup_id: str,
    request: RestoreBackupRequest,
) -> dict[str, Any]:
    """Restore from backup."""
    service = SignedBackupService()

    try:
        operation = await service.restore_backup(
            backup_id=backup_id,
            restored_by=request.restored_by,
            verify_first=request.verify_first,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return operation.to_dict()


@router.get("/backups/restores/history")
async def get_restore_history(
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get restore history."""
    service = SignedBackupService()
    operations = await service.get_restore_history(limit=limit)
    return [o.to_dict() for o in operations]


@router.delete("/backups/{backup_id}")
async def delete_backup(
    backup_id: str,
    deleted_by: str = Query(...),
) -> dict[str, str]:
    """Delete backup."""
    service = SignedBackupService()
    deleted = await service.delete_backup(backup_id, deleted_by)
    if not deleted:
        raise HTTPException(404, "Backup not found")
    return {"status": "deleted"}


# ============================================================================
# Dependency Graph (Round 9)
# ============================================================================


@router.get("/dependencies/graph")
async def get_dependency_graph() -> dict[str, Any]:
    """Get full dependency graph."""
    service = DependencyGraphService()
    return await service.get_graph()


@router.get("/dependencies/nodes")
async def list_dependency_nodes() -> list[dict[str, Any]]:
    """List all nodes."""
    service = DependencyGraphService()
    nodes = await service.get_all_nodes()
    return [n.to_dict() for n in nodes]


@router.post("/dependencies/nodes")
async def register_node(
    request: RegisterNodeRequest,
) -> dict[str, Any]:
    """Register dependency node."""
    service = DependencyGraphService()

    try:
        node_type = NodeType(request.node_type)
    except ValueError:
        valid = [t.value for t in NodeType]
        raise HTTPException(400, f"Invalid node type. Valid: {valid}")

    node = await service.register_node(
        name=request.name,
        node_type=node_type,
        version=request.version,
        metadata=request.metadata,
    )
    return node.to_dict()


@router.get("/dependencies/nodes/{name}")
async def get_dependency_node(name: str) -> dict[str, Any]:
    """Get node by name."""
    service = DependencyGraphService()
    node = await service.get_node(name)
    if not node:
        raise HTTPException(404, "Node not found")
    return node.to_dict()


@router.put("/dependencies/nodes/{name}/health")
async def update_node_health(
    name: str,
    request: UpdateNodeHealthRequest,
) -> dict[str, Any]:
    """Update node health."""
    service = DependencyGraphService()

    try:
        health = HealthStatus(request.health)
    except ValueError:
        valid = [h.value for h in HealthStatus]
        raise HTTPException(400, f"Invalid health. Valid: {valid}")

    node = await service.update_health(name, health)
    if not node:
        raise HTTPException(404, "Node not found")
    return node.to_dict()


@router.post("/dependencies/edges")
async def add_dependency(
    request: AddDependencyRequest,
) -> dict[str, Any]:
    """Add dependency edge."""
    service = DependencyGraphService()

    try:
        dep_type = DependencyType(request.dependency_type)
    except ValueError:
        valid = [t.value for t in DependencyType]
        raise HTTPException(400, f"Invalid dependency type. Valid: {valid}")

    edge = await service.add_dependency(
        source=request.source,
        target=request.target,
        dependency_type=dep_type,
        description=request.description,
    )
    return edge.to_dict()


@router.get("/dependencies/nodes/{name}/impact")
async def analyze_node_impact(name: str) -> dict[str, Any]:
    """Analyze impact of node failure."""
    service = DependencyGraphService()
    impact = await service.analyze_impact(name)
    return impact.to_dict()


@router.get("/dependencies/critical-path")
async def get_critical_path() -> list[str]:
    """Get critical path nodes."""
    service = DependencyGraphService()
    return await service.get_critical_path()


@router.get("/dependencies/health")
async def check_health_propagation() -> dict[str, str]:
    """Check health with propagation."""
    service = DependencyGraphService()
    return await service.check_health_propagation()


@router.post("/dependencies/initialize")
async def initialize_dependency_graph() -> dict[str, Any]:
    """Initialize default topology."""
    service = DependencyGraphService()
    nodes, edges = await service.initialize_defaults()
    return {"nodes_created": nodes, "edges_created": edges}


# ============================================================================
# Root Cause Helper (Round 9)
# ============================================================================


@router.post("/rootcause/symptoms")
async def record_symptom(
    request: RecordSymptomRequest,
) -> dict[str, Any]:
    """Record symptom."""
    service = RootCauseHelperService()

    try:
        category = SymptomCategory(request.category)
    except ValueError:
        valid = [c.value for c in SymptomCategory]
        raise HTTPException(400, f"Invalid category. Valid: {valid}")

    symptom = await service.record_symptom(
        category=category,
        description=request.description,
        severity=request.severity,
        metrics=request.metrics,
    )
    return symptom.to_dict()


@router.get("/rootcause/symptoms")
async def get_recent_symptoms(
    hours: int = Query(default=24, ge=1, le=168),
    category: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get recent symptoms."""
    service = RootCauseHelperService()

    cat = None
    if category:
        try:
            cat = SymptomCategory(category)
        except ValueError:
            valid = [c.value for c in SymptomCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    symptoms = await service.get_recent_symptoms(hours=hours, category=cat)
    return [s.to_dict() for s in symptoms]


@router.post("/rootcause/analyze")
async def analyze_root_cause(
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    """Analyze root cause of recent symptoms."""
    service = RootCauseHelperService()
    analysis = await service.analyze(hours=hours)
    return analysis.to_dict()


@router.post("/rootcause/analyze-error")
async def analyze_error(
    request: AnalyzeErrorRequest,
) -> dict[str, Any]:
    """Analyze specific error."""
    service = RootCauseHelperService()
    analysis = await service.analyze_error(
        error_message=request.error_message,
        stack_trace=request.stack_trace,
        context=request.context,
    )
    return analysis.to_dict()


@router.get("/rootcause/history")
async def get_analysis_history(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Get analysis history."""
    service = RootCauseHelperService()
    analyses = await service.get_analysis_history(limit=limit)
    return [a.to_dict() for a in analyses]


@router.get("/rootcause/common-causes")
async def get_common_causes(
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, int]:
    """Get common root causes."""
    service = RootCauseHelperService()
    return await service.get_common_causes(days=days)


# ============================================================================
# Drift Detection (Round 9)
# ============================================================================


@router.post("/drift/baseline")
async def capture_baseline(
    request: CaptureBaselineRequest,
) -> dict[str, Any]:
    """Capture drift baseline."""
    service = DriftDetectionService()

    try:
        drift_type = DriftType(request.drift_type)
    except ValueError:
        valid = [t.value for t in DriftType]
        raise HTTPException(400, f"Invalid drift type. Valid: {valid}")

    snapshot = await service.capture_baseline(
        resource=request.resource,
        drift_type=drift_type,
        state_data=request.state_data,
        captured_by=request.captured_by,
    )
    return snapshot.to_dict()


@router.get("/drift/baseline/{resource}")
async def get_baseline(resource: str) -> dict[str, Any]:
    """Get baseline for resource."""
    service = DriftDetectionService()
    baseline = await service.get_baseline(resource)
    if not baseline:
        raise HTTPException(404, "Baseline not found")
    return baseline.to_dict()


@router.post("/drift/check")
async def check_drift(
    request: CheckDriftRequest,
) -> dict[str, Any]:
    """Check for drift."""
    service = DriftDetectionService()
    event = await service.check_drift(
        resource=request.resource,
        current_state=request.current_state,
        critical_keys=request.critical_keys,
    )
    if event:
        return {"drift_detected": True, "event": event.to_dict()}
    return {"drift_detected": False}


@router.post("/drift/check-all")
async def run_drift_check_all() -> list[dict[str, Any]]:
    """Run drift check on all monitored resources."""
    service = DriftDetectionService()
    events = await service.run_check_all()
    return [e.to_dict() for e in events]


@router.get("/drift/events")
async def get_drift_events(
    severity: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get drift events."""
    service = DriftDetectionService()

    sev = None
    if severity:
        try:
            sev = DriftSeverity(severity)
        except ValueError:
            valid = [s.value for s in DriftSeverity]
            raise HTTPException(400, f"Invalid severity. Valid: {valid}")

    events = await service.get_events(limit=limit, severity=sev)
    return [e.to_dict() for e in events]


@router.post("/drift/events/{event_id}/acknowledge")
async def acknowledge_drift(
    event_id: str,
    acknowledged_by: str = Query(...),
) -> dict[str, Any]:
    """Acknowledge drift event."""
    service = DriftDetectionService()
    event = await service.acknowledge_drift(event_id, acknowledged_by)
    if not event:
        raise HTTPException(404, "Event not found")
    return event.to_dict()


@router.get("/drift/report")
async def get_drift_report() -> dict[str, Any]:
    """Generate drift report."""
    service = DriftDetectionService()
    report = await service.generate_report()
    return report.to_dict()


# ============================================================================
# Change Impact Analysis (Round 9)
# ============================================================================


@router.post("/impact/analyze")
async def analyze_change_impact(
    request: AnalyzeChangeRequest,
) -> dict[str, Any]:
    """Analyze change impact."""
    service = ChangeImpactService()

    try:
        change_type = ChangeType(request.change_type)
    except ValueError:
        valid = [t.value for t in ChangeType]
        raise HTTPException(400, f"Invalid change type. Valid: {valid}")

    report = await service.analyze(
        change_type=change_type,
        title=request.title,
        description=request.description,
        requested_by=request.requested_by,
        target_components=request.target_components,
        metadata=request.metadata,
    )
    return report.to_dict()


@router.get("/impact/quick-assess")
async def quick_assess(
    change_type: str = Query(...),
    components: list[str] = Query(default=[]),
) -> dict[str, Any]:
    """Quick risk assessment."""
    service = ChangeImpactService()

    try:
        ct = ChangeType(change_type)
    except ValueError:
        valid = [t.value for t in ChangeType]
        raise HTTPException(400, f"Invalid change type. Valid: {valid}")

    return await service.quick_assess(ct, components)


@router.get("/impact/reports/{report_id}")
async def get_impact_report(report_id: str) -> dict[str, Any]:
    """Get impact report by ID."""
    service = ChangeImpactService()
    report = await service.get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return report.to_dict()


@router.get("/impact/history")
async def get_impact_history(
    change_type: str = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Get impact analysis history."""
    service = ChangeImpactService()

    ct = None
    if change_type:
        try:
            ct = ChangeType(change_type)
        except ValueError:
            valid = [t.value for t in ChangeType]
            raise HTTPException(400, f"Invalid change type. Valid: {valid}")

    reports = await service.get_history(limit=limit, change_type=ct)
    return [r.to_dict() for r in reports]


# ============================================================================
# Round 9 Reference Data
# ============================================================================


@router.get("/reference/control-actions")
async def get_control_actions() -> list[dict[str, str]]:
    """Get control actions."""
    return [{"action": a.value} for a in ControlAction]


@router.get("/reference/policy-types")
async def get_policy_types() -> list[dict[str, str]]:
    """Get policy types."""
    return [{"type": t.value} for t in PolicyType]


@router.get("/reference/approval-categories")
async def get_approval_categories() -> list[dict[str, str]]:
    """Get approval categories."""
    return [{"category": c.value} for c in ApprovalCategory]


@router.get("/reference/backup-targets")
async def get_backup_targets() -> list[dict[str, str]]:
    """Get backup targets."""
    return [{"target": t.value} for t in BackupTarget]


@router.get("/reference/node-types")
async def get_node_types() -> list[dict[str, str]]:
    """Get dependency node types."""
    return [{"type": t.value} for t in NodeType]


@router.get("/reference/symptom-categories")
async def get_symptom_categories() -> list[dict[str, str]]:
    """Get symptom categories."""
    return [{"category": c.value} for c in SymptomCategory]


@router.get("/reference/drift-types")
async def get_drift_types() -> list[dict[str, str]]:
    """Get drift types."""
    return [{"type": t.value} for t in DriftType]


@router.get("/reference/change-types")
async def get_change_types() -> list[dict[str, str]]:
    """Get change types."""
    return [{"type": t.value} for t in ChangeType]


# ============================================================================
# Operational Cockpit (Round 10)
# ============================================================================


@router.get("/cockpit")
async def get_cockpit() -> dict[str, Any]:
    """Get full operational cockpit.

    Returns unified view of all operational data including:
    - Health status
    - Active incidents
    - Queue status
    - SLO/error budgets
    - Cost overview
    - Drift status
    - Pending approvals
    - Risky actions
    - Recommended actions
    """
    service = OpsCockpitService()
    cockpit = await service.get_cockpit()
    return cockpit.to_dict()


@router.get("/cockpit/status")
async def get_quick_status() -> dict[str, Any]:
    """Get quick status overview.

    Lightweight endpoint for dashboards and monitoring.
    """
    service = OpsCockpitService()
    return await service.get_quick_status()


@router.get("/cockpit/actions")
async def get_recommended_actions(
    priority: str = Query(default=None),
    category: str = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Get recommended actions.

    Args:
        priority: Filter by priority (critical, high, medium, low)
        category: Filter by category
        limit: Max actions to return
    """
    service = OpsCockpitService()

    prio = None
    if priority:
        try:
            prio = CockpitActionPriority(priority)
        except ValueError:
            valid = [p.value for p in CockpitActionPriority]
            raise HTTPException(400, f"Invalid priority. Valid: {valid}")

    cat = None
    if category:
        try:
            cat = CockpitActionCategory(category)
        except ValueError:
            valid = [c.value for c in CockpitActionCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    actions = await service.get_actions_only(priority=prio, category=cat, limit=limit)
    return [a.to_dict() for a in actions]


@router.get("/cockpit/health")
async def get_health_summary() -> dict[str, Any]:
    """Get health summary only."""
    service = OpsCockpitService()
    summary = await service._get_health_summary()
    return summary.to_dict()


@router.get("/cockpit/incidents")
async def get_cockpit_incidents() -> dict[str, Any]:
    """Get incident summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_incident_summary()
    return summary.to_dict()


@router.get("/cockpit/queues")
async def get_cockpit_queues() -> dict[str, Any]:
    """Get queue summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_queue_summary()
    return summary.to_dict()


@router.get("/cockpit/slos")
async def get_cockpit_slos() -> dict[str, Any]:
    """Get SLO summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_slo_summary()
    return summary.to_dict()


@router.get("/cockpit/costs")
async def get_cockpit_costs() -> dict[str, Any]:
    """Get cost summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_cost_summary()
    return summary.to_dict()


@router.get("/cockpit/drift")
async def get_cockpit_drift() -> dict[str, Any]:
    """Get drift summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_drift_summary()
    return summary.to_dict()


@router.get("/cockpit/approvals")
async def get_cockpit_approvals() -> dict[str, Any]:
    """Get approval summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_approval_summary()
    return summary.to_dict()


@router.get("/cockpit/risky-actions")
async def get_cockpit_risky_actions() -> dict[str, Any]:
    """Get risky actions summary for cockpit."""
    service = OpsCockpitService()
    summary = await service._get_risky_actions_summary()
    return summary.to_dict()


@router.get("/reference/action-priorities")
async def get_action_priorities() -> list[dict[str, str]]:
    """Get action priorities."""
    return [{"priority": p.value} for p in CockpitActionPriority]


@router.get("/reference/cockpit-categories")
async def get_cockpit_categories() -> list[dict[str, str]]:
    """Get cockpit action categories."""
    return [{"category": c.value} for c in CockpitActionCategory]


# ============================================================================
# Ops Assistant - Auto Triage
# ============================================================================


@router.post("/assistant/triage")
async def triage_incident(
    request: TriageIncidentRequest,
) -> dict[str, Any]:
    """Auto-triage an incident.

    Analyzes incident title and description to determine:
    - Severity (P0-P4)
    - Category (availability, performance, etc.)
    - Affected services
    - Escalation requirements
    - Similar past incidents
    """
    service = OpsAssistantService()
    triage = await service.auto_triage(
        incident_id=request.incident_id,
        title=request.title,
        description=request.description,
        metadata=request.metadata,
    )
    return triage.to_dict()


@router.get("/assistant/triage/{incident_id}")
async def get_triage(incident_id: str) -> dict[str, Any]:
    """Get triage result for an incident."""
    service = OpsAssistantService()
    triage = await service.get_triage(incident_id)
    if not triage:
        raise HTTPException(404, "Triage not found")
    return triage.to_dict()


# ============================================================================
# Ops Assistant - Remediation Plans
# ============================================================================


@router.post("/assistant/plans")
async def generate_remediation_plan(
    request: GeneratePlanRequest,
) -> dict[str, Any]:
    """Generate a remediation plan for an incident.

    Creates step-by-step plan based on incident triage:
    - Diagnostic steps
    - Automated runbook actions
    - Manual interventions
    - Verification steps
    """
    service = OpsAssistantService()
    plan = await service.generate_remediation_plan(
        incident_id=request.incident_id,
        created_by=request.created_by,
    )
    if not plan:
        raise HTTPException(404, "Incident triage not found")
    return plan.to_dict()


@router.get("/assistant/plans/{plan_id}")
async def get_remediation_plan(plan_id: str) -> dict[str, Any]:
    """Get a remediation plan."""
    service = OpsAssistantService()
    plan = await service.get_remediation_plan(plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    return plan.to_dict()


@router.post("/assistant/plans/{plan_id}/advance")
async def advance_plan(
    plan_id: str,
    request: AdvancePlanRequest,
) -> dict[str, Any]:
    """Advance plan to next step.

    Marks current step as complete and moves to next.
    """
    service = OpsAssistantService()
    plan = await service.advance_plan(plan_id, request.actor)
    if not plan:
        raise HTTPException(404, "Plan not found")
    return plan.to_dict()


# ============================================================================
# Ops Assistant - Safe Runbooks
# ============================================================================


@router.post("/assistant/runbooks/initialize")
async def initialize_runbooks() -> dict[str, Any]:
    """Initialize default runbooks.

    Creates safe, pre-defined runbooks for common operations.
    """
    service = OpsAssistantService()
    created = await service.initialize_runbooks()
    return {"created": created, "message": f"Created {created} runbooks"}


@router.get("/assistant/runbooks")
async def list_runbooks(
    category: str = Query(default=None),
    safety_level: str = Query(default=None),
) -> list[dict[str, Any]]:
    """List available runbooks.

    Args:
        category: Filter by category
        safety_level: Filter by safety level (safe, caution, dangerous, critical)
    """
    service = OpsAssistantService()

    cat = None
    if category:
        try:
            cat = TriageCategory(category)
        except ValueError:
            valid = [c.value for c in TriageCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    level = None
    if safety_level:
        try:
            level = RunbookSafetyLevel(safety_level)
        except ValueError:
            valid = [l.value for l in RunbookSafetyLevel]
            raise HTTPException(400, f"Invalid safety_level. Valid: {valid}")

    runbooks = await service.list_runbooks(category=cat, safety_level=level)
    return [r.to_dict() for r in runbooks]


@router.get("/assistant/runbooks/{runbook_id}")
async def get_runbook(runbook_id: str) -> dict[str, Any]:
    """Get runbook details."""
    service = OpsAssistantService()
    runbook = await service.get_runbook(runbook_id)
    if not runbook:
        raise HTTPException(404, "Runbook not found")
    return runbook.to_dict()


@router.post("/assistant/runbooks/{runbook_id}/execute")
async def execute_runbook(
    runbook_id: str,
    request: ExecuteRunbookRequest,
) -> dict[str, Any]:
    """Execute a runbook.

    Runs pre-checks, executes commands, runs post-checks.
    Requires approval for dangerous/critical runbooks.
    """
    service = OpsAssistantService()
    try:
        execution = await service.execute_runbook(
            runbook_id=runbook_id,
            executed_by=request.executed_by,
            parameters=request.parameters,
            approval_id=request.approval_id,
        )
        return execution.to_dict()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/assistant/executions")
async def get_execution_history(
    runbook_id: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get runbook execution history."""
    service = OpsAssistantService()
    executions = await service.get_execution_history(runbook_id=runbook_id, limit=limit)
    return [e.to_dict() for e in executions]


# ============================================================================
# Ops Assistant - Escalation Rules
# ============================================================================


@router.post("/assistant/escalation/initialize")
async def initialize_escalation_rules() -> dict[str, Any]:
    """Initialize default escalation rules."""
    service = OpsAssistantService()
    created = await service.initialize_escalation_rules()
    return {"created": created, "message": f"Created {created} escalation rules"}


@router.get("/assistant/escalation/rules")
async def list_escalation_rules() -> list[dict[str, Any]]:
    """List escalation rules."""
    service = OpsAssistantService()
    rules = await service.list_escalation_rules()
    return [r.to_dict() for r in rules]


# ============================================================================
# Ops Assistant - Operator Notes & Handoffs
# ============================================================================


@router.post("/assistant/notes")
async def create_note(request: CreateNoteRequest) -> dict[str, Any]:
    """Create an operator note.

    For documenting observations, actions, and handoff information.
    """
    service = OpsAssistantService()
    note = await service.create_note(
        author=request.author,
        content=request.content,
        shift=request.shift,
        incident_ids=request.incident_ids,
        action_items=request.action_items,
        tags=request.tags,
    )
    return note.to_dict()


@router.get("/assistant/notes")
async def get_recent_notes(
    hours: int = Query(default=24, ge=1, le=168),
    author: str = Query(default=None),
    shift: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get recent operator notes."""
    service = OpsAssistantService()
    notes = await service.get_recent_notes(hours=hours, author=author, shift=shift)
    return [n.to_dict() for n in notes]


@router.post("/assistant/handoffs")
async def create_handoff(request: CreateHandoffRequest) -> dict[str, Any]:
    """Create a shift handoff.

    Gathers notes, active incidents, and pending actions.
    """
    from datetime import datetime, timezone

    service = OpsAssistantService()
    handoff = await service.create_handoff(
        from_operator=request.from_operator,
        to_operator=request.to_operator,
        shift_start=datetime.fromisoformat(request.shift_start),
        shift_end=datetime.fromisoformat(request.shift_end),
    )
    return handoff.to_dict()


@router.get("/assistant/handoffs/{handoff_id}")
async def get_handoff(handoff_id: str) -> dict[str, Any]:
    """Get handoff details."""
    service = OpsAssistantService()
    handoff = await service.get_handoff(handoff_id)
    if not handoff:
        raise HTTPException(404, "Handoff not found")
    return handoff.to_dict()


@router.post("/assistant/handoffs/{handoff_id}/acknowledge")
async def acknowledge_handoff(
    handoff_id: str,
    request: AcknowledgeHandoffRequest,
) -> dict[str, Any]:
    """Acknowledge a shift handoff."""
    service = OpsAssistantService()
    handoff = await service.acknowledge_handoff(handoff_id, request.acknowledged_by)
    if not handoff:
        raise HTTPException(404, "Handoff not found")
    return handoff.to_dict()


# ============================================================================
# Ops Assistant - Historical Fixes
# ============================================================================


@router.post("/assistant/fixes")
async def record_fix(request: RecordFixRequest) -> dict[str, Any]:
    """Record a successful fix for future recommendations.

    Builds knowledge base for similar incidents.
    """
    service = OpsAssistantService()
    fix = await service.record_fix(
        incident_id=request.incident_id,
        fix_description=request.fix_description,
        runbook_id=request.runbook_id,
        resolution_minutes=request.resolution_minutes,
        tags=request.tags,
    )
    return fix.to_dict()


@router.get("/assistant/fixes")
async def list_historical_fixes(
    category: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """List historical fixes."""
    service = OpsAssistantService()

    cat = None
    if category:
        try:
            cat = TriageCategory(category)
        except ValueError:
            valid = [c.value for c in TriageCategory]
            raise HTTPException(400, f"Invalid category. Valid: {valid}")

    fixes = await service.list_historical_fixes(category=cat, limit=limit)
    return [f.to_dict() for f in fixes]


@router.get("/assistant/recommendations/{incident_id}")
async def get_fix_recommendations(
    incident_id: str,
    limit: int = Query(default=5, ge=1, le=20),
) -> list[dict[str, Any]]:
    """Get fix recommendations for an incident.

    Returns ranked recommendations based on:
    - Similar past incidents
    - Success rates
    - Resolution times
    """
    service = OpsAssistantService()
    recommendations = await service.get_fix_recommendations(incident_id, limit)
    return [r.to_dict() for r in recommendations]


# ============================================================================
# Ops Assistant - Reference Data
# ============================================================================


@router.get("/reference/triage-severities")
async def get_triage_severities() -> list[dict[str, str]]:
    """Get triage severity levels."""
    return [{"severity": s.value, "name": s.name} for s in TriageSeverity]


@router.get("/reference/triage-categories")
async def get_triage_categories() -> list[dict[str, str]]:
    """Get triage categories."""
    return [{"category": c.value} for c in TriageCategory]


@router.get("/reference/runbook-safety-levels")
async def get_runbook_safety_levels() -> list[dict[str, str]]:
    """Get runbook safety levels."""
    return [{"level": l.value} for l in RunbookSafetyLevel]


@router.get("/reference/escalation-levels")
async def get_escalation_levels() -> list[dict[str, str]]:
    """Get escalation levels."""
    return [{"level": l.value, "name": l.name} for l in EscalationLevel]


# ============================================================================
# Decision Safety - Confidence Scoring
# ============================================================================


@router.post("/safety/confidence")
async def calculate_confidence(
    request: CalculateConfidenceRequest,
) -> dict[str, Any]:
    """Calculate confidence score for a recommendation.

    Scores based on:
    - Historical success rate
    - Pattern match strength
    - Data completeness
    - Similar incident count
    - Environmental stability
    """
    service = DecisionSafetyService()
    score = await service.calculate_confidence(
        recommendation_type=request.recommendation_type,
        recommendation_id=request.recommendation_id,
        context=request.context,
    )
    return score.to_dict()


# ============================================================================
# Decision Safety - Auto-Remediation
# ============================================================================


@router.post("/safety/remediation/evaluate")
async def evaluate_auto_remediation(
    request: EvaluateRemediationRequest,
) -> dict[str, Any]:
    """Evaluate whether to auto-remediate.

    Returns decision (execute/defer/reject) with confidence
    and approval context.
    """
    service = DecisionSafetyService()
    decision = await service.evaluate_auto_remediation(
        incident_id=request.incident_id,
        runbook_id=request.runbook_id,
        context=request.context,
    )
    return decision.to_dict()


@router.post("/safety/remediation/mode")
async def set_remediation_mode(
    request: SetRemediationModeRequest,
) -> dict[str, Any]:
    """Set auto-remediation mode.

    Modes:
    - disabled: No auto-remediation
    - safe_only: Only safe runbooks
    - with_approval: Requires pre-approval
    - full_auto: Full automation (dangerous)
    """
    service = DecisionSafetyService()

    try:
        mode = AutoRemediationMode(request.mode)
    except ValueError:
        valid = [m.value for m in AutoRemediationMode]
        raise HTTPException(400, f"Invalid mode. Valid: {valid}")

    return await service.set_auto_remediation_mode(mode, request.set_by)


@router.get("/safety/remediation/mode")
async def get_remediation_mode() -> dict[str, Any]:
    """Get current auto-remediation mode."""
    service = DecisionSafetyService()
    mode = await service.get_auto_remediation_mode()
    return {"mode": mode.value}


# ============================================================================
# Decision Safety - Rollback Suggestions
# ============================================================================


@router.post("/safety/rollback/generate")
async def generate_rollback_suggestion(
    request: GenerateRollbackRequest,
) -> dict[str, Any]:
    """Generate rollback suggestion for an action.

    Includes urgency level, rollback steps, and risk assessment.
    """
    service = DecisionSafetyService()
    suggestion = await service.generate_rollback_suggestion(
        action_id=request.action_id,
        action_type=request.action_type,
        action_details=request.action_details,
    )
    return suggestion.to_dict()


@router.get("/safety/rollback/{action_id}")
async def get_rollback_suggestion(action_id: str) -> dict[str, Any]:
    """Get rollback suggestion for an action."""
    service = DecisionSafetyService()
    suggestion = await service.get_rollback_suggestion(action_id)
    if not suggestion:
        raise HTTPException(404, "Rollback suggestion not found")
    return suggestion.to_dict()


# ============================================================================
# Decision Safety - Post-Incident Reviews
# ============================================================================


@router.post("/safety/reviews/generate")
async def generate_post_incident_review(
    request: GenerateReviewRequest,
) -> dict[str, Any]:
    """Generate post-incident review (PIR).

    Includes timeline, root causes, action items, and lessons learned.
    """
    service = DecisionSafetyService()
    review = await service.generate_post_incident_review(
        incident_id=request.incident_id,
        created_by=request.created_by,
    )
    if not review:
        raise HTTPException(404, "Incident not found")
    return review.to_dict()


@router.get("/safety/reviews/{review_id}")
async def get_review(review_id: str) -> dict[str, Any]:
    """Get post-incident review."""
    service = DecisionSafetyService()
    review = await service.get_review(review_id)
    if not review:
        raise HTTPException(404, "Review not found")
    return review.to_dict()


@router.get("/safety/reviews")
async def list_reviews(
    status: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """List post-incident reviews."""
    service = DecisionSafetyService()

    review_status = None
    if status:
        try:
            review_status = ReviewStatus(status)
        except ValueError:
            valid = [s.value for s in ReviewStatus]
            raise HTTPException(400, f"Invalid status. Valid: {valid}")

    reviews = await service.list_reviews(status=review_status, limit=limit)
    return [r.to_dict() for r in reviews]


# ============================================================================
# Decision Safety - Policy Learning
# ============================================================================


@router.post("/safety/policies/learn")
async def learn_policies_from_incident(
    request: LearnPoliciesRequest,
) -> list[dict[str, Any]]:
    """Learn policies from incident.

    Generates prevention, detection, and response policies
    based on incident analysis.
    """
    service = DecisionSafetyService()
    policies = await service.learn_policy_from_incident(request.incident_id)
    return [p.to_dict() for p in policies]


@router.get("/safety/policies")
async def list_learned_policies(
    incident_id: str = Query(default=None),
    policy_type: str = Query(default=None),
    status: str = Query(default=None),
) -> list[dict[str, Any]]:
    """List learned policies."""
    service = DecisionSafetyService()

    ptype = None
    if policy_type:
        try:
            ptype = PolicyLearningType(policy_type)
        except ValueError:
            valid = [t.value for t in PolicyLearningType]
            raise HTTPException(400, f"Invalid policy_type. Valid: {valid}")

    policies = await service.list_learned_policies(
        incident_id=incident_id,
        policy_type=ptype,
        status=status,
    )
    return [p.to_dict() for p in policies]


@router.post("/safety/policies/{policy_id}/approve")
async def approve_learned_policy(
    policy_id: str,
    request: ApprovePolicyRequest,
) -> dict[str, Any]:
    """Approve a learned policy."""
    service = DecisionSafetyService()
    policy = await service.approve_learned_policy(policy_id, request.approved_by)
    if not policy:
        raise HTTPException(404, "Policy not found")
    return policy.to_dict()


# ============================================================================
# Decision Safety - Production Guards
# ============================================================================


@router.post("/safety/guards/initialize")
async def initialize_guards() -> dict[str, Any]:
    """Initialize default production guards."""
    service = DecisionSafetyService()
    created = await service.initialize_guards()
    return {"created": created, "message": f"Created {created} guards"}


@router.post("/safety/guards/check")
async def check_guard(request: CheckGuardRequest) -> dict[str, Any]:
    """Check if action violates any guards.

    Returns whether action is allowed and any violations.
    """
    service = DecisionSafetyService()
    allowed, message, violation = await service.check_guard(
        action=request.action,
        actor=request.actor,
        context=request.context,
        bypass_reason=request.bypass_reason,
    )
    return {
        "allowed": allowed,
        "message": message,
        "violation": violation.to_dict() if violation else None,
    }


@router.get("/safety/guards")
async def list_guards(
    active_only: bool = Query(default=False),
    guard_level: str = Query(default=None),
) -> list[dict[str, Any]]:
    """List production guards."""
    service = DecisionSafetyService()

    level = None
    if guard_level:
        try:
            level = ProdGuardLevel(guard_level)
        except ValueError:
            valid = [l.value for l in ProdGuardLevel]
            raise HTTPException(400, f"Invalid guard_level. Valid: {valid}")

    guards = await service.list_guards(active_only=active_only, guard_level=level)
    return [g.to_dict() for g in guards]


@router.get("/safety/guards/{guard_id}")
async def get_guard(guard_id: str) -> dict[str, Any]:
    """Get guard details."""
    service = DecisionSafetyService()
    guard = await service.get_guard(guard_id)
    if not guard:
        raise HTTPException(404, "Guard not found")
    return guard.to_dict()


@router.post("/safety/guards/{guard_id}/toggle")
async def toggle_guard(
    guard_id: str,
    request: ToggleGuardRequest,
) -> dict[str, Any]:
    """Toggle guard active state."""
    service = DecisionSafetyService()
    guard = await service.toggle_guard(guard_id, request.active, request.toggled_by)
    if not guard:
        raise HTTPException(404, "Guard not found")
    return guard.to_dict()


@router.get("/safety/violations")
async def get_violations(
    guard_id: str = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Get guard violations."""
    service = DecisionSafetyService()
    violations = await service.get_violations(guard_id=guard_id, limit=limit)
    return [v.to_dict() for v in violations]


# ============================================================================
# Decision Safety - Reference Data
# ============================================================================


@router.get("/reference/confidence-levels")
async def get_confidence_levels() -> list[dict[str, str]]:
    """Get confidence levels."""
    return [{"level": l.value} for l in ConfidenceLevel]


@router.get("/reference/remediation-modes")
async def get_remediation_modes() -> list[dict[str, str]]:
    """Get auto-remediation modes."""
    return [{"mode": m.value} for m in AutoRemediationMode]


@router.get("/reference/rollback-urgencies")
async def get_rollback_urgencies() -> list[dict[str, str]]:
    """Get rollback urgency levels."""
    return [{"urgency": u.value} for u in RollbackUrgency]


@router.get("/reference/review-statuses")
async def get_review_statuses() -> list[dict[str, str]]:
    """Get review statuses."""
    return [{"status": s.value} for s in ReviewStatus]


@router.get("/reference/policy-learning-types")
async def get_policy_learning_types() -> list[dict[str, str]]:
    """Get policy learning types."""
    return [{"type": t.value} for t in PolicyLearningType]


@router.get("/reference/guard-levels")
async def get_guard_levels() -> list[dict[str, str]]:
    """Get production guard levels."""
    return [{"level": l.value} for l in ProdGuardLevel]
