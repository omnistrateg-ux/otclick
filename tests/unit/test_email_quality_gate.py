"""Tests for Email Quality Gate.

Тесты валидации писем из ARCHITECTURE.md раздел 7.4.
"""

import pytest

from app.email.quality_gate import QualityGate
from app.models.domain import EmployerLead
from app.models.enums import EmailType, LeadStatus


@pytest.fixture
def quality_gate() -> QualityGate:
    """Create quality gate instance."""
    return QualityGate()


@pytest.fixture
def sample_lead() -> EmployerLead:
    """Create sample lead for testing."""
    return EmployerLead(
        company_name="Пятёрочка",
        source="hh.ru",
        city="Москва",
        status=LeadStatus.SCORED,
    )


class TestQualityGateValidation:
    """Tests for quality gate validation."""

    def test_valid_first_touch_email_passes(
        self,
        quality_gate: QualityGate,
        sample_lead: EmployerLead,
    ) -> None:
        """Valid first touch email should pass quality gate."""
        subject = "Кассиры в Москве за 48ч — актуально?"
        body = """
        Добрый день.

        Видел, что Пятёрочка ищет кассиров в Москве.
        Знаю, что в ритейле главная боль — скорость закрытия и текучка.

        Мы в Отклике закрываем линейные позиции за 48 часов
        с подтверждённой явкой 94%. Работаем с сетями от 50 точек.

        Имеет смысл обсудить?
        """

        result = quality_gate.validate(
            subject=subject,
            body=body,
            email_type=EmailType.FIRST_TOUCH,
            lead=sample_lead,
        )

        assert result.passed is True
        assert len(result.issues) == 0

    def test_spam_word_detected(
        self,
        quality_gate: QualityGate,
        sample_lead: EmployerLead,
    ) -> None:
        """Email with spam words should fail."""
        subject = "Уникальное предложение для Пятёрочки!"
        body = """
        Мы рады предложить вам уникальное решение.
        Гарантируем лучший результат на рынке.
        Не пропустите эксклюзивное предложение!
        """

        result = quality_gate.validate(
            subject=subject,
            body=body,
            email_type=EmailType.FIRST_TOUCH,
            lead=sample_lead,
        )

        assert result.passed is False
        assert any("spam_word" in issue for issue in result.issues)

    def test_too_long_body_detected(
        self,
        quality_gate: QualityGate,
        sample_lead: EmployerLead,
    ) -> None:
        """Email exceeding word limit should fail."""
        subject = "Кассиры для Пятёрочки"
        body = " ".join(["слово"] * 200)  # 200 words, exceeds 150 limit

        result = quality_gate.validate(
            subject=subject,
            body=body,
            email_type=EmailType.FIRST_TOUCH,
            lead=sample_lead,
        )

        assert result.passed is False
        assert any("too_long" in issue for issue in result.issues)

    def test_too_short_body_detected(
        self,
        quality_gate: QualityGate,
        sample_lead: EmployerLead,
    ) -> None:
        """Email with too few words should fail."""
        subject = "Кассиры для Пятёрочки"
        body = "Привет. Актуально?"  # Too short

        result = quality_gate.validate(
            subject=subject,
            body=body,
            email_type=EmailType.FIRST_TOUCH,
            lead=sample_lead,
        )

        assert result.passed is False
        assert any("too_short" in issue for issue in result.issues)

    def test_missing_cta_detected(
        self,
        quality_gate: QualityGate,
        sample_lead: EmployerLead,
    ) -> None:
        """Email without CTA should fail."""
        subject = "Кассиры для Пятёрочки"
        body = """
        Добрый день.

        Видел, что Пятёрочка ищет кассиров в Москве.
        Мы в Отклике закрываем линейные позиции за 48 часов.
        Работаем с сетями от 50 точек.
        Явка исполнителей 94 процента.
        """

        result = quality_gate.validate(
            subject=subject,
            body=body,
            email_type=EmailType.FIRST_TOUCH,
            lead=sample_lead,
        )

        assert result.passed is False
        assert "missing_cta" in result.issues

    def test_no_company_mention_detected(
        self,
        quality_gate: QualityGate,
        sample_lead: EmployerLead,
    ) -> None:
        """Email without company mention should fail."""
        subject = "Кассиры за 48ч"
        body = """
        Добрый день.

        Видел, что вы ищете кассиров в Москве.
        Мы закрываем линейные позиции за 48 часов.

        Актуально для вас?
        """

        result = quality_gate.validate(
            subject=subject,
            body=body,
            email_type=EmailType.FIRST_TOUCH,
            lead=sample_lead,
        )

        assert result.passed is False
        assert "no_company_mention" in result.issues

    def test_subject_too_long_detected(
        self,
        quality_gate: QualityGate,
        sample_lead: EmployerLead,
    ) -> None:
        """Subject exceeding 60 characters should fail."""
        subject = "Уникальное предложение по найму персонала для компании Пятёрочка в городе Москва"
        body = """
        Добрый день.

        Видел, что Пятёрочка ищет кассиров в Москве.
        Мы закрываем позиции за 48 часов.

        Актуально?
        """

        result = quality_gate.validate(
            subject=subject,
            body=body,
            email_type=EmailType.FIRST_TOUCH,
            lead=sample_lead,
        )

        assert result.passed is False
        assert any("subject_too_long" in issue for issue in result.issues)

    def test_subject_exclamation_detected(
        self,
        quality_gate: QualityGate,
        sample_lead: EmployerLead,
    ) -> None:
        """Subject ending with exclamation should fail."""
        subject = "Кассиры для Пятёрочки!"
        body = """
        Добрый день.

        Видел, что Пятёрочка ищет кассиров в Москве.
        Мы закрываем позиции за 48 часов.

        Актуально?
        """

        result = quality_gate.validate(
            subject=subject,
            body=body,
            email_type=EmailType.FIRST_TOUCH,
            lead=sample_lead,
        )

        assert result.passed is False
        assert "subject_exclamation" in result.issues

    def test_links_in_first_touch_detected(
        self,
        quality_gate: QualityGate,
        sample_lead: EmployerLead,
    ) -> None:
        """Links in first touch email should fail."""
        subject = "Кассиры для Пятёрочки"
        body = """
        Добрый день.

        Видел, что Пятёрочка ищет кассиров в Москве.
        Посмотрите наш сайт: https://otclick.ru

        Актуально?
        """

        result = quality_gate.validate(
            subject=subject,
            body=body,
            email_type=EmailType.FIRST_TOUCH,
            lead=sample_lead,
        )

        assert result.passed is False
        assert "links_in_first_touch" in result.issues

    def test_followup_allows_fewer_words(
        self,
        quality_gate: QualityGate,
        sample_lead: EmployerLead,
    ) -> None:
        """Follow-up emails have lower word limit."""
        subject = "Re: Кассиры для Пятёрочка"
        body = """
        Здравствуйте.

        Писал вам на прошлой неделе по поводу кассиров для Пятёрочка.
        Наши клиенты экономят 30% на подборе линейного персонала.
        Работаем с сетями любого масштаба и закрываем позиции быстро.

        Актуально для вас сейчас?
        """

        result = quality_gate.validate(
            subject=subject,
            body=body,
            email_type=EmailType.FOLLOWUP_1,
            lead=sample_lead,
        )

        assert result.passed is True

    def test_emoji_detected(
        self,
        quality_gate: QualityGate,
        sample_lead: EmployerLead,
    ) -> None:
        """Emoji in email should fail."""
        subject = "Кассиры для Пятёрочки 🎉"
        body = """
        Добрый день! 👋

        Видел, что Пятёрочка ищет кассиров.

        Актуально? 🤔
        """

        result = quality_gate.validate(
            subject=subject,
            body=body,
            email_type=EmailType.FIRST_TOUCH,
            lead=sample_lead,
        )

        assert result.passed is False
        assert "contains_emoji" in result.issues


