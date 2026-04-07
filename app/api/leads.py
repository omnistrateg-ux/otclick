"""Lead API endpoints.

CRUD операции и управление лидами.
"""

from datetime import datetime, timezone

UTC = timezone.utc
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.domain import EmployerLead
from app.models.enums import LeadStatus
from app.orchestrator.engine import LeadOrchestrator
from app.storage.database import async_session_factory

router = APIRouter(prefix="/leads", tags=["leads"])


# Request/Response models
class LeadResponse(BaseModel):
    """Lead response model."""

    id: str
    company_name: str
    status: str
    score: float | None = None
    segment: str | None = None
    industry: str | None = None
    city: str | None = None
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    """Lead list response."""

    items: list[LeadResponse]
    total: int
    page: int
    page_size: int


class LeadCreateRequest(BaseModel):
    """Lead creation request."""

    company_name: str = Field(..., min_length=1, max_length=500)
    hh_employer_id: str | None = None
    industry: str | None = None
    city: str | None = None
    website: str | None = None


class LeadUpdateRequest(BaseModel):
    """Lead update request."""

    status: str | None = None
    score: float | None = None
    segment: str | None = None
    notes: str | None = None


class LeadTransitionRequest(BaseModel):
    """Lead status transition request."""

    target_status: str
    reason: str | None = None


class LeadStatsResponse(BaseModel):
    """Lead statistics response."""

    total: int
    by_status: dict[str, int]
    by_segment: dict[str, int]
    average_score: float


