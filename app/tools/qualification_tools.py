"""Qualification tools for lead qualification.

Инструменты квалификации лидов.
"""

import json
import logging
from datetime import datetime, timezone

UTC = timezone.utc
from uuid import UUID

from app.llm.models import LLMRequest
from app.llm.router import LLMRouter
from app.models.domain import (
    CompanyProfile,
    EmployerContact,
    EmployerLead,
    LeadQualification,
    LeadScore,
    LeadSegment,
    LeadSignal,
)
from app.models.enums import LLMTaskType, ReplyIntent

logger = logging.getLogger(__name__)


# Минимальный скор для автоматической квалификации
MIN_SCORE_FOR_AUTO_QUALIFICATION = 50

# Intent'ы которые автоматически квалифицируют лида
AUTO_QUALIFY_INTENTS = {
    ReplyIntent.READY_TO_CALL,
    ReplyIntent.STRONG_INTEREST,
    ReplyIntent.REQUEST_DETAILS,
}

# Intent'ы которые требуют дополнительного анализа
NEEDS_REVIEW_INTENTS = {
    ReplyIntent.SOFT_INTEREST,
}


def check_auto_qualification(
    signals: list[LeadSignal],
    score: LeadScore | None,
) -> tuple[bool, str]:
    """Check if lead should be auto-qualified.

    Args:
        signals: List of lead signals
        score: Lead score

    Returns:
        Tuple of (is_qualified, reason)
    """
    if not signals:
        return False, "No signals"

    # Check for strong positive signals
    for signal in signals:
        if signal.intent in AUTO_QUALIFY_INTENTS:
            return True, f"Auto-qualified: {signal.intent.value}"

    # Check for soft interest with high score
    for signal in signals:
        if signal.intent == ReplyIntent.SOFT_INTEREST:
            if score and score.total_score >= MIN_SCORE_FOR_AUTO_QUALIFICATION:
                return True, "Soft interest with high score"

    return False, "Does not meet auto-qualification criteria"


async def qualify_lead_llm(
    lead: EmployerLead,
    profile: CompanyProfile | None,
    signals: list[LeadSignal],
    score: LeadScore | None,
    conversation_summary: str | None,
    llm_router: LLMRouter,
) -> tuple[bool, str, list[str]]:
    """Qualify lead using LLM analysis.

    Args:
        lead: Lead to qualify
        profile: Company profile
        signals: Lead signals
        score: Lead score
        conversation_summary: Summary of email conversation
        llm_router: LLM router

    Returns:
        Tuple of (is_qualified, reason, next_steps)
    """
    system_prompt = """Ты — эксперт по квалификации B2B лидов в сфере массового найма.

Твоя задача — определить, готов ли лид к передаче менеджеру для звонка.

Критерии квалификации:
1. Проявлен интерес (запрос деталей, готовность к звонку, вопросы о стоимости)
2. Компания соответствует целевому профилю (массовый наём, целевая отрасль)
3. Есть контактное лицо с полномочиями принимать решения

Ответь JSON: {
    "is_qualified": true/false,
    "reason": "краткое обоснование",
    "confidence": 0.0-1.0,
    "next_steps": ["шаг 1", "шаг 2"]
}"""

    # Build context
    signals_text = "\n".join([
        f"- {s.intent.value}: {s.raw_text[:100]}..." if s.raw_text else f"- {s.intent.value}"
        for s in signals
    ])

    user_prompt = f"""Оцени лида для квалификации:

Компания: {lead.company_name}
Город: {lead.city or 'Не указан'}
Отрасль: {profile.industry.value if profile else 'Не определена'}
Скор: {score.total_score if score else 'Не рассчитан'}

Сигналы:
{signals_text}

{f'Переписка: {conversation_summary}' if conversation_summary else ''}

Квалифицировать этого лида?"""

    request = LLMRequest(
        task_type=LLMTaskType.QUALIFICATION,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_mode=True,
        agent_name="qualification_tools",
    )

    try:
        response = await llm_router.complete(request)
        result = json.loads(response.content)

        is_qualified = result.get("is_qualified", False)
        reason = result.get("reason", "LLM qualification")
        next_steps = result.get("next_steps", [])

        return is_qualified, reason, next_steps

    except Exception as e:
        logger.warning(f"LLM qualification failed: {e}")
        # Fall back to rule-based
        is_qualified, reason = check_auto_qualification(signals, score)
        return is_qualified, reason, []


