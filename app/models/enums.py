"""All enumerations for the domain model."""

from enum import Enum


class LeadStatus(str, Enum):
    """Lead lifecycle status.

    Основной pipeline: LEAD_FOUND -> ENRICHED -> SCORED -> EMAIL_READY ->
    OUTREACH_SENT -> IN_SEQUENCE -> REPLY_RECEIVED -> INTEREST_DETECTED ->
    QUALIFIED -> HANDED_TO_MANAGER
    """

    # Основной pipeline
    LEAD_FOUND = "lead_found"
    ENRICHED = "enriched"  # company parsed + contacts found
    SCORED = "scored"  # scored + segmented
    EMAIL_READY = "email_ready"  # email generated, quality gate passed
    OUTREACH_SENT = "outreach_sent"  # first email sent
    IN_SEQUENCE = "in_sequence"  # follow-ups в процессе
    REPLY_RECEIVED = "reply_received"
    INTEREST_DETECTED = "interest_detected"
    QUALIFIED = "qualified"
    HANDED_TO_MANAGER = "handed_to_manager"

    # Терминальные / боковые
    ARCHIVED = "archived"  # не подошёл (low score, no contacts, etc.)
    REFUSED = "refused"  # явный отказ
    COOLDOWN = "cooldown"  # перезвонить через N дней
    OPTED_OUT = "opted_out"  # unsubscribe
    BOUNCED = "bounced"  # email не доставляется
    DUPLICATE = "duplicate"  # дубликат другого лида


class IndustrySegment(str, Enum):
    """Industry segment for company classification."""

    RETAIL = "retail"
    HORECA = "horeca"
    LOGISTICS = "logistics"
    CONSTRUCTION = "construction"
    MANUFACTURING = "manufacturing"
    WAREHOUSE = "warehouse"
    TRADE = "trade"
    OTHER = "other"


class ContactRole(str, Enum):
    """Role of contact person in the company."""

    HR_DIRECTOR = "hr_director"
    HR_MANAGER = "hr_manager"
    RECRUITER = "recruiter"
    GENERAL_MANAGER = "general_manager"
    OPERATIONS_MANAGER = "operations_manager"
    OWNER = "owner"
    OFFICE_MANAGER = "office_manager"
    OTHER = "other"


class ReplyIntent(str, Enum):
    """Classified intent of email reply."""

    NO_REPLY = "no_reply"
    AUTO_REPLY = "auto_reply"  # автоответ (отпуск, etc.)
    NEUTRAL = "neutral"  # "спасибо, посмотрим"
    REFUSAL = "refusal"  # "не интересно"
    SOFT_INTEREST = "soft_interest"  # "интересно, но не сейчас"
    REQUEST_DETAILS = "request_details"  # "а сколько стоит?"
    STRONG_INTEREST = "strong_interest"  # "расскажите подробнее"
    READY_TO_CALL = "ready_to_call"  # "давайте созвонимся"
    UNSUBSCRIBE = "unsubscribe"  # "отпишите меня"
    WRONG_PERSON = "wrong_person"  # "это не ко мне, напишите X"


class EmailType(str, Enum):
    """Type of email in the sequence."""

    FIRST_TOUCH = "first_touch"
    FOLLOWUP_1 = "followup_1"  # день +3
    FOLLOWUP_2 = "followup_2"  # день +7
    BREAKUP = "breakup"  # день +14, мягкое закрытие


class HiringIntensity(str, Enum):
    """Hiring intensity classification based on vacancy count."""

    LOW = "low"  # 1-2 вакансии
    MEDIUM = "medium"  # 3-10 вакансий
    HIGH = "high"  # 10-30 вакансий
    AGGRESSIVE = "aggressive"  # 30+ вакансий


class LeadPriority(str, Enum):
    """Lead priority based on score."""

    LOW = "low"  # score < 40
    NORMAL = "normal"  # score 40-69
    HIGH = "high"  # score 70-89
    CRITICAL = "critical"  # score 90+


class LLMTaskType(str, Enum):
    """Type of LLM task for routing."""

    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    SCORING = "scoring"
    SEGMENTATION = "segmentation"
    PERSONALIZATION = "personalization"
    EMAIL_GENERATION = "email_generation"
    RESPONSE_ANALYSIS = "response_analysis"
    QUALIFICATION = "qualification"
    SUMMARIZATION = "summarization"
