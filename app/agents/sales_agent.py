"""Sales Agent.

AI sales agent for B2B email conversations.
Analyzes replies, chooses strategy, generates personalized responses.
"""

import json
import logging
from dataclasses import asdict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent
from app.email.quality_gate import QualityGate, QualityResult
from app.email.sales_prompts import (
    UNSUBSCRIBE_RESPONSE,
    WRONG_PERSON_RESPONSE,
    build_sales_response_prompt,
)
from app.llm.router import LLMRouter
from app.models.domain import AgentTask, EmployerLead
from app.models.enums import EmailType, LLMTaskType, ReplyIntent
from app.services.sales_knowledge_base import (
    ConversationStage,
    ObjectionType,
    SalesKnowledgeBase,
    sales_knowledge_base,
)
from app.services.sales_strategy import (
    ConversationContext,
    ResponseStrategy,
    SalesStrategyService,
    StrategyDecision,
    sales_strategy_service,
)
from app.tools.analysis_tools import classify_reply_rule_based

logger = logging.getLogger(__name__)


class SalesAgent(BaseAgent):
    """AI Sales Agent for generating email responses.

    Handles:
    - Reply intent classification
    - Objection detection
    - Strategy selection
    - Response generation
    - Quality validation
    """

    agent_name = "sales"
    llm_task_types = [LLMTaskType.EMAIL_GENERATION]

    def __init__(
        self,
        llm_router: LLMRouter,
        db: AsyncSession,
        knowledge_base: SalesKnowledgeBase | None = None,
        strategy_service: SalesStrategyService | None = None,
        quality_gate: QualityGate | None = None,
    ) -> None:
        """Initialize SalesAgent.

        Args:
            llm_router: LLM router for generation
            db: Database session
            knowledge_base: Sales knowledge base (uses default if None)
            strategy_service: Strategy service (uses default if None)
            quality_gate: Quality gate for validation (uses default if None)
        """
        super().__init__(llm_router, db)
        self.knowledge_base = knowledge_base or sales_knowledge_base
        self.strategy_service = strategy_service or sales_strategy_service
        self.quality_gate = quality_gate or QualityGate()

    async def run(self, task: AgentTask) -> AgentResult:
        """Execute sales response generation.

        Args:
            task: Agent task with input data:
                - lead: EmployerLead dict
                - contact_name: str
                - reply_text: str | None
                - previous_emails: list[dict]
                - emails_sent_count: int

        Returns:
            AgentResult with generated email and strategy info
        """
        try:
            # 1. Parse inputs
            lead_data = task.input_data.get("lead", {})
            lead = EmployerLead.model_validate(lead_data)

            contact_name = task.input_data.get("contact_name", "")
            reply_text = task.input_data.get("reply_text")
            previous_emails = task.input_data.get("previous_emails", [])
            emails_sent_count = task.input_data.get("emails_sent_count", 0)
            industry = task.input_data.get("industry", "other")
            city = task.input_data.get("city") or lead.city

            # 2. Classify reply intent (if there's a reply)
            reply_intent: ReplyIntent | None = None
            intent_confidence: float = 0.0

            if reply_text:
                reply_intent, intent_confidence = classify_reply_rule_based(reply_text)
                logger.info(
                    f"Reply classified: intent={reply_intent}, confidence={intent_confidence}"
                )

            # 3. Detect objection
            objection_type: ObjectionType | None = None
            if reply_text:
                objection_type = self.knowledge_base.detect_objection(reply_text)
                if objection_type:
                    logger.info(f"Objection detected: {objection_type}")

            # 4. Build conversation context
            context = ConversationContext(
                lead_id=lead.id,
                company_name=lead.company_name,
                contact_name=contact_name,
                industry=industry,
                city=city,
                emails_sent_count=emails_sent_count,
                previous_emails=previous_emails,
                reply_text=reply_text,
                reply_intent=reply_intent,
                intent_confidence=intent_confidence,
                objection_type=objection_type,
                has_replied_before=emails_sent_count > 0 and reply_text is not None,
            )

            # 5. Get strategy decision
            strategy = self.strategy_service.determine_strategy(context)
            logger.info(
                f"Strategy: stage={strategy.stage}, strategy={strategy.strategy}"
            )

            # 6. Generate response based on strategy
            email_result = await self._generate_response(
                context=context,
                strategy=strategy,
                lead=lead,
            )

            if not email_result["success"]:
                return AgentResult(
                    success=False,
                    error=email_result.get("error", "Failed to generate response"),
                )

            # 7. Return result
            return AgentResult(
                success=True,
                data={
                    "email": {
                        "subject": email_result["subject"],
                        "body": email_result["body"],
                    },
                    "strategy": {
                        "stage": strategy.stage.value,
                        "strategy": strategy.strategy.value,
                        "cta_type": strategy.cta_type.value,
                        "tone": strategy.tone,
                        "handoff_recommended": strategy.handoff_recommended,
                        "reasoning": strategy.reasoning,
                    },
                    "analysis": {
                        "reply_intent": reply_intent.value if reply_intent else None,
                        "intent_confidence": intent_confidence,
                        "objection_type": (
                            objection_type.value if objection_type else None
                        ),
                    },
                    "quality": email_result.get("quality", {}),
                    "internal_notes": email_result.get("internal_notes"),
                },
            )

        except Exception as e:
            logger.exception(f"SalesAgent error: {e}")
            return AgentResult(success=False, error=str(e))

    async def _generate_response(
        self,
        context: ConversationContext,
        strategy: StrategyDecision,
        lead: EmployerLead,
    ) -> dict:
        """Generate email response based on strategy.

        Args:
            context: Conversation context
            strategy: Strategy decision
            lead: Lead for quality validation

        Returns:
            Dict with subject, body, quality info
        """
        # Handle special cases without LLM
        if strategy.strategy == ResponseStrategy.UNSUBSCRIBE:
            return {
                "success": True,
                "subject": UNSUBSCRIBE_RESPONSE["subject"],
                "body": UNSUBSCRIBE_RESPONSE["body"],
                "quality": {"passed": True, "issues": []},
                "internal_notes": "Unsubscribe - templated response",
            }

        if (
            context.reply_intent == ReplyIntent.WRONG_PERSON
            and strategy.strategy == ResponseStrategy.ACKNOWLEDGE_AND_ANSWER
        ):
            return {
                "success": True,
                "subject": WRONG_PERSON_RESPONSE["subject"],
                "body": WRONG_PERSON_RESPONSE["body"],
                "quality": {"passed": True, "issues": []},
                "internal_notes": "Wrong person - templated response",
            }

        # Build prompts
        system_prompt, user_prompt = build_sales_response_prompt(
            stage=strategy.stage,
            industry=context.industry,
            company_name=context.company_name,
            contact_name=context.contact_name,
            city=context.city,
            reply_text=context.reply_text,
            previous_emails=context.previous_emails,
            objection_type=strategy.objection_type,
            should_include_proof=strategy.should_include_proof,
            should_mention_free=strategy.should_mention_free,
            max_words=strategy.max_response_words,
        )

        # Generate via LLM
        try:
            result = await self.call_llm_json(
                task_type=LLMTaskType.EMAIL_GENERATION,
                system=system_prompt,
                user=user_prompt,
                temperature=0.7,
            )

            subject = result.get("subject", "")
            body = result.get("body", "")
            internal_notes = result.get("internal_notes", "")

            if not subject or not body:
                return {
                    "success": False,
                    "error": "LLM returned empty subject or body",
                }

            # Validate quality
            quality_result = self._validate_quality(
                subject=subject,
                body=body,
                strategy=strategy,
                lead=lead,
            )

            return {
                "success": True,
                "subject": subject,
                "body": body,
                "quality": {
                    "passed": quality_result.passed,
                    "issues": quality_result.issues,
                    "word_count": quality_result.word_count,
                    "subject_length": quality_result.subject_length,
                },
                "internal_notes": internal_notes,
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return {"success": False, "error": f"Invalid JSON response: {e}"}
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return {"success": False, "error": str(e)}

    def _validate_quality(
        self,
        subject: str,
        body: str,
        strategy: StrategyDecision,
        lead: EmployerLead,
    ) -> QualityResult:
        """Validate generated email quality.

        Args:
            subject: Email subject
            body: Email body
            strategy: Strategy used
            lead: Lead for context

        Returns:
            Quality validation result
        """
        # Map strategy stage to email type for quality gate
        email_type_map = {
            ConversationStage.COLD_OUTREACH: EmailType.FIRST_TOUCH,
            ConversationStage.FOLLOWUP: EmailType.FOLLOWUP_1,
            ConversationStage.AFTER_REPLY: EmailType.FOLLOWUP_1,
            ConversationStage.OBJECTION_HANDLING: EmailType.FOLLOWUP_1,
            ConversationStage.QUESTION_ANSWERING: EmailType.FOLLOWUP_1,
            ConversationStage.INTEREST_NURTURING: EmailType.FOLLOWUP_2,
            ConversationStage.CLOSING: EmailType.FOLLOWUP_2,
            ConversationStage.HANDOFF_PREP: EmailType.FOLLOWUP_2,
        }

        email_type = email_type_map.get(strategy.stage, EmailType.FOLLOWUP_1)

        return self.quality_gate.validate(
            subject=subject,
            body=body,
            email_type=email_type,
            lead=lead,
        )


# Factory function for creating agent
def create_sales_agent(
    llm_router: LLMRouter,
    db: AsyncSession,
) -> SalesAgent:
    """Create a SalesAgent instance.

    Args:
        llm_router: LLM router
        db: Database session

    Returns:
        Configured SalesAgent
    """
    return SalesAgent(llm_router=llm_router, db=db)
