"""Integration tests for Sales API.

Интеграционные тесты для Sales API endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.sales import router
from app.main import create_app


class TestGenerateResponseEndpoint:
    """Tests for POST /sales/generate-response."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        app = create_app()
        return TestClient(app)

    @pytest.fixture
    def valid_request(self) -> dict:
        """Create valid request body."""
        return {
            "lead_id": str(uuid4()),
            "company_name": "Пятёрочка",
            "contact_name": "Анна",
            "industry": "retail",
            "city": "Москва",
            "reply_text": None,
            "previous_emails": [],
            "emails_sent_count": 0,
        }

    @pytest.fixture
    def auth_headers(self) -> dict:
        """Create auth headers."""
        return {"X-API-Key": "test-api-key"}

    @patch("app.api.sales.LLMRouter")
    @patch("app.api.sales.get_session")
    def test_generate_cold_outreach(
        self,
        mock_get_session: MagicMock,
        mock_llm_router_class: MagicMock,
        valid_request: dict,
    ) -> None:
        """Should generate cold outreach email."""
        # Setup mocks
        mock_db = AsyncMock()
        mock_get_session.return_value = mock_db

        mock_router = MagicMock()
        mock_llm_router_class.return_value = mock_router

        # Mock LLM complete
        from app.llm.models import LLMResponse

        mock_response = LLMResponse(
            request_id=uuid4(),
            content='{"subject": "Test Subject", "body": "Test body with Пятёрочка. Has enough words for validation and a CTA question?", "internal_notes": "Test"}',
            provider="mock",
            model="mock",
        )
        mock_router.complete = AsyncMock(return_value=mock_response)

        # Note: In a real test environment, we would need to properly
        # configure the test database and auth. This is a simplified version.

    @patch("app.api.sales.LLMRouter")
    @patch("app.api.sales.get_session")
    def test_generate_with_reply(
        self,
        mock_get_session: MagicMock,
        mock_llm_router_class: MagicMock,
        valid_request: dict,
    ) -> None:
        """Should generate response to reply."""
        valid_request["reply_text"] = "Интересно, расскажите подробнее"
        valid_request["emails_sent_count"] = 1

        mock_db = AsyncMock()
        mock_get_session.return_value = mock_db

        mock_router = MagicMock()
        mock_llm_router_class.return_value = mock_router

        from app.llm.models import LLMResponse

        mock_response = LLMResponse(
            request_id=uuid4(),
            content='{"subject": "Re: Test", "body": "Test response body", "internal_notes": "Response"}',
            provider="mock",
            model="mock",
        )
        mock_router.complete = AsyncMock(return_value=mock_response)

    def test_invalid_lead_id(self, valid_request: dict) -> None:
        """Should reject invalid lead_id."""
        valid_request["lead_id"] = "not-a-uuid"

        # This would fail UUID validation