async def qualify_lead(
    lead: EmployerLead,
    profile: CompanyProfile | None,
    contact: EmployerContact,
    signals: list[LeadSignal],
    score: LeadScore | None,
    llm_router: LLMRouter | None = None,
    use_llm: bool = True,
) -> LeadQualification:
    """Qualify lead for handoff.

    Args:
        lead: Lead to qualify
        profile: Company profile
        contact: Primary contact
        signals: Lead signals
        score: Lead score
        llm_router: LLM router
        use_llm: Whether to use LLM

    Returns:
        Lead qualification decision
    """
    # First check auto-qualification
    is_auto_qualified, auto_reason = check_auto_qualification(signals, score)

    if is_auto_qualified:
        return LeadQualification(
            lead_id=lead.id,
            is_qualified=True,
            qualification_reason=auto_reason,
            signals=[s.id for s in signals],
            qualified_at=datetime.now(UTC),
            qualified_by="system_auto",
        )

    # Use LLM for uncertain cases
    if use_llm and llm_router:
        is_qualified, reason, next_steps = await qualify_lead_llm(
            lead=lead,
            profile=profile,
            signals=signals,
            score=score,
            conversation_summary=None,  # TODO: build from messages
            llm_router=llm_router,
        )
    else:
        is_qualified = False
        reason = "Does not meet qualification criteria"

    return LeadQualification(
        lead_id=lead.id,
        is_qualified=is_qualified,
        qualification_reason=reason,
        signals=[s.id for s in signals],
        qualified_at=datetime.now(UTC),
        qualified_by="system_llm" if use_llm else "system_rule",
    )


def calculate_qualification_score(
    signals: list[LeadSignal],
    lead_score: LeadScore | None,
    profile: CompanyProfile | None,
) -> float:
    """Calculate qualification score (0-100).

    Args:
        signals: Lead signals
        lead_score: Lead score
        profile: Company profile

    Returns:
        Qualification score
    """
    score = 0.0

    # Base score from lead score (40% weight)
    if lead_score:
        score += lead_score.total_score * 0.4

    # Signal score (40% weight)
    signal_points = {
        ReplyIntent.READY_TO_CALL: 100,
        ReplyIntent.STRONG_INTEREST: 90,
        ReplyIntent.REQUEST_DETAILS: 80,
        ReplyIntent.SOFT_INTEREST: 50,
        ReplyIntent.NEUTRAL: 20,
        ReplyIntent.AUTO_REPLY: 10,
        ReplyIntent.REFUSAL: 0,
        ReplyIntent.UNSUBSCRIBE: 0,
        ReplyIntent.WRONG_PERSON: 10,
        ReplyIntent.NO_REPLY: 0,
    }

    if signals:
        max_signal = max(signal_points.get(s.intent, 0) for s in signals)
        score += max_signal * 0.4

    # Profile completeness (20% weight)
    if profile:
        completeness = 0
        if profile.industry:
            completeness += 25
        if profile.employee_count:
            completeness += 25
        if profile.active_vacancies_count:
            completeness += 25
        if profile.pain_points:
            completeness += 25
        score += completeness * 0.2

    return min(score, 100)


def get_disqualification_reasons(
    lead: EmployerLead,
    signals: list[LeadSignal],
    score: LeadScore | None,
) -> list[str]:
    """Get reasons why lead cannot be qualified.

    Args:
        lead: Lead
        signals: Signals
        score: Score

    Returns:
        List of disqualification reasons
    """
    reasons = []

    # Check opt-out
    if lead.opted_out:
        reasons.append("Lead opted out")

    # Check refusal signals
    for signal in signals:
        if signal.intent == ReplyIntent.REFUSAL:
            reasons.append("Explicit refusal received")
        if signal.intent == ReplyIntent.UNSUBSCRIBE:
            reasons.append("Unsubscribe request")

    # Check low score
    if score and score.total_score < 20:
        reasons.append(f"Score too low: {score.total_score}")

    return reasons


def should_request_manual_review(
    signals: list[LeadSignal],
    score: LeadScore | None,
) -> tuple[bool, str]:
    """Check if lead should be sent for manual review.

    Args:
        signals: Lead signals
        score: Lead score

    Returns:
        Tuple of (needs_review, reason)
    """
    # Soft interest with medium score
    for signal in signals:
        if signal.intent == ReplyIntent.SOFT_INTEREST:
            if score and 30 <= score.total_score < MIN_SCORE_FOR_AUTO_QUALIFICATION:
                return True, "Soft interest with medium score"

    # Wrong person redirect
    for signal in signals:
        if signal.intent == ReplyIntent.WRONG_PERSON:
            return True, "Redirect to another contact"

    # Low confidence signals
    for signal in signals:
        if signal.confidence < 0.5 and signal.intent in AUTO_QUALIFY_INTENTS:
            return True, "Low confidence positive signal"

    return False, ""
