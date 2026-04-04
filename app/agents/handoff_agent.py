"""Handoff Agent.

Передача квалифицированных лидов менеджеру из ARCHITECTURE.md раздел 6.1.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent
from app.config.settings import settings
from app.llm.router import LLMRouter
from app.models.domain import (
    AgentTask,
    CompanyProfile,
    EmailMessage,
    EmployerContact,
    EmployerLead,
    LeadQualification,
    LeadScore,
    LeadSegment,
    LeadSignal,
    ManagerHandoff,
)
from app.models.enums import LLMTaskType
from app.tools.handoff_tools import (
    create_handoff,
    notify_manager_email,
    notify_manager_slack,
)

logger = logging.getLogger(__name__)


class HandoffAgent(BaseAgent):
    """Agent for manager handoff.

    Создаёт бриф для менеджера и отправляет нотификации.
    """

    agent_name = "handoff"
    llm_task_types = [LLMTaskType.SUMMARIZATION]

    def __init__(self, llm_router: LLMRouter, db: AsyncSession) -> None:
        """Initialize agent.

        Args:
            llm_router: Router for LLM calls
            db: Database session
        """
        super().__init__(llm_router, db)

    async def run(self, task: AgentTask) -> AgentResult:
        """Create handoff and notify manager.

        Expects task.input_data to contain:
        - lead: dict - EmployerLead
        - profile: dict - CompanyProfile (optional)
        - contact: dict - EmployerContact
        - segment: dict - LeadSegment (optional)
        - score: dict - LeadScore (optional)
        - qualification: dict - LeadQualification
        - signals: list[dict] - LeadSignals
        - emails: list[dict] - EmailMessages
        - notify_slack: bool - whether to notify via Slack
        - notify_email: bool - whether to notify via email
        - manager_email: str - manager email (for email notification)
        - slack_webhook: str - Slack webhook URL (for Slack notification)

        Args:
            task: Agent task with input data

        Returns:
            Result with handoff and notification status
        """
        try:
            # Parse input
            lead_data = task.input_data.get("lead")
            profile_data = task.input_data.get("profile")
            contact_data = task.input_data.get("contact")
            segment_data = task.input_data.get("segment")
            score_data = task.input_data.get("score")
            qualification_data = task.input_data.get("qualification")
            signals_data = task.input_data.get("signals", [])
            emails_data = task.input_data.get("emails", [])

            notify_slack = task.input_data.get("notify_slack", False)
            notify_email = task.input_data.get("notify_email", False)
            manager_email = task.input_data.get("manager_email")
            slack_webhook = task.input_data.get("slack_webhook")

            if not all([lead_data, contact_data, qualification_data]):
                return AgentResult(
                    success=False,
                    error="Missing required data (lead, contact, qualification)",
                )

            # Create domain objects
            lead = EmployerLead.model_validate(lead_data)
            contact = EmployerContact.model_validate(contact_data)
            qualification = LeadQualification.model_validate(qualification_data)

            profile = CompanyProfile.model_validate(profile_data) if profile_data else None
            segment = LeadSegment.model_validate(segment_data) if segment_data else None
            score = LeadScore.model_validate(score_data) if score_data else None

            signals = [LeadSignal.model_validate(s) for s in signals_data]
            emails = [EmailMessage.model_validate(e) for e in emails_data]

            # Create handoff
            handoff = await create_handoff(
                lead=lead,
                profile=profile,
                contact=contact,
                segment=segment,
                score=score,
                qualification=qualification,
                signals=signals,
                emails=emails,
                llm_router=self.llm,
            )

            # Send notifications
            notification_results = {}

            if notify_slack and slack_webhook:
                slack_success = await notify_manager_slack(handoff, slack_webhook)
                notification_results["slack"] = slack_success
                if slack_success:
                    handoff.notified_via = "slack"

            if notify_email and manager_email:
                email_success = await notify_manager_email(
                    handoff,
                    manager_email,
                    {
                        "smtp_host": settings.smtp_host,
                        "smtp_port": settings.smtp_port,
                        "smtp_user": settings.smtp_user,
                        "smtp_password": settings.smtp_password.get_secret_value() if settings.smtp_password else None,
                        "from_email": settings.smtp_from_email,
                    },
                )
                notification_results["email"] = email_success
                if email_success and not handoff.notified_via:
                    handoff.notified_via = "email"

            return AgentResult(
                success=True,
                data={
                    "handoff": handoff.model_dump(mode="json"),
                    "notifications": notification_results,
                    "notified": any(notification_results.values()) if notification_results else False,
                },
            )

        except Exception as e:
            logger.exception(f"Handoff agent failed: {e}")
            return AgentResult(
                success=False,
                error=str(e),
            )

    async def create_handoff_only(
        self,
        lead: EmployerLead,
        profile: CompanyProfile | None,
        contact: EmployerContact,
        segment: LeadSegment | None,
        score: LeadScore | None,
        qualification: LeadQualification,
        signals: list[LeadSignal],
        emails: list[EmailMessage],
    ) -> ManagerHandoff:
        """Create handoff without notifications.

        Args:
            lead: Lead
            profile: Company profile
            contact: Contact
            segment: Segment
            score: Score
            qualification: Qualification
            signals: Signals
            emails: Emails

        Returns:
            Manager handoff
        """
        return await create_handoff(
            lead=lead,
            profile=profile,
            contact=contact,
            segment=segment,
            score=score,
            qualification=qualification,
            signals=signals,
            emails=emails,
            llm_router=self.llm,
        )

    async def notify_only(
        self,
        handoff: ManagerHandoff,
        slack_webhook: str | None = None,
        manager_email: str | None = None,
    ) -> dict[str, bool]:
        """Send notifications for existing handoff.

        Args:
            handoff: Handoff to notify about
            slack_webhook: Slack webhook URL
            manager_email: Manager email

        Returns:
            Dict of notification results
        """
        results = {}

        if slack_webhook:
            results["slack"] = await notify_manager_slack(handoff, slack_webhook)

        if manager_email:
            results["email"] = await notify_manager_email(
                handoff,
                manager_email,
                {
                    "smtp_host": settings.smtp_host,
                    "smtp_port": settings.smtp_port,
                    "smtp_user": settings.smtp_user,
                    "smtp_password": settings.smtp_password.get_secret_value() if settings.smtp_password else None,
                    "from_email": settings.smtp_from_email,
                },
            )

        return results
