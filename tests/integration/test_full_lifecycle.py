"""Integration tests for full lead lifecycle.

Тесты полного жизненного цикла лида от discovery до handoff.
"""

import pytest
from datetime import UTC, datetime
from uuid import uuid4

from app.events.definitions import Event, EventType, create_event
from app.events.handlers import EventDispatcher, get_dispatcher
from app.models.domain import (
    AgentTask,
    EmployerContact,
    EmployerLead,
    CompanyProfile,
    LeadScore,
)
from app.models.enums import (
    ContactRole,
    EmailType,
    IndustrySegment,
    LeadStatus,
    ReplyIntent,
)
from app.orchestrator.engine import LeadOrchestrator
from app.orchestrator.pipeline import Pipeline, PipelineStageName, get_pipeline


class TestLeadOrchestrator:
    """Tests for LeadOrchestrator."""

    def test_create_orchestrator(self) -> None:
        """Can create orchestrator."""
        orchestrator = LeadOrchestrator()
        assert orchestrator is not None
        assert orchestrator.state_machine is not None

    def test_discover_lead(self) -> None:
        """Can discover a new lead."""
        orchestrator = LeadOrchestrator()

        lead = EmployerLead(
            company_name="Test Company",
            hh_employer_id="123456",
            source="hh.ru",
            status=LeadStatus.LEAD_FOUND,
        )

        lead, event = orchestrator.discover_lead(
            lead,
            source="hh.ru",
            actor="discovery_agent",
        )

        assert lead.status == LeadStatus.LEAD_FOUND
        assert event.event_type == EventType.LEAD_DISCOVERED
        assert event.data["source"] == "hh.ru"

    def test_enrich_lead(self) -> None:
        """Can enrich a discovered lead."""
        orchestrator = LeadOrchestrator()

        lead = EmployerLead(
            company_name="Test Company",
            source="hh.ru",
            status=LeadStatus.LEAD_FOUND,
        )

        lead, event = orchestrator.enrich_lead(
            lead,
            actor="enrichment_agent",
            enrichment_data={"contacts_found": 3},
        )

        assert lead.status == LeadStatus.ENRICHED
        assert event.event_type == EventType.LEAD_ENRICHED

    def test_score_lead_high_score(self) -> None:
        """Scoring above threshold marks lead as scored."""
        orchestrator = LeadOrchestrator()

        lead = EmployerLead(
            company_name="Test Company",
            source="hh.ru",
            status=LeadStatus.ENRICHED,
        )

        lead, event = orchestrator.score_lead(
            lead,
            score=75.0,
            actor="scoring_agent",
            segment="retail",
        )

        assert lead.status == LeadStatus.SCORED
        # Score is stored in event metadata, not on lead
        assert event.data["score"] == 75.0
        assert event.data["segment"] == "retail"
        assert event.event_type == EventType.LEAD_SCORED

    def test_score_lead_low_score(self) -> None:
        """Scoring below threshold archives lead."""
        orchestrator = LeadOrchestrator()

        lead = EmployerLead(
            company_name="Test Company",
            source="hh.ru",
            status=LeadStatus.ENRICHED,
        )

        lead, event = orchestrator.score_lead(
            lead,
            score=30.0,
            actor="scoring_agent",
        )

        assert lead.status == LeadStatus.ARCHIVED
        # Score is stored in event metadata
        assert event.data["score"] == 30.0
        assert event.event_type == EventType.LEAD_DISQUALIFIED

    def test_start_outreach(self) -> None:
        """Can start outreach for email-ready lead."""
        orchestrator = LeadOrchestrator()

        lead = EmployerLead(
            company_name="Test Company",
            source="hh.ru",
            status=LeadStatus.EMAIL_READY,
        )

        lead, event = orchestrator.start_outreach(
            lead,
            campaign_id="campaign-123",
            actor="outreach_agent",
        )

        assert lead.status == LeadStatus.OUTREACH_SENT
        assert event.event_type == EventType.OUTREACH_STARTED
        assert event.data["campaign_id"] == "campaign-123"

    def test_record_reply(self) -> None:
        """Can record lead reply."""
        orchestrator = LeadOrchestrator()

        lead = EmployerLead(
            company_name="Test Company",
            source="hh.ru",
            status=LeadStatus.OUTREACH_SENT,
        )

        lead, event = orchestrator.record_reply(
            lead,
            email_id="email-123",
            reply_text="Интересно, расскажите подробнее",
        )

        assert lead.status == LeadStatus.REPLY_RECEIVED
        assert event.event_type == EventType.REPLY_RECEIVED

    def test_mark_interested(self) -> None:
        """Can mark lead as interested."""
        orchestrator = LeadOrchestrator()

        lead = EmployerLead(
            company_name="Test Company",
            source="hh.ru",
            status=LeadStatus.REPLY_RECEIVED,
        )

        lead, event = orchestrator.mark_interested(
            lead,
            intent="strong_interest",
            confidence=0.9,
            actor="qualification_agent",
        )

        assert lead.status == LeadStatus.INTEREST_DETECTED
        assert event.event_type == EventType.QUALIFICATION_COMPLETED
        assert event.data["intent"] == "strong_interest"

    def test_handoff_to_manager(self) -> None:
        """Can hand off lead to manager."""
        orchestrator = LeadOrchestrator()

        lead = EmployerLead(
            company_name="Test Company",
            source="hh.ru",
            status=LeadStatus.QUALIFIED,
        )

        lead, event = orchestrator.handoff_to_manager(
            lead,
            manager_id="manager-123",
            handoff_id="handoff-456",
        )

        assert lead.status == LeadStatus.HANDED_TO_MANAGER
        assert event.event_type == EventType.HANDOFF_CREATED
        assert event.data["manager_id"] == "manager-123"

    def test_mark_converted(self) -> None:
        """Can mark lead as converted."""
        orchestrator = LeadOrchestrator()

        lead = EmployerLead(
            company_name="Test Company",
            source="hh.ru",
            status=LeadStatus.HANDED_TO_MANAGER,
        )

        lead, event = orchestrator.mark_converted(
            lead,
            deal_value=50000.0,
        )

        # Lead transitions to CONVERTED status
        assert lead.status == LeadStatus.CONVERTED
        assert event.event_type == EventType.HANDOFF_COMPLETED

    def test_invalid_transition_raises(self) -> None:
        """Invalid transition raises error."""
        orchestrator = LeadOrchestrator()

        lead = EmployerLead(
            company_name="Test Company",
            source="hh.ru",
            status=LeadStatus.LEAD_FOUND,
        )

        # Can't go directly to OUTREACH_SENT from LEAD_FOUND
        with pytest.raises(ValueError) as exc_info:
            orchestrator.start_outreach(lead)

        assert "Invalid transition" in str(exc_info.value)