@router.get("", response_model=LeadListResponse)
async def list_leads(
    status: str | None = Query(None, description="Filter by status"),
    segment: str | None = Query(None, description="Filter by segment"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> LeadListResponse:
    """List leads with optional filters.

    Args:
        status: Filter by lead status
        segment: Filter by segment
        page: Page number
        page_size: Items per page

    Returns:
        Paginated list of leads
    """
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)

        # Build filters
        filters = {}
        if status:
            try:
                filters["status"] = LeadStatus(status)
            except ValueError:
                raise HTTPException(400, f"Invalid status: {status}")
        if segment:
            filters["segment"] = segment

        # Get leads
        leads, total = await lead_repo.find_paginated(
            filters=filters,
            page=page,
            page_size=page_size,
        )

        return LeadListResponse(
            items=[
                LeadResponse(
                    id=str(lead.id),
                    company_name=lead.company_name,
                    status=lead.status.value,
                    score=None,
                    segment=None,
                    industry=None,
                    city=lead.city,
                    created_at=lead.created_at,
                    updated_at=lead.updated_at,
                )
                for lead in leads
            ],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/stats", response_model=LeadStatsResponse)
async def get_lead_stats() -> LeadStatsResponse:
    """Get lead statistics.

    Returns:
        Lead statistics
    """
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        stats = await lead_repo.get_stats()

        return LeadStatsResponse(
            total=stats.get("total", 0),
            by_status=stats.get("by_status", {}),
            by_segment=stats.get("by_segment", {}),
            average_score=stats.get("average_score", 0.0),
        )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: str) -> LeadResponse:
    """Get lead by ID.

    Args:
        lead_id: Lead ID

    Returns:
        Lead details

    Raises:
        HTTPException: If lead not found
    """
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        lead = await lead_repo.get(lead_id)

        if not lead:
            raise HTTPException(404, f"Lead {lead_id} not found")

        return LeadResponse(
            id=str(lead.id),
            company_name=lead.company_name,
            status=lead.status.value,
            score=None,
            segment=None,
            industry=None,
            city=lead.city,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )


@router.post("", response_model=LeadResponse, status_code=201)
async def create_lead(request: LeadCreateRequest) -> LeadResponse:
    """Create a new lead.

    Args:
        request: Lead creation data

    Returns:
        Created lead
    """
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)

        # Check for duplicate
        existing = await lead_repo.find_by_company_name(request.company_name)
        if existing:
            raise HTTPException(400, f"Lead for {request.company_name} already exists")

        # Create lead
        lead = EmployerLead(
            company_name=request.company_name,
            domain=request.website,
            source="api",
            city=request.city,
            status=LeadStatus.LEAD_FOUND,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        lead = await lead_repo.create(lead)
        await db.commit()

        return LeadResponse(
            id=str(lead.id),
            company_name=lead.company_name,
            status=lead.status.value,
            score=None,
            segment=None,
            industry=None,
            city=lead.city,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    request: LeadUpdateRequest,
) -> LeadResponse:
    """Update a lead.

    Args:
        lead_id: Lead ID
        request: Update data

    Returns:
        Updated lead
    """
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        lead = await lead_repo.get(lead_id)

        if not lead:
            raise HTTPException(404, f"Lead {lead_id} not found")

        # Update fields
        if request.status:
            try:
                lead.status = LeadStatus(request.status)
            except ValueError:
                raise HTTPException(400, f"Invalid status: {request.status}")
        # Note: score and segment are stored in related tables, not on lead
        # TODO: implement score/segment updates via related repos

        lead.updated_at = datetime.now(UTC)
        await lead_repo.update(lead)

        return LeadResponse(
            id=str(lead.id),
            company_name=lead.company_name,
            status=lead.status.value,
            score=None,
            segment=None,
            industry=None,
            city=lead.city,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )


@router.post("/{lead_id}/transition", response_model=LeadResponse)
async def transition_lead(
    lead_id: str,
    request: LeadTransitionRequest,
) -> LeadResponse:
    """Transition lead to new status.

    Args:
        lead_id: Lead ID
        request: Transition request

    Returns:
        Updated lead
    """
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        lead = await lead_repo.get(lead_id)

        if not lead:
            raise HTTPException(404, f"Lead {lead_id} not found")

        try:
            target_status = LeadStatus(request.target_status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {request.target_status}")

        orchestrator = LeadOrchestrator()

        if not orchestrator.can_transition(lead, target_status):
            allowed = orchestrator.get_valid_transitions(lead)
            raise HTTPException(
                400,
                f"Cannot transition from {lead.status} to {target_status}. "
                f"Allowed: {[s.value for s in allowed]}",
            )

        lead, event = orchestrator.transition(
            lead,
            target_status,
            actor="api",
            reason=request.reason,
        )
        await lead_repo.update(lead)

        return LeadResponse(
            id=str(lead.id),
            company_name=lead.company_name,
            status=lead.status.value,
            score=None,
            segment=None,
            industry=None,
            city=lead.city,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )


@router.get("/{lead_id}/transitions")
async def get_allowed_transitions(lead_id: str) -> dict[str, Any]:
    """Get allowed transitions for a lead.

    Args:
        lead_id: Lead ID

    Returns:
        Allowed transitions
    """
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        lead = await lead_repo.get(lead_id)

        if not lead:
            raise HTTPException(404, f"Lead {lead_id} not found")

        orchestrator = LeadOrchestrator()
        allowed = orchestrator.get_valid_transitions(lead)

        return {
            "current_status": lead.status.value,
            "allowed_transitions": [s.value for s in allowed],
        }


@router.post("/{lead_id}/enrich")
async def enrich_lead(lead_id: str) -> dict[str, Any]:
    """Trigger lead enrichment.

    Args:
        lead_id: Lead ID

    Returns:
        Task info
    """
    from workers.discovery_tasks import enrich_lead as enrich_task

    result = enrich_task.delay(lead_id=lead_id)

    return {
        "message": "Enrichment started",
        "task_id": result.id,
        "lead_id": lead_id,
    }


@router.post("/{lead_id}/score")
async def score_lead(lead_id: str) -> dict[str, Any]:
    """Trigger lead scoring.

    Args:
        lead_id: Lead ID

    Returns:
        Task info
    """
    from workers.discovery_tasks import score_lead as score_task

    result = score_task.delay(lead_id=lead_id)

    return {
        "message": "Scoring started",
        "task_id": result.id,
        "lead_id": lead_id,
    }


@router.post("/{lead_id}/outreach")
async def start_lead_outreach(
    lead_id: str,
    campaign_id: str | None = None,
) -> dict[str, Any]:
    """Start outreach for a lead.

    Args:
        lead_id: Lead ID
        campaign_id: Optional campaign ID

    Returns:
        Task info
    """
    from app.storage.repositories.lead_repo import LeadRepository

    from workers.outreach_tasks import start_outreach

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        lead = await lead_repo.get(lead_id)

        if not lead:
            raise HTTPException(404, f"Lead {lead_id} not found")

        if lead.status not in [LeadStatus.QUALIFIED, LeadStatus.SCORED]:
            raise HTTPException(
                400,
                f"Lead must be qualified to start outreach. "
                f"Current status: {lead.status.value}",
            )

    result = start_outreach.delay(
        lead_id=lead_id,
        campaign_id=campaign_id,
    )

    return {
        "message": "Outreach started",
        "task_id": result.id,
        "lead_id": lead_id,
    }


@router.delete("/{lead_id}")
async def delete_lead(lead_id: str) -> dict[str, str]:
    """Delete a lead.

    Args:
        lead_id: Lead ID

    Returns:
        Confirmation message
    """
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)
        lead = await lead_repo.get(lead_id)

        if not lead:
            raise HTTPException(404, f"Lead {lead_id} not found")

        await lead_repo.delete(lead_id)

        return {"message": f"Lead {lead_id} deleted"}


# Discovery models
class DiscoverRequest(BaseModel):
    """Discovery request parameters."""

    industry: str | None = None
    city: str | None = None
    max_leads: int = Field(default=10, ge=1, le=100)


class DiscoverCompany(BaseModel):
    """Discovered company info."""

    name: str
    vacancy: str | None = None
    lead_id: str | None = None
    status: str  # "created", "duplicate", "error"


class DiscoverResponse(BaseModel):
    """Discovery response."""

    task_id: str
    status: str
    leads_found: int
    leads_created: int
    companies: list[DiscoverCompany]


@router.post("/discover", response_model=DiscoverResponse)
async def discover_leads(request: DiscoverRequest) -> DiscoverResponse:
    """Запуск Discovery — парсим HH.ru и создаём лидов.

    Ищет через /vacancies API и извлекает уникальных работодателей.
    Автоматически обогащает доменом и генерирует hr@домен.
    """
    from uuid import uuid4

    from app.storage.repositories.lead_repo import LeadRepository
    from app.tools.discovery_tools import create_lead_with_contact, find_employers_hh

    task_id = str(uuid4())
    companies: list[DiscoverCompany] = []
    leads_created = 0

    # Map city names to HH.ru area IDs
    area_map = {
        "Москва": 1,
        "Санкт-Петербург": 2,
        "Новосибирск": 4,
        "Екатеринбург": 3,
        "Казань": 88,
        "Нижний Новгород": 66,
        "Челябинск": 104,
        "Самара": 78,
        "Ростов-на-Дону": 76,
        "Уфа": 99,
    }

    area_id = area_map.get(request.city, 1) if request.city else 1

    # Fetch employers from HH.ru vacancies (more results than /employers)
    employers = await find_employers_hh(
        query=request.industry,
        area=area_id,
        per_page=request.max_leads,
    )

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)

        for employer_data in employers:
            company_name = employer_data.get("name", "Unknown")
            # Vacancy name comes from the vacancies search
            vacancy_name = employer_data.get("sample_vacancy")

            # Check for duplicate
            existing = await lead_repo.find_by_company_name(company_name)
            if existing:
                companies.append(DiscoverCompany(
                    name=company_name,
                    vacancy=vacancy_name,
                    status="duplicate",
                ))
                continue

            # Create lead with auto-enrichment (domain + hr@domain)
            try:
                lead, email = await create_lead_with_contact(employer_data)
                created_lead = await lead_repo.create(lead)

                companies.append(DiscoverCompany(
                    name=company_name,
                    vacancy=vacancy_name,
                    lead_id=str(created_lead.id),
                    status="created",
                ))
                leads_created += 1
            except Exception as e:
                companies.append(DiscoverCompany(
                    name=company_name,
                    vacancy=vacancy_name,
                    status="error",
                ))

        # IMPORTANT: Commit the transaction
        await db.commit()

    return DiscoverResponse(
        task_id=task_id,
        status="completed",
        leads_found=len(employers),
        leads_created=leads_created,
        companies=companies,
    )


