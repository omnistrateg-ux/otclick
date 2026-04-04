"""Pydantic domain models - all 15 domain objects."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import (
    ContactRole,
    EmailType,
    HiringIntensity,
    IndustrySegment,
    LeadPriority,
    LeadStatus,
    ReplyIntent,
)


class StatusChange(BaseModel):
    """Record of a status transition."""

    from_status: LeadStatus
    to_status: LeadStatus
    changed_at: datetime
    reason: str | None = None


class EmployerLead(BaseModel):
    """Central lifecycle object for an employer lead.

    Центральный объект, проходящий через весь pipeline от обнаружения
    до передачи менеджеру.
    """

    model_config = ConfigDict(from_attributes=True)

    # Идентификация
    id: UUID = Field(default_factory=uuid4)
    company_name: str
    domain: str | None = None
    source: str  # "hh.ru", "avito", "csv_import", "manual"
    source_url: str | None = None

    # Lifecycle
    status: LeadStatus = LeadStatus.LEAD_FOUND
    status_changed_at: datetime = Field(default_factory=utcnow)
    status_history: list[StatusChange] = Field(default_factory=list)

    # География
    city: str | None = None
    region: str | None = None

    # Связи (FK)
    company_profile_id: UUID | None = None
    campaign_id: UUID | None = None

    # Мета
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    archived_at: datetime | None = None
    archived_reason: str | None = None

    # Compliance
    opted_out: bool = False
    opted_out_at: datetime | None = None
    do_not_contact_until: datetime | None = None


class CompanyProfile(BaseModel):
    """Enriched company data.

    Обогащённые данные о компании: размер, отрасль, вакансии, боли.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID

    # Основные данные
    legal_name: str | None = None
    brand_name: str | None = None
    inn: str | None = None  # ИНН для дедупликации
    domain: str | None = None
    website_url: str | None = None

    # Классификация
    industry: IndustrySegment = IndustrySegment.OTHER
    sub_industry: str | None = None
    employee_count: int | None = None
    employee_count_source: str | None = None

    # География
    city: str | None = None
    region: str | None = None
    branches_count: int | None = None
    cities_presence: list[str] = Field(default_factory=list)

    # Hiring сигналы
    active_vacancies_count: int | None = None
    hiring_intensity: HiringIntensity = HiringIntensity.LOW
    vacancy_sources: list[str] = Field(default_factory=list)
    typical_roles: list[str] = Field(default_factory=list)
    avg_vacancy_age_days: float | None = None
    has_hr_department: bool | None = None

    # Контекст для персонализации
    pain_points: list[str] = Field(default_factory=list)
    personalization_hooks: list[str] = Field(default_factory=list)
    recent_news: list[str] = Field(default_factory=list)

    # Timestamps
    enriched_at: datetime | None = None
    enrichment_source: str | None = None


class EmployerContact(BaseModel):
    """Contact person at the company.

    Конкретный человек в компании, которому отправляем письма.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID

    # Персональные данные
    full_name: str
    first_name: str | None = None
    last_name: str | None = None

    # Роль
    role: ContactRole = ContactRole.OTHER
    job_title: str | None = None

    # Каналы связи
    email: EmailStr | None = None
    email_verified: bool = False
    email_verification_date: datetime | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    telegram: str | None = None

    # Приоритет
    is_primary: bool = False
    contact_source: str | None = None

    # Compliance
    opted_out: bool = False
    bounce_count: int = 0
    last_bounce_at: datetime | None = None


class LeadScore(BaseModel):
    """Numeric quality score for a lead.

    Числовая оценка качества лида с компонентами.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID

    # Итоговый скор (0-100)
    total_score: float

    # Компоненты (каждый 0-100, с весами)
    hiring_intensity_score: float  # вес 0.30
    industry_fit_score: float  # вес 0.25
    contact_quality_score: float  # вес 0.20
    company_size_score: float  # вес 0.15
    recency_score: float  # вес 0.10

    # Мета
    scoring_model_version: str = "v1"
    reasoning: str | None = None
    scored_at: datetime = Field(default_factory=utcnow)


class LeadSegment(BaseModel):
    """Segment assignment with communication strategy.

    Сегмент лида и стратегия коммуникации.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID

    # Сегмент
    segment: IndustrySegment
    sub_segment: str | None = None

    # Стратегия коммуникации
    communication_angle: str  # "speed", "reliability", "cost", "compliance"
    tone: str  # "professional", "friendly", "direct"
    offer_type: str  # "general", "seasonal", "urgent", "enterprise"
    priority: LeadPriority = LeadPriority.NORMAL

    # Контент для писем
    pain_statement: str
    value_proposition: str
    proof_point: str
    suggested_cta: str


class OutreachCampaign(BaseModel):
    """Campaign grouping leads and sequences.

    Группировка лидов в кампанию.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str | None = None

    # Настройки
    segment_filter: IndustrySegment | None = None
    min_score: float | None = None
    max_daily_emails: int = 50

    # Статус
    is_active: bool = True
    paused_at: datetime | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None


