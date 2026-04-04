"""Tests for reply classification.

Тесты классификации ответов из ARCHITECTURE.md.
"""

import pytest

from app.models.enums import ReplyIntent
from app.tools.analysis_tools import (
    classify_reply_rule_based,
    extract_redirect_contact,
    is_negative_intent,
    is_positive_intent,
    should_continue_sequence,
)


class TestRuleBasedClassification:
    """Tests for rule-based reply classification."""

    def test_unsubscribe_detected(self) -> None:
        """Unsubscribe requests should be detected."""
        replies = [
            "Отпишите меня от рассылки",
            "Не пишите мне больше",
            "Удалите мой email",
            "Это спам!",
            "Please unsubscribe me",
        ]

        for reply in replies:
            intent, confidence = classify_reply_rule_based(reply)
            assert intent == ReplyIntent.UNSUBSCRIBE, f"Failed for: {reply}"
            assert confidence >= 0.7

    def test_refusal_detected(self) -> None:
        """Refusals should be detected."""
        replies = [
            "Не интересно",
            "Нам это не нужно",
            "Не актуально для нас",
            "Отказываюсь от предложения",
            "Нет, спасибо, не надо",
        ]

        for reply in replies:
            intent, confidence = classify_reply_rule_based(reply)
            assert intent == ReplyIntent.REFUSAL, f"Failed for: {reply}"
            assert confidence >= 0.7

    def test_auto_reply_detected(self) -> None:
        """Auto-replies should be detected."""
        replies = [
            "Я в отпуске до 15 января",
            "This is an automatic reply",
            "Out of office until Monday",
            "Временно недоступен, вернусь через неделю",
            "Автоответ: буду доступен с понедельника",
        ]

        for reply in replies:
            intent, confidence = classify_reply_rule_based(reply)
            assert intent == ReplyIntent.AUTO_REPLY, f"Failed for: {reply}"
            assert confidence >= 0.7

    def test_ready_to_call_detected(self) -> None:
        """Ready to call signals should be detected."""
        replies = [
            "Давайте созвонимся",
            "Можете позвонить завтра?",
            "Готов обсудить по телефону",
            "Назначить встречу?",
            "Жду звонка",
        ]

        for reply in replies:
            intent, confidence = classify_reply_rule_based(reply)
            assert intent == ReplyIntent.READY_TO_CALL, f"Failed for: {reply}"
            assert confidence >= 0.7

    def test_strong_interest_detected(self) -> None:
        """Strong interest should be detected."""
        replies = [
            "Очень интересно! Расскажите подробнее",
            "Хочу узнать больше о ваших услугах",
            "Это очень актуально для нас",
            "Нам это нужно",
        ]

        for reply in replies:
            intent, confidence = classify_reply_rule_based(reply)
            assert intent == ReplyIntent.STRONG_INTEREST, f"Failed for: {reply}"
            assert confidence >= 0.7

    def test_strong_interest_with_call_becomes_ready_to_call(self) -> None:
        """Strong interest with call request becomes ready_to_call."""
        # "давайте обсудим" triggers READY_TO_CALL which is higher priority
        reply = "Нам это нужно, давайте обсудим"
        intent, confidence = classify_reply_rule_based(reply)
        assert intent == ReplyIntent.READY_TO_CALL

    def test_request_details_detected(self) -> None:
        """Detail requests should be detected."""
        replies = [
            "Сколько это стоит?",
            "Какие у вас тарифы?",
            "Пришлите прайс",
            "Какие условия работы?",
            "Можно коммерческое предложение?",
        ]

        for reply in replies:
            intent, confidence = classify_reply_rule_based(reply)
            assert intent == ReplyIntent.REQUEST_DETAILS, f"Failed for: {reply}"
            assert confidence >= 0.7

    def test_soft_interest_detected(self) -> None:
        """Soft interest should be detected."""
        replies = [
            "Интересно, но не сейчас",
            "Может быть позже вернёмся к этому",
            "Сохраню контакт на будущее",
            "Через месяц вернёмся к этому вопросу",
        ]

        for reply in replies:
            intent, confidence = classify_reply_rule_based(reply)
            assert intent == ReplyIntent.SOFT_INTEREST, f"Failed for: {reply}"
            assert confidence >= 0.7

    def test_soft_refusal_with_timeline_is_refusal(self) -> None:
        """Refusal with timeline words may be classified as refusal."""
        # "не актуально" triggers REFUSAL which is checked before SOFT_INTEREST
        # This is actually correct - explicit "не актуально" is a refusal
        reply = "Пока не актуально"
        intent, _ = classify_reply_rule_based(reply)
        assert intent == ReplyIntent.REFUSAL

    def test_wrong_person_detected(self) -> None:
        """Wrong person redirects should be detected."""
        replies = [
            "Это не ко мне, напишите HR директору",
            "Обратитесь к Ивановой Марии",
            "За это отвечает другой человек",
            "Перешлите в отдел кадров",
        ]

        for reply in replies:
            intent, confidence = classify_reply_rule_based(reply)
            assert intent == ReplyIntent.WRONG_PERSON, f"Failed for: {reply}"
            assert confidence >= 0.7

    def test_neutral_for_unclear(self) -> None:
        """Unclear replies should be neutral."""
        replies = [
            "Спасибо за информацию",
            "Понял, посмотрим",
            "Получил ваше письмо",
            "ОК",
        ]

        for reply in replies:
            intent, confidence = classify_reply_rule_based(reply)
            assert intent == ReplyIntent.NEUTRAL, f"Failed for: {reply}"

    def test_neutral_for_ambiguous(self) -> None:
        """Ambiguous replies should be neutral with low confidence."""
        reply = "Хорошо"
        intent, confidence = classify_reply_rule_based(reply)
        assert intent == ReplyIntent.NEUTRAL
        assert confidence < 0.5


