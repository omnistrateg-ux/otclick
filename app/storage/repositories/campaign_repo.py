"""Campaign repository for database operations."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import OutreachCampaignDB

UTC = timezone.utc
logger = logging.getLogger(__name__)


class CampaignRepository:
    """Repository for OutreachCampaign operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        name: str,
        industries: list[str] | None = None,
        regions: list[str] | None = None,
        daily_discovery_limit: int = 100,
        auto_start: bool = False,
    ) -> OutreachCampaignDB:
        """Create a new campaign.

        Args:
            name: Campaign name
            industries: Target industries
            regions: Target regions
            daily_discovery_limit: Daily discovery limit
            auto_start: Whether to start immediately

        Returns:
            Created campaign
        """
        now = datetime.now(UTC)
        campaign = OutreachCampaignDB(
            name=name,
            industries=industries or [],
            regions=regions or [],
            daily_discovery_limit=daily_discovery_limit,
            status="active" if auto_start else "draft",
            is_active=auto_start,
            created_at=now,
            updated_at=now,
            started_at=now if auto_start else None,
        )

        self.session.add(campaign)
        await self.session.flush()
        await self.session.refresh(campaign)

        return campaign

    async def get_by_id(self, campaign_id: str | UUID) -> OutreachCampaignDB | None:
        """Get campaign by ID.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Campaign or None if not found
        """
        try:
            uuid_id = UUID(str(campaign_id))
        except (ValueError, TypeError):
            return None

        result = await self.session.execute(
            select(OutreachCampaignDB).where(OutreachCampaignDB.id == uuid_id)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[OutreachCampaignDB], int]:
        """List all campaigns.

        Args:
            status: Optional status filter
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Tuple of (campaigns list, total count)
        """
        query = select(OutreachCampaignDB)
        count_query = select(func.count(OutreachCampaignDB.id))

        if status:
            query = query.where(OutreachCampaignDB.status == status)
            count_query = count_query.where(OutreachCampaignDB.status == status)

        # Get total count
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one() or 0

        # Get paginated results
        query = query.order_by(OutreachCampaignDB.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)

        return list(result.scalars().all()), total

    async def update(
        self,
        campaign_id: str | UUID,
        **kwargs,
    ) -> OutreachCampaignDB | None:
        """Update a campaign.

        Args:
            campaign_id: Campaign UUID
            **kwargs: Fields to update

        Returns:
            Updated campaign or None if not found
        """
        try:
            uuid_id = UUID(str(campaign_id))
        except (ValueError, TypeError):
            return None

        # Add updated_at
        kwargs["updated_at"] = datetime.now(UTC)

        await self.session.execute(
            update(OutreachCampaignDB)
            .where(OutreachCampaignDB.id == uuid_id)
            .values(**kwargs)
        )

        return await self.get_by_id(uuid_id)

    async def update_status(
        self,
        campaign_id: str | UUID,
        status: str,
    ) -> OutreachCampaignDB | None:
        """Update campaign status.

        Args:
            campaign_id: Campaign UUID
            status: New status

        Returns:
            Updated campaign or None if not found
        """
        now = datetime.now(UTC)
        values = {"status": status, "updated_at": now}

        if status == "active":
            values["is_active"] = True
            values["started_at"] = now
            values["paused_at"] = None
        elif status == "paused":
            values["is_active"] = False
            values["paused_at"] = now

        return await self.update(campaign_id, **values)

    async def increment_stats(
        self,
        campaign_id: str | UUID,
        discovered: int = 0,
        qualified: int = 0,
        converted: int = 0,
    ) -> bool:
        """Increment campaign statistics.

        Args:
            campaign_id: Campaign UUID
            discovered: Increment for leads_discovered
            qualified: Increment for leads_qualified
            converted: Increment for leads_converted

        Returns:
            True if updated
        """
        try:
            uuid_id = UUID(str(campaign_id))
        except (ValueError, TypeError):
            return False

        campaign = await self.get_by_id(uuid_id)
        if not campaign:
            return False

        await self.session.execute(
            update(OutreachCampaignDB)
            .where(OutreachCampaignDB.id == uuid_id)
            .values(
                leads_discovered=campaign.leads_discovered + discovered,
                leads_qualified=campaign.leads_qualified + qualified,
                leads_converted=campaign.leads_converted + converted,
                updated_at=datetime.now(UTC),
            )
        )

        return True

    async def delete(self, campaign_id: str | UUID) -> bool:
        """Delete a campaign.

        Args:
            campaign_id: Campaign UUID

        Returns:
            True if deleted, False if not found
        """
        try:
            uuid_id = UUID(str(campaign_id))
        except (ValueError, TypeError):
            return False

        result = await self.session.execute(
            delete(OutreachCampaignDB).where(OutreachCampaignDB.id == uuid_id)
        )

        return result.rowcount > 0
