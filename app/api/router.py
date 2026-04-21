"""Root API router."""

from fastapi import APIRouter, Depends

from app.api.accounts import router as accounts_router
from app.api.admin import router as admin_router
from app.api.analytics import router as analytics_router
from app.api.governance import router as governance_router
from app.api.campaigns import router as campaigns_router
from app.api.capacity import router as capacity_router
from app.api.deliverability import router as deliverability_router
from app.api.emails import router as emails_router
from app.api.handoff_actions import router as handoff_actions_router
from app.api.handoffs import router as handoffs_router
from app.api.health import router as health_router
from app.api.leads import router as leads_router
from app.api.observability import router as observability_router
from app.api.ops import router as ops_router
from app.api.outreach import router as outreach_router
from app.api.platform import router as platform_router
from app.api.playbooks import router as playbooks_router
from app.api.quality import router as quality_router
from app.api.revenue import router as revenue_router
from app.api.sales import router as sales_router
from app.api.webhooks import router as webhooks_router
from app.auth.api_key import require_api_key

router = APIRouter(prefix="/api/v1")

# Auth dependency for protected routes
auth_dependency = [Depends(require_api_key)]

# Public routes (no auth required)
router.include_router(health_router, tags=["health"])
router.include_router(webhooks_router)  # Uses signature verification instead

# Protected routes (require API key)
router.include_router(leads_router, dependencies=auth_dependency)
router.include_router(campaigns_router, dependencies=auth_dependency)
router.include_router(emails_router, dependencies=auth_dependency)
router.include_router(handoffs_router, dependencies=auth_dependency)
router.include_router(analytics_router, dependencies=auth_dependency)
router.include_router(observability_router, dependencies=auth_dependency)
router.include_router(deliverability_router, dependencies=auth_dependency)
router.include_router(outreach_router, dependencies=auth_dependency)
router.include_router(quality_router, dependencies=auth_dependency)
router.include_router(revenue_router, dependencies=auth_dependency)
router.include_router(accounts_router, dependencies=auth_dependency)
router.include_router(handoff_actions_router, dependencies=auth_dependency)
router.include_router(admin_router, dependencies=auth_dependency)
router.include_router(playbooks_router, dependencies=auth_dependency)
router.include_router(capacity_router, dependencies=auth_dependency)
router.include_router(ops_router, dependencies=auth_dependency)
router.include_router(platform_router, dependencies=auth_dependency)
router.include_router(governance_router, dependencies=auth_dependency)
router.include_router(sales_router, dependencies=auth_dependency)
