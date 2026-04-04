"""Email Copy Agent.

Генерация писем через Email Engine из ARCHITECTURE.md раздел 6.1.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent
from app.email.engine import EmailIntelligenceEngine
from app.llm.router import LLMRouter
from app.models.domain import (
    AgentTask,
    CompanyProfile,
    EmployerContact,
    EmployerLead,
    LeadSegment,
)
from app.models.enums import EmailType, LLMTaskType

logger = logging.getLogger(__name__)


class EmailCopyAgent(BaseAgent):
    """Agent for generating email copy.

    Генерирует первое письмо для лида через EmailIntelligenceEngine.
    Использует LLMTaskType.EMAIL_GENERATION.
    """

    agent_name = "email_copy"
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
        """Generate first touch email.

        Expects task.input_data to contain:
        - lead: EmployerLead dict
        - profile: CompanyProfile dict
        - segment: LeadSegment dict
        - contact: EmployerContact dict

        Args:
            task: Agent task with input data

        Returns:
            Result with generated email
        """
        try:
            # Parse input data
            lead_data = task.input_data.get("lead")
            profile_data = task.input_data.get("profile")
            segment_data = task.input_data.get("segment")
            contact_data = task.input_data.get("contact")

            if not all([lead_data, profile_data, segment_data, contact_data]):
                return AgentResult(
                    success=False,
                    error="Missing required input data (lead, profile, segment, contact)",
                )

            # Create domain objects
            lead = EmployerLead.model_validate(lead_data)
            profile = CompanyProfile.model_validate(profile_data)
            segment = LeadSegment.model_validate(segment_data)
            contact = EmployerContact.model_validate(contact_data)

            # Generate first touch email
            result = await self.email_engine.generate_email(
                lead=lead,
                profile=profile,
                segment=segment,
                contact=contact,
                email_type=EmailType.FIRST_TOUCH,
            )

            if not result.success:
                return AgentResult(
                    success=False,
                    error=result.error or "Email generation failed",
                    data={
                        "quality_issues": result.quality_result.issues if result.quality_result else [],
                    },
                )

            # Return success with email data
            email_data = result.email.model_dump(mode="json") if result.email else {}

            return AgentResult(
                success=True,
                data={
                    "email": email_data,
                    "quality_result": {
                        "passed": result.quality_result.passed,
                        "issues": result.quality_result.issues,
                        "word_count": result.quality_result.word_count,
                        "subject_length": result.quality_result.subject_length,
                    } if result.quality_result else None,
                    "generation_model": result.generation_model,
                },
            )

        except Exception as e:
            logger.exception(f"Email copy agent failed: {e}")
            return AgentResult(
                success=False,
                error=str(e),
            )

    async def generate_with_retry(
        self,
        lead: EmployerLead,
        profile: CompanyProfile,
        segment: LeadSegment,
        contact: EmployerContact,
        max_retries: int = 3,
    ) -> AgentResult:
        """Generate email with retries on quality gate failure.

        Args:
            lead: Lead
            profile: Company profile
            segment: Lead segment
            contact: Contact
            max_retries: Maximum retries

        Returns:
            Agent result
        """
        last_error = None

        for attempt in range(max_retries):
            result = await self.email_engine.generate_email(
                lead=lead,
                profile=profile,
                segment=segment,
                contact=contact,
                email_type=EmailType.FIRST_TOUCH,
            )

            if result.success:
                email_data = result.email.model_dump(mode="json") if result.email else {}
                return AgentResult(
                    success=True,
                    data={
                        "email": email_data,
                        "attempts": attempt + 1,
                    },
                )

            last_error = result.error
            logger.warning(
                f"Email generation attempt {attempt + 1} failed: {result.error}"
            )

        return AgentResult(
            success=False,
            error=last_error or "Max retries exceeded",
            data={"attempts": max_retries},
        )
