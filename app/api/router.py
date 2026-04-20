"""Root API router."""

from fastapi import APIRouter

from app.api.analytics import router as analytics_router
from app.api.campaigns import router as campaigns_router
from app.api.emails import router as emails_router
from app.api.handoffs import router as handoffs_router
from app.api.health import router as health_router
from app.api.leads import router as leads_router
from app.api.observability import router as observability_router
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
