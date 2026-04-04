"""Scoring tools - lead scoring and segmentation.

Скоринг и сегментация согласно ARCHITECTURE.md раздел 4.5-4.6.
"""

from datetime import UTC, datetime
from uuid import uuid4

from app.models.domain import (
    CompanyProfile,
    EmployerContact,
    EmployerLead,
    LeadScore,
    LeadSegment,
)
from app.models.enums import (
    HiringIntensity,
    IndustrySegment,
    LeadPriority,
)

# Score weights
WEIGHTS = {
    "hiring_intensity": 0.30,
    "industry_fit": 0.25,
    "contact_quality": 0.20,
    "company_size": 0.15,
    "recency": 0.10,
}

# Target industries (higher score)
TARGET_INDUSTRIES = {
    IndustrySegment.RETAIL,
    IndustrySegment.HORECA,
    IndustrySegment.LOGISTICS,
    IndustrySegment.WAREHOUSE,
    IndustrySegment.CONSTRUCTION,
    IndustrySegment.MANUFACTURING,
}

# Segment communication strategies
SEGMENT_STRATEGIES = {
    IndustrySegment.RETAIL: {
        "communication_angle": "speed",
        "tone": "professional",
        "offer_type": "general",
        "pain_statement": "Сезонные пики, текучка кассиров и продавцов 80%+",
        "value_proposition": "Закрываем кассиров и продавцов за 48 часов",
        "proof_point": "Работаем с сетями от 50 точек",
        "suggested_cta": "Имеет смысл обсудить?",
    },
    IndustrySegment.HORECA: {
        "communication_angle": "reliability",
        "tone": "friendly",
        "offer_type": "general",
        "pain_statement": "Постоянная текучка, невыходы 25-30%",
        "value_proposition": "Повара и официанты с рейтингом надёжности",
        "proof_point": "Процент явки — 94% vs 70% по рынку",
        "suggested_cta": "Актуально для вас?",
    },
    IndustrySegment.LOGISTICS: {
        "communication_angle": "speed",
        "tone": "direct",
        "offer_type": "urgent",
        "pain_statement": "Масштабирование под пики, срочные замены",
        "value_proposition": "Курьеры и водители за 24 часа",
        "proof_point": "Покрываем пики доставки в 2x объёме",
        "suggested_cta": "Стоит обсудить?",
    },
    IndustrySegment.WAREHOUSE: {
        "communication_angle": "speed",
        "tone": "direct",
        "offer_type": "urgent",
        "pain_statement": "Пиковые нагрузки, срочный набор бригад",
        "value_proposition": "Комплектовщики и грузчики за 24 часа",
        "proof_point": "Бригады от 10 человек в течение суток",
        "suggested_cta": "Актуально сейчас?",
    },
    IndustrySegment.CONSTRUCTION: {
        "communication_angle": "compliance",
        "tone": "professional",
        "offer_type": "general",
        "pain_statement": "Бригады с документами, легальное оформление",
        "value_proposition": "Рабочие с документами и опытом за 48ч",
        "proof_point": "100% легальное оформление, все документы",
        "suggested_cta": "Имеет смысл обсудить?",
    },
    IndustrySegment.MANUFACTURING: {
        "communication_angle": "reliability",
        "tone": "professional",
        "offer_type": "general",
        "pain_statement": "Покрытие смен, стабильный состав",
        "value_proposition": "Операторы линий с опытом и стабильной явкой",
        "proof_point": "Средний срок работы сотрудника — 8+ месяцев",
        "suggested_cta": "Стоит рассмотреть?",
    },
}

DEFAULT_STRATEGY = {
    "communication_angle": "cost",
    "tone": "professional",
    "offer_type": "general",
    "pain_statement": "Сложности с наймом линейного персонала",
    "value_proposition": "Быстрый найм проверенных сотрудников",
    "proof_point": "Работаем с компаниями разных отраслей",
    "suggested_cta": "Имеет смысл обсудить?",
}


def calculate_score(
    lead: EmployerLead,
    profile: CompanyProfile | None,
    contacts: list[EmployerContact],
) -> LeadScore:
    """Calculate lead quality score.

    Расчёт скора по компонентам с весами из ARCHITECTURE.md.

    Args:
        lead: Lead to score
        profile: Company profile (optional)
        contacts: List of contacts

    Returns:
        LeadScore with component scores
    """
    # Calculate component scores (0-100)
    hiring_score = _score_hiring_intensity(profile)
    industry_score = _score_industry_fit(profile)
    contact_score = _score_contact_quality(contacts)
    size_score = _score_company_size(profile)
    recency_score = _score_recency(lead, profile)

    # Calculate weighted total
    total_score = (
        hiring_score * WEIGHTS["hiring_intensity"]
        + industry_score * WEIGHTS["industry_fit"]
        + contact_score * WEIGHTS["contact_quality"]
        + size_score * WEIGHTS["company_size"]
        + recency_score * WEIGHTS["recency"]
    )

    # Build reasoning
    reasoning_parts = []
    if hiring_score >= 70:
        reasoning_parts.append("высокая интенсивность найма")
    if industry_score >= 70:
        reasoning_parts.append("целевая отрасль")
    if contact_score >= 70:
        reasoning_parts.append("качественный контакт")
    if total_score < 40:
        reasoning_parts.append("низкий приоритет")

    reasoning = ", ".join(reasoning_parts) if reasoning_parts else "стандартный лид"

    return LeadScore(
        id=uuid4(),
        lead_id=lead.id,
        total_score=round(total_score, 1),
        hiring_intensity_score=round(hiring_score, 1),
        industry_fit_score=round(industry_score, 1),
        contact_quality_score=round(contact_score, 1),
        company_size_score=round(size_score, 1),
        recency_score=round(recency_score, 1),
        reasoning=reasoning.capitalize(),
        scored_at=datetime.now(UTC),
    )


