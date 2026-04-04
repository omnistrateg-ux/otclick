"""Analysis tools for email reply processing.

Инструменты анализа ответов на письма.
"""

import json
import logging
import re
from datetime import UTC, datetime

from app.email.prompts import build_response_analysis_prompt
from app.llm.models import LLMRequest
from app.llm.router import LLMRouter
from app.models.domain import EmailMessage, EmployerLead, LeadSignal
from app.models.enums import LLMTaskType, ReplyIntent

logger = logging.getLogger(__name__)


# Ключевые слова для rule-based классификации
INTENT_KEYWORDS: dict[ReplyIntent, list[str]] = {
    ReplyIntent.UNSUBSCRIBE: [
        "отпишите",
        "отписать",
        "не пишите",
        "не присылайте",
        "удалите",
        "спам",
        "unsubscribe",
        "remove me",
        "stop",
    ],
    ReplyIntent.REFUSAL: [
        "не интересно",
        "неинтересно",
        "не актуально",
        "неактуально",
        "не нужно",
        "не надо",
        "отказываюсь",
        "нет, спасибо",
        "не подходит",
        "не для нас",
        "мы не ищем",
    ],
    ReplyIntent.AUTO_REPLY: [
        "автоответ",
        "auto-reply",
        "out of office",
        "в отпуске",
        "на больничном",
        "не на рабочем месте",
        "вернусь",
        "буду доступен",
        "временно недоступен",
        "automatic reply",
    ],
    ReplyIntent.WRONG_PERSON: [
        "не ко мне",
        "не тот адрес",
        "не мой вопрос",
        "напишите лучше",
        "обратитесь к",
        "перешлите",
        "направьте",
        "свяжитесь с",
        "отвечает за это",
        "ответственный за",
        "другой человек",
        "отвечает другой",
        "в отдел кадров",
    ],
    ReplyIntent.READY_TO_CALL: [
        "созвонимся",
        "созвонёмся",
        "созвонемся",
        "позвоните",
        "позвонить",
        "созвониться",
        "можем обсудить",
        "давайте обсудим",
        "готов обсудить",
        "назначить встречу",
        "когда удобно",
        "жду звонка",
        "перезвоните",
        "можете позвонить",
    ],
    ReplyIntent.STRONG_INTEREST: [
        "очень интересно",
        "расскажите подробнее",
        "хочу узнать больше",
        "расскажите детали",
        "подробную информацию",
        "очень актуально",
        "нам это нужно",
        "ищем именно это",
    ],
    ReplyIntent.REQUEST_DETAILS: [
        "сколько стоит",
        "какая цена",
        "какие условия",
        "как это работает",
        "прайс",
        "тарифы",
        "стоимость",
        "расценки",
        "коммерческое предложение",
        "кп пришлите",
        "это стоит",
    ],
    ReplyIntent.SOFT_INTEREST: [
        "интересно, но",
        "может быть позже",
        "возможно в будущем",
        "не сейчас",
        "через месяц",
        "после нового года",
        "вернёмся к этому",
        "вернемся к этому",
        "сохраню контакт",
        "пока не актуально, через",
    ],
    ReplyIntent.NEUTRAL: [
        "спасибо",
        "благодарю",
        "понял",
        "принято",
        "получил",
        "посмотрим",
        "подумаем",
        "рассмотрим",
    ],
}


def classify_reply_rule_based(reply_text: str) -> tuple[ReplyIntent, float]:
    """Classify reply using rule-based approach.

    Args:
        reply_text: Text of the reply

    Returns:
        Tuple of (intent, confidence)
    """
    text_lower = reply_text.lower()

    # Check each intent in priority order
    priority_order = [
        ReplyIntent.UNSUBSCRIBE,      # Highest priority - must respect
        ReplyIntent.AUTO_REPLY,       # Auto-replies are easy to detect
        ReplyIntent.READY_TO_CALL,    # Strong positive signal
        ReplyIntent.STRONG_INTEREST,  # Strong positive
        ReplyIntent.REQUEST_DETAILS,  # Positive - wants info
        ReplyIntent.WRONG_PERSON,     # Redirect
        ReplyIntent.REFUSAL,          # Negative
        ReplyIntent.SOFT_INTEREST,    # Weak positive
        ReplyIntent.NEUTRAL,          # Default
    ]

    for intent in priority_order:
        keywords = INTENT_KEYWORDS.get(intent, [])
        for keyword in keywords:
            if keyword.lower() in text_lower:
                # Higher confidence for longer/more specific matches
                confidence = min(0.7 + len(keyword) * 0.02, 0.95)
                return intent, confidence

    # Default to neutral with low confidence
    return ReplyIntent.NEUTRAL, 0.3


