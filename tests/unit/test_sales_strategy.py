"""Tests for SalesStrategyService.

Тесты выбора стратегии для sales агента.
"""

from uuid import uuid4

import pytest

from app.models.enums import ReplyIntent
from app.services.sales_knowledge_base import ConversationStage, ObjectionType
from app.services.sales_strategy import (
    ConversationContext,
    CTAType,
    ResponseStrategy,
    SalesStrategyService,
    StrategyDecision,
    sales_strategy_service,
)


class TestStrategySelection:
    """Tests for strategy selection logic."""

    @pytest.fixture
    def service(self) -> SalesStrategyService:
        """Create strategy service instance."""
        return SalesStrategyService()

    @pytest.fixture
    def base_context(self) -> ConversationContext:
        """Create base conversation context."""
        return ConversationContext(
            lead_id=uuid4(),
            company_name="Test Company",
            contact_name="Test Contact",
            industry="retail",
            city="Москва",
            emails_sent_count=0,
        )

    def test_cold_outreach_for_new_lead(
        self, service: SalesStrategyService, base_context: ConversationContext
    ) -> None:
        """Should use cold outreach strategy for new leads."""
        base_context.emails_sent_count = 0
        base_context.reply_intent = None

        decision = service.determine_strategy(base_context)

        assert decision.stage == ConversationStage.COLD_OUTREACH
        assert decision.strategy == ResponseStrategy.SOFT_CLOSE
        assert decision.cta_type == CTAType.TRY_FREE
        assert decision.should_mention_free is True
        assert decision.should_include_proof is True

    def test_followup_for_no_reply(
        self, service: SalesStrategyService, base_context: ConversationContext
    ) -> None:
        """Should use followup strategy when no reply received."""
        base_context.emails_sent_count = 1
        base_context.reply_intent = ReplyIntent.NO_REPLY

        decision = service.determine_strategy(base_context)

        assert decision.stage == ConversationStage.FOLLOWUP
        assert decision.strategy == ResponseStrategy.FOLLOWUP
        assert decision.max_response_words <= 80

    def test_followup_for_auto_reply(
        self, service: SalesStrategyService, base_context: ConversationContext
    ) -> None:
        """Should use followup strategy for auto-replies."""
        base_context.emails_sent_count = 1
        base_context.reply_intent = ReplyIntent.AUTO_REPLY

        decision = service.determine_strategy(base_context)

        assert decision.stage == ConversationStage.FOLLOWUP
        assert decision.strategy == ResponseStrategy.FOLLOWUP

    def test_unsubscribe_strategy(
        self, service: SalesStrategyService, base_context: ConversationContext
    ) -> None:
        """Should use unsubscribe strategy for unsubscribe requests."""
        base_context.emails_sent_count = 1
        base_context.reply_intent = ReplyIntent.UNSUBSCRIBE
        base_context.reply_text = "Отпишите меня"

        decision = service.determine_strategy(base_context)

        assert decision.strategy == ResponseStrategy.UNSUBSCRIBE
        assert decision.cta_type == CTAType.NONE
        assert decision.tone == "respectful"
        assert decision.max_response_words == 30

    def test_handoff_for_ready_to_call(
        self, service: SalesStrategyService, base_context: ConversationContext
    ) -> None:
        """Should recommend handoff for ready-to-call prospects."""
        base_context.emails_sent_count = 1
        base_context.reply_intent = ReplyIntent.READY_TO_CALL
        base_context.reply_text = "Давайте созвонимся"

        decision = service.determine_strategy(base_context)

        assert decision.stage == ConversationStage.HANDOFF_PREP
        assert decision.strategy == ResponseStrategy.REDIRECT_TO_MANAGER
        assert decision.handoff_recommended is True
        assert decision.cta_type == CTAType.CONTACT_MANAGER

    def test_closing_for_strong_interest(
        self, service: SalesStrategyService, base_context: ConversationContext
    ) -> None:
        """Should use closing strategy for strong interest."""
        base_context.emails_sent_count = 1
        base_context.reply_intent = ReplyIntent.STRONG_INTEREST
        base_context.reply_text = "Очень интересно, расскажите подробнее"

        decision = service.determine_strategy(base_context)

        assert decision.stage == ConversationStage.CLOSING
        assert decision.strategy == ResponseStrategy.HARD_CLOSE
        assert decision.cta_type == CTAType.SCHEDULE_CALL
        assert decision.handoff_recommended is True

    def test_question_answering_for_details_request(
        self, service: SalesStrategyService, base_context: ConversationContext
    ) -> None:
        """Should use question strategy for details requests."""
        base_context.emails_sent_count = 1
        base_context.reply_intent = ReplyIntent.REQUEST_DETAILS
        base_context.reply_text = "Сколько это стоит?"

        decision = service.determine_strategy(base_context)

        assert decision.stage == ConversationStage.QUESTION_ANSWERING
        assert decision.strategy == ResponseStrategy.ACKNOWLEDGE_AND_ANSWER
        assert decision.should_include_proof is True

    def test_nurturing_for_soft_interest(
        self, service: SalesStrategyService, base_context: ConversationContext
    ) -> None:
        """Should use nurturing strategy for soft interest."""
        base_context.emails_sent_count = 1
        base_context.reply_intent = ReplyIntent.SOFT_INTEREST
        base_context.reply_text = "Интересно, но не сейчас"

        decision = service.determine_strategy(base_context)

        assert decision.stage == ConversationStage.INTEREST_NURTURING
        assert decision.strategy == ResponseStrategy.NURTURE
        assert decision.tone == "patient"


