"""Data Quality API endpoints.

Contact confidence, source quality, lead freshness, and manager feedback.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.data_quality import DataQualityService
from app.services.lead_freshness import LeadFreshnessService
from app.services.manager_feedback import ManagerFeedbackService, FeedbackType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quality", tags=["quality"])


# ============================================================================
# Request/Response Models
# ============================================================================


class ContactConfidenceRequest(BaseModel):
    """Request for contact confidence calculation."""

    email: str | None = None
    email_verified: bool = False
    email_source: str | None = None
    phone: str | None = None
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    job_title: str | None = None
    role: str | None = None
    contact_source: str | None = None
    bounce_count: int = 0
    reply_received: bool = False


class ContactConfidenceResponse(BaseModel):
    """Contact confidence response."""

    overall_score: float
    email_confidence: float
    phone_confidence: float
    name_confidence: float
    role_confidence: float
    source_quality: float
    verification_status: str
    issues: list[str]
    recommendations: list[str]


class SourceQualityResponse(BaseModel):
    """Source quality response."""

    source: str
    base_score: float
    adjusted_score: float
    sample_size: int
    success_rate: float
    bounce_rate: float
    reply_rate: float
    conversion_rate: float


class RecordOutcomeRequest(BaseModel):
    """Request to record source outcome."""

    source: str
    outcome: str  # delivered, bounced, replied, qualified


class FreshnessAssessmentResponse(BaseModel):
    """Freshness assessment response."""

    entity_type: str
    status: str
    days_old: int
    last_updated: str | None
    last_enriched: str | None
    needs_enrichment: bool
    enrichment_priority: str
    stale_fields: list[str]
    confidence_adjustment: float


class QueueEnrichmentRequest(BaseModel):
    """Request to queue entity for enrichment."""

    entity_type: str
    entity_id: str
    priority: str = "medium"
    reason: str = "manual_request"
    stale_fields: list[str] | None = None


class ManagerFeedbackRequest(BaseModel):
    """Request to submit manager feedback."""

    lead_id: str
    feedback_type: str
    contact_id: str | None = None
    manager_id: str = "api"
    notes: str | None = None
    metadata: dict[str, Any] | None = None


class ScoreAdjustmentResponse(BaseModel):
    """Score adjustment response."""

    lead_id: str
    score_adjustment: float
    feedback_count: int
    positive_count: int
    negative_count: int


class PrioritizeContactsRequest(BaseModel):
    """Request to prioritize contacts."""

    contacts: list[dict[str, Any]]


# ============================================================================
# Contact Confidence Endpoints
# ============================================================================


@router.post("/contact/confidence", response_model=ContactConfidenceResponse)
async def calculate_contact_confidence(
    request: ContactConfidenceRequest,
) -> ContactConfidenceResponse:
    """Calculate confidence score for a contact.

    Args:
        request: Contact details

    Returns:
        Confidence assessment
    """
    service = DataQualityService()

    confidence = service.calculate_contact_confidence(
        email=request.email,
        email_verified=request.email_verified,
        email_source=request.email_source,
        phone=request.phone,
        full_name=request.full_name,
        first_name=request.first_name,
        last_name=request.last_name,
        job_title=request.job_title,
        role=request.role,
        contact_source=request.contact_source,
        bounce_count=request.bounce_count,
        reply_received=request.reply_received,
    )

    return ContactConfidenceResponse(
        overall_score=round(confidence.overall_score, 3),
        email_confidence=round(confidence.email_confidence, 3),
        phone_confidence=round(confidence.phone_confidence, 3),
        name_confidence=round(confidence.name_confidence, 3),
        role_confidence=round(confidence.role_confidence, 3),
        source_quality=round(confidence.source_quality, 3),
        verification_status=confidence.verification_status,
        issues=confidence.issues,
        recommendations=confidence.recommendations,
    )


@router.post("/contacts/prioritize")
async def prioritize_contacts(
    request: PrioritizeContactsRequest,
) -> list[dict[str, Any]]:
    """Prioritize contacts by confidence score.

    Args:
        request: List of contacts

    Returns:
        Sorted contacts with confidence scores
    """
    service = DataQualityService()
    prioritized = service.prioritize_contacts(request.contacts)
    return prioritized


# ============================================================================
# Source Quality Endpoints
# ============================================================================


@router.get("/source/{source}", response_model=SourceQualityResponse)
async def get_source_quality(
    source: str,
) -> SourceQualityResponse:
    """Get quality score for a data source.

    Args:
        source: Source name (e.g., hh.ru, linkedin, csv_import)

    Returns:
        Source quality score
    """
    service = DataQualityService()
    quality = await service.get_source_quality(source)

    return SourceQualityResponse(
        source=quality.source,
        base_score=quality.base_score,
        adjusted_score=quality.adjusted_score,
        sample_size=quality.sample_size,
        success_rate=quality.success_rate,
        bounce_rate=quality.bounce_rate,
        reply_rate=quality.reply_rate,
        conversion_rate=quality.conversion_rate,
    )


@router.get("/sources")
async def get_all_source_qualities() -> list[dict[str, Any]]:
    """Get quality scores for all tracked sources.

    Returns:
        List of source quality scores, sorted by adjusted score
    """
    service = DataQualityService()
    qualities = await service.get_all_source_qualities()
    return [q.to_dict() for q in qualities]


@router.post("/source/outcome")
async def record_source_outcome(
    request: RecordOutcomeRequest,
) -> dict[str, Any]:
    """Record outcome for source quality tracking.

    Used to learn source quality over time.

    Args:
        request: Source and outcome

    Returns:
        Success status
    """
    service = DataQualityService()
    await service.record_source_outcome(
        source=request.source,
        outcome=request.outcome,
    )

    return {
        "success": True,
        "source": request.source,
        "outcome": request.outcome,
    }


# ============================================================================
# Lead Freshness Endpoints
# ============================================================================


@router.get("/freshness/lead/{lead_id}")
async def assess_lead_freshness(
    lead_id: str,
) -> FreshnessAssessmentResponse:
    """Assess freshness of a lead.

    Args:
        lead_id: Lead ID

    Returns:
        Freshness assessment
    """
    from datetime import datetime, timezone
    from app.storage.database import async_session_factory
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        lead = await lead_repo.get(lead_id)

        if not lead:
            raise HTTPException(404, f"Lead {lead_id} not found")

        service = LeadFreshnessService()
        assessment = service.assess_lead_freshness(
            created_at=lead.created_at,
            updated_at=lead.updated_at,
            enriched_at=getattr(lead, 'enriched_at', None),
            last_activity_at=getattr(lead, 'last_activity_at', None),
        )
        assessment.entity_id = lead_id

        return FreshnessAssessmentResponse(
            entity_type=assessment.entity_type,
            status=assessment.status.value,
            days_old=assessment.days_old,
            last_updated=assessment.last_updated.isoformat() if assessment.last_updated else None,
            last_enriched=assessment.last_enriched.isoformat() if assessment.last_enriched else None,
            needs_enrichment=assessment.needs_enrichment,
            enrichment_priority=assessment.enrichment_priority,
            stale_fields=assessment.stale_fields,
            confidence_adjustment=assessment.confidence_adjustment,
        )


@router.get("/freshness/stale-leads")
async def find_stale_leads(
    days_threshold: int = Query(default=None, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Find leads that need re-enrichment.

    Args:
        days_threshold: Days since last enrichment
        limit: Maximum leads to return

    Returns:
        List of stale leads
    """
    service = LeadFreshnessService()
    stale = await service.find_stale_leads(
        days_threshold=days_threshold,
        limit=limit,
    )
    return stale


