"""Segment-specific templates and contexts.

Сегментные контексты для персонализации писем по отраслям.
Раздел 7.2 ARCHITECTURE.md и email_strategy.md.
"""

from pydantic import BaseModel

from app.models.enums import EmailType, IndustrySegment


class SegmentContext(BaseModel):
    """Context for a specific industry segment.

    Содержит боли, ценностное предложение, доказательства и углы
    для персонализации писем.
    """

    pain: str
    value: str
    proof: str
    angles: list[str]


# Сегментные контексты из ARCHITECTURE.md раздел 7.2
SEGMENT_CONTEXTS: dict[IndustrySegment, SegmentContext] = {
    IndustrySegment.RETAIL: SegmentContext(
        pain=(
            "Сезонные пики, текучка кассиров и продавцов 80%+, "
            "сложности с графиком в пиковые часы"
        ),
        value=(
            "Закрываем кассиров и продавцов за 48 часов, "
            "подтверждённая явка 94%"
        ),
        proof=(
            "Работаем с сетями от 50 точек, "
            "средний срок закрытия позиции — 2 дня"
        ),
        angles=["speed", "reliability", "seasonal_scale"],
    ),
    IndustrySegment.HORECA: SegmentContext(
        pain=(
            "Постоянная текучка, невыходы 25-30%, "
            "срочные замены в день обращения"
        ),
        value=(
            "Повара и официанты с рейтингом надёжности, "
            "замена за 4 часа"
        ),
        proof=(
            "Процент явки — 94% vs 70% по рынку, "
            "подходит для ресторанов и сетевого фастфуда"
        ),
        angles=["reliability", "speed", "no_shows"],
    ),
    IndustrySegment.LOGISTICS: SegmentContext(
        pain=(
            "Пиковые нагрузки, нехватка водителей и курьеров, "
            "масштабирование под сезон"
        ),
        value=(
            "200 курьеров в неделю, водители категории B/C "
            "с проверенным опытом"
        ),
        proof=(
            "Масштабируем штат доставки за 24 часа, "
            "работаем с федеральными логистическими компаниями"
        ),
        angles=["scale", "speed", "rating"],
    ),
    IndustrySegment.WAREHOUSE: SegmentContext(
        pain=(
            "Пиковые нагрузки на складе, нехватка комплектовщиков, "
            "срочный набор под сезон"
        ),
        value=(
            "200 комплектовщиков в неделю, "
            "грузчики с рейтингом надёжности"
        ),
        proof=(
            "Масштабирование за 24 часа, "
            "работаем с крупными складскими операторами"
        ),
        angles=["scale", "speed", "rating"],
    ),
    IndustrySegment.CONSTRUCTION: SegmentContext(
        pain=(
            "Бригады с документами, скорость выхода на объект, "
            "compliance и допуски"
        ),
        value=(
            "Бригады разнорабочих за 24 часа, "
            "все с документами и допусками"
        ),
        proof=(
            "Формируем бригады под ваш объект, "
            "работаем с генподрядчиками"
        ),
        angles=["compliance", "speed", "brigade"],
    ),
    IndustrySegment.MANUFACTURING: SegmentContext(
        pain=(
            "Покрытие смен, операторы линий, "
            "стабильность состава, выходные и ночные смены"
        ),
        value=(
            "Операторы под ваш график смен, "
            "стабильный пул с опытом на производстве"
        ),
        proof=(
            "Масштабирование под вторую/третью смену, "
            "явка 94%"
        ),
        angles=["shift_coverage", "stability", "scale"],
    ),
    IndustrySegment.TRADE: SegmentContext(
        pain=(
            "Текучка продавцов-консультантов, "
            "быстрое закрытие после увольнений"
        ),
        value=(
            "Продавцы-консультанты за 48 часов, "
            "кладовщики с опытом"
        ),
        proof=(
            "Работаем с торговыми сетями, "
            "средний срок закрытия — 2 дня"
        ),
        angles=["speed", "reliability"],
    ),
    IndustrySegment.OTHER: SegmentContext(
        pain=(
            "Сложности с наймом линейного персонала, "
            "текучка, срочные замены"
        ),
        value=(
            "Закрываем линейные позиции за 48 часов, "
            "подтверждённая явка"
        ),
        proof=(
            "Работаем с компаниями разных отраслей, "
            "гибкий подход"
        ),
        angles=["speed", "flexibility"],
    ),
}


# CTA варианты по типам писем из email_strategy.md
CTA_VARIANTS: dict[EmailType, list[str]] = {
    EmailType.FIRST_TOUCH: [
        "Имеет смысл обсудить?",
        "Актуально для вас сейчас?",
        "Стоит рассказать подробнее?",
    ],
    EmailType.FOLLOWUP_1: [
        "Могу прислать пример, как это работает для вашей отрасли?",
        "Удобно обсудить на 10 минут?",
        "Подскажите, кому лучше написать по этому вопросу?",
    ],
    EmailType.FOLLOWUP_2: [
        "Может быть, кто-то из коллег отвечает за подбор?",
        "Когда тема найма станет актуальной — напишите, я на связи.",
        "Есть 10 минут обсудить на этой неделе?",
    ],
    EmailType.BREAKUP: [
        "Если не актуально — без проблем, не буду отвлекать.",
        "Закрываю тему, но если понадобится — я на связи.",
    ],
}


# Углы коммуникации с описаниями
COMMUNICATION_ANGLES: dict[str, str] = {
    "speed": "скорость закрытия позиций",
    "reliability": "надёжность и явка",
    "seasonal_scale": "масштабирование под сезон",
    "no_shows": "борьба с невыходами",
    "scale": "быстрое масштабирование",
    "rating": "рейтинг надёжности исполнителей",
    "compliance": "документы и допуски",
    "brigade": "формирование бригад",
    "shift_coverage": "покрытие смен",
    "stability": "стабильность состава",
    "flexibility": "гибкий подход",
}


# Максимальное количество слов по типам писем
MAX_WORDS: dict[EmailType, int] = {
    EmailType.FIRST_TOUCH: 150,
    EmailType.FOLLOWUP_1: 80,
    EmailType.FOLLOWUP_2: 80,
    EmailType.BREAKUP: 50,
}


# Дни отправки follow-up (относительно предыдущего письма)
FOLLOWUP_DELAYS_DAYS: dict[EmailType, int] = {
    EmailType.FIRST_TOUCH: 0,
    EmailType.FOLLOWUP_1: 3,
    EmailType.FOLLOWUP_2: 7,
    EmailType.BREAKUP: 14,
}


def get_segment_context(segment: IndustrySegment) -> SegmentContext:
    """Get context for industry segment.

    Args:
        segment: Industry segment

    Returns:
        Segment context with pain, value, proof, angles
    """
    return SEGMENT_CONTEXTS.get(segment, SEGMENT_CONTEXTS[IndustrySegment.OTHER])


def get_cta_variants(email_type: EmailType) -> list[str]:
    """Get CTA variants for email type.

    Args:
        email_type: Type of email

    Returns:
        List of CTA variants
    """
    return CTA_VARIANTS.get(email_type, CTA_VARIANTS[EmailType.FIRST_TOUCH])


def get_max_words(email_type: EmailType) -> int:
    """Get maximum word count for email type.

    Args:
        email_type: Type of email

    Returns:
        Maximum word count
    """
    return MAX_WORDS.get(email_type, 150)