class TestObjectionHandling:
    """Tests for objection handling strategy."""

    @pytest.fixture
    def service(self) -> SalesStrategyService:
        """Create strategy service instance."""
        return SalesStrategyService()

    @pytest.fixture
    def base_context(self) -> ConversationContext:
        """Create base conversation context."""
        return ConversationContext(
            lead_id=uuid4(),
            company_name="Test Company",
            contact_name="Test Contact",
            industry="retail",
            emails_sent_count=1,
            reply_intent=ReplyIntent.REFUSAL,
        )

    def test_objection_strategy_for_price(
        self, service: SalesStrategyService, base_context: ConversationContext
    ) -> None:
        """Should use objection handling for price objections."""
        base_context.objection_type = ObjectionType.PRICE
        base_context.reply_text = "Дорого"

        decision = service.determine_strategy(base_context)

        assert decision.stage == ConversationStage.OBJECTION_HANDLING
        assert decision.strategy == ResponseStrategy.HANDLE_OBJECTION
        assert decision.objection_type == ObjectionType.PRICE
        assert decision.should_mention_free is True

    def test_objection_strategy_for_competitor(
        self, service: SalesStrategyService, base_context: ConversationContext
    ) -> None:
        """Should use objection handling for competitor objections."""
        base_context.objection_type = ObjectionType.COMPETITOR
        base_context.reply_text = "Мы работаем с hh"

        decision = service.determine_strategy(base_context)

        assert decision.stage == ConversationStage.OBJECTION_HANDLING
        assert decision.strategy == ResponseStrategy.HANDLE_OBJECTION
        assert decision.objection_type == ObjectionType.COMPETITOR
        assert decision.tone == "understanding"

    def test_objection_strategy_for_timing(
        self, service: SalesStrategyService, base_context: ConversationContext
    ) -> None:
        """Should use objection handling for timing objections."""
        base_context.objection_type = ObjectionType.TIMING
        base_context.reply_text = "Не сейчас"

        decision = service.determine_strategy(base_context)

        assert decision.stage == ConversationStage.OBJECTION_HANDLING
        assert decision.strategy == ResponseStrategy.HANDLE_OBJECTION
        assert decision.objection_type == ObjectionType.TIMING

    def test_objection_strategy_for_why_free(
        self, service: SalesStrategyService, base_context: ConversationContext
    ) -> None:
        """Should mention free tier for 'why free' objections."""
        base_context.objection_type = ObjectionType.WHY_FREE
        base_context.reply_text = "Почему бесплатно?"

        decision = service.determine_strategy(base_context)

        assert decision.strategy == ResponseStrategy.HANDLE_OBJECTION
        assert decision.should_mention_free is True


class TestWrongPersonStrategy:
    """Tests for wrong person handling."""

    @pytest.fixture
    def service(self) -> SalesStrategyService:
        """Create strategy service instance."""
        return SalesStrategyService()

    def test_wrong_person_strategy(self, service: SalesStrategyService) -> None:
        """Should handle wrong person redirects."""
        context = ConversationContext(
            lead_id=uuid4(),
            company_name="Test Company",
            contact_name="Test Contact",
            industry="retail",
            emails_sent_count=1,
            reply_intent=ReplyIntent.WRONG_PERSON,
            reply_text="Это не ко мне, напишите HR",
        )

        decision = service.determine_strategy(context)

        assert decision.strategy == ResponseStrategy.ACKNOWLEDGE_AND_ANSWER
        assert decision.tone == "polite"
        assert decision.cta_type == CTAType.NONE