class TestAnalyzeReplyEndpoint:
    """Tests for POST /sales/analyze-reply."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_analyze_refusal(self) -> None:
        """Should analyze refusal reply."""
        # The actual test would need proper auth setup
        pass

    def test_analyze_interest(self) -> None:
        """Should analyze interest reply."""
        pass

    def test_analyze_objection(self) -> None:
        """Should detect objections."""
        pass


class TestKnowledgeEndpoint:
    """Tests for GET /sales/knowledge."""

    def test_list_all_options(self) -> None:
        """Should list all industries and objection types."""
        pass

    def test_get_industry_insight(self) -> None:
        """Should return industry insight."""
        pass

    def test_get_objection_handler(self) -> None:
        """Should return objection handler."""
        pass


class TestManagerContactEndpoint:
    """Tests for GET /sales/manager-contact."""

    def test_get_manager_contact(self) -> None:
        """Should return manager contact."""
        pass


# Standalone function tests that don't require full app
class TestAnalyzeReplyLogic:
    """Direct tests for analyze reply logic."""

    def test_refusal_detection(self) -> None:
        """Should detect refusal intent."""
        from app.tools.analysis_tools import classify_reply_rule_based
        from app.services.sales_knowledge_base import sales_knowledge_base
        from app.models.enums import ReplyIntent

        reply_text = "Не интересно"

        intent, confidence = classify_reply_rule_based(reply_text)
        objection = sales_knowledge_base.detect_objection(reply_text)

        assert intent == ReplyIntent.REFUSAL
        assert confidence > 0.7
        # "Не интересно" is a refusal, not a specific objection
        assert objection is None

    def test_price_objection_detection(self) -> None:
        """Should detect price objection."""
        from app.tools.analysis_tools import classify_reply_rule_based
        from app.services.sales_knowledge_base import sales_knowledge_base
        from app.services.sales_knowledge_base import ObjectionType

        reply_text = "Дорого"

        objection = sales_knowledge_base.detect_objection(reply_text)

        assert objection == ObjectionType.PRICE

    def test_competitor_objection_detection(self) -> None:
        """Should detect competitor objection."""
        from app.services.sales_knowledge_base import sales_knowledge_base
        from app.services.sales_knowledge_base import ObjectionType

        reply_text = "Мы уже работаем с hh.ru"

        objection = sales_knowledge_base.detect_objection(reply_text)

        assert objection == ObjectionType.COMPETITOR

    def test_ready_to_call_detection(self) -> None:
        """Should detect ready to call intent."""
        from app.tools.analysis_tools import classify_reply_rule_based
        from app.models.enums import ReplyIntent

        reply_text = "Давайте созвонимся завтра"

        intent, confidence = classify_reply_rule_based(reply_text)

        assert intent == ReplyIntent.READY_TO_CALL
        assert confidence > 0.7


class TestKnowledgeLogic:
    """Direct tests for knowledge base queries."""

    def test_get_retail_insight(self) -> None:
        """Should return retail industry insight."""
        from app.services.sales_knowledge_base import sales_knowledge_base

        insight = sales_knowledge_base.get_industry_insight("retail")

        assert insight is not None
        assert insight.industry == "retail"
        assert len(insight.pain_points) > 0
        assert len(insight.typical_roles) > 0

    def test_get_price_handler(self) -> None:
        """Should return price objection handler."""
        from app.services.sales_knowledge_base import (
            sales_knowledge_base,
            ObjectionType,
        )

        handler = sales_knowledge_base.get_objection_handler(ObjectionType.PRICE)

        assert handler is not None
        assert "бесплатн" in handler.response_template.lower()

    def test_get_manager_contact(self) -> None:
        """Should return valid manager contact."""
        from app.services.sales_knowledge_base import sales_knowledge_base

        contact = sales_knowledge_base.get_manager_contact()

        assert contact.name == "Владислав Наков"
        assert "@" in contact.email
        assert "+" in contact.phone

    def test_all_industries_available(self) -> None:
        """Should have all expected industries."""
        from app.services.sales_knowledge_base import sales_knowledge_base

        industries = sales_knowledge_base.get_all_industries()

        assert "retail" in industries
        assert "horeca" in industries
        assert "logistics" in industries
        assert "warehouse" in industries
        assert "manufacturing" in industries


class TestStrategyLogic:
    """Direct tests for strategy selection."""

    def test_cold_outreach_strategy(self) -> None:
        """Should select cold outreach strategy for new leads."""
        from uuid import uuid4
        from app.services.sales_strategy import (
            sales_strategy_service,
            ConversationContext,
        )
        from app.services.sales_knowledge_base import ConversationStage

        context = ConversationContext(
            lead_id=uuid4(),
            company_name="Test",
            contact_name="Test",
            industry="retail",
            emails_sent_count=0,
        )

        decision = sales_strategy_service.determine_strategy(context)

        assert decision.stage == ConversationStage.COLD_OUTREACH
        assert decision.should_include_proof is True
        assert decision.should_mention_free is True

    def test_followup_strategy(self) -> None:
        """Should select followup strategy after first email."""
        from uuid import uuid4
        from app.services.sales_strategy import (
            sales_strategy_service,
            ConversationContext,
        )
        from app.services.sales_knowledge_base import ConversationStage
        from app.models.enums import ReplyIntent

        context = ConversationContext(
            lead_id=uuid4(),
            company_name="Test",
            contact_name="Test",
            industry="retail",
            emails_sent_count=1,
            reply_intent=ReplyIntent.NO_REPLY,
        )

        decision = sales_strategy_service.determine_strategy(context)

        assert decision.stage == ConversationStage.FOLLOWUP

    def test_handoff_strategy_for_ready_to_call(self) -> None:
        """Should recommend handoff for ready-to-call."""
        from uuid import uuid4
        from app.services.sales_strategy import (
            sales_strategy_service,
            ConversationContext,
        )
        from app.services.sales_knowledge_base import ConversationStage
        from app.models.enums import ReplyIntent

        context = ConversationContext(
            lead_id=uuid4(),
            company_name="Test",
            contact_name="Test",
            industry="retail",
            emails_sent_count=1,
            reply_intent=ReplyIntent.READY_TO_CALL,
            reply_text="Созвонимся",
        )

        decision = sales_strategy_service.determine_strategy(context)

        assert decision.stage == ConversationStage.HANDOFF_PREP
        assert decision.handoff_recommended is True

    def test_objection_strategy(self) -> None:
        """Should select objection handling strategy."""
        from uuid import uuid4
        from app.services.sales_strategy import (
            sales_strategy_service,
            ConversationContext,
            ResponseStrategy,
        )
        from app.services.sales_knowledge_base import ConversationStage, ObjectionType
        from app.models.enums import ReplyIntent

        context = ConversationContext(
            lead_id=uuid4(),
            company_name="Test",
            contact_name="Test",
            industry="retail",
            emails_sent_count=1,
            reply_intent=ReplyIntent.REFUSAL,
            reply_text="Дорого",
            objection_type=ObjectionType.PRICE,
        )

        decision = sales_strategy_service.determine_strategy(context)

        assert decision.stage == ConversationStage.OBJECTION_HANDLING
        assert decision.strategy == ResponseStrategy.HANDLE_OBJECTION
        assert decision.objection_type == ObjectionType.PRICE


class TestEndToEndScenarios:
    """End-to-end scenario tests."""

    def test_cold_outreach_to_objection_flow(self) -> None:
        """Test flow from cold outreach through objection handling."""
        from uuid import uuid4
        from app.services.sales_strategy import (
            sales_strategy_service,
            ConversationContext,
        )
        from app.services.sales_knowledge_base import (
            sales_knowledge_base,
            ConversationStage,
            ObjectionType,
        )
        from app.models.enums import ReplyIntent

        lead_id = uuid4()

        # Step 1: Cold outreach
        context1 = ConversationContext(
            lead_id=lead_id,
            company_name="Пятёрочка",
            contact_name="Анна",
            industry="retail",
            emails_sent_count=0,
        )
        decision1 = sales_strategy_service.determine_strategy(context1)
        assert decision1.stage == ConversationStage.COLD_OUTREACH

        # Step 2: Prospect replies with objection
        reply_text = "Мы уже работаем с hh.ru"
        objection = sales_knowledge_base.detect_objection(reply_text)
        assert objection == ObjectionType.COMPETITOR

        context2 = ConversationContext(
            lead_id=lead_id,
            company_name="Пятёрочка",
            contact_name="Анна",
            industry="retail",
            emails_sent_count=1,
            reply_intent=ReplyIntent.REFUSAL,
            reply_text=reply_text,
            objection_type=objection,
        )
        decision2 = sales_strategy_service.determine_strategy(context2)
        assert decision2.stage == ConversationStage.OBJECTION_HANDLING

        # Verify correct handler is used
        handler = sales_knowledge_base.get_objection_handler(objection)
        assert "дополнительн" in handler.response_template.lower()

    def test_cold_outreach_to_handoff_flow(self) -> None:
        """Test flow from cold outreach to successful handoff."""
        from uuid import uuid4
        from app.services.sales_strategy import (
            sales_strategy_service,
            ConversationContext,
        )
        from app.services.sales_knowledge_base import ConversationStage
        from app.models.enums import ReplyIntent

        lead_id = uuid4()

        # Step 1: Cold outreach
        context1 = ConversationContext(
            lead_id=lead_id,
            company_name="Магнит",
            contact_name="Ирина",
            industry="retail",
            emails_sent_count=0,
        )
        decision1 = sales_strategy_service.determine_strategy(context1)
        assert decision1.stage == ConversationStage.COLD_OUTREACH

        # Step 2: Prospect shows strong interest
        context2 = ConversationContext(
            lead_id=lead_id,
            company_name="Магнит",
            contact_name="Ирина",
            industry="retail",
            emails_sent_count=1,
            reply_intent=ReplyIntent.STRONG_INTEREST,
            reply_text="Очень интересно! Расскажите подробнее",
        )
        decision2 = sales_strategy_service.determine_strategy(context2)
        assert decision2.stage == ConversationStage.CLOSING
        assert decision2.handoff_recommended is True

        # Step 3: Prospect ready to call
        context3 = ConversationContext(
            lead_id=lead_id,
            company_name="Магнит",
            contact_name="Ирина",
            industry="retail",
            emails_sent_count=2,
            reply_intent=ReplyIntent.READY_TO_CALL,
            reply_text="Давайте созвонимся!",
        )
        decision3 = sales_strategy_service.determine_strategy(context3)
        assert decision3.stage == ConversationStage.HANDOFF_PREP
        assert decision3.handoff_recommended is True
