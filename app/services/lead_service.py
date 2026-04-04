"""Lead service - business logic for lead operations."""

from datetime import datetime, timezone

UTC = timezone.utc
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateLeadError, LeadNotFoundError
from app.core.state_machine import LeadStateMachine
from app.models.domain import (
    CompanyProfile,
    DomainEvent,
    EmployerContact,
    EmployerLead,
    LeadScore,
    LeadSegment,
)
from app.models.enums import LeadStatus
from app.storage.repositories.company_repo import CompanyRepository
from app.storage.repositories.contact_repo import ContactRepository
from app.storage.repositories.event_repo import EventRepository
from app.storage.repositories.lead_repo import LeadRepository


class LeadService:
    """Service for lead business logic.

    Координирует работу с лидами: создание, обогащение,
    переходы статусов, события.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.lead_repo = LeadRepository(session)
        self.company_repo = CompanyRepository(session)
        self.contact_repo = ContactRepository(session)
        self.event_repo = EventRepository(session)
        self.state_machine = LeadStateMachine()

    async def create_lead(
        self,
        lead: EmployerLead,
        check_duplicate: bool = True,
    ) -> EmployerLead:
        """Create a new lead.

        Args:
            lead: Lead to create
            check_duplicate: Check for duplicates by domain

        Returns:
            Created lead

        Raises:
            DuplicateLeadError: If duplicate found
        """
        # Check for duplicates
        if check_duplicate and lead.domain:
            existing = await self.lead_repo.get_by_domain(lead.domain)
            if existing:
                raise DuplicateLeadError(
                    existing_lead_id=str(existing.id),
                    reason=f"domain:{lead.domain}",
                )

        # Create lead
        created = await self.lead_repo.create(lead)

        # Emit event
        await self._emit_event("lead_discovered", lead.id, {
            "source": lead.source,
            "company_name": lead.company_name,
        })

        return created

    async def get_lead(self, lead_id: UUID) -> EmployerLead:
        """Get lead by ID.

        Args:
            lead_id: Lead UUID

        Returns:
            Lead

        Raises:
            LeadNotFoundError: If not found
        """
        lead = await self.lead_repo.get_by_id(lead_id)
        if not lead:
            raise LeadNotFoundError(str(lead_id))
        return lead

    async def list_leads(
        self,
        status: LeadStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EmployerLead]:
        """List leads with optional filtering.

        Args:
            status: Filter by status
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of leads
        """
        if status:
            return await self.lead_repo.list_by_status(status, limit, offset)
        # TODO: Add general listing without status filter
        return await self.lead_repo.list_by_status(LeadStatus.LEAD_FOUND, limit, offset)

    async def transition_lead(
        self,
        lead_id: UUID,
        to_status: LeadStatus,
        reason: str | None = None,
    ) -> EmployerLead:
        """Transition lead to new status.

        Uses state machine to validate transition.

        Args:
            lead_id: Lead UUID
            to_status: Target status
            reason: Reason for transition

        Returns:
            Updated lead

        Raises:
            LeadNotFoundError: If lead not found
            InvalidStateTransitionError: If transition invalid
        """
        lead = await self.get_lead(lead_id)

        # Validate and perform transition
        self.state_machine.transition(lead, to_status, reason)

        # Save updated lead
        await self.lead_repo.update(lead)

        # Emit event
        await self._emit_event(f"lead_status_{to_status.value}", lead_id, {
            "from_status": lead.status_history[-1].from_status.value if lead.status_history else None,
            "to_status": to_status.value,
            "reason": reason,
        })

        return lead

    async def enrich_lead(
        self,
        lead_id: UUID,
        profile: CompanyProfile,
        contacts: list[EmployerContact],
    ) -> EmployerLead:
        """Add enrichment data to lead.

        Args:
            lead_id: Lead UUID
            profile: Company profile
            contacts: List of contacts

        Returns:
            Updated lead
        """
        lead = await self.get_lead(lead_id)

        # Save profile
        await self.company_repo.create(profile)
        lead.company_profile_id = profile.id

        # Save contacts
        if contacts:
            await self.contact_repo.create_many(contacts)

        # Transition to ENRICHED
        self.state_machine.transition(lead, LeadStatus.ENRICHED)
        await self.lead_repo.update(lead)

        # Emit event
        await self._emit_event("lead_enriched", lead_id, {
            "profile_id": str(profile.id),
            "contacts_count": len(contacts),
            "industry": profile.industry.value,
        })

        return lead

    async def score_lead(
        self,
        lead_id: UUID,
        score: LeadScore,
        segment: LeadSegment,
    ) -> EmployerLead:
        """Add score and segment to lead.

        Args:
            lead_id: Lead UUID
            score: Calculated score
            segment: Determined segment

        Returns:
            Updated lead
        """
        lead = await self.get_lead(lead_id)

        # TODO: Save score and segment to DB
        # For now, we'll just transition the lead

        # Check if score is too low
        if score.total_score < 20:
            self.state_machine.transition(
                lead,
                LeadStatus.ARCHIVED,
                reason="low_score",
            )
            await self.lead_repo.update(lead)

            await self._emit_event("lead_archived_low_score", lead_id, {
                "score": score.total_score,
            })

            return lead

        # Transition to SCORED
        self.state_machine.transition(lead, LeadStatus.SCORED)
        await self.lead_repo.update(lead)

        # Emit event
        await self._emit_event("lead_scored", lead_id, {
            "total_score": score.total_score,
            "segment": segment.segment.value,
            "priority": segment.priority.value,
        })

        return lead

    async def archive_lead(
        self,
        lead_id: UUID,
        reason: str,
    ) -> EmployerLead:
        """Archive a lead.

        Args:
            lead_id: Lead UUID
            reason: Archive reason

        Returns:
            Archived lead
        """
        return await self.transition_lead(lead_id, LeadStatus.ARCHIVED, reason)

    async def get_lead_with_details(
        self,
        lead_id: UUID,
    ) -> dict:
        """Get lead with all related data.

        Args:
            lead_id: Lead UUID

        Returns:
            Dict with lead, profile, contacts
        """
        lead = await self.get_lead(lead_id)

        profile = None
        if lead.company_profile_id:
            profile = await self.company_repo.get_by_id(lead.company_profile_id)

        contacts = await self.contact_repo.get_by_lead_id(lead_id)

        return {
            "lead": lead,
            "profile": profile,
            "contacts": contacts,
        }

    async def get_next_leads_for_processing(
        self,
        status: LeadStatus,
        limit: int = 10,
    ) -> list[EmployerLead]:
        """Get leads ready for next processing step.

        Args:
            status: Current status to filter by
            limit: Maximum leads to return

        Returns:
            List of leads ready for processing
        """
        return await self.lead_repo.list_by_status(status, limit)

    async def _emit_event(
        self,
        event_type: str,
        lead_id: UUID,
        payload: dict,
    ) -> DomainEvent:
        """Emit a domain event.

        Args:
            event_type: Type of event
            lead_id: Associated lead ID
            payload: Event data

        Returns:
            Created event
        """
        event = DomainEvent(
            lead_id=lead_id,
            event_type=event_type,
            payload=payload,
            created_at=datetime.now(UTC),
        )

        return await self.event_repo.create(event)