class TestFollowupProgression:
    """Tests for followup strategy progression."""

    @pytest.fixture
    def service(self) -> SalesStrategyService:
        """Create strategy service instance."""
        return SalesStrategyService()

    def test_first_followup(self, service: SalesStrategyService) -> None:
        """First followup should have helpful tone."""
        context = ConversationContext(
            lead_id=uuid4(),
            company_name="Test Company",
            contact_name="Test Contact",
            industry="retail",
            emails_sent_count=1,
            reply_intent=ReplyIntent.NO_REPLY,
        )

        decision = service.determine_strategy(context)

        assert decision.tone == "helpful"
        assert decision.cta_type == CTAType.POST_VACANCY

    def test_second_followup(self, service: SalesStrategyService) -> None:
        """Second followup should have curious tone."""
        context = ConversationContext(
            lead_id=uuid4(),
            company_name="Test Company",
            contact_name="Test Contact",
            industry="retail",
            emails_sent_count=2,
            reply_intent=ReplyIntent.NO_REPLY,
        )

        decision = service.determine_strategy(context)

        assert decision.tone == "curious"
        assert decision.cta_type == CTAType.LEARN_MORE

    def test_third_followup_and_beyond(self, service: SalesStrategyService) -> None:
        """Third+ followup should have direct tone."""
        context = ConversationContext(
            lead_id=uuid4(),
            company_name="Test Company",
            contact_name="Test Contact",
            industry="retail",
            emails_sent_count=3,
            reply_intent=ReplyIntent.NO_REPLY,
        )

        decision = service.determine_strategy(context)

        assert decision.tone == "direct"
        assert decision.cta_type == CTAType.REGISTER


class TestStrategyDecisionFields:
    """Tests for StrategyDecision dataclass."""

    def test_strategy_decision_has_reasoning(self) -> None:
        """Strategy decisions should include reasoning."""
        service = SalesStrategyService()
        context = ConversationContext(
            lead_id=uuid4(),
            company_name="Test Company",
            contact_name="Test Contact",
            industry="retail",
            emails_sent_count=0,
        )

        decision = service.determine_strategy(context)

        assert decision.reasoning != ""
        assert len(decision.reasoning) > 0

    def test_all_strategy_decisions_have_max_words(self) -> None:
        """All strategy decisions should have max_response_words."""
        service = SalesStrategyService()

        intents = [
            ReplyIntent.NO_REPLY,
            ReplyIntent.NEUTRAL,
            ReplyIntent.REFUSAL,
            ReplyIntent.SOFT_INTEREST,
            ReplyIntent.REQUEST_DETAILS,
            ReplyIntent.STRONG_INTEREST,
            ReplyIntent.READY_TO_CALL,
            ReplyIntent.UNSUBSCRIBE,
        ]

        for intent in intents:
            context = ConversationContext(
                lead_id=uuid4(),
                company_name="Test",
                contact_name="Test",
                industry="retail",
                emails_sent_count=1,
                reply_intent=intent,
            )

            decision = service.determine_strategy(context)
            assert decision.max_response_words > 0
            assert decision.max_response_words <= 150


class TestSingletonInstance:
    """Tests for singleton instance."""

    def test_singleton_exists(self) -> None:
        """Singleton instance should exist."""
        assert sales_strategy_service is not None
        assert isinstance(sales_strategy_service, SalesStrategyService)

    def test_singleton_works(self) -> None:
        """Singleton should be fully functional."""
        context = ConversationContext(
            lead_id=uuid4(),
            company_name="Test",
            contact_name="Test",
            industry="retail",
            emails_sent_count=0,
        )

        decision = sales_strategy_service.determine_strategy(context)
        assert decision is not None
        assert isinstance(decision, StrategyDecision)


class TestEnums:
    """Tests for strategy enums."""

    def test_response_strategy_values(self) -> None:
        """ResponseStrategy should have all expected values."""
        expected = [
            "acknowledge_and_answer",
            "handle_objection",
            "soft_close",
            "hard_close",
            "redirect_to_manager",
            "nurture",
            "followup",
            "unsubscribe",
        ]

        for value in expected:
            strategy = ResponseStrategy(value)
            assert strategy is not None

    def test_cta_type_values(self) -> None:
        """CTAType should have all expected values."""
        expected = [
            "register",
            "try_free",
            "schedule_call",
            "learn_more",
            "post_vacancy",
            "contact_manager",
            "none",
        ]

        for value in expected:
            cta = CTAType(value)
            assert cta is not None
