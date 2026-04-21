"""Tests for SalesKnowledgeBase.

Тесты базы знаний для sales агента.
"""

import pytest

from app.services.sales_knowledge_base import (
    ConversationStage,
    DEFAULT_INDUSTRY_INSIGHTS,
    DEFAULT_MANAGER_CONTACT,
    DEFAULT_OBJECTION_HANDLERS,
    IndustryInsight,
    ObjectionHandler,
    ObjectionType,
    SalesContact,
    SalesKnowledgeBase,
    sales_knowledge_base,
)


class TestObjectionDetection:
    """Tests for objection detection."""

    @pytest.fixture
    def kb(self) -> SalesKnowledgeBase:
        """Create knowledge base instance."""
        return SalesKnowledgeBase()

    def test_detect_price_objection(self, kb: SalesKnowledgeBase) -> None:
        """Should detect price objections."""
        texts = [
            "Это дорого для нас",
            "Нет бюджета на это",
            "Слишком дорого",
            "Бюджет не позволяет",
        ]

        for text in texts:
            result = kb.detect_objection(text)
            assert result == ObjectionType.PRICE, f"Failed for: {text}"

    def test_detect_competitor_objection(self, kb: SalesKnowledgeBase) -> None:
        """Should detect competitor objections."""
        texts = [
            "Мы уже работаем с hh.ru",
            "Есть hh, этого достаточно",
            "Используем HeadHunter",
            "Уже есть площадка для размещения",
        ]

        for text in texts:
            result = kb.detect_objection(text)
            assert result == ObjectionType.COMPETITOR, f"Failed for: {text}"

    def test_detect_timing_objection(self, kb: SalesKnowledgeBase) -> None:
        """Should detect timing objections."""
        texts = [
            "Не сейчас, может позже",
            "Через месяц вернёмся",
            "После нового года обсудим",
            "Сейчас не актуально",
        ]

        for text in texts:
            result = kb.detect_objection(text)
            assert result == ObjectionType.TIMING, f"Failed for: {text}"

    def test_detect_trust_objection(self, kb: SalesKnowledgeBase) -> None:
        """Should detect trust objections."""
        texts = [
            "Не знаем вас",
            "Вы новые на рынке",
            "Первый раз слышу о вас",
            "Никогда не слышал об Отклике",
        ]

        for text in texts:
            result = kb.detect_objection(text)
            assert result == ObjectionType.TRUST, f"Failed for: {text}"

    def test_detect_why_free_objection(self, kb: SalesKnowledgeBase) -> None:
        """Should detect 'why free' objections."""
        texts = [
            "Почему бесплатно?",
            "В чём подвох?",
            "Где подвох?",
            "Ничего не бывает бесплатно",
            "За счёт чего это бесплатно?",
        ]

        for text in texts:
            result = kb.detect_objection(text)
            assert result == ObjectionType.WHY_FREE, f"Failed for: {text}"

    def test_detect_candidates_objection(self, kb: SalesKnowledgeBase) -> None:
        """Should detect candidates-related objections."""
        texts = [
            "Много кандидатов у вас?",
            "Есть соискатели?",
            "Будут отклики?",
            "Какой охват?",
        ]

        for text in texts:
            result = kb.detect_objection(text)
            assert result == ObjectionType.CANDIDATES, f"Failed for: {text}"

    def test_detect_no_need_objection(self, kb: SalesKnowledgeBase) -> None:
        """Should detect 'no need' objections."""
        texts = [
            "Сами справляемся с наймом",
            "Нам не нужно это",
            "Справимся сами без вас",
            "Знакомые приводят сотрудников",
            "Сарафанное радио работает",
        ]

        for text in texts:
            result = kb.detect_objection(text)
            assert result == ObjectionType.NO_NEED, f"Failed for: {text}"

    def test_no_objection_detected(self, kb: SalesKnowledgeBase) -> None:
        """Should return None when no objection."""
        texts = [
            "Спасибо за информацию",
            "Интересно, расскажите подробнее",
            "Когда можно созвониться?",
            "Хорошо, попробуем",
        ]

        for text in texts:
            result = kb.detect_objection(text)
            assert result is None, f"False positive for: {text}"

    def test_case_insensitive_detection(self, kb: SalesKnowledgeBase) -> None:
        """Detection should be case-insensitive."""
        texts = [
            "ДОРОГО",
            "Дорого",
            "дорого",
        ]

        for text in texts:
            result = kb.detect_objection(text)
            assert result == ObjectionType.PRICE


