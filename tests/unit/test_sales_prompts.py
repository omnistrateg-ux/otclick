"""Tests for sales prompts.

Тесты промптов для sales агента.
"""

import pytest

from app.email.sales_prompts import (
    OBJECTION_PROMPTS,
    SALES_AGENT_SYSTEM_PROMPT,
    STAGE_PROMPTS,
    UNSUBSCRIBE_RESPONSE,
    WRONG_PERSON_RESPONSE,
    build_sales_response_prompt,
)
from app.services.sales_knowledge_base import ConversationStage, ObjectionType


class TestSystemPrompt:
    """Tests for the main system prompt."""

    def test_system_prompt_contains_platform_info(self) -> None:
        """System prompt should contain platform information."""
        assert "Отклик" in SALES_AGENT_SYSTEM_PROMPT
        assert "бесплатн" in SALES_AGENT_SYSTEM_PROMPT.lower()
        assert "турбо" in SALES_AGENT_SYSTEM_PROMPT.lower()

    def test_system_prompt_contains_manager_contact(self) -> None:
        """System prompt should contain manager contact."""
        assert "Владислав Наков" in SALES_AGENT_SYSTEM_PROMPT
        assert "+7" in SALES_AGENT_SYSTEM_PROMPT
        assert "team@otclick-hr.ru" in SALES_AGENT_SYSTEM_PROMPT

    def test_system_prompt_contains_rules(self) -> None:
        """System prompt should contain writing rules."""
        assert "3-6 предложений" in SALES_AGENT_SYSTEM_PROMPT
        assert "emoji" in SALES_AGENT_SYSTEM_PROMPT.lower()
        assert "JSON" in SALES_AGENT_SYSTEM_PROMPT

    def test_system_prompt_contains_spam_words(self) -> None:
        """System prompt should list spam words to avoid."""
        spam_words = ["уникальный", "гарантируем", "эксклюзив"]
        for word in spam_words:
            assert word in SALES_AGENT_SYSTEM_PROMPT.lower()


class TestStagePrompts:
    """Tests for stage-specific prompts."""

    def test_all_stages_have_prompts(self) -> None:
        """All conversation stages should have prompts."""
        for stage in ConversationStage:
            assert stage in STAGE_PROMPTS, f"Missing prompt for {stage}"

    def test_cold_outreach_prompt_structure(self) -> None:
        """Cold outreach prompt should have correct structure."""
        prompt = STAGE_PROMPTS[ConversationStage.COLD_OUTREACH]

        assert "зацепк" in prompt.lower()
        assert "CTA" in prompt
        assert "150" in prompt  # max words

    def test_followup_prompt_shorter_than_cold(self) -> None:
        """Followup prompt should specify shorter length."""
        prompt = STAGE_PROMPTS[ConversationStage.FOLLOWUP]

        assert "60-80" in prompt or "80" in prompt
        assert "короче" in prompt.lower()

    def test_objection_handling_prompt(self) -> None:
        """Objection handling prompt should guide proper handling."""
        prompt = STAGE_PROMPTS[ConversationStage.OBJECTION_HANDLING]

        assert "признай" in prompt.lower() or "не спорь" in prompt.lower()
        assert "80-100" in prompt

    def test_closing_prompt_for_interested(self) -> None:
        """Closing prompt should push for action."""
        prompt = STAGE_PROMPTS[ConversationStage.CLOSING]

        assert "звонок" in prompt.lower() or "регистрац" in prompt.lower()

    def test_handoff_prompt_contains_manager_contact(self) -> None:
        """Handoff prompt should mention manager contact."""
        prompt = STAGE_PROMPTS[ConversationStage.HANDOFF_PREP]

        assert "Владислав Наков" in prompt
        assert "+7" in prompt


