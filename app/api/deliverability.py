"""Deliverability API endpoints.

Endpoints for monitoring email deliverability metrics.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.outbound_service import OutboundService, CampaignHealth, ReputationScore
from app.services.ab_testing import ABTestingService, VariantType
from app.services.warmup_service import WarmupService
from app.services.send_time_optimizer import SendTimeOptimizer
from app.services.deliverability_trends import DeliverabilityTrendsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deliverability", tags=["deliverability"])


# ============================================================================
# Response Models
# ============================================================================


class DomainMetricsResponse(BaseModel):
    """Domain deliverability metrics."""

    domain: str
    period_days: int
    total_sent: int
    total_delivered: int
    total_bounced: int
    delivery_rate: float
    bounce_rate: float


class CampaignMetricsResponse(BaseModel):
    """Campaign deliverability metrics."""

    campaign_id: str
    period_days: int
    total_sent: int
    total_delivered: int
    total_bounced: int
    total_complained: int
    delivery_rate: float
    bounce_rate: float
    complaint_rate: float
    is_paused: bool
    pause_reason: str | None
    daily_metrics: list[dict[str, Any]]


class CampaignHealthResponse(BaseModel):
    """Campaign health status."""

    campaign_id: str
    total_sent: int
    total_delivered: int
    total_bounced: int
    total_complained: int
    bounce_rate: float
    complaint_rate: float
    is_healthy: bool
    should_pause: bool
    pause_reason: str | None
    sample_size_met: bool = True


class ReputationResponse(BaseModel):
    """Reputation score response."""

    entity: str
    entity_type: str
    score: float
    rating: str
    total_sent: int
    total_delivered: int
    total_bounced: int
    total_complained: int
    delivery_rate: float
    bounce_rate: float
    complaint_rate: float


class SuppressionEntry(BaseModel):
    """Suppression list entry."""

    email: str
    reason: str
    added_at: str | None = None


class SuppressionAddRequest(BaseModel):
    """Request to add email to suppression list."""

    email: str
    reason: str = "manual"
    expires_days: int | None = None


class BulkSuppressionRequest(BaseModel):
    """Request to bulk add emails to suppression list."""

    emails: list[str]
    reason: str = "bulk_import"


class ABTestCreateRequest(BaseModel):
    """Request to create an A/B test."""

    campaign_id: str
    variant_type: str  # "subject", "sequence", "body"
    variants: list[dict[str, Any]]
    min_sample_size: int = 100
    holdout_percent: float | None = None  # 0.0-1.0, uses settings default if None
    winner_metric: str = "qualified_rate"  # reply_rate, qualified_rate, handoff_rate


class SubjectTestCreateRequest(BaseModel):
    """Quick request to create subject A/B test."""

    campaign_id: str
    subject_a: str
    subject_b: str
    name_a: str = "Subject A"
    name_b: str = "Subject B"


class WarmupStartRequest(BaseModel):
    """Request to start warm-up."""

    entity: str  # Email or domain
    entity_type: str = "sender"  # "sender" or "domain"
    initial_daily_limit: int | None = None
    max_daily_limit: int | None = None
    increment_percent: int | None = None


class SendTimeRequest(BaseModel):
    """Request for send time recommendation."""

    segment: str
    earliest: str | None = None  # ISO format datetime
    latest: str | None = None  # ISO format datetime


class ValidationRequest(BaseModel):
    """Pre-send validation request."""

    lead_id: str
    contact_email: str
    subject: str
    body: str


class ValidationResponse(BaseModel):
    """Pre-send validation response."""

    status: str
    can_send: bool
    errors: list[str]
    warnings: list[str]
    checks_passed: list[str]


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/domain/{domain}", response_model=DomainMetricsResponse)
async def get_domain_metrics(
    domain: str,
    days: int = Query(default=7, ge=1, le=30),
) -> DomainMetricsResponse:
    """Get deliverability metrics for a specific domain.

    Args:
        domain: Email domain to check
        days: Number of days to look back (1-30)

    Returns:
        Domain metrics
    """
    outbound = OutboundService()
    metrics = await outbound.get_domain_metrics(domain, days=days)

    return DomainMetricsResponse(**metrics)


@router.get("/campaign/{campaign_id}", response_model=CampaignMetricsResponse)
async def get_campaign_metrics(
    campaign_id: str,
    days: int = Query(default=7, ge=1, le=30),
) -> CampaignMetricsResponse:
    """Get deliverability metrics for a campaign.

    Args:
        campaign_id: Campaign ID
        days: Number of days to look back (1-30)

    Returns:
        Campaign metrics with daily breakdown
    """
    outbound = OutboundService()
    metrics = await outbound.get_campaign_metrics(campaign_id, days=days)

    return CampaignMetricsResponse(**metrics)


@router.get("/campaign/{campaign_id}/health", response_model=CampaignHealthResponse)
async def get_campaign_health(
    campaign_id: str,
) -> CampaignHealthResponse:
    """Get campaign health status.

    Checks if campaign should be paused based on bounce/complaint rates.

    Args:
        campaign_id: Campaign ID

    Returns:
        Campaign health status
    """
    outbound = OutboundService()
    health = await outbound.check_campaign_health(campaign_id)

    return CampaignHealthResponse(
        campaign_id=health.campaign_id,
        total_sent=health.total_sent,
        total_delivered=health.total_delivered,
        total_bounced=health.total_bounced,
        total_complained=health.total_complained,
        bounce_rate=health.bounce_rate,
        complaint_rate=health.complaint_rate,
        is_healthy=health.is_healthy,
        should_pause=health.should_pause,
        pause_reason=health.pause_reason,
        sample_size_met=health.sample_size_met,
    )


@router.post("/campaign/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    reason: str = Query(default="manual_pause"),
) -> dict[str, Any]:
    """Manually pause a campaign.

    Args:
        campaign_id: Campaign ID
        reason: Pause reason

    Returns:
        Pause result
    """
    from app.storage.redis import get_redis

    redis = await get_redis()
    paused_key = f"campaign:paused:{campaign_id}"

    await redis.set(paused_key, reason, ex=86400 * 7)  # 7 days

    logger.warning(f"[API] Campaign manually paused | campaign={campaign_id} | reason={reason}")

    return {
        "success": True,
        "campaign_id": campaign_id,
        "paused": True,
        "reason": reason,
    }


@router.post("/campaign/{campaign_id}/unpause")
async def unpause_campaign(
    campaign_id: str,
) -> dict[str, Any]:
    """Unpause a campaign.

    Args:
        campaign_id: Campaign ID

    Returns:
        Unpause result
    """
    from app.storage.redis import get_redis

    redis = await get_redis()
    paused_key = f"campaign:paused:{campaign_id}"

    deleted = await redis.delete(paused_key)

    logger.info(f"[API] Campaign unpaused | campaign={campaign_id}")

    return {
        "success": True,
        "campaign_id": campaign_id,
        "paused": False,
        "was_paused": deleted > 0,
    }


@router.post("/validate", response_model=ValidationResponse)
async def validate_pre_send(
    request: ValidationRequest,
) -> ValidationResponse:
    """Validate email before sending.

    Performs comprehensive pre-send validation without actually sending.

    Args:
        request: Validation request with lead, contact, and email content

    Returns:
        Validation result with errors and warnings
    """
    from app.storage.database import async_session_factory
    from app.storage.repositories.lead_repo import LeadRepository
    from app.storage.repositories.contact_repo import ContactRepository

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        contact_repo = ContactRepository(db)

        lead = await lead_repo.get(request.lead_id)
        if not lead:
            raise HTTPException(404, f"Lead {request.lead_id} not found")

        # Find contact by email
        contacts = await contact_repo.find_by_lead(request.lead_id)
        contact = next(
            (c for c in contacts if c.email == request.contact_email),
            None,
        )
        if not contact:
            raise HTTPException(404, f"Contact {request.contact_email} not found")

        outbound = OutboundService()
        result = await outbound.validate_pre_send(
            lead=lead,
            contact=contact,
            subject=request.subject,
            body=request.body,
        )

        return ValidationResponse(
            status=result.status.value,
            can_send=result.can_send,
            errors=result.errors,
            warnings=result.warnings,
            checks_passed=result.checks_passed,
        )


@router.get("/throttle/status")
async def get_throttle_status(
    sender_email: str = Query(...),
    recipient_domain: str = Query(default=""),
    campaign_id: str = Query(default=None),
) -> dict[str, Any]:
    """Check current throttle status.

    Args:
        sender_email: Sender email
        recipient_domain: Recipient domain (optional)
        campaign_id: Campaign ID (optional)

    Returns:
        Throttle status
    """
    outbound = OutboundService()
    result = await outbound.check_throttle(
        sender_email=sender_email,
        recipient_domain=recipient_domain,
        campaign_id=campaign_id,
    )

    return {
        "allowed": result.allowed,
        "reason": result.reason,
        "retry_after_seconds": result.retry_after_seconds,
        "current_rate": result.current_rate,
        "limit": result.limit,
    }


# ============================================================================
# Suppression List Endpoints
# ============================================================================


@router.get("/suppression", response_model=list[SuppressionEntry])
async def get_suppression_list(
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[SuppressionEntry]:
    """Get emails in global suppression list.

    Args:
        limit: Maximum emails to return

    Returns:
        List of suppressed emails
    """
    outbound = OutboundService()
    entries = await outbound.get_suppression_list(limit=limit)
    return [SuppressionEntry(**e) for e in entries]


@router.post("/suppression")
async def add_to_suppression(
    request: SuppressionAddRequest,
) -> dict[str, Any]:
    """Add email to global suppression list.

    Args:
        request: Suppression request

    Returns:
        Result
    """
    outbound = OutboundService()
    success = await outbound.add_to_suppression_list(
        email=request.email,
        reason=request.reason,
        expires_days=request.expires_days,
    )

    return {
        "success": success,
        "email": request.email,
        "reason": request.reason,
    }


@router.post("/suppression/bulk")
async def bulk_add_suppression(
    request: BulkSuppressionRequest,
) -> dict[str, Any]:
    """Bulk add emails to suppression list.

    Args:
        request: Bulk suppression request

    Returns:
        Result with count
    """
    outbound = OutboundService()
    count = await outbound.bulk_add_suppression(
        emails=request.emails,
        reason=request.reason,
    )

    return {
        "success": True,
        "added_count": count,
        "reason": request.reason,
    }


@router.delete("/suppression/{email}")
async def remove_from_suppression(
    email: str,
) -> dict[str, Any]:
    """Remove email from suppression list.

    Args:
        email: Email to remove

    Returns:
        Result
    """
    outbound = OutboundService()
    removed = await outbound.remove_from_suppression_list(email)

    return {
        "success": removed,
        "email": email,
        "was_suppressed": removed,
    }


@router.get("/suppression/check/{email}")
async def check_suppression(
    email: str,
) -> dict[str, Any]:
    """Check if email is suppressed.

    Args:
        email: Email to check

    Returns:
        Suppression status
    """
    outbound = OutboundService()
    is_suppressed, reason = await outbound.check_suppression(email)

    return {
        "email": email,
        "is_suppressed": is_suppressed,
        "reason": reason,
    }


# ============================================================================
# Reputation Score Endpoints
# ============================================================================


@router.get("/reputation/sender/{sender_email}", response_model=ReputationResponse)
async def get_sender_reputation(
    sender_email: str,
    days: int = Query(default=30, ge=1, le=90),
) -> ReputationResponse:
    """Get sender reputation score.

    Args:
        sender_email: Sender email address
        days: Days to look back

    Returns:
        Reputation score
    """
    outbound = OutboundService()
    rep = await outbound.get_sender_reputation(sender_email, days=days)

    return ReputationResponse(
        entity=rep.entity,
        entity_type=rep.entity_type,
        score=rep.score,
        rating=rep.rating,
        total_sent=rep.total_sent,
        total_delivered=rep.total_delivered,
        total_bounced=rep.total_bounced,
        total_complained=rep.total_complained,
        delivery_rate=rep.delivery_rate,
        bounce_rate=rep.bounce_rate,
        complaint_rate=rep.complaint_rate,
    )


@router.get("/reputation/domain/{domain}", response_model=ReputationResponse)
async def get_domain_reputation(
    domain: str,
    days: int = Query(default=30, ge=1, le=90),
) -> ReputationResponse:
    """Get domain reputation score.

    Args:
        domain: Recipient domain
        days: Days to look back

    Returns:
        Reputation score
    """
    outbound = OutboundService()
    rep = await outbound.get_domain_reputation(domain, days=days)

    return ReputationResponse(
        entity=rep.entity,
        entity_type=rep.entity_type,
        score=rep.score,
        rating=rep.rating,
        total_sent=rep.total_sent,
        total_delivered=rep.total_delivered,
        total_bounced=rep.total_bounced,
        total_complained=rep.total_complained,
        delivery_rate=rep.delivery_rate,
        bounce_rate=rep.bounce_rate,
        complaint_rate=rep.complaint_rate,
    )


# ============================================================================
# A/B Testing Endpoints
# ============================================================================


@router.post("/ab-test")
async def create_ab_test(
    request: ABTestCreateRequest,
) -> dict[str, Any]:
    """Create an A/B test for a campaign.

    Args:
        request: Test configuration

    Returns:
        Created test info
    """
    ab_service = ABTestingService()

    try:
        variant_type = VariantType(request.variant_type)
    except ValueError:
        raise HTTPException(400, f"Invalid variant_type: {request.variant_type}")

    test = await ab_service.create_test(
        campaign_id=request.campaign_id,
        variant_type=variant_type,
        variants=request.variants,
        min_sample_size=request.min_sample_size,
        holdout_percent=request.holdout_percent,
        winner_metric=request.winner_metric,
    )

    return {
        "test_id": test.test_id,
        "campaign_id": test.campaign_id,
        "variant_type": test.variant_type.value,
        "variants": [{"id": v.id, "name": v.name} for v in test.variants],
        "is_active": test.is_active,
    }


@router.post("/ab-test/subject")
async def create_subject_test(
    request: SubjectTestCreateRequest,
) -> dict[str, Any]:
    """Quick helper to create a subject line A/B test.

    Args:
        request: Subject test configuration

    Returns:
        Created test info
    """
    ab_service = ABTestingService()

    test = await ab_service.create_subject_test(
        campaign_id=request.campaign_id,
        subject_a=request.subject_a,
        subject_b=request.subject_b,
        name_a=request.name_a,
        name_b=request.name_b,
    )

    return {
        "test_id": test.test_id,
        "campaign_id": test.campaign_id,
        "variant_type": test.variant_type.value,
        "variants": [{"id": v.id, "name": v.name, "content": v.content} for v in test.variants],
        "is_active": test.is_active,
    }


@router.get("/ab-test/{test_id}")
async def get_ab_test(
    test_id: str,
) -> dict[str, Any]:
    """Get A/B test details.

    Args:
        test_id: Test ID

    Returns:
        Test details
    """
    ab_service = ABTestingService()
    test = await ab_service.get_test(test_id)

    if not test:
        raise HTTPException(404, f"Test {test_id} not found")

    return {
        "test_id": test.test_id,
        "campaign_id": test.campaign_id,
        "variant_type": test.variant_type.value,
        "variants": [
            {"id": v.id, "name": v.name, "content": v.content, "weight": v.weight}
            for v in test.variants
        ],
        "is_active": test.is_active,
        "winner_variant_id": test.winner_variant_id,
        "created_at": test.created_at.isoformat(),
    }


@router.get("/ab-test/{test_id}/results")
async def get_ab_test_results(
    test_id: str,
) -> dict[str, Any]:
    """Get A/B test results with statistics.

    Args:
        test_id: Test ID

    Returns:
        Test results with variant statistics
    """
    ab_service = ABTestingService()
    results = await ab_service.get_test_results(test_id)

    if not results:
        raise HTTPException(404, f"Test {test_id} not found")

    return results.to_dict()


@router.get("/ab-test/campaign/{campaign_id}")
async def get_campaign_tests(
    campaign_id: str,
) -> list[dict[str, Any]]:
    """Get all A/B tests for a campaign.

    Args:
        campaign_id: Campaign ID

    Returns:
        List of tests
    """
    ab_service = ABTestingService()
    tests = await ab_service.get_campaign_tests(campaign_id)

    return [
        {
            "test_id": t.test_id,
            "variant_type": t.variant_type.value,
            "is_active": t.is_active,
            "winner_variant_id": t.winner_variant_id,
            "created_at": t.created_at.isoformat(),
        }
        for t in tests
    ]


@router.post("/ab-test/{test_id}/stop")
async def stop_ab_test(
    test_id: str,
    winner_variant_id: str = Query(default=None),
) -> dict[str, Any]:
    """Stop an A/B test.

    Args:
        test_id: Test ID
        winner_variant_id: Winning variant ID (optional)

    Returns:
        Result
    """
    ab_service = ABTestingService()
    stopped = await ab_service.stop_test(test_id, winner_variant_id)

    if not stopped:
        raise HTTPException(404, f"Test {test_id} not found")

    return {
        "success": True,
        "test_id": test_id,
        "is_active": False,
        "winner_variant_id": winner_variant_id,
    }


# ============================================================================
# Warm-up Endpoints
# ============================================================================


@router.post("/warmup/start")
async def start_warmup(
    request: WarmupStartRequest,
) -> dict[str, Any]:
    """Start warm-up for a sender or domain.

    Args:
        request: Warm-up configuration

    Returns:
        Warm-up status
    """
    warmup = WarmupService()

    custom_config = None
    if any([request.initial_daily_limit, request.max_daily_limit, request.increment_percent]):
        custom_config = {
            k: v for k, v in {
                "initial_daily_limit": request.initial_daily_limit,
                "max_daily_limit": request.max_daily_limit,
                "increment_percent": request.increment_percent,
            }.items() if v is not None
        }

    status = await warmup.start_warmup(
        entity=request.entity,
        entity_type=request.entity_type,
        custom_config=custom_config,
    )

    return status.to_dict()


@router.get("/warmup/{entity_type}/{entity}")
async def get_warmup_status(
    entity_type: str,
    entity: str,
) -> dict[str, Any]:
    """Get warm-up status for a sender or domain.

    Args:
        entity_type: "sender" or "domain"
        entity: Email or domain

    Returns:
        Warm-up status
    """
    warmup = WarmupService()
    status = await warmup.get_warmup_status(entity, entity_type)
    return status.to_dict()


@router.get("/warmup/{entity_type}/{entity}/limit")
async def get_warmup_limit(
    entity_type: str,
    entity: str,
) -> dict[str, Any]:
    """Get current daily limit considering warm-up.

    Args:
        entity_type: "sender" or "domain"
        entity: Email or domain

    Returns:
        Current limit
    """
    warmup = WarmupService()
    limit = await warmup.get_current_limit(entity, entity_type)
    can_send, reason = await warmup.can_send(entity, entity_type)

    return {
        "entity": entity,
        "entity_type": entity_type,
        "current_daily_limit": limit,
        "can_send": can_send,
        "blocked_reason": reason,
    }


@router.post("/warmup/{entity_type}/{entity}/pause")
async def pause_warmup(
    entity_type: str,
    entity: str,
    reason: str = Query(default="manual"),
) -> dict[str, Any]:
    """Pause warm-up for a sender or domain.

    Args:
        entity_type: "sender" or "domain"
        entity: Email or domain
        reason: Pause reason

    Returns:
        Result
    """
    warmup = WarmupService()
    paused = await warmup.pause_warmup(entity, entity_type, reason)

    return {
        "success": paused,
        "entity": entity,
        "entity_type": entity_type,
        "paused": paused,
        "reason": reason,
    }


@router.post("/warmup/{entity_type}/{entity}/resume")
async def resume_warmup(
    entity_type: str,
    entity: str,
) -> dict[str, Any]:
    """Resume warm-up for a sender or domain.

    Args:
        entity_type: "sender" or "domain"
        entity: Email or domain

    Returns:
        Result
    """
    warmup = WarmupService()
    resumed = await warmup.resume_warmup(entity, entity_type)

    return {
        "success": resumed,
        "entity": entity,
        "entity_type": entity_type,
        "resumed": resumed,
    }


@router.get("/warmup/active")
async def get_active_warmups(
    entity_type: str = Query(default=None),
) -> list[dict[str, Any]]:
    """Get all entities currently in warm-up.

    Args:
        entity_type: Filter by type (optional)

    Returns:
        List of warm-up statuses
    """
    warmup = WarmupService()
    entities = await warmup.get_all_warmup_entities(entity_type)
    return [e.to_dict() for e in entities]


# ============================================================================
# Send-Time Optimization Endpoints
# ============================================================================


@router.get("/send-time/recommend")
async def get_send_time_recommendation(
    segment: str = Query(...),
    earliest: str = Query(default=None),
    latest: str = Query(default=None),
    use_learned: bool = Query(default=True),
) -> dict[str, Any]:
    """Get optimal send time recommendation for a segment.

    Args:
        segment: Lead segment (retail, horeca, it, etc.)
        earliest: Earliest acceptable time (ISO format)
        latest: Latest acceptable time (ISO format)
        use_learned: Use learned data if available

    Returns:
        Send time recommendation
    """
    from datetime import datetime

    optimizer = SendTimeOptimizer()

    earliest_dt = datetime.fromisoformat(earliest) if earliest else None
    latest_dt = datetime.fromisoformat(latest) if latest else None

    if use_learned:
        recommendation = await optimizer.get_learned_optimal_time(
            segment, earliest_dt, latest_dt
        )
    else:
        recommendation = optimizer.get_optimal_send_time(
            segment, earliest_dt, latest_dt
        )

    return recommendation.to_dict()


@router.get("/send-time/stats/{segment}")
async def get_segment_send_stats(
    segment: str,
) -> dict[str, Any]:
    """Get send time statistics for a segment.

    Args:
        segment: Segment to analyze

    Returns:
        Segment statistics
    """
    optimizer = SendTimeOptimizer()
    stats = await optimizer.get_segment_stats(segment)
    return stats.to_dict()


# ============================================================================
# Deliverability Trends / Dashboard Endpoints
# ============================================================================


@router.get("/dashboard")
async def get_deliverability_dashboard(
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, Any]:
    """Get complete deliverability dashboard.

    Args:
        days: Number of days to analyze

    Returns:
        Dashboard data with trends, metrics, and recommendations
    """
    trends_service = DeliverabilityTrendsService()
    dashboard = await trends_service.get_dashboard(days=days)
    return dashboard.to_dict()


@router.get("/trends")
async def get_deliverability_trends(
    days: int = Query(default=14, ge=7, le=90),
) -> dict[str, Any]:
    """Get deliverability trends comparison.

    Compares current period vs previous period.

    Args:
        days: Total days to analyze (split in half for comparison)

    Returns:
        Trend analysis
    """
    trends_service = DeliverabilityTrendsService()
    dashboard = await trends_service.get_dashboard(days=days)

    return {
        "period_days": days,
        "comparison_period": days // 2,
        "trends": [
            {
                "metric": t.metric,
                "current_value": t.current_value,
                "previous_value": t.previous_value,
                "change_percent": t.change_percent,
                "trend": t.trend,
                "is_healthy": t.is_healthy,
            }
            for t in dashboard.trends
        ],
        "overall_health": dashboard.overall_health,
        "issues": dashboard.health_issues,
    }


@router.get("/health")
async def get_deliverability_health(
    days: int = Query(default=7, ge=1, le=30),
) -> dict[str, Any]:
    """Get current deliverability health status.

    Args:
        days: Days to analyze

    Returns:
        Health status with issues and recommendations
    """
    trends_service = DeliverabilityTrendsService()
    dashboard = await trends_service.get_dashboard(days=days)

    return {
        "overall_health": dashboard.overall_health,
        "rates": {
            "delivery_rate": dashboard.delivery_rate,
            "bounce_rate": dashboard.bounce_rate,
            "complaint_rate": dashboard.complaint_rate,
            "open_rate": dashboard.open_rate,
            "reply_rate": dashboard.reply_rate,
        },
        "issues": dashboard.health_issues,
        "recommendations": dashboard.recommendations,
        "period_days": days,
    }


@router.get("/top-performers")
async def get_top_performers(
    days: int = Query(default=30, ge=1, le=90),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    """Get top performing senders and domains.

    Args:
        days: Days to analyze
        limit: Number of results per category

    Returns:
        Top performers
    """
    trends_service = DeliverabilityTrendsService()
    dashboard = await trends_service.get_dashboard(days=days)

    return {
        "period_days": days,
        "top_senders": dashboard.top_senders[:limit],
        "top_domains": dashboard.top_domains[:limit],
        "problem_domains": dashboard.problem_domains[:limit],
    }


@router.get("/daily-metrics")
async def get_daily_metrics(
    days: int = Query(default=14, ge=1, le=90),
) -> list[dict[str, Any]]:
    """Get daily metrics breakdown.

    Args:
        days: Number of days

    Returns:
        Daily metrics list
    """
    trends_service = DeliverabilityTrendsService()
    dashboard = await trends_service.get_dashboard(days=days)

    return [
        {
            "date": m.date,
            "sent": m.sent,
            "delivered": m.delivered,
            "bounced": m.bounced,
            "complained": m.complained,
            "opened": m.opened,
            "replied": m.replied,
            "delivery_rate": round(m.delivery_rate, 4),
            "bounce_rate": round(m.bounce_rate, 4),
            "open_rate": round(m.open_rate, 4),
            "reply_rate": round(m.reply_rate, 4),
        }
        for m in dashboard.daily_metrics
    ]
