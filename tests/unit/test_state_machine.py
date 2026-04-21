"""Tests for LeadStateMachine."""

import pytest

from app.core.exceptions import InvalidStateTransitionError
from app.core.state_machine import LeadStateMachine
from app.models.domain import EmployerLead
from app.models.enums import LeadStatus


class TestLeadStateMachine:
    """Tests for LeadStateMachine class."""

    @pytest.fixture
    def state_machine(self) -> LeadStateMachine:
        """Create state machine instance."""
        return LeadStateMachine()

    @pytest.fixture
    def new_lead(self) -> EmployerLead:
        """Create a new lead in LEAD_FOUND status."""
        return EmployerLead(
            company_name="Test Company",
            source="hh.ru",
        )

    # --- can_transition tests ---

    def test_can_transition_lead_found_to_enriched(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Valid transition from LEAD_FOUND to ENRICHED."""
        assert state_machine.can_transition(
            LeadStatus.LEAD_FOUND, LeadStatus.ENRICHED
        )

    def test_can_transition_lead_found_to_archived(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Valid transition from LEAD_FOUND to ARCHIVED."""
        assert state_machine.can_transition(
            LeadStatus.LEAD_FOUND, LeadStatus.ARCHIVED
        )

    def test_can_transition_lead_found_to_duplicate(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Valid transition from LEAD_FOUND to DUPLICATE."""
        assert state_machine.can_transition(
            LeadStatus.LEAD_FOUND, LeadStatus.DUPLICATE
        )

    def test_cannot_transition_lead_found_to_qualified(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Invalid transition from LEAD_FOUND to QUALIFIED (skipping steps)."""
        assert not state_machine.can_transition(
            LeadStatus.LEAD_FOUND, LeadStatus.QUALIFIED
        )

    def test_cannot_transition_opted_out_to_anything(
        self, state_machine: LeadStateMachine
    ) -> None:
        """OPTED_OUT is terminal - no transitions allowed."""
        assert not state_machine.can_transition(
            LeadStatus.OPTED_OUT, LeadStatus.LEAD_FOUND
        )
        assert not state_machine.can_transition(
            LeadStatus.OPTED_OUT, LeadStatus.ARCHIVED
        )

    def test_can_transition_archived_to_lead_found(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Can reactivate from ARCHIVED to LEAD_FOUND."""
        assert state_machine.can_transition(
            LeadStatus.ARCHIVED, LeadStatus.LEAD_FOUND
        )

    def test_can_transition_cooldown_to_lead_found(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Can re-engage from COOLDOWN to LEAD_FOUND."""
        assert state_machine.can_transition(
            LeadStatus.COOLDOWN, LeadStatus.LEAD_FOUND
        )

    def test_full_happy_path_transitions(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Test entire happy path is valid."""
        happy_path = [
            (LeadStatus.LEAD_FOUND, LeadStatus.ENRICHED),
            (LeadStatus.ENRICHED, LeadStatus.SCORED),
            (LeadStatus.SCORED, LeadStatus.EMAIL_READY),
            (LeadStatus.EMAIL_READY, LeadStatus.OUTREACH_SENT),
            (LeadStatus.OUTREACH_SENT, LeadStatus.IN_SEQUENCE),
            (LeadStatus.IN_SEQUENCE, LeadStatus.REPLY_RECEIVED),
            (LeadStatus.REPLY_RECEIVED, LeadStatus.INTEREST_DETECTED),
            (LeadStatus.INTEREST_DETECTED, LeadStatus.QUALIFIED),
            (LeadStatus.QUALIFIED, LeadStatus.HANDED_TO_MANAGER),
        ]
        for from_status, to_status in happy_path:
            assert state_machine.can_transition(from_status, to_status), (
                f"Should allow {from_status} -> {to_status}"
            )

    # --- get_valid_transitions tests ---

    def test_get_valid_transitions_from_lead_found(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Get valid transitions from LEAD_FOUND."""
        transitions = state_machine.get_valid_transitions(LeadStatus.LEAD_FOUND)
        assert LeadStatus.ENRICHED in transitions
        assert LeadStatus.ARCHIVED in transitions
        assert LeadStatus.DUPLICATE in transitions
        assert len(transitions) == 3

    def test_get_valid_transitions_from_terminal(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Terminal states have no transitions."""
        assert state_machine.get_valid_transitions(LeadStatus.OPTED_OUT) == []
        assert state_machine.get_valid_transitions(LeadStatus.DUPLICATE) == []
        assert state_machine.get_valid_transitions(LeadStatus.CONVERTED) == []

    def test_get_valid_transitions_from_reply_received(
        self, state_machine: LeadStateMachine
    ) -> None:
        """REPLY_RECEIVED has multiple possible transitions."""
        transitions = state_machine.get_valid_transitions(LeadStatus.REPLY_RECEIVED)
        assert LeadStatus.INTEREST_DETECTED in transitions
        assert LeadStatus.REFUSED in transitions
        assert LeadStatus.IN_SEQUENCE in transitions
        assert LeadStatus.OPTED_OUT in transitions
        assert LeadStatus.COOLDOWN in transitions

    # --- transition tests ---

    def test_transition_updates_status(
        self, state_machine: LeadStateMachine, new_lead: EmployerLead
    ) -> None:
        """Transition updates lead status."""
        assert new_lead.status == LeadStatus.LEAD_FOUND

        updated = state_machine.transition(new_lead, LeadStatus.ENRICHED)

        assert updated.status == LeadStatus.ENRICHED
        assert updated is new_lead  # Same object

    def test_transition_updates_status_changed_at(
        self, state_machine: LeadStateMachine, new_lead: EmployerLead
    ) -> None:
        """Transition updates status_changed_at timestamp."""
        original_time = new_lead.status_changed_at

        updated = state_machine.transition(new_lead, LeadStatus.ENRICHED)

        assert updated.status_changed_at >= original_time

    def test_transition_adds_to_history(
        self, state_machine: LeadStateMachine, new_lead: EmployerLead
    ) -> None:
        """Transition adds entry to status_history."""
        assert len(new_lead.status_history) == 0

        state_machine.transition(new_lead, LeadStatus.ENRICHED)

        assert len(new_lead.status_history) == 1
        change = new_lead.status_history[0]
        assert change.from_status == LeadStatus.LEAD_FOUND
        assert change.to_status == LeadStatus.ENRICHED

    def test_transition_with_reason(
        self, state_machine: LeadStateMachine, new_lead: EmployerLead
    ) -> None:
        """Transition can include reason."""
        state_machine.transition(
            new_lead, LeadStatus.ARCHIVED, reason="no_contacts"
        )

        change = new_lead.status_history[0]
        assert change.reason == "no_contacts"

    def test_transition_to_archived_sets_fields(
        self, state_machine: LeadStateMachine, new_lead: EmployerLead
    ) -> None:
        """Transition to ARCHIVED sets archived_at and archived_reason."""
        state_machine.transition(
            new_lead, LeadStatus.ARCHIVED, reason="low_score"
        )

        assert new_lead.archived_at is not None
        assert new_lead.archived_reason == "low_score"

    def test_transition_to_opted_out_sets_fields(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Transition to OPTED_OUT sets opted_out fields."""
        lead = EmployerLead(company_name="Test", source="test")
        lead.status = LeadStatus.REPLY_RECEIVED

        state_machine.transition(lead, LeadStatus.OPTED_OUT)

        assert lead.opted_out is True
        assert lead.opted_out_at is not None

    def test_transition_invalid_raises_error(
        self, state_machine: LeadStateMachine, new_lead: EmployerLead
    ) -> None:
        """Invalid transition raises InvalidStateTransitionError."""
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            state_machine.transition(new_lead, LeadStatus.QUALIFIED)

        assert exc_info.value.from_status == LeadStatus.LEAD_FOUND
        assert exc_info.value.to_status == LeadStatus.QUALIFIED

    def test_multiple_transitions(
        self, state_machine: LeadStateMachine, new_lead: EmployerLead
    ) -> None:
        """Multiple sequential transitions work correctly."""
        state_machine.transition(new_lead, LeadStatus.ENRICHED)
        state_machine.transition(new_lead, LeadStatus.SCORED)
        state_machine.transition(new_lead, LeadStatus.EMAIL_READY)

        assert new_lead.status == LeadStatus.EMAIL_READY
        assert len(new_lead.status_history) == 3

    # --- is_terminal tests ---

    def test_is_terminal_for_terminal_states(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Terminal states are correctly identified."""
        assert state_machine.is_terminal(LeadStatus.OPTED_OUT)
        assert state_machine.is_terminal(LeadStatus.DUPLICATE)
        assert state_machine.is_terminal(LeadStatus.CONVERTED)

    def test_is_terminal_for_non_terminal_states(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Non-terminal states are correctly identified."""
        assert not state_machine.is_terminal(LeadStatus.LEAD_FOUND)
        assert not state_machine.is_terminal(LeadStatus.ENRICHED)
        assert not state_machine.is_terminal(LeadStatus.ARCHIVED)

    # --- is_active tests ---

    def test_is_active_for_pipeline_states(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Active pipeline states are correctly identified."""
        active_states = [
            LeadStatus.LEAD_FOUND,
            LeadStatus.ENRICHED,
            LeadStatus.SCORED,
            LeadStatus.EMAIL_READY,
            LeadStatus.OUTREACH_SENT,
            LeadStatus.IN_SEQUENCE,
            LeadStatus.REPLY_RECEIVED,
            LeadStatus.INTEREST_DETECTED,
            LeadStatus.QUALIFIED,
        ]
        for status in active_states:
            assert state_machine.is_active(status), f"{status} should be active"

    def test_is_active_for_inactive_states(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Inactive states are correctly identified."""
        inactive_states = [
            LeadStatus.ARCHIVED,
            LeadStatus.REFUSED,
            LeadStatus.COOLDOWN,
            LeadStatus.OPTED_OUT,
            LeadStatus.BOUNCED,
            LeadStatus.DUPLICATE,
            LeadStatus.HANDED_TO_MANAGER,
        ]
        for status in inactive_states:
            assert not state_machine.is_active(status), f"{status} should be inactive"

    # --- is_positive_outcome tests ---

    def test_is_positive_outcome(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Positive outcomes are correctly identified."""
        assert state_machine.is_positive_outcome(LeadStatus.QUALIFIED)
        assert state_machine.is_positive_outcome(LeadStatus.HANDED_TO_MANAGER)
        assert not state_machine.is_positive_outcome(LeadStatus.ARCHIVED)
        assert not state_machine.is_positive_outcome(LeadStatus.LEAD_FOUND)

    # --- is_negative_outcome tests ---

    def test_is_negative_outcome(
        self, state_machine: LeadStateMachine
    ) -> None:
        """Negative outcomes are correctly identified."""
        assert state_machine.is_negative_outcome(LeadStatus.ARCHIVED)
        assert state_machine.is_negative_outcome(LeadStatus.REFUSED)
        assert state_machine.is_negative_outcome(LeadStatus.OPTED_OUT)
        assert state_machine.is_negative_outcome(LeadStatus.BOUNCED)
        assert state_machine.is_negative_outcome(LeadStatus.DUPLICATE)
        assert not state_machine.is_negative_outcome(LeadStatus.QUALIFIED)
        assert not state_machine.is_negative_outcome(LeadStatus.LEAD_FOUND)