@router.post("/freshness/enrich")
async def queue_for_enrichment(
    request: QueueEnrichmentRequest,
) -> dict[str, Any]:
    """Queue entity for re-enrichment.

    Args:
        request: Enrichment queue request

    Returns:
        Result
    """
    service = LeadFreshnessService()

    success = await service.queue_for_enrichment(
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        priority=request.priority,
        reason=request.reason,
        stale_fields=request.stale_fields,
    )

    return {
        "success": success,
        "entity_type": request.entity_type,
        "entity_id": request.entity_id,
        "priority": request.priority,
    }


@router.get("/freshness/queue/{entity_type}")
async def get_enrichment_queue(
    entity_type: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get entities queued for re-enrichment.

    Args:
        entity_type: Type of entity (lead, contact, profile)
        limit: Maximum to return

    Returns:
        Enrichment queue
    """
    service = LeadFreshnessService()
    queue = await service.get_enrichment_queue(
        entity_type=entity_type,
        limit=limit,
    )
    return [task.to_dict() for task in queue]


@router.post("/freshness/record-enrichment")
async def record_enrichment(
    entity_type: str,
    entity_id: str,
    source: str,
    fields_updated: list[str],
) -> dict[str, Any]:
    """Record that enrichment was performed.

    Removes entity from enrichment queue.

    Args:
        entity_type: Type of entity
        entity_id: Entity ID
        source: Enrichment source
        fields_updated: Fields that were updated

    Returns:
        Result
    """
    service = LeadFreshnessService()

    await service.record_enrichment(
        entity_type=entity_type,
        entity_id=entity_id,
        source=source,
        fields_updated=fields_updated,
    )

    return {
        "success": True,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "source": source,
        "fields_updated": fields_updated,
    }


# ============================================================================
# Manager Feedback Endpoints
# ============================================================================


@router.post("/feedback")
async def submit_feedback(
    request: ManagerFeedbackRequest,
) -> dict[str, Any]:
    """Submit manager feedback for a lead.

    Affects future scoring for similar leads.

    Args:
        request: Feedback details

    Returns:
        Feedback ID and score adjustment
    """
    service = ManagerFeedbackService()

    try:
        feedback_type = FeedbackType(request.feedback_type)
    except ValueError:
        valid_types = [t.value for t in FeedbackType]
        raise HTTPException(400, f"Invalid feedback_type. Valid: {valid_types}")

    # Get lead source and segment for learning
    lead_source = None
    lead_segment = None
    if request.metadata:
        lead_source = request.metadata.get("source")
        lead_segment = request.metadata.get("segment")

    feedback = await service.submit_feedback(
        lead_id=request.lead_id,
        manager_id=request.manager_id,
        feedback_type=feedback_type,
        comment=request.notes,
        contact_id=request.contact_id,
        lead_source=lead_source,
        lead_segment=lead_segment,
    )

    # Get updated score adjustment
    adjustment = await service.get_lead_score_adjustment(request.lead_id)

    return {
        "feedback_id": feedback.id,
        "lead_id": request.lead_id,
        "feedback_type": request.feedback_type,
        "score_adjustment": round(adjustment, 3),
    }


@router.get("/feedback/lead/{lead_id}")
async def get_lead_feedback(
    lead_id: str,
) -> dict[str, Any]:
    """Get all feedback for a lead.

    Args:
        lead_id: Lead ID

    Returns:
        Lead feedback with score adjustment
    """
    service = ManagerFeedbackService()

    feedback_list = await service.get_lead_feedback(lead_id)
    adjustment = await service.get_lead_score_adjustment(lead_id)

    return {
        "lead_id": lead_id,
        "feedback": [f.to_dict() for f in feedback_list],
        "score_adjustment": round(adjustment, 3),
        "feedback_count": len(feedback_list),
    }


@router.get("/feedback/lead/{lead_id}/adjustment", response_model=ScoreAdjustmentResponse)
async def get_score_adjustment(
    lead_id: str,
) -> ScoreAdjustmentResponse:
    """Get score adjustment for a lead based on feedback.

    Args:
        lead_id: Lead ID

    Returns:
        Score adjustment details
    """
    service = ManagerFeedbackService()

    adjustment = await service.get_lead_score_adjustment(lead_id)
    feedback_list = await service.get_lead_feedback(lead_id)

    positive_count = sum(
        1 for f in feedback_list
        if f.feedback_type in [FeedbackType.MEETING_SCHEDULED, FeedbackType.DEAL_CLOSED,
                               FeedbackType.HIGH_QUALITY_LEAD, FeedbackType.GOOD_TIMING]
    )
    negative_count = sum(
        1 for f in feedback_list
        if f.feedback_type in [FeedbackType.WRONG_CONTACT, FeedbackType.LOW_QUALITY_LEAD,
                               FeedbackType.NOT_INTERESTED, FeedbackType.WRONG_EMAIL]
    )

    return ScoreAdjustmentResponse(
        lead_id=lead_id,
        score_adjustment=round(adjustment, 3),
        feedback_count=len(feedback_list),
        positive_count=positive_count,
        negative_count=negative_count,
    )


@router.get("/feedback/source/{source}/adjustment")
async def get_source_adjustment(
    source: str,
) -> dict[str, Any]:
    """Get score adjustment for a data source based on feedback.

    Args:
        source: Source name

    Returns:
        Source adjustment
    """
    service = ManagerFeedbackService()
    adjustment = await service.get_source_adjustment(source)

    return {
        "source": source,
        "original_weight": round(adjustment.original_weight, 3),
        "suggested_weight": round(adjustment.suggested_weight, 3),
        "score_adjustment": round(adjustment.suggested_weight - adjustment.original_weight, 3),
        "confidence": round(adjustment.confidence, 3),
        "sample_size": adjustment.sample_size,
        "summary": adjustment.feedback_summary,
    }


@router.get("/feedback/segment/{segment}/adjustment")
async def get_segment_adjustment(
    segment: str,
) -> dict[str, Any]:
    """Get score adjustment for a segment based on feedback.

    Args:
        segment: Segment name

    Returns:
        Segment adjustment
    """
    service = ManagerFeedbackService()
    adjustment = await service.get_segment_adjustment(segment)

    return {
        "segment": segment,
        "original_weight": round(adjustment.original_weight, 3),
        "suggested_weight": round(adjustment.suggested_weight, 3),
        "score_adjustment": round(adjustment.suggested_weight - adjustment.original_weight, 3),
        "confidence": round(adjustment.confidence, 3),
        "sample_size": adjustment.sample_size,
        "summary": adjustment.feedback_summary,
    }


@router.get("/feedback/types")
async def get_feedback_types() -> list[dict[str, Any]]:
    """Get all available feedback types.

    Returns:
        List of feedback types with descriptions
    """
    from app.services.manager_feedback import FEEDBACK_SCORE_ADJUSTMENTS

    return [
        {
            "type": ft.value,
            "score_adjustment": adj,
            "is_positive": adj > 0,
        }
        for ft, adj in FEEDBACK_SCORE_ADJUSTMENTS.items()
    ]


@router.get("/feedback/stats")
async def get_feedback_stats(
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, Any]:
    """Get feedback statistics.

    Args:
        days: Days to analyze

    Returns:
        Feedback statistics
    """
    service = ManagerFeedbackService()
    stats = await service.get_feedback_stats(days=days)
    return stats


# ============================================================================
# Combined Quality Score Endpoint
# ============================================================================


@router.get("/lead/{lead_id}/quality-score")
async def get_lead_quality_score(
    lead_id: str,
) -> dict[str, Any]:
    """Get combined quality score for a lead.

    Includes data quality, freshness, and feedback adjustments.

    Args:
        lead_id: Lead ID

    Returns:
        Combined quality assessment
    """
    from datetime import datetime
    from app.storage.database import async_session_factory
    from app.storage.repositories.lead_repo import LeadRepository
    from app.storage.repositories.contact_repo import ContactRepository

    data_quality = DataQualityService()
    freshness_service = LeadFreshnessService()
    feedback_service = ManagerFeedbackService()

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        contact_repo = ContactRepository(db)

        lead = await lead_repo.get(lead_id)
        if not lead:
            raise HTTPException(404, f"Lead {lead_id} not found")

        # Get contacts
        contacts = await contact_repo.find_by_lead(lead_id)

        # Score contacts
        contact_scores = []
        for contact in contacts:
            conf = data_quality.calculate_contact_confidence(
                email=contact.email,
                email_verified=getattr(contact, 'email_verified', False),
                phone=contact.phone,
                full_name=contact.full_name,
                job_title=contact.job_title,
                role=contact.role.value if contact.role else None,
            )
            contact_scores.append({
                "contact_id": str(contact.id),
                "email": contact.email,
                "confidence_score": round(conf.overall_score, 3),
            })

        # Average contact confidence
        avg_contact_confidence = (
            sum(c["confidence_score"] for c in contact_scores) / len(contact_scores)
            if contact_scores else 0.5
        )

        # Freshness assessment
        freshness = freshness_service.assess_lead_freshness(
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )

        # Feedback adjustment
        feedback_adj = await feedback_service.get_lead_score_adjustment(lead_id)

        # Source adjustment
        source_adj = await feedback_service.get_source_adjustment(lead.source or "unknown")

        # Calculate combined quality score
        base_score = avg_contact_confidence
        freshness_adj = freshness.confidence_adjustment
        total_adjustment = feedback_adj + source_adj + freshness_adj

        final_score = max(0.0, min(1.0, base_score + total_adjustment))

        return {
            "lead_id": lead_id,
            "final_quality_score": round(final_score, 3),
            "base_score": round(base_score, 3),
            "adjustments": {
                "freshness": round(freshness_adj, 3),
                "feedback": round(feedback_adj, 3),
                "source": round(source_adj, 3),
                "total": round(total_adjustment, 3),
            },
            "freshness": {
                "status": freshness.status.value,
                "days_old": freshness.days_old,
                "needs_enrichment": freshness.needs_enrichment,
            },
            "contacts": contact_scores,
            "contact_count": len(contact_scores),
        }