class TestFullLifecycle:
    """Test complete lead lifecycle."""

    def test_full_happy_path(self) -> None:
        """Test complete lifecycle from discovery to handoff."""
        orchestrator = LeadOrchestrator()

        # 1. Discovery
        lead = EmployerLead(
            company_name="Пятёрочка",
            hh_employer_id="123456",
            source="hh.ru",
            status=LeadStatus.LEAD_FOUND,
        )
        lead, event = orchestrator.discover_lead(lead, source="hh.ru")
        assert lead.status == LeadStatus.LEAD_FOUND

        # 2. Enrichment
        # Note: In real code, contacts would be created separately
        # Here we just transition the lead status
        lead, event = orchestrator.enrich_lead(lead)
        assert lead.status == LeadStatus.ENRICHED

        # 3. Scoring (high score)
        lead, event = orchestrator.score_lead(lead, score=85.0, segment="retail")
        assert lead.status == LeadStatus.SCORED
        assert event.data["score"] == 85.0

        # 4. Transition to email ready (manual for test)
        lead.status = LeadStatus.EMAIL_READY

        # 5. Start outreach
        lead, event = orchestrator.start_outreach(lead, campaign_id="retail-q1")
        assert lead.status == LeadStatus.OUTREACH_SENT

        # 6. Reply received
        lead, event = orchestrator.record_reply(
            lead,
            email_id="email-001",
            reply_text="Очень интересно, давайте созвонимся",
        )
        assert lead.status == LeadStatus.REPLY_RECEIVED

        # 7. Interest detected
        lead, event = orchestrator.mark_interested(
            lead,
            intent="ready_to_call",
            confidence=0.95,
        )
        assert lead.status == LeadStatus.INTEREST_DETECTED

        # 8. Transition to qualified (manual for test)
        lead.status = LeadStatus.QUALIFIED

        # 9. Handoff
        lead, event = orchestrator.handoff_to_manager(
            lead,
            manager_id="manager-001",
            handoff_id="handoff-001",
        )
        assert lead.status == LeadStatus.HANDED_TO_MANAGER

        # 10. Conversion
        lead, event = orchestrator.mark_converted(lead, deal_value=100000.0)
        assert lead.status == LeadStatus.CONVERTED

    def test_lifecycle_with_negative_reply(self) -> None:
        """Test lifecycle when lead refuses."""
        orchestrator = LeadOrchestrator()

        # Discovery -> Enrichment -> Scoring
        lead = EmployerLead(
            company_name="Test Company",
            source="hh.ru",
            status=LeadStatus.LEAD_FOUND,
        )
        lead, _ = orchestrator.enrich_lead(lead)
        lead, _ = orchestrator.score_lead(lead, score=70.0)

        # Transition to email ready and outreach
        lead.status = LeadStatus.EMAIL_READY
        lead, _ = orchestrator.start_outreach(lead)

        # Reply received
        lead, _ = orchestrator.record_reply(
            lead,
            email_id="email-001",
            reply_text="Не интересно",
        )

        # Mark not interested
        lead, event = orchestrator.mark_not_interested(
            lead,
            intent="refusal",
            confidence=0.9,
        )

        assert lead.status == LeadStatus.REFUSED
        assert event.event_type == EventType.LEAD_DISQUALIFIED


