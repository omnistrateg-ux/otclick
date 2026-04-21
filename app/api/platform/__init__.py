"""Platform operations API - modular structure.

This module aggregates all platform-related API endpoints:
- environment: Environment guardrails
- deployment: Deployment safety, feature flags
- costs: Cost observability
- slos: SLO and error budgets
- incidents: Incident timeline
- probes: Synthetic probes
- chaos: Chaos drills
- control: Control plane, policies
- approvals: Approval gates
- backups: Backup management
- dependencies: Dependency graph
- rootcause: Root cause analysis
- drift: Drift detection
- impact: Change impact analysis
- cockpit: Operational cockpit
- assistant: Ops assistant
- safety: Decision safety
- knowledge: Knowledge base, patterns, simulation, training
"""

from fastapi import APIRouter

from app.api.platform.approvals import router as approvals_router
from app.api.platform.assistant import router as assistant_router
from app.api.platform.backups import router as backups_router
from app.api.platform.chaos import router as chaos_router
from app.api.platform.cockpit import router as cockpit_router
from app.api.platform.control import router as control_router
from app.api.platform.costs import router as costs_router
from app.api.platform.dependencies import router as dependencies_router
from app.api.platform.deployment import router as deployment_router
from app.api.platform.drift import router as drift_router
from app.api.platform.environment import router as environment_router
from app.api.platform.impact import router as impact_router
from app.api.platform.incidents import router as incidents_router
from app.api.platform.knowledge import router as knowledge_router
from app.api.platform.probes import router as probes_router
from app.api.platform.rootcause import router as rootcause_router
from app.api.platform.safety import router as safety_router
from app.api.platform.slos import router as slos_router

# Create main platform router
router = APIRouter(prefix="/platform", tags=["platform"])

# Include all sub-routers
router.include_router(environment_router)
router.include_router(deployment_router)
router.include_router(costs_router)
router.include_router(slos_router)
router.include_router(incidents_router)
router.include_router(probes_router)
router.include_router(chaos_router)
router.include_router(control_router)
router.include_router(approvals_router)
router.include_router(backups_router)
router.include_router(dependencies_router)
router.include_router(rootcause_router)
router.include_router(drift_router)
router.include_router(impact_router)
router.include_router(cockpit_router)
router.include_router(assistant_router)
router.include_router(safety_router)
router.include_router(knowledge_router)

__all__ = ["router"]