class TestObjectionHandlers:
    """Tests for objection handlers."""

    @pytest.fixture
    def kb(self) -> SalesKnowledgeBase:
        """Create knowledge base instance."""
        return SalesKnowledgeBase()

    def test_all_objection_types_have_handlers(self, kb: SalesKnowledgeBase) -> None:
        """All objection types should have handlers."""
        for objection_type in ObjectionType:
            handler = kb.get_objection_handler(objection_type)
            assert handler is not None
            assert isinstance(handler, ObjectionHandler)

    def test_handler_has_required_fields(self, kb: SalesKnowledgeBase) -> None:
        """Handlers should have all required fields."""
        handler = kb.get_objection_handler(ObjectionType.PRICE)

        assert handler.objection_type == ObjectionType.PRICE
        assert len(handler.trigger_phrases) > 0
        assert len(handler.response_template) > 0
        assert len(handler.tone) > 0
        assert len(handler.follow_up_cta) > 0

    def test_handler_response_contains_key_points(self, kb: SalesKnowledgeBase) -> None:
        """Price handler should mention free tier."""
        handler = kb.get_objection_handler(ObjectionType.PRICE)
        assert "бесплатн" in handler.response_template.lower()

    def test_competitor_handler_mentions_additional_channel(
        self, kb: SalesKnowledgeBase
    ) -> None:
        """Competitor handler should position as additional channel."""
        handler = kb.get_objection_handler(ObjectionType.COMPETITOR)
        assert "дополнительн" in handler.response_template.lower()


class TestIndustryInsights:
    """Tests for industry insights."""

    @pytest.fixture
    def kb(self) -> SalesKnowledgeBase:
        """Create knowledge base instance."""
        return SalesKnowledgeBase()

    def test_get_existing_industry(self, kb: SalesKnowledgeBase) -> None:
        """Should return insight for existing industry."""
        insight = kb.get_industry_insight("retail")

        assert insight is not None
        assert insight.industry == "retail"
        assert len(insight.pain_points) > 0
        assert len(insight.typical_roles) > 0
        assert len(insight.value_angles) > 0
        assert len(insight.proof_points) > 0

    def test_get_nonexistent_industry(self, kb: SalesKnowledgeBase) -> None:
        """Should return None for nonexistent industry."""
        insight = kb.get_industry_insight("unknown_industry")
        assert insight is None

    def test_case_insensitive_industry(self, kb: SalesKnowledgeBase) -> None:
        """Industry lookup should be case-insensitive."""
        insight1 = kb.get_industry_insight("RETAIL")
        insight2 = kb.get_industry_insight("Retail")
        insight3 = kb.get_industry_insight("retail")

        assert insight1 is not None
        assert insight2 is not None
        assert insight3 is not None

    def test_all_default_industries_exist(self, kb: SalesKnowledgeBase) -> None:
        """All default industries should be accessible."""
        expected_industries = ["retail", "horeca", "logistics", "warehouse", "manufacturing"]

        for industry in expected_industries:
            insight = kb.get_industry_insight(industry)
            assert insight is not None, f"Missing industry: {industry}"

    def test_get_all_industries(self, kb: SalesKnowledgeBase) -> None:
        """Should return list of all industries."""
        industries = kb.get_all_industries()

        assert len(industries) >= 5
        assert "retail" in industries
        assert "horeca" in industries