def _score_hiring_intensity(profile: CompanyProfile | None) -> float:
    """Score based on hiring intensity."""
    if not profile:
        return 30.0

    intensity_scores = {
        HiringIntensity.AGGRESSIVE: 100.0,
        HiringIntensity.HIGH: 80.0,
        HiringIntensity.MEDIUM: 50.0,
        HiringIntensity.LOW: 20.0,
    }

    return intensity_scores.get(profile.hiring_intensity, 30.0)


def _score_industry_fit(profile: CompanyProfile | None) -> float:
    """Score based on industry fit."""
    if not profile:
        return 40.0

    if profile.industry in TARGET_INDUSTRIES:
        return 90.0
    elif profile.industry == IndustrySegment.TRADE:
        return 70.0
    elif profile.industry == IndustrySegment.OTHER:
        return 40.0

    return 50.0


def _score_contact_quality(contacts: list[EmployerContact]) -> float:
    """Score based on contact quality."""
    if not contacts:
        return 0.0

    score = 30.0  # Base score for having any contact

    for contact in contacts:
        if contact.email:
            score += 20.0
            if contact.email_verified:
                score += 20.0
        if contact.phone:
            score += 15.0
        if contact.role in [
            "hr_director", "hr_manager", "recruiter"
        ]:
            score += 15.0

    return min(score, 100.0)


def _score_company_size(profile: CompanyProfile | None) -> float:
    """Score based on company size."""
    if not profile or not profile.employee_count:
        return 50.0

    count = profile.employee_count

    if count >= 500:
        return 90.0
    elif count >= 200:
        return 80.0
    elif count >= 50:
        return 70.0
    elif count >= 20:
        return 50.0
    else:
        return 30.0


def _score_recency(lead: EmployerLead, profile: CompanyProfile | None) -> float:
    """Score based on data recency."""
    # Base score from lead creation date
    days_since_created = (datetime.now(UTC) - lead.created_at).days

    if days_since_created <= 1:
        score = 100.0
    elif days_since_created <= 7:
        score = 80.0
    elif days_since_created <= 30:
        score = 60.0
    else:
        score = 40.0

    # Boost if profile has recent enrichment
    if profile and profile.enriched_at:
        days_since_enriched = (datetime.now(UTC) - profile.enriched_at).days
        if days_since_enriched <= 1:
            score = min(score + 10, 100.0)

    return score


def determine_segment(
    lead: EmployerLead,
    profile: CompanyProfile | None,
    score: LeadScore,
) -> LeadSegment:
    """Determine lead segment and communication strategy.

    Args:
        lead: Lead to segment
        profile: Company profile
        score: Calculated lead score

    Returns:
        LeadSegment with strategy
    """
    # Determine industry segment
    if profile:
        segment = profile.industry
        sub_segment = profile.sub_industry
    else:
        segment = IndustrySegment.OTHER
        sub_segment = None

    # Get strategy for segment
    strategy = SEGMENT_STRATEGIES.get(segment, DEFAULT_STRATEGY)

    # Determine priority from score
    priority = _score_to_priority(score.total_score)

    # Adjust offer type based on hiring intensity
    offer_type = strategy["offer_type"]
    if profile and profile.hiring_intensity == HiringIntensity.AGGRESSIVE:
        offer_type = "urgent"
    elif score.total_score >= 80:
        offer_type = "enterprise"

    return LeadSegment(
        id=uuid4(),
        lead_id=lead.id,
        segment=segment,
        sub_segment=sub_segment,
        communication_angle=strategy["communication_angle"],
        tone=strategy["tone"],
        offer_type=offer_type,
        priority=priority,
        pain_statement=strategy["pain_statement"],
        value_proposition=strategy["value_proposition"],
        proof_point=strategy["proof_point"],
        suggested_cta=strategy["suggested_cta"],
    )


def _score_to_priority(score: float) -> LeadPriority:
    """Convert score to priority level."""
    if score >= 90:
        return LeadPriority.CRITICAL
    elif score >= 70:
        return LeadPriority.HIGH
    elif score >= 40:
        return LeadPriority.NORMAL
    else:
        return LeadPriority.LOW
