"""Qualification Agent.

Квалификация лидов из ARCHITECTURE.md раздел 6.1.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent
from app.llm.router import LLMRouter
from app.models.domain import (
    AgentTask,
    CompanyProfile,
    EmployerContact,
    EmployerLead,
    LeadQualification,
    LeadScore,
    LeadSegment,
    LeadSignal,
)
from app.models.enums import LLMTaskType
from app.tools.qualification_tools import (
    calculate_qualification_score,
    get_disqualification_reasons,
    qualify_lead,
    should_request_manual_review,
)

logger = logging.getLogger(__name__)


class QualificationAgent(BaseAgent):
    """Agent for lead qualification.

    Определяет, готов ли лид к передаче менеджеру на основе
    сигналов интереса, скора и профиля компании.
    """

    agent_name = "qualification"
    llm_task_types = [LLMTaskType.QUALIFICATION]

    def __init__(self, llm_router: LLMRouter, db: AsyncSession) -> None:
        """Initialize agent.

        Args:
            llm_router: Router for LLM calls
            db: Database session
        """
        super().__init__(llm_router, db)

    async def run(self, task: AgentTask) -> AgentResult:
        """Qualify lead.

        Expects task.input_data to contain:
        - lead: dict - EmployerLead
        - profile: dict - CompanyProfile (optional)
        - contact: dict - EmployerContact
        - signals: list[dict] - LeadSignals
        - score: dict - LeadScore (optional)
        - segment: dict - LeadSegment (optional)

        Args:
            task: Agent task with input data

        Returns:
            Result with qualification decision
        """
        try:
            # Parse input
            lead_data = task.input_data.get("lead")
            profile_data = task.input_data.get("profile")
            contact_data = task.input_data.get("contact")
            signals_data = task.input_data.get("signals", [])
            score_data = task.input_data.get("score")
            segment_data = task.input_data.get("segment")

            if not lead_data or not contact_data:
                return AgentResult(
                    success=False,
                    error="Missing lead or contact data",
                )

            if not signals_data:
                return AgentResult(
                    success=False,
                    error="No signals to qualify on",
                )

            # Create domain objects
            lead = EmployerLead.model_validate(lead_data)
            contact = EmployerContact.model_validate(contact_data)
            profile = CompanyProfile.model_validate(profile_data) if profile_data else None
            score = LeadScore.model_validate(score_data) if score_data else None
            segment = LeadSegment.model_validate(segment_data) if segment_data else None

            signals = [LeadSignal.model_validate(s) for s in signals_data]

            # Check for disqualification
            disqualification_reasons = get_disqualification_reasons(lead, signals, score)
            if disqualification_reasons:
                return AgentResult(
                    success=True,
                    data={
                        "is_qualified": False,
                        "reason": "Disqualified: " + "; ".join(disqualification_reasons),
                        "disqualification_reasons": disqualification_reasons,
                        "needs_manual_review": False,
                    },
                )

            # Check if needs manual review
            needs_review, review_reason = should_request_manual_review(signals, score)
            if needs_review:
                return AgentResult(
                    success=True,
                    data={
                        "is_qualified": False,
                        "reason": review_reason,
                        "needs_manual_review": True,
                        "review_reason": review_reason,
                    },
                )

            # Qualify lead
            qualification = await qualify_lead(
                lead=lead,
                profile=profile,
                contact=contact,
                signals=signals,
                score=score,
                llm_router=self.llm,
                use_llm=True,
            )

            # Calculate qualification score
            qual_score = calculate_qualification_score(signals, score, profile)

            return AgentResult(
                success=True,
                data={
                    "qualification": qualification.model_dump(mode="json"),
                    "is_qualified": qualification.is_qualified,
                    "reason": qualification.qualification_reason,
                    "qualification_score": qual_score,
                    "needs_manual_review": False,
                },
            )

        except Exception as e:
            logger.exception(f"Qualification agent failed: {e}")
            return AgentResult(
                success=False,
                error=str(e),
            )

    async def quick_qualify(
        self,
        lead: EmployerLead,
        signals: list[LeadSignal],
        score: LeadScore | None = None,
    ) -> tuple[bool, str]:
        """Quick qualification without full context.

        Args:
            lead: Lead
            signals: Signals
            score: Score (optional)

        Returns:
            Tuple of (is_qualified, reason)
        """
        from app.tools.qualification_tools import check_auto_qualification

        return check_auto_qualification(signals, score)

    async def batch_qualify(
        self,
        leads_data: list[dict],
    ) -> list[AgentResult]:
        """Qualify multiple leads.

        Args:
            leads_data: List of lead data dicts

        Returns:
            List of results
        """
        results = []

        for data in leads_data:
            task = AgentTask(
                lead_id=data.get("lead", {}).get("id"),
                agent_name=self.agent_name,
                task_type="qualify",
                input_data=data,
            )

            result = await self.execute(task)
            results.append(result)

        return results