# Enrichment models
class EnrichResult(BaseModel):
    """Single enrichment result."""

    lead_id: str
    company_name: str
    domain: str | None = None
    email: str | None = None
    status: str  # "enriched", "no_domain", "error"
    error: str | None = None


class EnrichAllResponse(BaseModel):
    """Enrich-all response."""

    total: int
    enriched: int
    results: list[EnrichResult]


@router.post("/enrich-all", response_model=EnrichAllResponse)
async def enrich_all_leads() -> EnrichAllResponse:
    """Enrich all leads - find domains via HH.ru and generate hr@domain emails.

    Returns:
        Enrichment results for all leads
    """
    from urllib.parse import urlparse

    import httpx

    from app.models.domain import EmployerContact
    from app.models.enums import ContactRole
    from app.storage.repositories.lead_repo import LeadRepository

    results: list[EnrichResult] = []
    enriched_count = 0

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)

        # Get all leads without domain
        leads, total = await lead_repo.find_paginated(filters={}, page=1, page_size=1000)

        for lead in leads:
            try:
                # Skip if already has domain
                if lead.domain:
                    results.append(EnrichResult(
                        lead_id=str(lead.id),
                        company_name=lead.company_name,
                        domain=lead.domain,
                        email=f"hr@{lead.domain}",
                        status="enriched",
                    ))
                    enriched_count += 1
                    continue

                # Try to find domain via HH.ru API using company name
                domain = None
                headers = {"User-Agent": "OtclickEmployerEngine/1.0"}

                async with httpx.AsyncClient(timeout=30.0) as client:
                    # Search employers by company name
                    resp = await client.get(
                        "https://api.hh.ru/employers",
                        params={"text": lead.company_name, "per_page": 1},
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        items = data.get("items", [])
                        if items:
                            employer_id = items[0].get("id")
                            # Get detailed employer info
                            detail_resp = await client.get(
                                f"https://api.hh.ru/employers/{employer_id}",
                                headers=headers,
                            )
                            if detail_resp.status_code == 200:
                                detail = detail_resp.json()
                                site_url = detail.get("site_url")
                                if site_url:
                                    parsed = urlparse(site_url)
                                    domain = parsed.netloc.replace("www.", "")

                if domain:
                    # Update lead with domain
                    lead.domain = domain
                    lead.updated_at = datetime.now(UTC)
                    await lead_repo.update(lead)

                    # Create HR contact
                    hr_email = f"hr@{domain}"

                    results.append(EnrichResult(
                        lead_id=str(lead.id),
                        company_name=lead.company_name,
                        domain=domain,
                        email=hr_email,
                        status="enriched",
                    ))
                    enriched_count += 1
                else:
                    results.append(EnrichResult(
                        lead_id=str(lead.id),
                        company_name=lead.company_name,
                        status="no_domain",
                    ))

            except Exception as e:
                results.append(EnrichResult(
                    lead_id=str(lead.id),
                    company_name=lead.company_name,
                    status="error",
                    error=str(e),
                ))

        await db.commit()

    return EnrichAllResponse(
        total=len(leads),
        enriched=enriched_count,
        results=results,
    )


# Campaign send models
class SendCampaignRequest(BaseModel):
    """Send campaign request."""

    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    lead_ids: list[str] | None = None  # If None, send to all leads with email


class SendResult(BaseModel):
    """Single send result."""

    lead_id: str
    company_name: str
    email: str
    status: str  # "sent", "no_email", "error"
    message_id: str | None = None
    error: str | None = None


class SendCampaignResponse(BaseModel):
    """Send campaign response."""

    total: int
    sent: int
    results: list[SendResult]


@router.post("/send-campaign", response_model=SendCampaignResponse)
async def send_campaign(request: SendCampaignRequest) -> SendCampaignResponse:
    """Send campaign emails via Resend.

    Args:
        request: Campaign email details

    Returns:
        Send results for all targeted leads
    """
    import httpx

    from app.storage.repositories.lead_repo import LeadRepository

    RESEND_API_KEY = "re_ipEHgUB2_3APNXpwvAhtKAxRuYaxHTeAB"
    FROM_EMAIL = "Владислав Наков <team@otclick-hr.ru>"

    results: list[SendResult] = []
    sent_count = 0

    async with async_session_factory() as db:
        lead_repo = LeadRepository(db)

        # Get leads to send to
        if request.lead_ids:
            leads = []
            for lead_id in request.lead_ids:
                lead = await lead_repo.get(lead_id)
                if lead:
                    leads.append(lead)
        else:
            leads, _ = await lead_repo.find_paginated(filters={}, page=1, page_size=1000)

        for lead in leads:
            # Check if lead has domain for email
            if not lead.domain:
                results.append(SendResult(
                    lead_id=str(lead.id),
                    company_name=lead.company_name,
                    email="",
                    status="no_email",
                    error="No domain available",
                ))
                continue

            hr_email = f"hr@{lead.domain}"

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "https://api.resend.com/emails",
                        headers={
                            "Authorization": f"Bearer {RESEND_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "from": FROM_EMAIL,
                            "to": [hr_email],
                            "subject": request.subject,
                            "html": request.body,
                        },
                    )

                    if resp.status_code in (200, 201):
                        data = resp.json()
                        message_id = data.get("id")

                        # Update lead status
                        lead.status = LeadStatus.OUTREACH_SENT
                        lead.updated_at = datetime.now(UTC)
                        await lead_repo.update(lead)

                        results.append(SendResult(
                            lead_id=str(lead.id),
                            company_name=lead.company_name,
                            email=hr_email,
                            status="sent",
                            message_id=message_id,
                        ))
                        sent_count += 1
                    else:
                        results.append(SendResult(
                            lead_id=str(lead.id),
                            company_name=lead.company_name,
                            email=hr_email,
                            status="error",
                            error=f"Resend API error: {resp.status_code} - {resp.text}",
                        ))

            except Exception as e:
                results.append(SendResult(
                    lead_id=str(lead.id),
                    company_name=lead.company_name,
                    email=hr_email,
                    status="error",
                    error=str(e),
                ))

        await db.commit()

    return SendCampaignResponse(
        total=len(leads),
        sent=sent_count,
        results=results,
    )
