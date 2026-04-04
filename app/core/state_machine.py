"""Lead state machine with transition validation.

Реализует граф переходов из ARCHITECTURE.md раздел 5.
"""

from datetime import datetime, timezone

UTC = timezone.utc

from app.core.exceptions import InvalidStateTransitionError
from app.models.domain import EmployerLead, StatusChange
from app.models.enums import LeadStatus

# Допустимые переходы из каждого состояния
TRANSITIONS: dict[LeadStatus, list[LeadStatus]] = {
    LeadStatus.LEAD_FOUND: [
        LeadStatus.ENRICHED,
        LeadStatus.ARCHIVED,
        LeadStatus.DUPLICATE,
    ],
    LeadStatus.ENRICHED: [
        LeadStatus.SCORED,
        LeadStatus.ARCHIVED,
    ],
    LeadStatus.SCORED: [
        LeadStatus.EMAIL_READY,
        LeadStatus.ARCHIVED,
    ],
    LeadStatus.EMAIL_READY: [
        LeadStatus.OUTREACH_SENT,
    ],
    LeadStatus.OUTREACH_SENT: [
        LeadStatus.IN_SEQUENCE,
        LeadStatus.REPLY_RECEIVED,
        LeadStatus.BOUNCED,
    ],
    LeadStatus.IN_SEQUENCE: [
        LeadStatus.REPLY_RECEIVED,
        LeadStatus.ARCHIVED,
        LeadStatus.BOUNCED,
    ],
    LeadStatus.REPLY_RECEIVED: [
        LeadStatus.INTEREST_DETECTED,
        LeadStatus.REFUSED,
        LeadStatus.IN_SEQUENCE,
        LeadStatus.OPTED_OUT,
        LeadStatus.COOLDOWN,
    ],
    LeadStatus.INTEREST_DETECTED: [
        LeadStatus.QUALIFIED,
    ],
    LeadStatus.QUALIFIED: [
        LeadStatus.HANDED_TO_MANAGER,
    ],
    LeadStatus.HANDED_TO_MANAGER: [],  # терминальное состояние
    LeadStatus.BOUNCED: [
        LeadStatus.ARCHIVED,
    ],
    LeadStatus.REFUSED: [
        LeadStatus.COOLDOWN,
        LeadStatus.ARCHIVED,
    ],
    LeadStatus.COOLDOWN: [
        LeadStatus.LEAD_FOUND,  # re-engage
    ],
    LeadStatus.OPTED_OUT: [],  # терминальное, не трогаем
    LeadStatus.DUPLICATE: [],  # терминальное
    LeadStatus.ARCHIVED: [
        LeadStatus.LEAD_FOUND,  # можно реактивировать
    ],
}


class LeadStateMachine:
    """State machine for lead lifecycle management.

    Валидирует переходы и обновляет историю состояний.
    Только Orchestrator должен использовать этот класс.
    """

    def __init__(self) -> None:
        self._transitions = TRANSITIONS

    def can_transition(self, from_status: LeadStatus, to_status: LeadStatus) -> bool:
        """Check if transition is allowed.

        Args:
            from_status: Current lead status
            to_status: Target status

        Returns:
            True if transition is valid
        """
        allowed = self._transitions.get(from_status, [])
        return to_status in allowed

    def get_valid_transitions(self, status: LeadStatus) -> list[LeadStatus]:
        """Get list of valid next states.

        Args:
            status: Current lead status

        Returns:
            List of valid target statuses
        """
        return self._transitions.get(status, [])

    def transition(
        self,
        lead: EmployerLead,
        to_status: LeadStatus,
        reason: str | None = None,
    ) -> EmployerLead:
        """Perform state transition with validation.

        Обновляет статус лида и добавляет запись в историю.

        Args:
            lead: Lead to transition
            to_status: Target status
            reason: Optional reason for transition

        Returns:
            Updated lead with new status

        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        if not self.can_transition(lead.status, to_status):
            raise InvalidStateTransitionError(
                from_status=lead.status,
                to_status=to_status,
            )

        now = datetime.now(UTC)

        # Записываем в историю
        change = StatusChange(
            from_status=lead.status,
            to_status=to_status,
            changed_at=now,
            reason=reason,
        )
        lead.status_history.append(change)

        # Обновляем статус
        lead.status = to_status
        lead.status_changed_at = now
        lead.updated_at = now

        # Обновляем связанные поля для терминальных состояний
        if to_status == LeadStatus.ARCHIVED:
            lead.archived_at = now
            lead.archived_reason = reason

        if to_status == LeadStatus.OPTED_OUT:
            lead.opted_out = True
            lead.opted_out_at = now

        return lead

    def is_terminal(self, status: LeadStatus) -> bool:
        """Check if status is terminal (no outgoing transitions).

        Args:
            status: Status to check

        Returns:
            True if no further transitions are possible
        """
        return len(self._transitions.get(status, [])) == 0

    def is_active(self, status: LeadStatus) -> bool:
        """Check if lead is in active pipeline state.

        Args:
            status: Status to check

        Returns:
            True if lead is actively being processed
        """
        active_statuses = {
            LeadStatus.LEAD_FOUND,
            LeadStatus.ENRICHED,
            LeadStatus.SCORED,
            LeadStatus.EMAIL_READY,
            LeadStatus.OUTREACH_SENT,
            LeadStatus.IN_SEQUENCE,
            LeadStatus.REPLY_RECEIVED,
            LeadStatus.INTEREST_DETECTED,
            LeadStatus.QUALIFIED,
        }
        return status in active_statuses

    def is_positive_outcome(self, status: LeadStatus) -> bool:
        """Check if status represents positive outcome.

        Args:
            status: Status to check

        Returns:
            True if outcome is positive (qualified, handed off)
        """
        return status in {LeadStatus.QUALIFIED, LeadStatus.HANDED_TO_MANAGER}

    def is_negative_outcome(self, status: LeadStatus) -> bool:
        """Check if status represents negative outcome.

        Args:
            status: Status to check

        Returns:
            True if outcome is negative (archived, refused, etc.)
        """
        return status in {
            LeadStatus.ARCHIVED,
            LeadStatus.REFUSED,
            LeadStatus.OPTED_OUT,
            LeadStatus.BOUNCED,
            LeadStatus.DUPLICATE,
        }
