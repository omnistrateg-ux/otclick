"""Root API router."""

from fastapi import APIRouter

from app.api.accounts import router as accounts_router
from app.api.admin import router as admin_router
from app.api.analytics import router as analytics_router
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
from app.api.webhooks import router as webhooks_router

router = APIRouter(prefix="/api/v1")

# Include sub-routers
router.include_router(health_router, tags=["health"])
router.include_router(leads_router)
router.include_router(campaigns_router)
router.include_router(emails_router)
router.include_router(handoffs_router)
router.include_router(analytics_router)
router.include_router(webhooks_router)
router.include_router(observability_router)
router.include_router(deliverability_router)
router.include_router(outreach_router)
router.include_router(quality_router)
router.include_router(revenue_router)
router.include_router(accounts_router)
router.include_router(handoff_actions_router)
router.include_router(admin_router)
router.include_router(playbooks_router)
router.include_router(capacity_router)
router.include_router(ops_router)
router.include_router(platform_router)