class TestObjectionPrompts:
    """Tests for objection-specific prompts."""

    def test_all_objections_have_prompts(self) -> None:
        """All objection types should have prompts."""
        for objection in ObjectionType:
            assert objection in OBJECTION_PROMPTS, f"Missing prompt for {objection}"

    def test_price_objection_prompt(self) -> None:
        """Price objection prompt should emphasize free tier."""
        prompt = OBJECTION_PROMPTS[ObjectionType.PRICE]

        assert "бесплатн" in prompt.lower()
        assert "турбо" in prompt.lower()

    def test_competitor_objection_prompt(self) -> None:
        """Competitor objection prompt should position as additional."""
        prompt = OBJECTION_PROMPTS[ObjectionType.COMPETITOR]

        assert "дополнительн" in prompt.lower()

    def test_trust_objection_prompt(self) -> None:
        """Trust objection prompt should mention proof points."""
        prompt = OBJECTION_PROMPTS[ObjectionType.TRUST]

        # Should mention either young company advantage or big clients
        has_young = "молод" in prompt.lower()
        has_clients = "клиент" in prompt.lower() or "компани" in prompt.lower()
        assert has_young or has_clients

    def test_why_free_objection_prompt(self) -> None:
        """Why free objection prompt should explain model."""
        prompt = OBJECTION_PROMPTS[ObjectionType.WHY_FREE]

        assert "турбо" in prompt.lower() or "зарабатыва" in prompt.lower()


class TestBuildPromptFunction:
    """Tests for build_sales_response_prompt function."""

    def test_basic_prompt_building(self) -> None:
        """Should build valid system and user prompts."""
        system, user = build_sales_response_prompt(
            stage=ConversationStage.COLD_OUTREACH,
            industry="retail",
            company_name="Test Company",
            contact_name="Test Person",
            city="Москва",
            reply_text=None,
            previous_emails=[],
            objection_type=None,
            should_include_proof=True,
            should_mention_free=True,
            max_words=150,
        )

        assert len(system) > 0
        assert len(user) > 0
        assert "Test Company" in user
        assert "Test Person" in user
        assert "retail" in user

    def test_prompt_with_reply_text(self) -> None:
        """Should include reply text in user prompt."""
        system, user = build_sales_response_prompt(
            stage=ConversationStage.AFTER_REPLY,
            industry="retail",
            company_name="Test Company",
            contact_name="Test Person",
            city=None,
            reply_text="Интересно, расскажите подробнее",
            previous_emails=[],
            objection_type=None,
            should_include_proof=True,
            should_mention_free=True,
            max_words=100,
        )

        assert "Интересно, расскажите подробнее" in user
        assert "Ответ клиента" in user

    def test_prompt_with_objection(self) -> None:
        """Should include objection handling in system prompt."""
        system, user = build_sales_response_prompt(
            stage=ConversationStage.OBJECTION_HANDLING,
            industry="retail",
            company_name="Test Company",
            contact_name="Test Person",
            city=None,
            reply_text="Дорого",
            previous_emails=[],
            objection_type=ObjectionType.PRICE,
            should_include_proof=True,
            should_mention_free=True,
            max_words=100,
        )

        # System should include objection prompt
        assert "бесплатн" in system.lower()
        # User should note detected objection
        assert "price" in user.lower() or "возражен" in user.lower()

    def test_prompt_with_previous_emails(self) -> None:
        """Should include previous emails in user prompt."""
        previous = [
            {"subject": "Кассиры для Пятёрочки", "body": "Здравствуйте, ..."},
            {"subject": "Re: Кассиры для Пятёрочки", "body": "Напоминаю..."},
        ]

        system, user = build_sales_response_prompt(
            stage=ConversationStage.FOLLOWUP,
            industry="retail",
            company_name="Пятёрочка",
            contact_name="Анна",
            city="Москва",
            reply_text=None,
            previous_emails=previous,
            objection_type=None,
            should_include_proof=True,
            should_mention_free=True,
            max_words=80,
        )

        assert "Кассиры" in user
        assert "Предыдущие письма" in user

    def test_prompt_limits_previous_emails(self) -> None:
        """Should limit to last 3 previous emails."""
        previous = [
            {"subject": f"Email {i}", "body": f"Body {i}"}
            for i in range(5)
        ]

        _, user = build_sales_response_prompt(
            stage=ConversationStage.FOLLOWUP,
            industry="retail",
            company_name="Test",
            contact_name="Test",
            city=None,
            reply_text=None,
            previous_emails=previous,
            objection_type=None,
            should_include_proof=True,
            should_mention_free=True,
            max_words=80,
        )

        # Should include only last 3
        assert "Email 2" in user
        assert "Email 3" in user
        assert "Email 4" in user
        assert "Email 0" not in user
        assert "Email 1" not in user

    def test_prompt_includes_instructions(self) -> None:
        """Should include proof and free instructions when requested."""
        _, user_with = build_sales_response_prompt(
            stage=ConversationStage.COLD_OUTREACH,
            industry="retail",
            company_name="Test",
            contact_name="Test",
            city=None,
            reply_text=None,
            previous_emails=[],
            objection_type=None,
            should_include_proof=True,
            should_mention_free=True,
            max_words=150,
        )

        assert "proof" in user_with.lower()
        assert "бесплатн" in user_with.lower()

    def test_prompt_includes_max_words(self) -> None:
        """Should include max words constraint."""
        _, user = build_sales_response_prompt(
            stage=ConversationStage.FOLLOWUP,
            industry="retail",
            company_name="Test",
            contact_name="Test",
            city=None,
            reply_text=None,
            previous_emails=[],
            objection_type=None,
            should_include_proof=False,
            should_mention_free=False,
            max_words=80,
        )

        assert "80" in user

    def test_prompt_industry_insertion(self) -> None:
        """Should insert industry into stage prompt."""
        system, _ = build_sales_response_prompt(
            stage=ConversationStage.COLD_OUTREACH,
            industry="horeca",
            company_name="Test",
            contact_name="Test",
            city=None,
            reply_text=None,
            previous_emails=[],
            objection_type=None,
            should_include_proof=True,
            should_mention_free=True,
            max_words=150,
        )

        assert "horeca" in system.lower()