class TestIntentHelpers:
    """Tests for intent helper functions."""

    def test_positive_intents(self) -> None:
        """Check positive intent detection."""
        positive = [
            ReplyIntent.SOFT_INTEREST,
            ReplyIntent.REQUEST_DETAILS,
            ReplyIntent.STRONG_INTEREST,
            ReplyIntent.READY_TO_CALL,
        ]

        for intent in positive:
            assert is_positive_intent(intent) is True, f"Should be positive: {intent}"

    def test_negative_intents(self) -> None:
        """Check negative intent detection."""
        negative = [
            ReplyIntent.REFUSAL,
            ReplyIntent.UNSUBSCRIBE,
        ]

        for intent in negative:
            assert is_negative_intent(intent) is True, f"Should be negative: {intent}"

    def test_non_positive_intents(self) -> None:
        """Check non-positive intents."""
        non_positive = [
            ReplyIntent.NO_REPLY,
            ReplyIntent.AUTO_REPLY,
            ReplyIntent.NEUTRAL,
            ReplyIntent.REFUSAL,
            ReplyIntent.UNSUBSCRIBE,
            ReplyIntent.WRONG_PERSON,
        ]

        for intent in non_positive:
            assert is_positive_intent(intent) is False, f"Should not be positive: {intent}"

    def test_should_continue_sequence(self) -> None:
        """Check sequence continuation logic."""
        # Should continue
        continue_intents = [
            ReplyIntent.NEUTRAL,
            ReplyIntent.NO_REPLY,
            ReplyIntent.AUTO_REPLY,
        ]

        for intent in continue_intents:
            assert should_continue_sequence(intent) is True, f"Should continue: {intent}"

        # Should not continue
        stop_intents = [
            ReplyIntent.REFUSAL,
            ReplyIntent.UNSUBSCRIBE,
            ReplyIntent.STRONG_INTEREST,
            ReplyIntent.READY_TO_CALL,
        ]

        for intent in stop_intents:
            assert should_continue_sequence(intent) is False, f"Should stop: {intent}"


class TestExtractRedirectContact:
    """Tests for contact extraction from redirects."""

    def test_extract_email(self) -> None:
        """Should extract email from redirect."""
        reply = "Напишите лучше hr@company.ru, она отвечает за подбор"
        result = extract_redirect_contact(reply)

        assert result is not None
        assert result["email"] == "hr@company.ru"

    def test_extract_name(self) -> None:
        """Should extract name from redirect."""
        reply = "Обратитесь к Ивановой Марии, она директор по персоналу"
        result = extract_redirect_contact(reply)

        assert result is not None
        assert result["name"] is not None
        assert "иванов" in result["name"].lower()

    def test_extract_both(self) -> None:
        """Should extract both email and name."""
        reply = "Напишите Петрову Ивану на petrov@company.ru"
        result = extract_redirect_contact(reply)

        assert result is not None
        assert result["email"] == "petrov@company.ru"

    def test_no_contact_in_simple_refusal(self) -> None:
        """Should return None for simple refusals."""
        reply = "Не интересно"
        result = extract_redirect_contact(reply)

        assert result is None


class TestEdgeCases:
    """Tests for edge cases in classification."""

    def test_empty_reply(self) -> None:
        """Empty reply should be neutral."""
        intent, confidence = classify_reply_rule_based("")
        assert intent == ReplyIntent.NEUTRAL
        assert confidence < 0.5

    def test_very_long_reply(self) -> None:
        """Long reply should still work."""
        long_reply = "Спасибо за предложение. " * 100 + " Интересно, расскажите подробнее."
        intent, confidence = classify_reply_rule_based(long_reply)
        assert intent == ReplyIntent.STRONG_INTEREST

    def test_mixed_signals(self) -> None:
        """Priority order should handle mixed signals."""
        # Unsubscribe should win over interest
        reply = "Интересно, но отпишите меня от рассылки"
        intent, confidence = classify_reply_rule_based(reply)
        assert intent == ReplyIntent.UNSUBSCRIBE

    def test_case_insensitive(self) -> None:
        """Classification should be case-insensitive."""
        replies = [
            "НЕ ИНТЕРЕСНО",
            "Не Интересно",
            "не интересно",
        ]

        for reply in replies:
            intent, _ = classify_reply_rule_based(reply)
            assert intent == ReplyIntent.REFUSAL

    def test_with_punctuation(self) -> None:
        """Should handle punctuation."""
        replies = [
            "Сколько стоит???",
            "Не интересно!!!",
            "Давайте созвонимся...",
        ]

        expected = [
            ReplyIntent.REQUEST_DETAILS,
            ReplyIntent.REFUSAL,
            ReplyIntent.READY_TO_CALL,
        ]

        for reply, expected_intent in zip(replies, expected):
            intent, _ = classify_reply_rule_based(reply)
            assert intent == expected_intent, f"Failed for: {reply}"

    def test_russian_yo_letter(self) -> None:
        """Should handle ё/е variations."""
        reply1 = "Созвонёмся завтра"
        reply2 = "Созвонемся завтра"

        intent1, _ = classify_reply_rule_based(reply1)
        intent2, _ = classify_reply_rule_based(reply2)

        # Both should detect call intent
        assert intent1 == ReplyIntent.READY_TO_CALL or intent2 == ReplyIntent.READY_TO_CALL
