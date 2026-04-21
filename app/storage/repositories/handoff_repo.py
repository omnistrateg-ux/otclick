"""Handoff repository for database operations."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import ManagerHandoffDB

UTC = timezone.utc
logger = logging.getLogger(__name__)


class HandoffRepository:
    """Repository for ManagerHandoff operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        lead_id: str | UUID,
        manager_id: str,
        company_name: str,
        priority: str = "normal",
        talking_points: list[str] | None = None,
        notes: str | None = None,
    ) -> ManagerHandoffDB:
        """Create a new handoff.

        Args:
            lead_id: Lead UUID
            manager_id: Manager ID
            company_name: Company name
            priority: Handoff priority
            talking_points: List of talking points
            notes: Optional notes

        Returns:
            Created handoff
        """
        try:
            uuid_lead_id = UUID(str(lead_id))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid lead_id: {lead_id}")

        now = datetime.now(UTC)
        handoff = ManagerHandoffDB(
            lead_id=uuid_lead_id,
            manager_id=manager_id,
            company_name=company_name,
            status="pending",
            priority=priority,
            talking_points=talking_points or [],
            notes=notes,
            created_at=now,
        )

        self.session.add(handoff)
        await self.session.flush()
        await self.session.refresh(handoff)

        return handoff

    async def get_by_id(self, handoff_id: str | UUID) -> ManagerHandoffDB | None:
        """Get handoff by ID.

        Args:
            handoff_id: Handoff UUID

        Returns:
            Handoff or None if not found
        """
        try:
            uuid_id = UUID(str(handoff_id))
        except (ValueError, TypeError):
            return None

        result = await self.session.execute(
            select(ManagerHandoffDB).where(ManagerHandoffDB.id == uuid_id)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        manager_id: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ManagerHandoffDB], int]:
        """List handoffs with optional filters.

        Args:
            manager_id: Filter by manager
            status: Filter by status
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (handoffs list, total count)
        """
        query = select(ManagerHandoffDB)
        count_query = select(func.count(ManagerHandoffDB.id))

        if manager_id:
            query = query.where(ManagerHandoffDB.manager_id == manager_id)
            count_query = count_query.where(ManagerHandoffDB.manager_id == manager_id)

        if status:
            query = query.where(ManagerHandoffDB.status == status)
            count_query = count_query.where(ManagerHandoffDB.status == status)

        # Get total count
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one() or 0

        # Get paginated results
        offset = (page - 1) * page_size
        query = query.order_by(ManagerHandoffDB.created_at.desc()).offset(offset).limit(page_size)
        result = await self.session.execute(query)

        return list(result.scalars().all()), total

    async def get_stats(self) -> dict[str, int | float | None]:
        """Get handoff statistics.

        Returns:
            Dict with statistics
        """
        # Count by status
        result = await self.session.execute(
            select(
                ManagerHandoffDB.status,
                func.count(ManagerHandoffDB.id),
            ).group_by(ManagerHandoffDB.status)
        )

        status_counts = dict(result.all())
        total = sum(status_counts.values())

        return {
            "total": total,
            "pending": status_counts.get("pending", 0),
            "accepted": status_counts.get("accepted", 0),
            "completed": status_counts.get("completed", 0),
            "rejected": status_counts.get("rejected", 0),
            "avg_acceptance_time_hours": None,  # Would calculate from timestamps
            "avg_completion_time_hours": None,
        }

    async def update_status(
        self,
        handoff_id: str | UUID,
        status: str,
        **kwargs,
    ) -> ManagerHandoffDB | None:
        """Update handoff status.

        Args:
            handoff_id: Handoff UUID
            status: New status
            **kwargs: Additional fields to update

        Returns:
            Updated handoff or None if not found
        """
        try:
            uuid_id = UUID(str(handoff_id))
        except (ValueError, TypeError):
            return None

        now = datetime.now(UTC)
        values = {"status": status, **kwargs}

        if status == "accepted":
            values["accepted_at"] = now
        elif status == "rejected":
            values["rejected_at"] = now
        elif status == "completed":
            values["completed_at"] = now

        await self.session.execute(
            update(ManagerHandoffDB)
            .where(ManagerHandoffDB.id == uuid_id)
            .values(**values)
        )

        return await self.get_by_id(uuid_id)

    async def accept(self, handoff_id: str | UUID) -> ManagerHandoffDB | None:
        """Accept a handoff.

        Args:
            handoff_id: Handoff UUID

        Returns:
            Updated handoff or None
        """
        return await self.update_status(handoff_id, "accepted")

    async def reject(
        self,
        handoff_id: str | UUID,
        reason: str | None = None,
    ) -> ManagerHandoffDB | None:
        """Reject a handoff.

        Args:
            handoff_id: Handoff UUID
            reason: Rejection reason

        Returns:
            Updated handoff or None
        """
        return await self.update_status(
            handoff_id,
            "rejected",
            rejection_reason=reason,
        )

    async def complete(
        self,
        handoff_id: str | UUID,
        outcome: str | None = None,
        deal_value: float | None = None,
    ) -> ManagerHandoffDB | None:
        """Complete a handoff.

        Args:
            handoff_id: Handoff UUID
            outcome: Outcome description
            deal_value: Deal value if converted

        Returns:
            Updated handoff or None
        """
        return await self.update_status(
            handoff_id,
            "completed",
            outcome=outcome,
            deal_value=deal_value,
        )

    async def reassign(
        self,
        handoff_id: str | UUID,
        new_manager_id: str,
    ) -> ManagerHandoffDB | None:
        """Reassign handoff to another manager.

        Args:
            handoff_id: Handoff UUID
            new_manager_id: New manager ID

        Returns:
            Updated handoff or None
        """
        try:
            uuid_id = UUID(str(handoff_id))
        except (ValueError, TypeError):
            return None

        await self.session.execute(
            update(ManagerHandoffDB)
            .where(ManagerHandoffDB.id == uuid_id)
            .values(
                manager_id=new_manager_id,
                status="pending",
                accepted_at=None,
            )
        )

        return await self.get_by_id(uuid_id)

    async def delete(self, handoff_id: str | UUID) -> bool:
        """Delete a handoff.

        Args:
            handoff_id: Handoff UUID

        Returns:
            True if deleted, False if not found
        """
        try:
            uuid_id = UUID(str(handoff_id))
        except (ValueError, TypeError):
            return False

        result = await self.session.execute(
            delete(ManagerHandoffDB).where(ManagerHandoffDB.id == uuid_id)
        )

        return result.rowcount > 0