class TestEventDispatcher:
    """Tests for event dispatcher."""

    @pytest.mark.asyncio
    async def test_register_and_dispatch(self) -> None:
        """Can register and dispatch events."""
        dispatcher = EventDispatcher()
        received_events: list[Event] = []

        async def handler(event: Event) -> None:
            received_events.append(event)

        dispatcher.register(EventType.LEAD_DISCOVERED, handler)

        event = create_event(
            EventType.LEAD_DISCOVERED,
            lead_id="lead-123",
        )

        errors = await dispatcher.dispatch(event)

        assert len(errors) == 0
        assert len(received_events) == 1
        assert received_events[0].lead_id == "lead-123"

    @pytest.mark.asyncio
    async def test_multiple_handlers(self) -> None:
        """Multiple handlers receive same event."""
        dispatcher = EventDispatcher()
        handler1_called = False
        handler2_called = False

        async def handler1(event: Event) -> None:
            nonlocal handler1_called
            handler1_called = True

        async def handler2(event: Event) -> None:
            nonlocal handler2_called
            handler2_called = True

        dispatcher.register(EventType.LEAD_ENRICHED, handler1)
        dispatcher.register(EventType.LEAD_ENRICHED, handler2)

        event = create_event(EventType.LEAD_ENRICHED, lead_id="lead-123")
        await dispatcher.dispatch(event)

        assert handler1_called
        assert handler2_called

    @pytest.mark.asyncio
    async def test_global_handler(self) -> None:
        """Global handler receives all events."""
        dispatcher = EventDispatcher()
        received_types: list[EventType] = []

        async def global_handler(event: Event) -> None:
            received_types.append(event.event_type)

        dispatcher.register_global(global_handler)

        await dispatcher.dispatch(create_event(EventType.LEAD_DISCOVERED))
        await dispatcher.dispatch(create_event(EventType.LEAD_ENRICHED))
        await dispatcher.dispatch(create_event(EventType.EMAIL_SENT))

        assert len(received_types) == 3
        assert EventType.LEAD_DISCOVERED in received_types
        assert EventType.LEAD_ENRICHED in received_types
        assert EventType.EMAIL_SENT in received_types

    @pytest.mark.asyncio
    async def test_handler_error_captured(self) -> None:
        """Handler errors are captured, not propagated."""
        dispatcher = EventDispatcher()

        async def failing_handler(event: Event) -> None:
            raise ValueError("Handler error")

        async def success_handler(event: Event) -> None:
            pass

        dispatcher.register(EventType.LEAD_SCORED, failing_handler)
        dispatcher.register(EventType.LEAD_SCORED, success_handler)

        event = create_event(EventType.LEAD_SCORED)
        errors = await dispatcher.dispatch(event)

        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)


class TestPipeline:
    """Tests for pipeline."""

    def test_create_pipeline(self) -> None:
        """Can create pipeline."""
        pipeline = Pipeline()
        assert pipeline is not None

    def test_pipeline_has_stages(self) -> None:
        """Pipeline has all expected stages."""
        pipeline = Pipeline()

        expected_stages = [
            PipelineStageName.DISCOVERY,
            PipelineStageName.ENRICHMENT,
            PipelineStageName.SCORING,
            PipelineStageName.QUALIFICATION,
            PipelineStageName.OUTREACH,
            PipelineStageName.FOLLOWUP,
            PipelineStageName.ANALYSIS,
            PipelineStageName.HANDOFF,
        ]

        for stage_name in expected_stages:
            stage = pipeline.get_stage(stage_name)
            assert stage is not None, f"Missing stage: {stage_name}"

    def test_get_next_stage(self) -> None:
        """Can get next stage for lead."""
        pipeline = Pipeline()

        # Test progression
        test_cases = [
            (LeadStatus.LEAD_FOUND, PipelineStageName.ENRICHMENT),
            (LeadStatus.ENRICHED, PipelineStageName.SCORING),
            (LeadStatus.SCORED, PipelineStageName.QUALIFICATION),
            (LeadStatus.EMAIL_READY, PipelineStageName.OUTREACH),
            (LeadStatus.REPLY_RECEIVED, PipelineStageName.ANALYSIS),
            (LeadStatus.INTEREST_DETECTED, PipelineStageName.HANDOFF),
        ]

        for status, expected_stage in test_cases:
            lead = EmployerLead(
                company_name="Test",
                source="hh.ru",
                status=status,
            )
            next_stage = pipeline.get_next_stage(lead)
            assert next_stage is not None, f"No next stage for {status}"
            assert next_stage.name == expected_stage, f"Wrong stage for {status}"

    def test_stage_can_enter(self) -> None:
        """Stage entry validation works."""
        pipeline = Pipeline()

        enrichment_stage = pipeline.get_stage(PipelineStageName.ENRICHMENT)
        assert enrichment_stage is not None

        # Can enter from LEAD_FOUND
        lead_found = EmployerLead(
            company_name="Test",
            source="hh.ru",
            status=LeadStatus.LEAD_FOUND,
        )
        assert enrichment_stage.can_enter(lead_found) is True

        # Cannot enter from QUALIFIED
        lead_qualified = EmployerLead(
            company_name="Test",
            source="hh.ru",
            status=LeadStatus.QUALIFIED,
        )
        assert enrichment_stage.can_enter(lead_qualified) is False

    def test_pipeline_status(self) -> None:
        """Can get pipeline status for lead."""
        pipeline = Pipeline()

        lead = EmployerLead(
            company_name="Test",
            source="hh.ru",
            status=LeadStatus.ENRICHED,
        )

        status = pipeline.get_pipeline_status(lead)

        assert status["lead_id"] == lead.id
        assert status["current_status"] == "enriched"
        assert status["next_stage"] == PipelineStageName.SCORING
        assert status["can_proceed"] is True