class TestManagerContact:
    """Tests for manager contact."""

    @pytest.fixture
    def kb(self) -> SalesKnowledgeBase:
        """Create knowledge base instance."""
        return SalesKnowledgeBase()

    def test_get_manager_contact(self, kb: SalesKnowledgeBase) -> None:
        """Should return manager contact."""
        contact = kb.get_manager_contact()

        assert contact is not None
        assert isinstance(contact, SalesContact)
        assert len(contact.name) > 0
        assert len(contact.phone) > 0
        assert len(contact.email) > 0

    def test_default_manager_contact(self) -> None:
        """Default manager should be Vladislav Nakov."""
        assert DEFAULT_MANAGER_CONTACT.name == "Владислав Наков"
        assert "964" in DEFAULT_MANAGER_CONTACT.phone
        assert "@" in DEFAULT_MANAGER_CONTACT.email


class TestSearchObjection:
    """Tests for objection search."""

    @pytest.fixture
    def kb(self) -> SalesKnowledgeBase:
        """Create knowledge base instance."""
        return SalesKnowledgeBase()

    def test_search_by_keyword(self, kb: SalesKnowledgeBase) -> None:
        """Should find objections by keyword."""
        matches = kb.search_objection_by_keyword("дорого")
        assert ObjectionType.PRICE in matches

    def test_search_multiple_matches(self, kb: SalesKnowledgeBase) -> None:
        """Should find multiple matching objections."""
        matches = kb.search_objection_by_keyword("не")
        assert len(matches) >= 1  # "не сейчас", "не знаем", etc.

    def test_search_no_matches(self, kb: SalesKnowledgeBase) -> None:
        """Should return empty list for no matches."""
        matches = kb.search_objection_by_keyword("xyzzywhatever")
        assert matches == []


class TestCustomKnowledgeBase:
    """Tests for custom knowledge base configuration."""

    def test_custom_objection_handlers(self) -> None:
        """Should accept custom objection handlers."""
        custom_handler = ObjectionHandler(
            objection_type=ObjectionType.PRICE,
            trigger_phrases=["custom trigger"],
            response_template="Custom response",
            tone="custom",
            follow_up_cta="Custom CTA",
        )

        kb = SalesKnowledgeBase(
            objection_handlers={ObjectionType.PRICE: custom_handler}
        )

        handler = kb.get_objection_handler(ObjectionType.PRICE)
        assert handler.response_template == "Custom response"

    def test_custom_industry_insights(self) -> None:
        """Should accept custom industry insights."""
        custom_insight = IndustryInsight(
            industry="custom_industry",
            pain_points=["Custom pain"],
            typical_roles=["Custom role"],
            value_angles=["Custom angle"],
            proof_points=["Custom proof"],
        )

        kb = SalesKnowledgeBase(
            industry_insights={"custom": custom_insight}
        )

        insight = kb.get_industry_insight("custom")
        assert insight is not None
        assert insight.industry == "custom_industry"

    def test_custom_manager_contact(self) -> None:
        """Should accept custom manager contact."""
        custom_contact = SalesContact(
            name="Custom Manager",
            phone="+1234567890",
            email="custom@test.com",
        )

        kb = SalesKnowledgeBase(manager_contact=custom_contact)

        contact = kb.get_manager_contact()
        assert contact.name == "Custom Manager"


class TestSingletonInstance:
    """Tests for singleton instance."""

    def test_singleton_exists(self) -> None:
        """Singleton instance should exist."""
        assert sales_knowledge_base is not None
        assert isinstance(sales_knowledge_base, SalesKnowledgeBase)

    def test_singleton_works(self) -> None:
        """Singleton should be fully functional."""
        result = sales_knowledge_base.detect_objection("дорого")
        assert result == ObjectionType.PRICE


class TestConversationStageEnum:
    """Tests for ConversationStage enum."""

    def test_all_stages_defined(self) -> None:
        """All expected stages should be defined."""
        expected = [
            "cold_outreach",
            "followup",
            "after_reply",
            "objection",
            "question",
            "nurturing",
            "closing",
            "handoff",
        ]

        for stage_value in expected:
            stage = ConversationStage(stage_value)
            assert stage is not None