async def classify_reply_llm(
    reply_text: str,
    llm_router: LLMRouter,
) -> tuple[ReplyIntent, float, str | None]:
    """Classify reply using LLM.

    Args:
        reply_text: Text of the reply
        llm_router: LLM router

    Returns:
        Tuple of (intent, confidence, summary)
    """
    system_prompt, user_prompt = build_response_analysis_prompt(reply_text)

    request = LLMRequest(
        task_type=LLMTaskType.RESPONSE_ANALYSIS,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_mode=True,
        agent_name="analysis_tools",
    )

    try:
        response = await llm_router.complete(request)
        result = json.loads(response.content)

        intent_str = result.get("intent", "neutral")
        confidence = result.get("confidence", 0.5)
        summary = result.get("summary")

        # Map string to enum
        try:
            intent = ReplyIntent(intent_str)
        except ValueError:
            intent = ReplyIntent.NEUTRAL

        return intent, confidence, summary

    except Exception as e:
        logger.warning(f"LLM classification failed: {e}, falling back to rule-based")
        intent, confidence = classify_reply_rule_based(reply_text)
        return intent, confidence, None


async def analyze_reply(
    reply_text: str,
    email: EmailMessage,
    lead: EmployerLead,
    llm_router: LLMRouter | None = None,
    use_llm: bool = True,
) -> LeadSignal:
    """Analyze email reply and create signal.

    Args:
        reply_text: Text of the reply
        email: Original email that was replied to
        lead: Lead
        llm_router: LLM router (required if use_llm=True)
        use_llm: Whether to use LLM for classification

    Returns:
        Lead signal with intent classification
    """
    # First, try rule-based for obvious cases
    rule_intent, rule_confidence = classify_reply_rule_based(reply_text)

    # If rule-based is confident enough, use it
    if rule_confidence >= 0.8:
        intent = rule_intent
        confidence = rule_confidence
        summary = None
    elif use_llm and llm_router:
        # Use LLM for uncertain cases
        intent, confidence, summary = await classify_reply_llm(reply_text, llm_router)

        # If LLM is uncertain, combine with rule-based
        if confidence < 0.6 and rule_confidence > 0.5:
            intent = rule_intent
            confidence = (rule_confidence + confidence) / 2
    else:
        intent = rule_intent
        confidence = rule_confidence
        summary = None

    return LeadSignal(
        lead_id=lead.id,
        email_id=email.id,
        intent=intent,
        confidence=confidence,
        raw_text=reply_text[:1000],  # Limit stored text
        analyzed_at=datetime.now(UTC),
        analysis_model="llm" if use_llm else "rule_based",
    )


def is_positive_intent(intent: ReplyIntent) -> bool:
    """Check if intent indicates interest.

    Args:
        intent: Reply intent

    Returns:
        True if positive signal
    """
    return intent in {
        ReplyIntent.SOFT_INTEREST,
        ReplyIntent.REQUEST_DETAILS,
        ReplyIntent.STRONG_INTEREST,
        ReplyIntent.READY_TO_CALL,
    }


def is_negative_intent(intent: ReplyIntent) -> bool:
    """Check if intent indicates refusal.

    Args:
        intent: Reply intent

    Returns:
        True if negative signal
    """
    return intent in {
        ReplyIntent.REFUSAL,
        ReplyIntent.UNSUBSCRIBE,
    }


def should_continue_sequence(intent: ReplyIntent) -> bool:
    """Check if should continue email sequence.

    Args:
        intent: Reply intent

    Returns:
        True if should continue sending follow-ups
    """
    # Continue only for neutral or no reply
    return intent in {
        ReplyIntent.NEUTRAL,
        ReplyIntent.NO_REPLY,
        ReplyIntent.AUTO_REPLY,
    }


def extract_redirect_contact(reply_text: str) -> dict | None:
    """Try to extract redirect contact from wrong_person reply.

    Args:
        reply_text: Reply text

    Returns:
        Dict with contact info if found
    """
    text_lower = reply_text.lower()

    # Look for email patterns
    email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
    emails = re.findall(email_pattern, reply_text)

    # Look for name patterns after redirect phrases
    name_patterns = [
        r'напишите\s+(\w+\s+\w+)',
        r'обратитесь к\s+(\w+\s+\w+)',
        r'свяжитесь с\s+(\w+\s+\w+)',
        r'ответственный[:\s]+(\w+\s+\w+)',
    ]

    names = []
    for pattern in name_patterns:
        matches = re.findall(pattern, text_lower)
        names.extend(matches)

    if emails or names:
        return {
            "email": emails[0] if emails else None,
            "name": names[0].title() if names else None,
        }

    return None