class TestTemplateResponses:
    """Tests for template responses."""

    def test_unsubscribe_response_structure(self) -> None:
        """Unsubscribe response should have correct structure."""
        assert "subject" in UNSUBSCRIBE_RESPONSE
        assert "body" in UNSUBSCRIBE_RESPONSE
        assert len(UNSUBSCRIBE_RESPONSE["body"]) > 0

    def test_unsubscribe_response_tone(self) -> None:
        """Unsubscribe response should be respectful."""
        body = UNSUBSCRIBE_RESPONSE["body"]

        assert "благодар" in body.lower() or "спасибо" in body.lower()
        assert "удалил" in body.lower() or "убрал" in body.lower()

    def test_wrong_person_response_structure(self) -> None:
        """Wrong person response should have correct structure."""
        assert "subject" in WRONG_PERSON_RESPONSE
        assert "body" in WRONG_PERSON_RESPONSE
        assert len(WRONG_PERSON_RESPONSE["body"]) > 0

    def test_wrong_person_response_apologetic(self) -> None:
        """Wrong person response should be apologetic."""
        body = WRONG_PERSON_RESPONSE["body"]

        assert "извин" in body.lower()


class TestPromptQuality:
    """Tests for prompt quality and consistency."""

    def test_no_duplicate_instructions(self) -> None:
        """Prompts should not have excessive repetition."""
        system, user = build_sales_response_prompt(
            stage=ConversationStage.COLD_OUTREACH,
            industry="retail",
            company_name="Test",
            contact_name="Test",
            city=None,
            reply_text=None,
            previous_emails=[],
            objection_type=None,
            should_include_proof=True,
            should_mention_free=True,
            max_words=150,
        )

        # System prompt shouldn't repeat rules excessively
        # Count occurrences of key phrases
        full_prompt = system + user
        json_count = full_prompt.lower().count("json")
        # Should mention JSON but not excessively
        assert json_count <= 5

    def test_stage_prompts_have_word_limits(self) -> None:
        """Each stage prompt should specify word limits."""
        for stage, prompt in STAGE_PROMPTS.items():
            has_limit = any(
                word in prompt
                for word in ["слов", "предложени", "60", "80", "100", "150"]
            )
            assert has_limit, f"Stage {stage} missing word limit"
