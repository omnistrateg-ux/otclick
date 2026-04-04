"""Response Agent.

Анализ ответов на письма из ARCHITECTURE.md раздел 6.1.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent
from app.llm.router import LLMRouter
from app.models.domain import AgentTask, EmailMessage, EmployerLead, LeadSignal
from app.models.enums import LLMTaskType, ReplyIntent
from app.tools.analysis_tools import (
    analyze_reply,
    extract_redirect_contact,
    is_negative_intent,
    is_positive_intent,
)

logger = logging.getLogger(__name__)


class ResponseAgent(BaseAgent):
    """Agent for analyzing email replies.

    Анализирует входящие ответы на письма, классифицирует intent,
    определяет следующие шаги.
    """

    agent_name = "response"
    llm_task_types = [LLMTaskType.RESPONSE_ANALYSIS]

    def __init__(self, llm_router: LLMRouter, db: AsyncSession) -> None:
        """Initialize agent.

        Args:
            llm_router: Router for LLM calls
            db: Database session
        """
        super().__init__(llm_router, db)

    async def run(self, task: AgentTask) -> AgentResult:
        """Analyze email reply.

        Expects task.input_data to contain:
        - reply_text: str - text of the reply
        - email: dict - EmailMessage that was replied to
        - lead: dict - EmployerLead

        Args:
            task: Agent task with input data

        Returns:
            Result with analyzed signal
        """
        try:
            # Parse input
            reply_text = task.input_data.get("reply_text")
            email_data = task.input_data.get("email")
            lead_data = task.input_data.get("lead")

            if not reply_text:
                return AgentResult(
                    success=False,
                    error="Missing reply_text",
                )

            if not email_data or not lead_data:
                return AgentResult(
                    success=False,
                    error="Missing email or lead data",
                )

            # Create domain objects
            email = EmailMessage.model_validate(email_data)
            lead = EmployerLead.model_validate(lead_data)

            # Analyze reply
            signal = await analyze_reply(
                reply_text=reply_text,
                email=email,
                lead=lead,
                llm_router=self.llm,
                use_llm=True,
            )

            # Determine next action
            next_action = self._determine_next_action(signal)

            # Check for redirect contact
            redirect_contact = None
            if signal.intent == ReplyIntent.WRONG_PERSON:
                redirect_contact = extract_redirect_contact(reply_text)

            return AgentResult(
                success=True,
                data={
                    "signal": signal.model_dump(mode="json"),
                    "intent": signal.intent.value,
                    "confidence": signal.confidence,
                    "is_positive": is_positive_intent(signal.intent),
                    "is_negative": is_negative_intent(signal.intent),
                    "next_action": next_action,
                    "redirect_contact": redirect_contact,
                },
            )

        except Exception as e:
            logger.exception(f"Response agent failed: {e}")
            return AgentResult(
                success=False,
                error=str(e),
            )

    def _determine_next_action(self, signal: LeadSignal) -> str:
        """Determine next action based on signal.

        Args:
            signal: Analyzed signal

        Returns:
            Next action string
        """
        action_map = {
            ReplyIntent.READY_TO_CALL: "qualify_and_handoff",
            ReplyIntent.STRONG_INTEREST: "qualify_and_handoff",
            ReplyIntent.REQUEST_DETAILS: "qualify_and_handoff",
            ReplyIntent.SOFT_INTEREST: "qualify",
            ReplyIntent.NEUTRAL: "continue_sequence",
            ReplyIntent.AUTO_REPLY: "pause_and_retry",
            ReplyIntent.WRONG_PERSON: "update_contact",
            ReplyIntent.REFUSAL: "mark_refused",
            ReplyIntent.UNSUBSCRIBE: "mark_opted_out",
            ReplyIntent.NO_REPLY: "continue_sequence",
        }

        return action_map.get(signal.intent, "manual_review")

    async def analyze_batch(
        self,
        replies: list[dict],
    ) -> list[AgentResult]:
        """Analyze batch of replies.

        Args:
            replies: List of {reply_text, email, lead} dicts

        Returns:
            List of results
        """
        results = []

        for reply_data in replies:
            task = AgentTask(
                lead_id=reply_data.get("lead", {}).get("id"),
                agent_name=self.agent_name,
                task_type="analyze_reply",
                input_data=reply_data,
            )

            result = await self.execute(task)
            results.append(result)

        return results

    async def classify_intent_only(
        self,
        reply_text: str,
    ) -> tuple[ReplyIntent, float]:
        """Classify intent without full analysis.

        Args:
            reply_text: Reply text

        Returns:
            Tuple of (intent, confidence)
        """
        from app.tools.analysis_tools import classify_reply_llm

        intent, confidence, _ = await classify_reply_llm(reply_text, self.llm)
        return intent, confidence