class TestEventCreation:
    """Tests for event creation."""

    def test_create_lead_event(self) -> None:
        """Can create lead event."""
        event = create_event(
            EventType.LEAD_DISCOVERED,
            lead_id="lead-123",
            actor="discovery_agent",
            data={"source": "hh.ru"},
        )

        assert event.event_type == EventType.LEAD_DISCOVERED
        assert event.lead_id == "lead-123"
        assert event.actor == "discovery_agent"
        assert event.data["source"] == "hh.ru"
        assert event.processed is False

    def test_create_email_event(self) -> None:
        """Can create email event."""
        event = create_event(
            EventType.EMAIL_SENT,
            lead_id="lead-123",
            email_id="email-456",
            data={"subject": "Test subject"},
        )

        assert event.event_type == EventType.EMAIL_SENT
        assert event.lead_id == "lead-123"
        assert event.email_id == "email-456"

    def test_event_has_uuid(self) -> None:
        """Event has unique ID."""
        event1 = create_event(EventType.LEAD_DISCOVERED)
        event2 = create_event(EventType.LEAD_DISCOVERED)

        assert event1.id != event2.id

    def test_event_has_timestamp(self) -> None:
        """Event has timestamp."""
        event = create_event(EventType.LEAD_DISCOVERED)

        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)

    def test_correlation_and_causation(self) -> None:
        """Events can have correlation and causation IDs."""
        parent_event = create_event(
            EventType.LEAD_DISCOVERED,
            lead_id="lead-123",
        )

        child_event = create_event(
            EventType.LEAD_ENRICHED,
            lead_id="lead-123",
            causation_id=parent_event.id,
            correlation_id=parent_event.id,
        )

        assert child_event.causation_id == parent_event.id
        assert child_event.correlation_id == parent_event.id


class TestTransitionValidation:
    """Tests for state transition validation."""

    def test_can_transition_check(self) -> None:
        """can_transition returns correct values."""
        orchestrator = LeadOrchestrator()

        lead = EmployerLead(
            company_name="Test",
            source="hh.ru",
            status=LeadStatus.LEAD_FOUND,
        )

        # Valid transitions
        assert orchestrator.can_transition(lead, LeadStatus.ENRICHED) is True

        # Invalid transitions
        assert orchestrator.can_transition(lead, LeadStatus.HANDED_TO_MANAGER) is False
        assert orchestrator.can_transition(lead, LeadStatus.OUTREACH_SENT) is False

    def test_get_valid_transitions(self) -> None:
        """get_valid_transitions returns valid next states."""
        orchestrator = LeadOrchestrator()

        # From EMAIL_READY, only OUTREACH_SENT is valid
        lead = EmployerLead(
            company_name="Test",
            source="hh.ru",
            status=LeadStatus.EMAIL_READY,
        )

        allowed = orchestrator.get_valid_transitions(lead)

        assert LeadStatus.OUTREACH_SENT in allowed
        assert LeadStatus.HANDED_TO_MANAGER not in allowed

        # From SCORED, can go to EMAIL_READY or ARCHIVED
        lead2 = EmployerLead(
            company_name="Test",
            source="hh.ru",
            status=LeadStatus.SCORED,
        )

        allowed2 = orchestrator.get_valid_transitions(lead2)
        assert LeadStatus.EMAIL_READY in allowed2
        assert LeadStatus.ARCHIVED in allowed2
