"""Campaign API endpoints.

Управление кампаниями по сбору и обработке лидов.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.enums import LeadStatus
from app.storage.database import async_session_factory
from app.storage.repositories.campaign_repo import CampaignRepository

UTC = timezone.utc
router = APIRouter(prefix="/campaigns", tags=["campaigns"])


# Request/Response models
class CampaignResponse(BaseModel):
    """Campaign response model."""

    id: str
    name: str
    status: str
    industries: list[str]
    regions: list[str]
    leads_discovered: int = 0
    leads_qualified: int = 0
    leads_converted: int = 0
    created_at: datetime
    updated_at: datetime


class CampaignListResponse(BaseModel):
    """Campaign list response."""

    items: list[CampaignResponse]
    total: int


class CampaignCreateRequest(BaseModel):
    """Campaign creation request."""

    name: str = Field(..., min_length=1, max_length=200)
    industries: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    daily_discovery_limit: int = Field(default=100, ge=1, le=1000)
    auto_start: bool = False


class CampaignUpdateRequest(BaseModel):
    """Campaign update request."""

    name: str | None = None
    industries: list[str] | None = None
    regions: list[str] | None = None
    daily_discovery_limit: int | None = None


class CampaignStatsResponse(BaseModel):
    """Campaign statistics."""

    campaign_id: str
    name: str
    funnel: dict[str, int]
    conversion_rate: float
    avg_days_to_conversion: float | None


def _to_response(campaign) -> CampaignResponse:
    """Convert DB model to response."""
    return CampaignResponse(
        id=str(campaign.id),
        name=campaign.name,
        status=campaign.status,
        industries=campaign.industries or [],
        regions=campaign.regions or [],
        leads_discovered=campaign.leads_discovered or 0,
        leads_qualified=campaign.leads_qualified or 0,
        leads_converted=campaign.leads_converted or 0,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    status: str | None = Query(None, description="Filter by status"),
) -> CampaignListResponse:
    """List all campaigns.

    Args:
        status: Optional status filter

    Returns:
        List of campaigns
    """
    async with async_session_factory() as db:
        repo = CampaignRepository(db)
        campaigns, total = await repo.list_all(status=status)

        return CampaignListResponse(
            items=[_to_response(c) for c in campaigns],
            total=total,
        )


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: str) -> CampaignResponse:
    """Get campaign by ID.

    Args:
        campaign_id: Campaign ID

    Returns:
        Campaign details
    """
    async with async_session_factory() as db:
        repo = CampaignRepository(db)
        campaign = await repo.get_by_id(campaign_id)

        if not campaign:
            raise HTTPException(404, f"Campaign {campaign_id} not found")

        return _to_response(campaign)


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(request: CampaignCreateRequest) -> CampaignResponse:
    """Create a new campaign.

    Args:
        request: Campaign creation data

    Returns:
        Created campaign
    """
    async with async_session_factory() as db:
        repo = CampaignRepository(db)
        campaign = await repo.create(
            name=request.name,
            industries=request.industries,
            regions=request.regions,
            daily_discovery_limit=request.daily_discovery_limit,
            auto_start=request.auto_start,
        )
        await db.commit()

        # If auto_start, trigger discovery
        if request.auto_start:
            from workers.discovery_tasks import batch_discover

            batch_discover.delay(
                industries=request.industries,
                regions=request.regions,
                limit_per_industry=request.daily_discovery_limit,
            )

        return _to_response(campaign)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    request: CampaignUpdateRequest,
) -> CampaignResponse:
    """Update a campaign.

    Args:
        campaign_id: Campaign ID
        request: Update data

    Returns:
        Updated campaign
    """
    async with async_session_factory() as db:
        repo = CampaignRepository(db)

        # Check exists
        existing = await repo.get_by_id(campaign_id)
        if not existing:
            raise HTTPException(404, f"Campaign {campaign_id} not found")

        # Build update dict
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.industries is not None:
            updates["industries"] = request.industries
        if request.regions is not None:
            updates["regions"] = request.regions
        if request.daily_discovery_limit is not None:
            updates["daily_discovery_limit"] = request.daily_discovery_limit

        if updates:
            campaign = await repo.update(campaign_id, **updates)
            await db.commit()
        else:
            campaign = existing

        return _to_response(campaign)


@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: str) -> dict[str, Any]:
    """Start a campaign.

    Args:
        campaign_id: Campaign ID

    Returns:
        Start confirmation
    """
    async with async_session_factory() as db:
        repo = CampaignRepository(db)

        campaign = await repo.get_by_id(campaign_id)
        if not campaign:
            raise HTTPException(404, f"Campaign {campaign_id} not found")

        if campaign.status == "active":
            raise HTTPException(400, "Campaign is already active")

        campaign = await repo.update_status(campaign_id, "active")
        await db.commit()

        # Trigger discovery
        from workers.discovery_tasks import batch_discover

        task = batch_discover.delay(
            industries=campaign.industries or [],
            regions=campaign.regions or [],
            limit_per_industry=campaign.daily_discovery_limit or 100,
        )

        return {
            "message": "Campaign started",
            "campaign_id": campaign_id,
            "task_id": task.id,
        }


@router.post("/{campaign_id}/pause")
async def pause_campaign(campaign_id: str) -> dict[str, str]:
    """Pause a campaign.

    Args:
        campaign_id: Campaign ID

    Returns:
        Pause confirmation
    """
    async with async_session_factory() as db:
        repo = CampaignRepository(db)

        campaign = await repo.get_by_id(campaign_id)
        if not campaign:
            raise HTTPException(404, f"Campaign {campaign_id} not found")

        if campaign.status != "active":
            raise HTTPException(400, "Campaign is not active")

        await repo.update_status(campaign_id, "paused")
        await db.commit()

        return {
            "message": "Campaign paused",
            "campaign_id": campaign_id,
        }


@router.post("/{campaign_id}/resume")
async def resume_campaign(campaign_id: str) -> dict[str, str]:
    """Resume a paused campaign.

    Args:
        campaign_id: Campaign ID

    Returns:
        Resume confirmation
    """
    async with async_session_factory() as db:
        repo = CampaignRepository(db)

        campaign = await repo.get_by_id(campaign_id)
        if not campaign:
            raise HTTPException(404, f"Campaign {campaign_id} not found")

        if campaign.status != "paused":
            raise HTTPException(400, "Campaign is not paused")

        await repo.update_status(campaign_id, "active")
        await db.commit()

        return {
            "message": "Campaign resumed",
            "campaign_id": campaign_id,
        }


@router.get("/{campaign_id}/stats", response_model=CampaignStatsResponse)
async def get_campaign_stats(campaign_id: str) -> CampaignStatsResponse:
    """Get campaign statistics.

    Args:
        campaign_id: Campaign ID

    Returns:
        Campaign statistics
    """
    async with async_session_factory() as db:
        repo = CampaignRepository(db)

        campaign = await repo.get_by_id(campaign_id)
        if not campaign:
            raise HTTPException(404, f"Campaign {campaign_id} not found")

        # Calculate funnel
        discovered = campaign.leads_discovered or 0
        qualified = campaign.leads_qualified or 0
        converted = campaign.leads_converted or 0

        conversion_rate = converted / discovered if discovered > 0 else 0.0

        return CampaignStatsResponse(
            campaign_id=str(campaign.id),
            name=campaign.name,
            funnel={
                "discovered": discovered,
                "qualified": qualified,
                "converted": converted,
            },
            conversion_rate=conversion_rate,
            avg_days_to_conversion=None,  # Would calculate from lead data
        )


@router.get("/{campaign_id}/leads")
async def get_campaign_leads(
    campaign_id: str,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Get leads for a campaign.

    Args:
        campaign_id: Campaign ID
        status: Filter by status
        page: Page number
        page_size: Items per page

    Returns:
        Campaign leads
    """
    async with async_session_factory() as db:
        # Check campaign exists
        repo = CampaignRepository(db)
        campaign = await repo.get_by_id(campaign_id)
        if not campaign:
            raise HTTPException(404, f"Campaign {campaign_id} not found")

        from app.storage.repositories.lead_repo import LeadRepository

        lead_repo = LeadRepository(db)

        filters = {"campaign_id": campaign_id}
        if status:
            try:
                filters["status"] = LeadStatus(status)
            except ValueError:
                raise HTTPException(400, f"Invalid status: {status}")

        leads, total = await lead_repo.find_paginated(
            filters=filters,
            page=page,
            page_size=page_size,
        )

        return {
            "items": [
                {
                    "id": str(lead.id),
                    "company_name": lead.company_name,
                    "status": lead.status.value,
                    "score": getattr(lead, "score", None),
                }
                for lead in leads
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: str) -> dict[str, str]:
    """Delete a campaign.

    Args:
        campaign_id: Campaign ID

    Returns:
        Deletion confirmation
    """
    async with async_session_factory() as db:
        repo = CampaignRepository(db)

        deleted = await repo.delete(campaign_id)
        if not deleted:
            raise HTTPException(404, f"Campaign {campaign_id} not found")

        await db.commit()

        return {"message": f"Campaign {campaign_id} deleted"}
