"""Follow-up Agent.

Генерация follow-up писем из ARCHITECTURE.md раздел 6.1.
"""

import logging
from datetime import datetime, timezone, timedelta

UTC = timezone.utc

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent
from app.email.engine import EmailIntelligenceEngine
from app.email.templates import FOLLOWUP_DELAYS_DAYS
from app.llm.router import LLMRouter
from app.models.domain import (
    AgentTask,
    CompanyProfile,
    EmailMessage,
    EmailSequence,
    EmployerContact,
    EmployerLead,
    LeadSegment,
)
from app.models.enums import EmailType, LLMTaskType

logger = logging.getLogger(__name__)


class FollowUpAgent(BaseAgent):
    """Agent for generating follow-up emails.

    Генерирует follow-up письма на основе предыдущих писем в цепочке.
    """

    agent_name = "followup"
    llm_task_types = [LLMTaskType.EMAIL_GENERATION]

    def __init__(self, llm_router: LLMRouter, db: AsyncSession) -> None:
        """Initialize agent.

        Args:
            llm_router: Router for LLM calls
            db: Database session
        """
        super().__init__(llm_router, db)
        self.email_engine = EmailIntelligenceEngine(llm_router)

    async def run(self, task: AgentTask) -> AgentResult:
        """Generate follow-up email.

        Expects task.input_data to contain:
        - lead: EmployerLead dict
        - profile: CompanyProfile dict
        - segment: LeadSegment dict
        - contact: EmployerContact dict
        - sequence: EmailSequence dict
        - previous_emails: list of EmailMessage dicts
        - email_type: EmailType string (followup_1, followup_2, or breakup)

        Args:
            task: Agent task with input data

        Returns:
            Result with generated follow-up email
        """
        try:
            # Parse input data
            lead_data = task.input_data.get("lead")
            profile_data = task.input_data.get("profile")
            segment_data = task.input_data.get("segment")
            contact_data = task.input_data.get("contact")
            sequence_data = task.input_data.get("sequence")
            previous_emails_data = task.input_data.get("previous_emails", [])
            email_type_str = task.input_data.get("email_type", "followup_1")

            if not all([lead_data, profile_data, segment_data, contact_data]):
                return AgentResult(
                    success=False,
                    error="Missing required input data",
                )

            # Create domain objects
            lead = EmployerLead.model_validate(lead_data)
            profile = CompanyProfile.model_validate(profile_data)
            segment = LeadSegment.model_validate(segment_data)
            contact = EmployerContact.model_validate(contact_data)

            # Parse email type
            email_type = EmailType(email_type_str)

            # Validate it's a follow-up type
            if email_type == EmailType.FIRST_TOUCH:
                return AgentResult(
                    success=False,
                    error="FollowUpAgent cannot generate first_touch emails",
                )

            # Parse previous emails for context
            previous_emails = []
            for email_data in previous_emails_data:
                previous_emails.append({
                    "subject": email_data.get("subject", ""),
                    "body": email_data.get("body", ""),
                })

            # Generate follow-up
            result = await self.email_engine.generate_email(
                lead=lead,
                profile=profile,
                segment=segment,
                contact=contact,
                email_type=email_type,
                sequence_id=sequence_data.get("id") if sequence_data else None,
                previous_emails=previous_emails if previous_emails else None,
            )

            if not result.success:
                return AgentResult(
                    success=False,
                    error=result.error or "Follow-up generation failed",
                    data={
                        "quality_issues": result.quality_result.issues if result.quality_result else [],
                    },
                )

            email_data = result.email.model_dump(mode="json") if result.email else {}

            return AgentResult(
                success=True,
                data={
                    "email": email_data,
                    "email_type": email_type.value,
                    "quality_result": {
                        "passed": result.quality_result.passed,
                        "issues": result.quality_result.issues,
                        "word_count": result.quality_result.word_count,
                    } if result.quality_result else None,
                    "generation_model": result.generation_model,
                },
            )

        except Exception as e:
            logger.exception(f"Follow-up agent failed: {e}")
            return AgentResult(
                success=False,
                error=str(e),
            )

    def get_next_email_type(self, current_step: int) -> EmailType | None:
        """Determine next email type based on current step.

        Args:
            current_step: Current step in sequence (1-4)

        Returns:
            Next email type or None if sequence complete
        """
        step_to_type = {
            1: EmailType.FOLLOWUP_1,  # After first_touch
            2: EmailType.FOLLOWUP_2,  # After followup_1
            3: EmailType.BREAKUP,     # After followup_2
        }
        return step_to_type.get(current_step)

    def get_send_time(
        self,
        email_type: EmailType,
        last_email_time: datetime,
    ) -> datetime:
        """Calculate when to send next email.

        Args:
            email_type: Type of email to send
            last_email_time: When last email was sent

        Returns:
            Datetime when to send
        """
        delay_days = FOLLOWUP_DELAYS_DAYS.get(email_type, 3)
        return last_email_time + timedelta(days=delay_days)

    async def should_send_followup(
        self,
        sequence: EmailSequence,
        last_email: EmailMessage,
    ) -> tuple[bool, EmailType | None, datetime | None]:
        """Check if follow-up should be sent.

        Args:
            sequence: Email sequence
            last_email: Last email in sequence

        Returns:
            Tuple of (should_send, email_type, scheduled_time)
        """
        # Sequence not active
        if not sequence.is_active:
            return False, None, None

        # Sequence completed
        if sequence.completed_at:
            return False, None, None

        # Check if reply received
        if last_email.replied:
            return False, None, None

        # Get next email type
        next_type = self.get_next_email_type(sequence.current_step)
        if not next_type:
            return False, None, None

        # Calculate send time
        last_sent = last_email.sent_at or datetime.now(UTC)
        send_time = self.get_send_time(next_type, last_sent)

        # Check if time has come
        if datetime.now(UTC) >= send_time:
            return True, next_type, send_time

        return False, next_type, send_time

    async def generate_all_followups(
        self,
        lead: EmployerLead,
        profile: CompanyProfile,
        segment: LeadSegment,
        contact: EmployerContact,
        first_email: EmailMessage,
    ) -> list[AgentResult]:
        """Pre-generate all follow-ups for a sequence.

        Args:
            lead: Lead
            profile: Company profile
            segment: Lead segment
            contact: Contact
            first_email: First email in sequence

        Returns:
            List of results for followup_1, followup_2, breakup
        """
        results = []
        previous_emails = [{
            "subject": first_email.subject,
            "body": first_email.body,
        }]

        for email_type in [EmailType.FOLLOWUP_1, EmailType.FOLLOWUP_2, EmailType.BREAKUP]:
            result = await self.email_engine.generate_email(
                lead=lead,
                profile=profile,
                segment=segment,
                contact=contact,
                email_type=email_type,
                sequence_id=str(first_email.sequence_id),
                previous_emails=previous_emails,
            )

            agent_result = AgentResult(
                success=result.success,
                error=result.error,
                data={
                    "email": result.email.model_dump(mode="json") if result.email else {},
                    "email_type": email_type.value,
                },
            )
            results.append(agent_result)

            if result.success and result.email:
                previous_emails.append({
                    "subject": result.email.subject,
                    "body": result.email.body,
                })

        return results
