"""Sales Strategy Service.

Выбор стратегии ответа на основе контекста переписки.
"""

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from app.models.enums import ReplyIntent
from app.services.sales_knowledge_base import ConversationStage, ObjectionType


class ResponseStrategy(str, Enum):
    """Strategy for generating response."""

    ACKNOWLEDGE_AND_ANSWER = "acknowledge_and_answer"  # Ответ на вопрос
    HANDLE_OBJECTION = "handle_objection"  # Обработка возражения
    SOFT_CLOSE = "soft_close"  # Мягкое закрытие на следующий шаг
    HARD_CLOSE = "hard_close"  # Закрытие на звонок
    REDIRECT_TO_MANAGER = "redirect_to_manager"  # Передача менеджеру
    NURTURE = "nurture"  # Прогрев интереса
    FOLLOWUP = "followup"  # Follow-up письмо
    UNSUBSCRIBE = "unsubscribe"  # Отписка


class CTAType(str, Enum):
    """Type of call-to-action."""

    REGISTER = "register"  # Зарегистрируйтесь
    TRY_FREE = "try_free"  # Попробуйте бесплатно
    SCHEDULE_CALL = "schedule_call"  # Назначить звонок
    LEARN_MORE = "learn_more"  # Узнать больше
    POST_VACANCY = "post_vacancy"  # Разместить вакансию
    CONTACT_MANAGER = "contact_manager"  # Связаться с менеджером
    NONE = "none"  # Без CTA (unsubscribe)


@dataclass
class ConversationContext:
    """Context of the sales conversation."""

    lead_id: UUID
    company_name: str
    contact_name: str
    industry: str
    city: str | None = None

    # Email history
    emails_sent_count: int = 0
    last_email_type: str | None = None
    previous_emails: list[dict] = field(default_factory=list)

    # Reply analysis
    reply_text: str | None = None
    reply_intent: ReplyIntent | None = None
    intent_confidence: float = 0.0

    # Objection detected
    objection_type: ObjectionType | None = None

    # Additional flags
    has_phone: bool = False
    has_replied_before: bool = False


@dataclass
class StrategyDecision:
    """Decision on how to respond."""

    stage: ConversationStage
    strategy: ResponseStrategy
    cta_type: CTAType
    tone: str
    max_response_words: int
    should_include_proof: bool
    should_mention_free: bool
    handoff_recommended: bool
    objection_type: ObjectionType | None = None
    reasoning: str = ""


# Strategy selection rules
INTENT_TO_STAGE: dict[ReplyIntent, ConversationStage] = {
    ReplyIntent.NO_REPLY: ConversationStage.FOLLOWUP,
    ReplyIntent.AUTO_REPLY: ConversationStage.FOLLOWUP,
    ReplyIntent.NEUTRAL: ConversationStage.AFTER_REPLY,
    ReplyIntent.REFUSAL: ConversationStage.OBJECTION_HANDLING,
    ReplyIntent.SOFT_INTEREST: ConversationStage.INTEREST_NURTURING,
    ReplyIntent.REQUEST_DETAILS: ConversationStage.QUESTION_ANSWERING,
    ReplyIntent.STRONG_INTEREST: ConversationStage.CLOSING,
    ReplyIntent.READY_TO_CALL: ConversationStage.HANDOFF_PREP,
    ReplyIntent.UNSUBSCRIBE: ConversationStage.COLD_OUTREACH,  # Will be overridden
    ReplyIntent.WRONG_PERSON: ConversationStage.COLD_OUTREACH,  # Need to find new contact
}


