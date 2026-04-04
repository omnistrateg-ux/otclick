"""Event repository."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import DomainEventDB
from app.models.domain import DomainEvent


class EventRepository:
    """Repository for DomainEvent operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, event: DomainEvent) -> DomainEvent:
        """Create a new event.

        Args:
            event: Event to create

        Returns:
            Created event
        """
        db_event = DomainEventDB(
            id=event.id,
            lead_id=event.lead_id,
            event_type=event.event_type,
            payload=event.payload,
            created_at=event.created_at,
            processed=event.processed,
            processed_at=event.processed_at,
        )

        self.session.add(db_event)
        await self.session.flush()

        return event

    async def get_by_id(self, event_id: UUID) -> DomainEvent | None:
        """Get event by ID.

        Args:
            event_id: Event UUID

        Returns:
            Event or None
        """
        result = await self.session.execute(
            select(DomainEventDB).where(DomainEventDB.id == event_id)
        )
        db_event = result.scalar_one_or_none()

        if not db_event:
            return None

        return self._to_domain(db_event)

    async def get_unprocessed(
        self,
        limit: int = 100,
        event_types: list[str] | None = None,
    ) -> list[DomainEvent]:
        """Get unprocessed events.

        Args:
            limit: Maximum events to return
            event_types: Filter by event types (optional)

        Returns:
            List of unprocessed events
        """
        query = (
            select(DomainEventDB)
            .where(DomainEventDB.processed == False)
            .order_by(DomainEventDB.created_at)
            .limit(limit)
        )

        if event_types:
            query = query.where(DomainEventDB.event_type.in_(event_types))

        result = await self.session.execute(query)
        return [self._to_domain(row) for row in result.scalars()]

    async def get_by_lead_id(
        self,
        lead_id: UUID,
        limit: int = 100,
    ) -> list[DomainEvent]:
        """Get events for a lead.

        Args:
            lead_id: Lead UUID
            limit: Maximum events

        Returns:
            List of events
        """
        result = await self.session.execute(
            select(DomainEventDB)
            .where(DomainEventDB.lead_id == lead_id)
            .order_by(DomainEventDB.created_at.desc())
            .limit(limit)
        )

        return [self._to_domain(row) for row in result.scalars()]

    async def mark_processed(self, event_id: UUID) -> bool:
        """Mark event as processed.

        Args:
            event_id: Event UUID

        Returns:
            True if updated
        """
        result = await self.session.execute(
            update(DomainEventDB)
            .where(DomainEventDB.id == event_id)
            .values(
                processed=True,
                processed_at=datetime.now(UTC),
            )
        )

        return result.rowcount > 0

    async def mark_many_processed(self, event_ids: list[UUID]) -> int:
        """Mark multiple events as processed.

        Args:
            event_ids: List of event UUIDs

        Returns:
            Number of events updated
        """
        if not event_ids:
            return 0

        result = await self.session.execute(
            update(DomainEventDB)
            .where(DomainEventDB.id.in_(event_ids))
            .values(
                processed=True,
                processed_at=datetime.now(UTC),
            )
        )

        return result.rowcount

    def _to_domain(self, db_event: DomainEventDB) -> DomainEvent:
        """Convert DB model to domain model."""
        return DomainEvent(
            id=db_event.id,
            lead_id=db_event.lead_id,
            event_type=db_event.event_type,
            payload=db_event.payload or {},
            created_at=db_event.created_at,
            processed=db_event.processed,
            processed_at=db_event.processed_at,
        )
