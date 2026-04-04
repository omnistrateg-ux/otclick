"""Lead repository for database operations."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import EmployerLeadDB
from app.models.domain import EmployerLead
from app.models.enums import LeadStatus


class LeadRepository:
    """Repository for EmployerLead operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, lead: EmployerLead) -> EmployerLead:
        """Create a new lead.

        Args:
            lead: Lead to create

        Returns:
            Created lead
        """
        db_lead = EmployerLeadDB(
            id=lead.id,
            company_name=lead.company_name,
            domain=lead.domain,
            source=lead.source,
            source_url=lead.source_url,
            status=lead.status.value,
            status_changed_at=lead.status_changed_at,
            status_history=[h.model_dump(mode="json") for h in lead.status_history],
            city=lead.city,
            region=lead.region,
            company_profile_id=lead.company_profile_id,
            campaign_id=lead.campaign_id,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
            archived_at=lead.archived_at,
            archived_reason=lead.archived_reason,
            opted_out=lead.opted_out,
            opted_out_at=lead.opted_out_at,
            do_not_contact_until=lead.do_not_contact_until,
        )

        self.session.add(db_lead)
        await self.session.flush()

        return lead

    async def get_by_id(self, lead_id: UUID) -> EmployerLead | None:
        """Get lead by ID.

        Args:
            lead_id: Lead UUID

        Returns:
            Lead or None if not found
        """
        result = await self.session.execute(
            select(EmployerLeadDB).where(EmployerLeadDB.id == lead_id)
        )
        db_lead = result.scalar_one_or_none()

        if not db_lead:
            return None

        return self._to_domain(db_lead)

    async def get_by_domain(self, domain: str) -> EmployerLead | None:
        """Get lead by company domain.

        Args:
            domain: Company domain

        Returns:
            Lead or None if not found
        """
        result = await self.session.execute(
            select(EmployerLeadDB).where(EmployerLeadDB.domain == domain)
        )
        db_lead = result.scalar_one_or_none()

        if not db_lead:
            return None

        return self._to_domain(db_lead)

    async def list_by_status(
        self,
        status: LeadStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EmployerLead]:
        """List leads by status.

        Args:
            status: Lead status to filter by
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of leads
        """
        result = await self.session.execute(
            select(EmployerLeadDB)
            .where(EmployerLeadDB.status == status.value)
            .order_by(EmployerLeadDB.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        return [self._to_domain(row) for row in result.scalars()]

    async def update(self, lead: EmployerLead) -> EmployerLead:
        """Update an existing lead.

        Args:
            lead: Lead with updated data

        Returns:
            Updated lead
        """
        await self.session.execute(
            update(EmployerLeadDB)
            .where(EmployerLeadDB.id == lead.id)
            .values(
                company_name=lead.company_name,
                domain=lead.domain,
                source=lead.source,
                source_url=lead.source_url,
                status=lead.status.value,
                status_changed_at=lead.status_changed_at,
                status_history=[h.model_dump(mode="json") for h in lead.status_history],
                city=lead.city,
                region=lead.region,
                company_profile_id=lead.company_profile_id,
                campaign_id=lead.campaign_id,
                updated_at=datetime.now(UTC),
                archived_at=lead.archived_at,
                archived_reason=lead.archived_reason,
                opted_out=lead.opted_out,
                opted_out_at=lead.opted_out_at,
                do_not_contact_until=lead.do_not_contact_until,
            )
        )

        return lead

    async def update_status(
        self,
        lead_id: UUID,
        status: LeadStatus,
        reason: str | None = None,
    ) -> bool:
        """Update lead status.

        Args:
            lead_id: Lead UUID
            status: New status
            reason: Optional reason for status change

        Returns:
            True if updated, False if lead not found
        """
        now = datetime.now(UTC)

        values: dict = {
            "status": status.value,
            "status_changed_at": now,
            "updated_at": now,
        }

        if status == LeadStatus.ARCHIVED:
            values["archived_at"] = now
            values["archived_reason"] = reason

        if status == LeadStatus.OPTED_OUT:
            values["opted_out"] = True
            values["opted_out_at"] = now

        result = await self.session.execute(
            update(EmployerLeadDB)
            .where(EmployerLeadDB.id == lead_id)
            .values(**values)
        )

        return result.rowcount > 0

    async def exists_by_domain(self, domain: str) -> bool:
        """Check if lead with domain exists.

        Args:
            domain: Company domain

        Returns:
            True if exists
        """
        result = await self.session.execute(
            select(EmployerLeadDB.id).where(EmployerLeadDB.domain == domain).limit(1)
        )
        return result.scalar_one_or_none() is not None

    def _to_domain(self, db_lead: EmployerLeadDB) -> EmployerLead:
        """Convert DB model to domain model."""
        from app.models.domain import StatusChange

        status_history = []
        for h in db_lead.status_history or []:
            if isinstance(h, dict):
                status_history.append(StatusChange.model_validate(h))

        return EmployerLead(
            id=db_lead.id,
            company_name=db_lead.company_name,
            domain=db_lead.domain,
            source=db_lead.source,
            source_url=db_lead.source_url,
            status=LeadStatus(db_lead.status),
            status_changed_at=db_lead.status_changed_at,
            status_history=status_history,
            city=db_lead.city,
            region=db_lead.region,
            company_profile_id=db_lead.company_profile_id,
            campaign_id=db_lead.campaign_id,
            created_at=db_lead.created_at,
            updated_at=db_lead.updated_at,
            archived_at=db_lead.archived_at,
            archived_reason=db_lead.archived_reason,
            opted_out=db_lead.opted_out,
            opted_out_at=db_lead.opted_out_at,
            do_not_contact_until=db_lead.do_not_contact_until,
        )
