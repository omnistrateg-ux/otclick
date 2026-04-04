"""Contact repository."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import EmployerContactDB
from app.models.domain import EmployerContact
from app.models.enums import ContactRole

UTC = timezone.utc

class ContactRepository:
    """Repository for EmployerContact operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, contact: EmployerContact) -> EmployerContact:
        """Create a new contact.

        Args:
            contact: Contact to create

        Returns:
            Created contact
        """
        db_contact = EmployerContactDB(
            id=contact.id,
            lead_id=contact.lead_id,
            full_name=contact.full_name,
            first_name=contact.first_name,
            last_name=contact.last_name,
            role=contact.role.value,
            job_title=contact.job_title,
            email=contact.email,
            email_verified=contact.email_verified,
            email_verification_date=contact.email_verification_date,
            phone=contact.phone,
            linkedin_url=contact.linkedin_url,
            telegram=contact.telegram,
            is_primary=contact.is_primary,
            contact_source=contact.contact_source,
            opted_out=contact.opted_out,
            bounce_count=contact.bounce_count,
            last_bounce_at=contact.last_bounce_at,
        )

        self.session.add(db_contact)
        await self.session.flush()

        return contact

    async def create_many(self, contacts: list[EmployerContact]) -> list[EmployerContact]:
        """Create multiple contacts.

        Args:
            contacts: Contacts to create

        Returns:
            Created contacts
        """
        for contact in contacts:
            await self.create(contact)
        return contacts

    async def get_by_id(self, contact_id: UUID) -> EmployerContact | None:
        """Get contact by ID.

        Args:
            contact_id: Contact UUID

        Returns:
            Contact or None
        """
        result = await self.session.execute(
            select(EmployerContactDB).where(EmployerContactDB.id == contact_id)
        )
        db_contact = result.scalar_one_or_none()

        if not db_contact:
            return None

        return self._to_domain(db_contact)

    async def get_by_lead_id(self, lead_id: UUID) -> list[EmployerContact]:
        """Get all contacts for a lead.

        Args:
            lead_id: Lead UUID

        Returns:
            List of contacts
        """
        result = await self.session.execute(
            select(EmployerContactDB)
            .where(EmployerContactDB.lead_id == lead_id)
            .order_by(EmployerContactDB.is_primary.desc())
        )

        return [self._to_domain(row) for row in result.scalars()]

    async def get_primary_for_lead(self, lead_id: UUID) -> EmployerContact | None:
        """Get primary contact for a lead.

        Args:
            lead_id: Lead UUID

        Returns:
            Primary contact or None
        """
        result = await self.session.execute(
            select(EmployerContactDB)
            .where(
                EmployerContactDB.lead_id == lead_id,
                EmployerContactDB.is_primary == True,
            )
            .limit(1)
        )
        db_contact = result.scalar_one_or_none()

        if not db_contact:
            return None

        return self._to_domain(db_contact)

    async def get_by_email(self, email: str) -> EmployerContact | None:
        """Get contact by email.

        Args:
            email: Contact email

        Returns:
            Contact or None
        """
        result = await self.session.execute(
            select(EmployerContactDB).where(EmployerContactDB.email == email)
        )
        db_contact = result.scalar_one_or_none()

        if not db_contact:
            return None

        return self._to_domain(db_contact)

    async def update(self, contact: EmployerContact) -> EmployerContact:
        """Update contact.

        Args:
            contact: Contact with updated data

        Returns:
            Updated contact
        """
        await self.session.execute(
            update(EmployerContactDB)
            .where(EmployerContactDB.id == contact.id)
            .values(
                full_name=contact.full_name,
                first_name=contact.first_name,
                last_name=contact.last_name,
                role=contact.role.value,
                job_title=contact.job_title,
                email=contact.email,
                email_verified=contact.email_verified,
                email_verification_date=contact.email_verification_date,
                phone=contact.phone,
                linkedin_url=contact.linkedin_url,
                telegram=contact.telegram,
                is_primary=contact.is_primary,
                contact_source=contact.contact_source,
                opted_out=contact.opted_out,
                bounce_count=contact.bounce_count,
                last_bounce_at=contact.last_bounce_at,
            )
        )

        return contact

    async def increment_bounce(self, contact_id: UUID) -> None:
        """Increment bounce count for contact.

        Args:
            contact_id: Contact UUID
        """
        await self.session.execute(
            update(EmployerContactDB)
            .where(EmployerContactDB.id == contact_id)
            .values(
                bounce_count=EmployerContactDB.bounce_count + 1,
                last_bounce_at=datetime.now(UTC),
            )
        )

    def _to_domain(self, db_contact: EmployerContactDB) -> EmployerContact:
        """Convert DB model to domain model."""
        return EmployerContact(
            id=db_contact.id,
            lead_id=db_contact.lead_id,
            full_name=db_contact.full_name,
            first_name=db_contact.first_name,
            last_name=db_contact.last_name,
            role=ContactRole(db_contact.role),
            job_title=db_contact.job_title,
            email=db_contact.email,
            email_verified=db_contact.email_verified,
            email_verification_date=db_contact.email_verification_date,
            phone=db_contact.phone,
            linkedin_url=db_contact.linkedin_url,
            telegram=db_contact.telegram,
            is_primary=db_contact.is_primary,
            contact_source=db_contact.contact_source,
            opted_out=db_contact.opted_out,
            bounce_count=db_contact.bounce_count,
            last_bounce_at=db_contact.last_bounce_at,
        )