class EmailSequence(BaseModel):
    """Email sequence for a lead-contact pair.

    Цепочка писем одному контакту.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID
    contact_id: UUID
    campaign_id: UUID | None = None

    # Статус
    current_step: int = 0  # 0 = not started
    is_active: bool = True
    completed_at: datetime | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    last_email_at: datetime | None = None
    next_email_at: datetime | None = None


class EmailMessage(BaseModel):
    """Single email message in a sequence.

    Одно письмо.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    sequence_id: UUID
    lead_id: UUID
    contact_id: UUID

    # Контент
    email_type: EmailType
    subject: str
    body: str
    step_number: int

    # Генерация
    generation_model: str | None = None
    generation_prompt_version: str | None = None
    quality_gate_passed: bool = False
    quality_gate_issues: list[str] = Field(default_factory=list)

    # Доставка
    sent_at: datetime | None = None
    message_id_header: str | None = None
    delivered: bool | None = None
    bounced: bool | None = None
    bounce_type: str | None = None
    bounce_reason: str | None = None

    # Трекинг
    opened: bool | None = None
    opened_at: datetime | None = None
    open_count: int = 0
    clicked: bool | None = None

    # Ответ
    replied: bool | None = None
    replied_at: datetime | None = None
    reply_text: str | None = None


class MessageThread(BaseModel):
    """Full conversation thread with a contact.

    Полная переписка с контактом.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID
    contact_id: UUID

    messages: list[EmailMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class LeadSignal(BaseModel):
    """Interest or refusal signal from a lead.

    Сигнал интереса или отказа.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID
    email_id: UUID | None = None

    # Сигнал
    intent: ReplyIntent
    confidence: float = 1.0
    raw_text: str | None = None

    # Анализ
    analyzed_at: datetime = Field(default_factory=utcnow)
    analysis_model: str | None = None


class LeadQualification(BaseModel):
    """Qualification decision for a lead.

    Решение о квалификации лида.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID

    # Решение
    is_qualified: bool
    qualification_reason: str
    signals: list[UUID] = Field(default_factory=list)  # LeadSignal IDs

    # Мета
    qualified_at: datetime = Field(default_factory=utcnow)
    qualified_by: str | None = None  # "system" or user ID


class ManagerHandoff(BaseModel):
    """Handoff brief for manager.

    Бриф для менеджера с контекстом для звонка.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID
    qualification_id: UUID

    # Кто
    company_name: str
    contact_name: str
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_role: str

    # Контекст
    segment: IndustrySegment
    city: str | None = None
    company_size: str | None = None
    hiring_intensity: str | None = None

    # Почему этот лид важен
    why_this_lead_matters: str
    lead_score: float

    # Что произошло
    interest_signals: list[str] = Field(default_factory=list)
    emails_sent_summary: list[str] = Field(default_factory=list)
    employer_reply_summary: str | None = None
    conversation_history: str | None = None

    # Рекомендация
    suggested_next_step: str
    talking_points: list[str] = Field(default_factory=list)

    # Статус handoff'а
    manager_id: str | None = None
    notified_via: str | None = None
    notified_at: datetime | None = None
    accepted_at: datetime | None = None
    call_scheduled_at: datetime | None = None
    call_result: str | None = None


class AgentTask(BaseModel):
    """Unit of work for an agent.

    Единица работы для агента.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID
    agent_name: str
    task_type: str

    # Input
    input_data: dict = Field(default_factory=dict)

    # Status
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    error_message: str | None = None


class AgentRun(BaseModel):
    """Execution log for an agent task.

    Лог выполнения задачи агента.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    agent_name: str

    # Execution
    started_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None
    duration_ms: int | None = None

    # Result
    success: bool = False
    output_data: dict = Field(default_factory=dict)
    error_message: str | None = None

    # LLM usage
    llm_calls_count: int = 0
    llm_tokens_used: int = 0
    llm_cost_usd: float | None = None


class DomainEvent(BaseModel):
    """Event in the system.

    Событие в системе для event-driven обработки.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID | None = None
    event_type: str
    payload: dict = Field(default_factory=dict)

    # Meta
    created_at: datetime = Field(default_factory=utcnow)
    processed: bool = False
    processed_at: datetime | None = None
