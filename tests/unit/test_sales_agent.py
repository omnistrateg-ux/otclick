"""Tests for SalesAgent.

Тесты для sales агента.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agents.sales_agent import SalesAgent, create_sales_agent
from app.email.quality_gate import QualityGate, QualityResult
from app.llm.router import LLMRouter
from app.models.domain import AgentTask, EmployerLead
from app.models.enums import EmailType, ReplyIntent
from app.services.sales_knowledge_base import (
    ConversationStage,
    ObjectionType,
    SalesKnowledgeBase,
)
from app.services.sales_strategy import (
    CTAType,
    ResponseStrategy,
    SalesStrategyService,
    StrategyDecision,
)


class TestSalesAgentInit:
    """Tests for SalesAgent initialization."""

    def test_agent_name(self) -> None:
        """Agent should have correct name."""
        router = MagicMock(spec=LLMRouter)
        db = MagicMock()

        agent = SalesAgent(llm_router=router, db=db)

        assert agent.agent_name == "sales"

    def test_default_dependencies(self) -> None:
        """Should use default dependencies when not provided."""
        router = MagicMock(spec=LLMRouter)
        db = MagicMock()

        agent = SalesAgent(llm_router=router, db=db)

        assert agent.knowledge_base is not None
        assert agent.strategy_service is not None
        assert agent.quality_gate is not None

    def test_custom_dependencies(self) -> None:
        """Should accept custom dependencies."""
        router = MagicMock(spec=LLMRouter)
        db = MagicMock()
        custom_kb = MagicMock(spec=SalesKnowledgeBase)
        custom_strategy = MagicMock(spec=SalesStrategyService)
        custom_gate = MagicMock(spec=QualityGate)

        agent = SalesAgent(
            llm_router=router,
            db=db,
            knowledge_base=custom_kb,
            strategy_service=custom_strategy,
            quality_gate=custom_gate,
        )

        assert agent.knowledge_base is custom_kb
        assert agent.strategy_service is custom_strategy
        assert agent.quality_gate is custom_gate


class TestSalesAgentRun:
    """Tests for SalesAgent.run() method."""

    @pytest.fixture
    def mock_llm_router(self) -> MagicMock:
        """Create mock LLM router."""
        router = MagicMock(spec=LLMRouter)
        return router

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def base_task(self) -> AgentTask:
        """Create base task for testing."""
        lead_id = uuid4()
        return AgentTask(
            lead_id=lead_id,
            agent_name="sales",
            task_type="generate_response",
            input_data={
                "lead": {
                    "id": str(lead_id),
                    "company_name": "Test Company",
                    "source": "test",
                },
                "contact_name": "Test Person",
                "reply_text": None,
                "previous_emails": [],
                "emails_sent_count": 0,
                "industry": "retail",
                "city": "Москва",
            },
        )

    @pytest.mark.asyncio
    async def test_successful_cold_outreach(
        self, mock_llm_router: MagicMock, mock_db: MagicMock, base_task: AgentTask
    ) -> None:
        """Should generate successful cold outreach email."""
        agent = SalesAgent(llm_router=mock_llm_router, db=mock_db)

        # Mock LLM response
        agent.call_llm_json = AsyncMock(
            return_value={
                "subject": "Кассиры для Test Company",
                "body": "Здравствуйте, Test Person! Знаю, как сложно найти кассиров...",
                "internal_notes": "Cold outreach",
            }
        )

        result = await agent.run(base_task)

        assert result.success is True
        assert "email" in result.data
        assert result.data["email"]["subject"] == "Кассиры для Test Company"
        assert "strategy" in result.data
        assert result.data["strategy"]["stage"] == "cold_outreach"

    @pytest.mark.asyncio
    async def test_unsubscribe_handling(
        self, mock_llm_router: MagicMock, mock_db: MagicMock, base_task: AgentTask
    ) -> None:
        """Should handle unsubscribe without LLM call."""
        base_task.input_data["reply_text"] = "Отпишите меня"
        base_task.input_data["emails_sent_count"] = 1

        agent = SalesAgent(llm_router=mock_llm_router, db=mock_db)
        agent.call_llm_json = AsyncMock()  # Should not be called

        result = await agent.run(base_task)

        assert result.success is True
        assert "Отписка" in result.data["email"]["subject"]
        agent.call_llm_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_wrong_person_handling(
        self, mock_llm_router: MagicMock, mock_db: MagicMock, base_task: AgentTask
    ) -> None:
        """Should handle wrong person without LLM call."""
        base_task.input_data["reply_text"] = "Это не ко мне"
        base_task.input_data["emails_sent_count"] = 1

        agent = SalesAgent(llm_router=mock_llm_router, db=mock_db)
        agent.call_llm_json = AsyncMock()  # Should not be called

        result = await agent.run(base_task)

        assert result.success is True
        assert "извин" in result.data["email"]["subject"].lower()
        agent.call_llm_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_objection_detection(
        self, mock_llm_router: MagicMock, mock_db: MagicMock, base_task: AgentTask
    ) -> None:
        """Should detect objections and include in response."""
        base_task.input_data["reply_text"] = "Дорого"
        base_task.input_data["emails_sent_count"] = 1

        agent = SalesAgent(llm_router=mock_llm_router, db=mock_db)
        agent.call_llm_json = AsyncMock(
            return_value={
                "subject": "Re: Test",
                "body": "Базовое размещение бесплатное...",
                "internal_notes": "Handling price objection",
            }
        )

        result = await agent.run(base_task)

        assert result.success is True
        assert result.data["analysis"]["objection_type"] == "price"
        assert result.data["strategy"]["stage"] == "objection"

    @pytest.mark.asyncio
    async def test_intent_classification(
        self, mock_llm_router: MagicMock, mock_db: MagicMock, base_task: AgentTask
    ) -> None:
        """Should classify reply intent."""
        base_task.input_data["reply_text"] = "Сколько это стоит?"
        base_task.input_data["emails_sent_count"] = 1

        agent = SalesAgent(llm_router=mock_llm_router, db=mock_db)
        agent.call_llm_json = AsyncMock(
            return_value={
                "subject": "Re: Test",
                "body": "Базовое размещение бесплатное...",
                "internal_notes": "Answering question",
            }
        )

        result = await agent.run(base_task)

        assert result.success is True
        assert result.data["analysis"]["reply_intent"] == "request_details"
        assert result.data["analysis"]["intent_confidence"] > 0

    @pytest.mark.asyncio
    async def test_handoff_recommendation(
        self, mock_llm_router: MagicMock, mock_db: MagicMock, base_task: AgentTask
    ) -> None:
        """Should recommend handoff for ready-to-call prospects."""
        base_task.input_data["reply_text"] = "Давайте созвонимся"
        base_task.input_data["emails_sent_count"] = 1

        agent = SalesAgent(llm_router=mock_llm_router, db=mock_db)
        agent.call_llm_json = AsyncMock(
            return_value={
                "subject": "Re: Test",
                "body": "Отлично! Наш менеджер Владислав свяжется с вами...",
                "internal_notes": "Handoff prep",
            }
        )

        result = await agent.run(base_task)

        assert result.success is True
        assert result.data["strategy"]["handoff_recommended"] is True
        assert result.data["strategy"]["stage"] == "handoff"

    @pytest.mark.asyncio
    async def test_quality_validation(
        self, mock_llm_router: MagicMock, mock_db: MagicMock, base_task: AgentTask
    ) -> None:
        """Should validate generated email quality."""
        agent = SalesAgent(llm_router=mock_llm_router, db=mock_db)
        agent.call_llm_json = AsyncMock(
            return_value={
                "subject": "Test Subject",
                "body": "Test body with Test Company mentioned. This is a test email with enough words to pass validation. Имеет смысл обсудить?",
                "internal_notes": "Test",
            }
        )

        result = await agent.run(base_task)

        assert result.success is True
        assert "quality" in result.data
        assert "passed" in result.data["quality"]

    @pytest.mark.asyncio
    async def test_llm_error_handling(
        self, mock_llm_router: MagicMock, mock_db: MagicMock, base_task: AgentTask
    ) -> None:
        """Should handle LLM errors gracefully."""
        agent = SalesAgent(llm_router=mock_llm_router, db=mock_db)
        agent.call_llm_json = AsyncMock(side_effect=Exception("LLM error"))

        result = await agent.run(base_task)

        assert result.success is False
        assert "LLM error" in result.error

    @pytest.mark.asyncio
    async def test_empty_llm_response(
        self, mock_llm_router: MagicMock, mock_db: MagicMock, base_task: AgentTask
    ) -> None:
        """Should handle empty LLM response."""
        agent = SalesAgent(llm_router=mock_llm_router, db=mock_db)
        agent.call_llm_json = AsyncMock(
            return_value={
                "subject": "",
                "body": "",
            }
        )

        result = await agent.run(base_task)

        assert result.success is False
        assert "empty" in result.error.lower()


class TestSalesAgentWithMockedStrategy:
    """Tests with mocked strategy service."""

    @pytest.fixture
    def mock_strategy_service(self) -> MagicMock:
        """Create mock strategy service."""
        service = MagicMock(spec=SalesStrategyService)
        service.determine_strategy.return_value = StrategyDecision(
            stage=ConversationStage.COLD_OUTREACH,
            strategy=ResponseStrategy.SOFT_CLOSE,
            cta_type=CTAType.TRY_FREE,
            tone="professional",
            max_response_words=150,
            should_include_proof=True,
            should_mention_free=True,
            handoff_recommended=False,
            reasoning="Test strategy",
        )
        return service

    @pytest.mark.asyncio
    async def test_uses_strategy_service(
        self, mock_strategy_service: MagicMock
    ) -> None:
        """Should use strategy service for decision."""
        router = MagicMock(spec=LLMRouter)
        db = MagicMock()

        agent = SalesAgent(
            llm_router=router,
            db=db,
            strategy_service=mock_strategy_service,
        )
        agent.call_llm_json = AsyncMock(
            return_value={
                "subject": "Test",
                "body": "Test body with company mentioned. Has enough words and CTA question?",
                "internal_notes": "Test",
            }
        )

        task = AgentTask(
            lead_id=uuid4(),
            agent_name="sales",
            task_type="test",
            input_data={
                "lead": {"id": str(uuid4()), "company_name": "Test", "source": "test"},
                "contact_name": "Test",
                "emails_sent_count": 0,
                "industry": "retail",
            },
        )

        await agent.run(task)

        mock_strategy_service.determine_strategy.assert_called_once()


class TestFactoryFunction:
    """Tests for create_sales_agent factory."""

    def test_creates_agent(self) -> None:
        """Factory should create valid agent."""
        router = MagicMock(spec=LLMRouter)
        db = MagicMock()

        agent = create_sales_agent(router, db)

        assert isinstance(agent, SalesAgent)
        assert agent.llm is router
        assert agent.db is db


class TestQualityValidation:
    """Tests for email quality validation in agent."""

    @pytest.fixture
    def agent_with_strict_gate(self) -> SalesAgent:
        """Create agent with strict quality gate."""
        router = MagicMock(spec=LLMRouter)
        db = MagicMock()
        return SalesAgent(llm_router=router, db=db)

    @pytest.mark.asyncio
    async def test_passes_good_email(
        self, agent_with_strict_gate: SalesAgent
    ) -> None:
        """Should pass well-formed emails."""
        agent_with_strict_gate.call_llm_json = AsyncMock(
            return_value={
                "subject": "Кассиры для Пятёрочки",
                "body": (
                    "Здравствуйте, Анна! Знаю, как сложно найти надёжных кассиров в сезон. "
                    "На Отклике работодатели находят их в среднем за 3 дня. "
                    "Пятёрочка уже разместила 200 вакансий через нас. "
                    "Мы специализируемся на линейном персонале — кассиры, продавцы, кладовщики. "
                    "Регистрация занимает 2 минуты, а первые отклики приходят в течение 48 часов. "
                    "Имеет смысл попробовать размещение?"
                ),
                "internal_notes": "Cold outreach",
            }
        )

        task = AgentTask(
            lead_id=uuid4(),
            agent_name="sales",
            task_type="test",
            input_data={
                "lead": {
                    "id": str(uuid4()),
                    "company_name": "Пятёрочка",
                    "source": "test",
                },
                "contact_name": "Анна",
                "emails_sent_count": 0,
                "industry": "retail",
            },
        )

        result = await agent_with_strict_gate.run(task)

        assert result.success is True
        assert result.data["quality"]["passed"] is True

    @pytest.mark.asyncio
    async def test_reports_quality_issues(
        self, agent_with_strict_gate: SalesAgent
    ) -> None:
        """Should report quality issues but still succeed."""
        # Email with spam words and missing CTA
        agent_with_strict_gate.call_llm_json = AsyncMock(
            return_value={
                "subject": "УНИКАЛЬНОЕ предложение для вас!",
                "body": "Это уникальное предложение. Гарантируем результат. Эксклюзив только для вас.",
                "internal_notes": "Test",
            }
        )

        task = AgentTask(
            lead_id=uuid4(),
            agent_name="sales",
            task_type="test",
            input_data={
                "lead": {
                    "id": str(uuid4()),
                    "company_name": "Test",
                    "source": "test",
                },
                "contact_name": "Test",
                "emails_sent_count": 0,
                "industry": "retail",
            },
        )

        result = await agent_with_strict_gate.run(task)

        # Should still succeed but report issues
        assert result.success is True
        assert result.data["quality"]["passed"] is False
        assert len(result.data["quality"]["issues"]) > 0


class TestIntegrationWithKnowledgeBase:
    """Integration tests with knowledge base."""

    @pytest.mark.asyncio
    async def test_uses_knowledge_base_for_detection(self) -> None:
        """Should use knowledge base for objection detection."""
        router = MagicMock(spec=LLMRouter)
        db = MagicMock()
        kb = SalesKnowledgeBase()

        agent = SalesAgent(llm_router=router, db=db, knowledge_base=kb)
        agent.call_llm_json = AsyncMock(
            return_value={
                "subject": "Re: Test",
                "body": "Test response about free tier for TestCo. Интересно?",
                "internal_notes": "Test",
            }
        )

        task = AgentTask(
            lead_id=uuid4(),
            agent_name="sales",
            task_type="test",
            input_data={
                "lead": {
                    "id": str(uuid4()),
                    "company_name": "TestCo",
                    "source": "test",
                },
                "contact_name": "Test",
                "reply_text": "Почему бесплатно? В чём подвох?",
                "emails_sent_count": 1,
                "industry": "retail",
            },
        )

        result = await agent.run(task)

        assert result.success is True
        assert result.data["analysis"]["objection_type"] == "why_free"