class SalesStrategyService:
    """Service for determining sales response strategy."""

    def determine_strategy(
        self,
        context: ConversationContext,
    ) -> StrategyDecision:
        """Determine the best strategy for responding.

        Args:
            context: Current conversation context

        Returns:
            Strategy decision with all parameters
        """
        # Handle special cases first
        if context.reply_intent == ReplyIntent.UNSUBSCRIBE:
            return self._unsubscribe_strategy(context)

        if context.reply_intent == ReplyIntent.READY_TO_CALL:
            return self._handoff_strategy(context)

        if context.reply_intent == ReplyIntent.WRONG_PERSON:
            return self._wrong_person_strategy(context)

        # Handle objection if detected
        if context.objection_type is not None:
            return self._objection_strategy(context)

        # Map intent to stage
        stage = self._determine_stage(context)

        # Get strategy based on stage
        if stage == ConversationStage.FOLLOWUP:
            return self._followup_strategy(context)
        elif stage == ConversationStage.QUESTION_ANSWERING:
            return self._question_strategy(context)
        elif stage == ConversationStage.CLOSING:
            return self._closing_strategy(context)
        elif stage == ConversationStage.INTEREST_NURTURING:
            return self._nurturing_strategy(context)
        elif stage == ConversationStage.AFTER_REPLY:
            return self._after_reply_strategy(context)
        else:
            # Default: cold outreach or first touch
            return self._cold_outreach_strategy(context)

    def _determine_stage(self, context: ConversationContext) -> ConversationStage:
        """Determine conversation stage from context.

        Args:
            context: Conversation context

        Returns:
            Current conversation stage
        """
        # No emails sent yet
        if context.emails_sent_count == 0:
            return ConversationStage.COLD_OUTREACH

        # No reply yet - followup
        if context.reply_intent in (ReplyIntent.NO_REPLY, ReplyIntent.AUTO_REPLY):
            return ConversationStage.FOLLOWUP

        # Map from intent
        return INTENT_TO_STAGE.get(
            context.reply_intent or ReplyIntent.NEUTRAL,
            ConversationStage.AFTER_REPLY,
        )

    def _cold_outreach_strategy(self, context: ConversationContext) -> StrategyDecision:
        """Strategy for initial cold outreach."""
        return StrategyDecision(
            stage=ConversationStage.COLD_OUTREACH,
            strategy=ResponseStrategy.SOFT_CLOSE,
            cta_type=CTAType.TRY_FREE,
            tone="professional",
            max_response_words=150,
            should_include_proof=True,
            should_mention_free=True,
            handoff_recommended=False,
            reasoning="Первое письмо: нужно заинтересовать и показать ценность",
        )

    def _followup_strategy(self, context: ConversationContext) -> StrategyDecision:
        """Strategy for followup emails."""
        # Adjust based on followup number
        followup_num = context.emails_sent_count

        if followup_num <= 1:
            cta_type = CTAType.POST_VACANCY
            tone = "helpful"
        elif followup_num == 2:
            cta_type = CTAType.LEARN_MORE
            tone = "curious"
        else:
            cta_type = CTAType.REGISTER
            tone = "direct"

        return StrategyDecision(
            stage=ConversationStage.FOLLOWUP,
            strategy=ResponseStrategy.FOLLOWUP,
            cta_type=cta_type,
            tone=tone,
            max_response_words=80,
            should_include_proof=followup_num <= 2,
            should_mention_free=True,
            handoff_recommended=False,
            reasoning=f"Follow-up #{followup_num}: короче и конкретнее",
        )

    def _objection_strategy(self, context: ConversationContext) -> StrategyDecision:
        """Strategy for handling objections."""
        return StrategyDecision(
            stage=ConversationStage.OBJECTION_HANDLING,
            strategy=ResponseStrategy.HANDLE_OBJECTION,
            cta_type=CTAType.TRY_FREE,
            tone="understanding",
            max_response_words=100,
            should_include_proof=True,
            should_mention_free=context.objection_type
            in (ObjectionType.PRICE, ObjectionType.WHY_FREE),
            handoff_recommended=False,
            objection_type=context.objection_type,
            reasoning=f"Обработка возражения: {context.objection_type}",
        )

    def _question_strategy(self, context: ConversationContext) -> StrategyDecision:
        """Strategy for answering questions."""
        return StrategyDecision(
            stage=ConversationStage.QUESTION_ANSWERING,
            strategy=ResponseStrategy.ACKNOWLEDGE_AND_ANSWER,
            cta_type=CTAType.POST_VACANCY,
            tone="informative",
            max_response_words=120,
            should_include_proof=True,
            should_mention_free=True,
            handoff_recommended=False,
            reasoning="Ответ на вопрос: дать информацию и предложить следующий шаг",
        )

    def _closing_strategy(self, context: ConversationContext) -> StrategyDecision:
        """Strategy for closing interested prospects."""
        # Strong interest → push for call
        return StrategyDecision(
            stage=ConversationStage.CLOSING,
            strategy=ResponseStrategy.HARD_CLOSE,
            cta_type=CTAType.SCHEDULE_CALL,
            tone="enthusiastic",
            max_response_words=80,
            should_include_proof=False,
            should_mention_free=False,
            handoff_recommended=True,
            reasoning="Сильный интерес: закрываем на звонок",
        )

    def _nurturing_strategy(self, context: ConversationContext) -> StrategyDecision:
        """Strategy for nurturing soft interest."""
        return StrategyDecision(
            stage=ConversationStage.INTEREST_NURTURING,
            strategy=ResponseStrategy.NURTURE,
            cta_type=CTAType.REGISTER,
            tone="patient",
            max_response_words=100,
            should_include_proof=True,
            should_mention_free=True,
            handoff_recommended=False,
            reasoning="Мягкий интерес: греем, но не давим",
        )

    def _after_reply_strategy(self, context: ConversationContext) -> StrategyDecision:
        """Strategy for neutral replies."""
        return StrategyDecision(
            stage=ConversationStage.AFTER_REPLY,
            strategy=ResponseStrategy.SOFT_CLOSE,
            cta_type=CTAType.TRY_FREE,
            tone="friendly",
            max_response_words=100,
            should_include_proof=True,
            should_mention_free=True,
            handoff_recommended=False,
            reasoning="Нейтральный ответ: продолжаем диалог",
        )

    def _handoff_strategy(self, context: ConversationContext) -> StrategyDecision:
        """Strategy for ready-to-call prospects."""
        return StrategyDecision(
            stage=ConversationStage.HANDOFF_PREP,
            strategy=ResponseStrategy.REDIRECT_TO_MANAGER,
            cta_type=CTAType.CONTACT_MANAGER,
            tone="excited",
            max_response_words=60,
            should_include_proof=False,
            should_mention_free=False,
            handoff_recommended=True,
            reasoning="Готов к звонку: передаём менеджеру",
        )

    def _unsubscribe_strategy(self, context: ConversationContext) -> StrategyDecision:
        """Strategy for unsubscribe requests."""
        return StrategyDecision(
            stage=ConversationStage.COLD_OUTREACH,  # Effectively ends conversation
            strategy=ResponseStrategy.UNSUBSCRIBE,
            cta_type=CTAType.NONE,
            tone="respectful",
            max_response_words=30,
            should_include_proof=False,
            should_mention_free=False,
            handoff_recommended=False,
            reasoning="Отписка: уважаем решение",
        )

    def _wrong_person_strategy(self, context: ConversationContext) -> StrategyDecision:
        """Strategy for wrong person replies."""
        return StrategyDecision(
            stage=ConversationStage.COLD_OUTREACH,
            strategy=ResponseStrategy.ACKNOWLEDGE_AND_ANSWER,
            cta_type=CTAType.NONE,
            tone="polite",
            max_response_words=50,
            should_include_proof=False,
            should_mention_free=False,
            handoff_recommended=False,
            reasoning="Не тот человек: благодарим и извиняемся",
        )


# Singleton instance
sales_strategy_service = SalesStrategyService()