class TestQualityGateHelpers:
    """Tests for quality gate helper methods."""

    def test_has_cta_with_question_mark(
        self,
        quality_gate: QualityGate,
    ) -> None:
        """Question mark should indicate CTA."""
        assert quality_gate._has_cta("Актуально для вас?") is True

    def test_has_cta_with_signal_word(
        self,
        quality_gate: QualityGate,
    ) -> None:
        """Signal words should indicate CTA."""
        assert quality_gate._has_cta("Имеет смысл обсудить") is True
        assert quality_gate._has_cta("Готовы созвониться") is True

    def test_no_cta_in_plain_text(
        self,
        quality_gate: QualityGate,
    ) -> None:
        """Plain text without signals should not have CTA."""
        assert quality_gate._has_cta("Мы закрываем позиции за 48 часов.") is False

    def test_company_mention_exact_match(
        self,
        quality_gate: QualityGate,
    ) -> None:
        """Exact company name should be detected."""
        assert quality_gate._has_company_mention(
            "Видел, что Пятёрочка ищет кассиров",
            "Пятёрочка",
        ) is True

    def test_company_mention_first_word(
        self,
        quality_gate: QualityGate,
    ) -> None:
        """First word of company should be detected."""
        assert quality_gate._has_company_mention(
            "Видел, что Пятёрочка ищет кассиров",
            "Пятёрочка ООО",
        ) is True

    def test_has_emoji(
        self,
        quality_gate: QualityGate,
    ) -> None:
        """Emoji detection should work."""
        assert quality_gate._has_emoji("Hello 🎉") is True
        assert quality_gate._has_emoji("Hello!") is False

    def test_has_links(
        self,
        quality_gate: QualityGate,
    ) -> None:
        """Link detection should work."""
        assert quality_gate._has_links("Visit https://example.com") is True
        assert quality_gate._has_links("Visit www.example.com") is True
        assert quality_gate._has_links("Visit our office") is False


class TestQualityGateBatch:
    """Tests for batch validation."""

    def test_validate_batch(
        self,
        quality_gate: QualityGate,
        sample_lead: EmployerLead,
    ) -> None:
        """Batch validation should work."""
        emails = [
            {"subject": "Тема 1", "body": "Пятёрочка текст текст текст текст текст текст текст текст текст текст актуально?"},
            {"subject": "Тема 2 спам уникальный", "body": "Пятёрочка короткий текст актуально?"},
        ]

        results = quality_gate.validate_batch(
            emails=emails,
            email_type=EmailType.FIRST_TOUCH,
            lead=sample_lead,
        )

        assert len(results) == 2
        # First should fail (too short)
        # Second should fail (spam word)
        assert any(r.passed is False for r in results)
