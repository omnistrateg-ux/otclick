"""Campaign API endpoints.

Управление кампаниями по сбору и обработке лидов.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.enums import LeadStatus

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


# In-memory campaign storage (would be database in production)
_campaigns: dict[str, dict[str, Any]] = {}


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
    campaigns = []
    for campaign_id, campaign_data in _campaigns.items():
        if status and campaign_data.get("status") != status:
            continue

        campaigns.append(
            CampaignResponse(
                id=campaign_id,
                name=campaign_data["name"],
                status=campaign_data["status"],
                industries=campaign_data.get("industries", []),
                regions=campaign_data.get("regions", []),
                leads_discovered=campaign_data.get("leads_discovered", 0),
                leads_qualified=campaign_data.get("leads_qualified", 0),
                leads_converted=campaign_data.get("leads_converted", 0),
                created_at=campaign_data["created_at"],
                updated_at=campaign_data["updated_at"],
            )
        )

    return CampaignListResponse(
        items=campaigns,
        total=len(campaigns),
    )


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: str) -> CampaignResponse:
    """Get campaign by ID.

    Args:
        campaign_id: Campaign ID

    Returns:
        Campaign details
    """
    if campaign_id not in _campaigns:
        raise HTTPException(404, f"Campaign {campaign_id} not found")

    campaign_data = _campaigns[campaign_id]

    return CampaignResponse(
        id=campaign_id,
        name=campaign_data["name"],
        status=campaign_data["status"],
        industries=campaign_data.get("industries", []),
        regions=campaign_data.get("regions", []),
        leads_discovered=campaign_data.get("leads_discovered", 0),
        leads_qualified=campaign_data.get("leads_qualified", 0),
        leads_converted=campaign_data.get("leads_converted", 0),
        created_at=campaign_data["created_at"],
        updated_at=campaign_data["updated_at"],
    )


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(request: CampaignCreateRequest) -> CampaignResponse:
    """Create a new campaign.

    Args:
        request: Campaign creation data

    Returns:
        Created campaign
    """
    campaign_id = str(uuid4())
    now = datetime.now(UTC)

    campaign_data = {
        "name": request.name,
        "status": "active" if request.auto_start else "draft",
        "industries": request.industries,
        "regions": request.regions,
        "daily_discovery_limit": request.daily_discovery_limit,
        "leads_discovered": 0,
        "leads_qualified": 0,
        "leads_converted": 0,
        "created_at": now,
        "updated_at": now,
    }

    _campaigns[campaign_id] = campaign_data

    # If auto_start, trigger discovery
    if request.auto_start:
        from workers.discovery_tasks import batch_discover

        batch_discover.delay(
            industries=request.industries,
            regions=request.regions,
            limit_per_industry=request.daily_discovery_limit,
        )

    return CampaignResponse(
        id=campaign_id,
        name=campaign_data["name"],
        status=campaign_data["status"],
        industries=campaign_data["industries"],
        regions=campaign_data["regions"],
        leads_discovered=0,
        leads_qualified=0,
        leads_converted=0,
        created_at=now,
        updated_at=now,
    )


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
    if campaign_id not in _campaigns:
        raise HTTPException(404, f"Campaign {campaign_id} not found")

    campaign_data = _campaigns[campaign_id]

    if request.name:
        campaign_data["name"] = request.name
    if request.industries is not None:
        campaign_data["industries"] = request.industries
    if request.regions is not None:
        campaign_data["regions"] = request.regions
    if request.daily_discovery_limit is not None:
        campaign_data["daily_discovery_limit"] = request.daily_discovery_limit

    campaign_data["updated_at"] = datetime.now(UTC)

    return CampaignResponse(
        id=campaign_id,
        name=campaign_data["name"],
        status=campaign_data["status"],
        industries=campaign_data.get("industries", []),
        regions=campaign_data.get("regions", []),
        leads_discovered=campaign_data.get("leads_discovered", 0),
        leads_qualified=campaign_data.get("leads_qualified", 0),
        leads_converted=campaign_data.get("leads_converted", 0),
        created_at=campaign_data["created_at"],
        updated_at=campaign_data["updated_at"],
    )


@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: str) -> dict[str, Any]:
    """Start a campaign.

    Args:
        campaign_id: Campaign ID

    Returns:
        Start confirmation
    """
    if campaign_id not in _campaigns:
        raise HTTPException(404, f"Campaign {campaign_id} not found")

    campaign_data = _campaigns[campaign_id]

    if campaign_data["status"] == "active":
        raise HTTPException(400, "Campaign is already active")

    campaign_data["status"] = "active"
    campaign_data["updated_at"] = datetime.now(UTC)

    # Trigger discovery
    from workers.discovery_tasks import batch_discover

    task = batch_discover.delay(
        industries=campaign_data.get("industries", []),
        regions=campaign_data.get("regions", []),
        limit_per_industry=campaign_data.get("daily_discovery_limit", 100),
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
    if campaign_id not in _campaigns:
        raise HTTPException(404, f"Campaign {campaign_id} not found")

    campaign_data = _campaigns[campaign_id]

    if campaign_data["status"] != "active":
        raise HTTPException(400, "Campaign is not active")

    campaign_data["status"] = "paused"
    campaign_data["updated_at"] = datetime.now(UTC)

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
    if campaign_id not in _campaigns:
        raise HTTPException(404, f"Campaign {campaign_id} not found")

    campaign_data = _campaigns[campaign_id]

    if campaign_data["status"] != "paused":
        raise HTTPException(400, "Campaign is not paused")

    campaign_data["status"] = "active"
    campaign_data["updated_at"] = datetime.now(UTC)

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
    if campaign_id not in _campaigns:
        raise HTTPException(404, f"Campaign {campaign_id} not found")

    campaign_data = _campaigns[campaign_id]

    # Calculate funnel
    discovered = campaign_data.get("leads_discovered", 0)
    qualified = campaign_data.get("leads_qualified", 0)
    converted = campaign_data.get("leads_converted", 0)

    conversion_rate = converted / discovered if discovered > 0 else 0.0

    return CampaignStatsResponse(
        campaign_id=campaign_id,
        name=campaign_data["name"],
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
    if campaign_id not in _campaigns:
        raise HTTPException(404, f"Campaign {campaign_id} not found")

    from app.storage.database import async_session_factory
    from app.storage.repositories.lead_repo import LeadRepository

    async with async_session_factory() as db:
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
                    "id": lead.id,
                    "company_name": lead.company_name,
                    "status": lead.status.value,
                    "score": lead.score,
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
    if campaign_id not in _campaigns:
        raise HTTPException(404, f"Campaign {campaign_id} not found")

    del _campaigns[campaign_id]

    return {"message": f"Campaign {campaign_id} deleted"}
