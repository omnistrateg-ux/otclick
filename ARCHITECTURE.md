# Отклик — Employer Acquisition Engine
# Полная архитектура и структура проекта

> Единый документ для разработки в Cursor + Claude Code.
> Всё, что нужно знать, чтобы строить систему — здесь.

---

## 1. Что мы строим

AI-система, которая автоматически находит работодателей в сфере массового найма, квалифицирует их через персонализированные email-цепочки и передаёт только тёплых, заинтересованных лидов менеджеру на звонок.

### Целевые отрасли

| Отрасль | Типичные вакансии | Боль работодателя |
|---------|-------------------|-------------------|
| Ритейл | Кассиры, продавцы, мерчандайзеры | Сезонные пики, текучка 80%+ |
| HoReCa | Повара, официанты, бармены | Невыходы, срочные замены |
| Логистика | Курьеры, водители кат. B/C | Масштабирование под пики |
| Склад | Комплектовщики, грузчики | Пиковые нагрузки, срочный набор |
| Стройка | Разнорабочие, бетонщики | Бригады с документами за 24ч |
| Производство | Операторы линий, упаковщики | Покрытие смен, стабильный состав |
| Торговля | Продавцы-консультанты, кладовщики | Быстрое закрытие после увольнений |

### Что это НЕ

- Не marketplace кандидатов
- Не matching engine
- Не система закрытия смен
- Не CRM (хотя интегрируется с CRM)

### Бизнес-воронка

```
Источник данных (hh.ru, Avito, 2GIS, CSV)
    ↓
Обнаружение компании
    ↓
Обогащение (профиль + вакансии + интенсивность найма)
    ↓
Поиск контактов (HR, рекрутер, директор)
    ↓
Скоринг + Сегментация
    ↓
Генерация персонализированного письма
    ↓
Отправка → Follow-up цепочка (3 письма)
    ↓
Анализ ответа → Классификация интереса
    ↓
Квалификация лида
    ↓
Handoff менеджеру (бриф + контекст для звонка)
```

### Финальная точка

Менеджер получает в Slack/CRM карточку:
- Кто компания, что за отрасль, где находится
- Почему этот лид ценный
- Какие письма отправляли, на что ответили
- Конкретный следующий шаг для звонка

---

## 2. Архитектура верхнего уровня

```
┌──────────────────────────────────────────────────────────────────────┐
│                        FastAPI Gateway                                │
│                   /api/v1/* — REST endpoints                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                     ┌─────────────────────┐                          │
│                     │   Orchestrator      │                          │
│                     │   (State Machine)   │                          │
│                     │   Event Dispatcher  │                          │
│                     └─────────┬───────────┘                          │
│                               │                                      │
│              ┌────────────────┼────────────────┐                     │
│              ▼                ▼                ▼                     │
│    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│    │  Research     │  │  Outreach    │  │  Analysis    │             │
│    │  Pipeline     │  │  Pipeline    │  │  Pipeline    │             │
│    │              │  │              │  │              │             │
│    │ Discovery    │  │ EmailCopy    │  │ Response     │             │
│    │ Enrichment   │  │ FollowUp     │  │ Qualification│             │
│    │ Contacts     │  │ Delivery     │  │ Handoff      │             │
│    │ Scoring      │  │              │  │              │             │
│    │ Segmentation │  │              │  │              │             │
│    └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
│           │                 │                 │                      │
│           ▼                 ▼                 ▼                      │
│    ┌────────────────────────────────────────────────┐                │
│    │              Tools Layer                       │                │
│    │  find_employers · parse_profile · find_contacts│                │
│    │  score · segment · generate_email · send_email │                │
│    │  parse_reply · detect_interest · qualify       │                │
│    │  create_handoff · notify_manager               │                │
│    └────────────────────┬───────────────────────────┘                │
│                         │                                            │
│    ┌────────────────────┼───────────────────────┐                    │
│    │           LLM Router                       │                    │
│    │  Task classification → Provider selection  │                    │
│    │  OpenAI · Claude · Qwen · YandexGPT        │                    │
│    └────────────────────────────────────────────┘                    │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  PostgreSQL     │  Redis (cache +    │  Celery       │  SMTP / ESP  │
│  (все данные)   │  rate limits +     │  (async jobs) │  (Mailgun /  │
│                 │  short-term state) │               │  собств.)    │
└──────────────────────────────────────────────────────────────────────┘
```

### Ключевые архитектурные решения

**1. Agent = мозг, Tool = руки.**
Агент решает ЧТО делать и в каком порядке. Tool выполняет КАК — вызов API, парсинг, отправка. Агент никогда не вызывает внешний сервис напрямую.

**2. Orchestrator владеет state machine.**
Ни один агент не меняет статус лида напрямую. Агент возвращает результат → Orchestrator валидирует переход → обновляет статус → эмитит event.

**3. LLM Router — единая точка вызова моделей.**
Ни один агент не знает, какую модель использует. Router выбирает модель по типу задачи и доступности провайдера.

**4. Event-driven, но без over-engineering.**
Events — это записи в PostgreSQL-таблице `events` + Celery tasks для async обработки. Не Kafka, не Redis Streams, не отдельный event bus в памяти. Простота важнее теоретической чистоты.

**5. Email Intelligence Engine — центр системы.**
Не шаблонная система. LLM-генерация с structured prompts, quality gates, A/B вариантами. Каждое письмо проходит валидацию перед отправкой.

---

## 3. Структура проекта

```
otclick_employer_engine/
│
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app factory
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py                  # Pydantic Settings (env vars)
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── enums.py                     # LeadStatus, IndustrySegment, ReplyIntent, ...
│   │   ├── domain.py                    # Pydantic domain models (15 объектов)
│   │   └── db.py                        # SQLAlchemy ORM models
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── state_machine.py             # LeadStateMachine — переходы + валидация
│   │   ├── dependencies.py              # FastAPI Depends (db session, current_user)
│   │   └── exceptions.py               # Доменные исключения
│   │
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── engine.py                    # LeadOrchestrator — центральный координатор
│   │   └── pipeline.py                  # Pipeline definitions (research, outreach, analysis)
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                      # BaseAgent — интерфейс + lifecycle tracking
│   │   ├── discovery_agent.py           # Поиск компаний из источников
│   │   ├── enrichment_agent.py          # Обогащение профиля + вакансии + контакты
│   │   ├── scoring_agent.py             # Скоринг + сегментация (объединены)
│   │   ├── email_copy_agent.py          # Генерация писем через Email Engine
│   │   ├── followup_agent.py            # Follow-up последовательности
│   │   ├── response_agent.py            # Анализ ответов + определение интереса
│   │   ├── qualification_agent.py       # Квалификация лида
│   │   └── handoff_agent.py             # Формирование handoff + нотификация
│   │
│   ├── email/
│   │   ├── __init__.py
│   │   ├── engine.py                    # EmailIntelligenceEngine — ядро генерации
│   │   ├── prompts.py                   # Системные промпты по сегментам
│   │   ├── quality_gate.py              # Валидация письма перед отправкой
│   │   ├── delivery.py                  # SMTP / ESP отправка + bounce handling
│   │   └── templates.py                 # Segment-specific контекст (боли, value props)
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── discovery_tools.py           # find_employers (hh.ru, Avito, 2GIS, CSV)
│   │   ├── enrichment_tools.py          # parse_company, parse_hiring, enrich
│   │   ├── contact_tools.py             # find_contacts (email finders, LinkedIn, сайты)
│   │   ├── scoring_tools.py             # score_lead, segment_lead
│   │   ├── email_tools.py               # generate_email, send_email, track_delivery
│   │   ├── analysis_tools.py            # parse_reply, detect_interest
│   │   ├── qualification_tools.py       # qualify_lead
│   │   └── handoff_tools.py             # create_handoff, notify_manager
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── router.py                    # LLMRouter — маршрутизация по задачам
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                  # LLMProvider ABC
│   │   │   ├── openai_provider.py       # OpenAI GPT-4o / GPT-4o-mini
│   │   │   ├── anthropic_provider.py    # Claude Sonnet / Opus
│   │   │   ├── qwen_provider.py         # Qwen Plus / Turbo
│   │   │   └── yandexgpt_provider.py    # YandexGPT Lite / Pro
│   │   └── models.py                    # LLMRequest, LLMResponse, LLMTaskType
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── lead_service.py              # CRUD + бизнес-логика лидов
│   │   ├── campaign_service.py          # Управление кампаниями
│   │   ├── email_service.py             # Управление email-последовательностями
│   │   ├── analytics_service.py         # KPI, метрики, дашборд
│   │   └── compliance_service.py        # Unsubscribe, opt-out, 152-ФЗ, дедупликация
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py                  # SQLAlchemy async engine + session factory
│   │   ├── redis.py                     # Redis client (cache, rate limits, locks)
│   │   └── repositories/
│   │       ├── __init__.py
│   │       ├── lead_repo.py             # LeadRepository
│   │       ├── company_repo.py          # CompanyRepository
│   │       ├── contact_repo.py          # ContactRepository
│   │       ├── email_repo.py            # EmailRepository
│   │       ├── event_repo.py            # EventRepository
│   │       └── handoff_repo.py          # HandoffRepository
│   │
│   ├── events/
│   │   ├── __init__.py
│   │   ├── definitions.py              # Event type constants + создание событий
│   │   └── handlers.py                  # Event → Celery task mapping
│   │
│   └── api/
│       ├── __init__.py
│       ├── router.py                    # Корневой router
│       ├── leads.py                     # /leads — CRUD, запуск pipeline
│       ├── campaigns.py                 # /campaigns — управление кампаниями
│       ├── emails.py                    # /emails — просмотр писем, ручная отправка
│       ├── handoffs.py                  # /handoffs — список handoff'ов для менеджера
│       ├── analytics.py                 # /analytics — KPI, метрики
│       ├── webhooks.py                  # /webhooks — входящие email replies, ESP events
│       └── health.py                    # /health — readiness + liveness
│
├── workers/
│   ├── __init__.py
│   ├── celery_app.py                    # Celery конфигурация
│   ├── discovery_tasks.py               # Async задачи discovery pipeline
│   ├── outreach_tasks.py                # Async задачи email pipeline
│   ├── analysis_tasks.py                # Async задачи analysis pipeline
│   └── scheduled_tasks.py              # Celery Beat: follow-up расписание, cleanup
│
├── migrations/
│   ├── env.py                           # Alembic configuration
│   └── versions/                        # Migration files
│
├── scripts/
│   ├── seed_data.py                     # Тестовые данные для dev
│   ├── import_csv.py                    # Импорт компаний из CSV
│   ├── run_pipeline.py                  # CLI: запустить pipeline для одного лида
│   └── test_email_gen.py               # CLI: тест генерации письма
│
├── tests/
│   ├── conftest.py                      # Fixtures (db, redis, mock LLM)
│   ├── unit/
│   │   ├── test_state_machine.py
│   │   ├── test_scoring.py
│   │   ├── test_email_quality_gate.py
│   │   ├── test_reply_classification.py
│   │   └── test_llm_router.py
│   ├── integration/
│   │   ├── test_discovery_pipeline.py
│   │   ├── test_outreach_pipeline.py
│   │   └── test_full_lifecycle.py
│   └── fixtures/
│       ├── companies.json
│       ├── contacts.json
│       └── replies.json
│
├── docs/
│   ├── architecture.md                  # → этот файл
│   ├── email_strategy.md                # Стратегия email-коммуникации
│   ├── data_sources.md                  # Источники данных и API
│   ├── llm_routing.md                   # Таблица маршрутизации LLM
│   └── deployment.md                    # Деплой, инфра, мониторинг
│
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   └── docker-compose.yml               # postgres + redis + app + worker + mailhog
│
├── .env.example
├── .cursorrules                         # Правила для Cursor AI
├── pyproject.toml
├── alembic.ini
└── README.md
```

### Правила для .cursorrules

```
# .cursorrules

Этот проект — Employer Acquisition Engine для платформы массового найма «Отклик».

## Что это
AI-система поиска работодателей → обогащения → email outreach → квалификации → передачи менеджеру.

## Чего здесь НЕТ и не должно быть
- Поиска кандидатов, исполнителей, соискателей
- Matching engine
- Candidate distribution
- Marketplace вакансий

## Архитектурные правила
1. Agent решает ЧТО делать. Tool делает КАК. Agent никогда не вызывает внешний API.
2. Только Orchestrator меняет статус лида. Agent возвращает результат.
3. Только LLM Router вызывает LLM-провайдеров. Agent передаёт LLMRequest.
4. Каждый domain object — Pydantic model. ORM модели отдельно в models/db.py.
5. Events — записи в БД + Celery tasks. Не in-memory bus.
6. Все email проходят quality gate перед отправкой.

## Стек
- Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2
- PostgreSQL 16, Redis 7, Celery 5
- Alembic для миграций
- pytest + pytest-asyncio для тестов

## Стиль кода
- Type hints везде
- Async/await для I/O
- Docstrings на русском для бизнес-логики, на английском для инфраструктуры
- Не больше 200 строк на файл. Если больше — разбивай.
- Имена переменных на английском, комментарии к бизнес-логике можно на русском.
```

---

## 4. Domain Objects

### 4.1 Полный список объектов

| # | Объект | Назначение | Ключевые связи |
|---|--------|------------|----------------|
| 1 | `EmployerLead` | Центральный объект lifecycle | → CompanyProfile, Contact[], Score, Segment |
| 2 | `CompanyProfile` | Обогащённые данные компании | → EmployerLead |
| 3 | `EmployerContact` | Конкретный человек в компании | → EmployerLead |
| 4 | `LeadScore` | Числовая оценка качества | → EmployerLead |
| 5 | `LeadSegment` | Сегмент + стратегия коммуникации | → EmployerLead |
| 6 | `OutreachCampaign` | Группировка лидов в кампанию | → EmployerLead[], EmailSequence[] |
| 7 | `EmailSequence` | Цепочка писем одному контакту | → EmployerLead, EmployerContact, EmailMessage[] |
| 8 | `EmailMessage` | Одно письмо (subject + body + metadata) | → EmailSequence, EmployerLead, EmployerContact |
| 9 | `MessageThread` | Полная переписка с контактом | → EmployerLead, EmployerContact |
| 10 | `LeadSignal` | Сигнал интереса/отказа | → EmployerLead, EmailMessage |
| 11 | `LeadQualification` | Решение о квалификации | → EmployerLead, LeadSignal[] |
| 12 | `ManagerHandoff` | Бриф для менеджера | → EmployerLead, EmployerContact, LeadQualification |
| 13 | `AgentTask` | Единица работы для агента | → EmployerLead |
| 14 | `AgentRun` | Лог выполнения задачи | → AgentTask |
| 15 | `DomainEvent` | Событие в системе | → EmployerLead |

### 4.2 EmployerLead — детальная схема

```python
class EmployerLead:
    # Идентификация
    id: UUID
    company_name: str
    domain: str | None                  # example.com
    source: str                         # "hh.ru", "avito", "csv_import", "manual"
    source_url: str | None              # URL вакансии/страницы откуда нашли

    # Lifecycle
    status: LeadStatus                  # state machine (см. раздел 5)
    status_changed_at: datetime
    status_history: list[StatusChange]  # лог всех переходов

    # География
    city: str | None
    region: str | None

    # Связи (FK)
    company_profile_id: UUID | None
    campaign_id: UUID | None

    # Мета
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    archived_reason: str | None         # "no_contacts", "low_score", "refused", "duplicate"

    # Compliance
    opted_out: bool = False
    opted_out_at: datetime | None
    do_not_contact_until: datetime | None  # cooldown
```

### 4.3 CompanyProfile

```python
class CompanyProfile:
    id: UUID
    lead_id: UUID                       # FK → EmployerLead

    # Основные данные
    legal_name: str | None
    brand_name: str | None
    inn: str | None                     # ИНН для дедупликации
    domain: str | None
    website_url: str | None

    # Классификация
    industry: IndustrySegment
    sub_industry: str | None            # "продуктовый ритейл", "dark store"
    employee_count: int | None
    employee_count_source: str | None   # "sparc", "hh_estimate", "2gis"

    # География
    city: str | None
    region: str | None
    branches_count: int | None
    cities_presence: list[str]          # ["Москва", "СПб", "Казань"]

    # Hiring сигналы
    active_vacancies_count: int | None
    hiring_intensity: HiringIntensity   # low | medium | high | aggressive
    vacancy_sources: list[str]          # ["hh.ru", "avito"]
    typical_roles: list[str]            # ["кассир", "продавец", "грузчик"]
    avg_vacancy_age_days: float | None  # свежесть вакансий
    has_hr_department: bool | None

    # Контекст для персонализации
    pain_points: list[str]              # заполняется LLM при enrichment
    personalization_hooks: list[str]    # "открыли 5 новых точек", "ищут 30 кассиров"
    recent_news: list[str]              # новости о компании

    # Timestamps
    enriched_at: datetime | None
    enrichment_source: str | None       # "hh_api", "website_parse", "2gis"
```

### 4.4 EmployerContact

```python
class EmployerContact:
    id: UUID
    lead_id: UUID                       # FK → EmployerLead

    # Персональные данные
    full_name: str
    first_name: str | None
    last_name: str | None

    # Роль
    role: ContactRole                   # hr_director, recruiter, general_manager, ...
    job_title: str | None               # оригинальная должность

    # Каналы связи
    email: str | None
    email_verified: bool = False
    email_verification_date: datetime | None
    phone: str | None
    linkedin_url: str | None
    telegram: str | None

    # Приоритет
    is_primary: bool = False            # основной контакт для outreach
    contact_source: str | None          # "hh_vacancy", "website", "linkedin", "hunter.io"

    # Compliance
    opted_out: bool = False
    bounce_count: int = 0               # сколько раз bounce
    last_bounce_at: datetime | None
```

### 4.5 LeadScore

```python
class LeadScore:
    id: UUID
    lead_id: UUID

    # Итоговый скор (0-100)
    total_score: float

    # Компоненты (каждый 0-100, с весами)
    hiring_intensity_score: float       # вес 0.30 — активно нанимают?
    industry_fit_score: float           # вес 0.25 — целевая отрасль?
    contact_quality_score: float        # вес 0.20 — есть верифицированный email?
    company_size_score: float           # вес 0.15 — достаточно крупные?
    recency_score: float                # вес 0.10 — свежие вакансии?

    # Мета
    scoring_model_version: str          # "v1", "v2" — для A/B тестов скоринга
    reasoning: str | None               # объяснение скора (от LLM или rule-based)
    scored_at: datetime
```

### 4.6 LeadSegment

```python
class LeadSegment:
    id: UUID
    lead_id: UUID

    # Сегмент
    segment: IndustrySegment            # retail, horeca, logistics, ...
    sub_segment: str | None             # "федеральная сеть", "локальный ресторан"

    # Стратегия коммуникации
    communication_angle: str            # "speed", "reliability", "cost", "compliance"
    tone: str                           # "professional", "friendly", "direct"
    offer_type: str                     # "general", "seasonal", "urgent", "enterprise"
    priority: LeadPriority              # low, normal, high, critical

    # Контент для писем (заполняется при сегментации)
    pain_statement: str                 # "Сезонные пики, текучка кассиров"
    value_proposition: str              # "Закрываем линейные позиции за 48ч"
    proof_point: str                    # "Работаем с сетями от 50 точек"
    suggested_cta: str                  # "Имеет смысл обсудить?"
```

### 4.7 EmailMessage

```python
class EmailMessage:
    id: UUID
    sequence_id: UUID                   # FK → EmailSequence
    lead_id: UUID
    contact_id: UUID

    # Контент
    email_type: EmailType               # first_touch, followup_1, followup_2, breakup
    subject: str
    body: str                           # plain text (без HTML)
    step_number: int                    # 1, 2, 3, 4

    # Генерация
    generation_model: str | None        # "claude-sonnet-4-20250514"
    generation_prompt_version: str | None
    quality_gate_passed: bool = False
    quality_gate_issues: list[str]      # проблемы найденные gate

    # Доставка
    sent_at: datetime | None
    message_id_header: str | None       # SMTP Message-ID
    delivered: bool | None
    bounced: bool | None
    bounce_type: str | None             # "hard", "soft"
    bounce_reason: str | None

    # Трекинг
    opened: bool | None
    opened_at: datetime | None
    open_count: int = 0
    clicked: bool | None

    # Ответ
    replied: bool | None
    replied_at: datetime | None
    reply_text: str | None
```

### 4.8 ManagerHandoff

```python
class ManagerHandoff:
    id: UUID
    lead_id: UUID
    qualification_id: UUID

    # Кто
    company_name: str
    contact_name: str
    contact_email: str | None
    contact_phone: str | None
    contact_role: str

    # Контекст
    segment: IndustrySegment
    city: str | None
    company_size: str | None            # "50-200 сотрудников"
    hiring_intensity: str | None

    # Почему этот лид важен
    why_this_lead_matters: str          # 2-3 предложения
    lead_score: float

    # Что произошло
    interest_signals: list[str]         # ["Запросил детали по ценам", "Открыл 3 письма"]
    emails_sent_summary: list[str]      # ["[First touch] Кассиры за 48ч — актуально?"]
    employer_reply_summary: str | None  # краткое содержание ответа
    conversation_history: str | None    # полная выжимка переписки

    # Рекомендация
    suggested_next_step: str            # "Позвонить, предложить демо"
    talking_points: list[str]           # подсказки для звонка

    # Статус handoff'а
    manager_id: str | None              # кому назначен
    notified_via: str | None            # "slack", "email", "crm"
    notified_at: datetime | None
    accepted_at: datetime | None
    call_scheduled_at: datetime | None
    call_result: str | None             # "demo_booked", "not_interested", "callback_later"
```

### 4.9 Все Enums

```python
class LeadStatus(str, Enum):
    # Основной pipeline
    LEAD_FOUND = "lead_found"
    ENRICHED = "enriched"               # company parsed + contacts found
    SCORED = "scored"                    # scored + segmented
    EMAIL_READY = "email_ready"         # email generated, quality gate passed
    OUTREACH_SENT = "outreach_sent"     # first email sent
    IN_SEQUENCE = "in_sequence"         # follow-ups в процессе
    REPLY_RECEIVED = "reply_received"
    INTEREST_DETECTED = "interest_detected"
    QUALIFIED = "qualified"
    HANDED_TO_MANAGER = "handed_to_manager"

    # Терминальные / боковые
    ARCHIVED = "archived"               # не подошёл (low score, no contacts, etc.)
    REFUSED = "refused"                 # явный отказ
    COOLDOWN = "cooldown"               # перезвонить через N дней
    OPTED_OUT = "opted_out"             # unsubscribe
    BOUNCED = "bounced"                 # email не доставляется
    DUPLICATE = "duplicate"             # дубликат другого лида


class IndustrySegment(str, Enum):
    RETAIL = "retail"
    HORECA = "horeca"
    LOGISTICS = "logistics"
    CONSTRUCTION = "construction"
    MANUFACTURING = "manufacturing"
    WAREHOUSE = "warehouse"
    TRADE = "trade"
    OTHER = "other"


class ContactRole(str, Enum):
    HR_DIRECTOR = "hr_director"
    HR_MANAGER = "hr_manager"
    RECRUITER = "recruiter"
    GENERAL_MANAGER = "general_manager"
    OPERATIONS_MANAGER = "operations_manager"
    OWNER = "owner"
    OFFICE_MANAGER = "office_manager"
    OTHER = "other"


class ReplyIntent(str, Enum):
    NO_REPLY = "no_reply"
    AUTO_REPLY = "auto_reply"           # автоответ (отпуск, etc.)
    NEUTRAL = "neutral"                 # "спасибо, посмотрим"
    REFUSAL = "refusal"                 # "не интересно"
    SOFT_INTEREST = "soft_interest"     # "интересно, но не сейчас"
    REQUEST_DETAILS = "request_details" # "а сколько стоит?"
    STRONG_INTEREST = "strong_interest" # "расскажите подробнее"
    READY_TO_CALL = "ready_to_call"     # "давайте созвонимся"
    UNSUBSCRIBE = "unsubscribe"         # "отпишите меня"
    WRONG_PERSON = "wrong_person"       # "это не ко мне, напишите X"


class EmailType(str, Enum):
    FIRST_TOUCH = "first_touch"
    FOLLOWUP_1 = "followup_1"           # день +3
    FOLLOWUP_2 = "followup_2"           # день +7
    BREAKUP = "breakup"                 # день +14, мягкое закрытие


class HiringIntensity(str, Enum):
    LOW = "low"                         # 1-2 вакансии
    MEDIUM = "medium"                   # 3-10 вакансий
    HIGH = "high"                       # 10-30 вакансий
    AGGRESSIVE = "aggressive"           # 30+ вакансий


class LeadPriority(str, Enum):
    LOW = "low"                         # score < 40
    NORMAL = "normal"                   # score 40-69
    HIGH = "high"                       # score 70-89
    CRITICAL = "critical"              # score 90+


class LLMTaskType(str, Enum):
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    SCORING = "scoring"
    SEGMENTATION = "segmentation"
    PERSONALIZATION = "personalization"
    EMAIL_GENERATION = "email_generation"
    RESPONSE_ANALYSIS = "response_analysis"
    QUALIFICATION = "qualification"
    SUMMARIZATION = "summarization"
```

---

## 5. State Machine

### 5.1 Граф переходов

```
                         ┌──────────┐
                    ┌───►│ ARCHIVED │◄─── из любого состояния
                    │    └──────────┘     (no_contacts, low_score,
                    │                      duplicate, error)
                    │
              ┌─────┴─────┐
              │ LEAD_FOUND │
              └─────┬──────┘
                    │ enrichment_agent
                    ▼
              ┌───────────┐
              │ ENRICHED  │────────────►  ARCHIVED (если нет контактов)
              └─────┬─────┘
                    │ scoring_agent
                    ▼
              ┌──────────┐
              │  SCORED   │────────────►  ARCHIVED (если score < 20)
              └─────┬─────┘
                    │ email_copy_agent
                    ▼
             ┌────────────┐
             │ EMAIL_READY │
             └─────┬──────┘
                   │ delivery (Celery task)
                   ▼
          ┌────────────────┐
          │ OUTREACH_SENT  │────────────► BOUNCED (hard bounce)
          └────────┬───────┘
                   │ followup_agent (по расписанию)
                   ▼
          ┌──────────────┐
          │ IN_SEQUENCE   │◄─── повторный follow-up
          └───┬───────┬───┘
              │       │ нет ответа после всей цепочки
              │       └────────────────► ARCHIVED
              │ ответ получен
              ▼
        ┌────────────────┐
        │ REPLY_RECEIVED │
        └───┬──┬──┬──┬───┘
            │  │  │  │
            │  │  │  └─► OPTED_OUT (unsubscribe)
            │  │  └────► REFUSED → COOLDOWN (90 дней)
            │  └───────► IN_SEQUENCE (нейтральный → ещё follow-up)
            │
            ▼ (soft/strong interest, request_details, ready_to_call)
     ┌───────────────────┐
     │ INTEREST_DETECTED  │
     └────────┬──────────┘
              │ qualification_agent
              ▼
        ┌────────────┐
        │ QUALIFIED   │
        └──────┬─────┘
               │ handoff_agent
               ▼
     ┌──────────────────────┐
     │ HANDED_TO_MANAGER    │ ← финальное состояние
     └──────────────────────┘

     ┌──────────┐
     │ COOLDOWN │──── через 30-90 дней ────► LEAD_FOUND (re-engage)
     └──────────┘
```

### 5.2 Правила переходов

```python
TRANSITIONS: dict[LeadStatus, list[LeadStatus]] = {
    LeadStatus.LEAD_FOUND:          [ENRICHED, ARCHIVED, DUPLICATE],
    LeadStatus.ENRICHED:            [SCORED, ARCHIVED],
    LeadStatus.SCORED:              [EMAIL_READY, ARCHIVED],
    LeadStatus.EMAIL_READY:         [OUTREACH_SENT],
    LeadStatus.OUTREACH_SENT:       [IN_SEQUENCE, REPLY_RECEIVED, BOUNCED],
    LeadStatus.IN_SEQUENCE:         [REPLY_RECEIVED, ARCHIVED, BOUNCED],
    LeadStatus.REPLY_RECEIVED:      [INTEREST_DETECTED, REFUSED, IN_SEQUENCE,
                                     OPTED_OUT, COOLDOWN],
    LeadStatus.INTEREST_DETECTED:   [QUALIFIED],
    LeadStatus.QUALIFIED:           [HANDED_TO_MANAGER],
    LeadStatus.HANDED_TO_MANAGER:   [],  # терминал
    LeadStatus.BOUNCED:             [ARCHIVED],
    LeadStatus.REFUSED:             [COOLDOWN, ARCHIVED],
    LeadStatus.COOLDOWN:            [LEAD_FOUND],  # re-engage
    LeadStatus.OPTED_OUT:           [],  # терминал, не трогаем
    LeadStatus.DUPLICATE:           [],  # терминал
    LeadStatus.ARCHIVED:            [LEAD_FOUND],  # можно реактивировать
}
```

### 5.3 Упрощение vs предыдущая версия

Предыдущая версия имела 13 линейных шагов. Новая:
- **10 основных + 6 боковых** состояний
- `company_parsed` и `contacts_found` объединены в `ENRICHED` (один агент делает всё)
- `scored` и `segmented` объединены в `SCORED` (один агент)
- Добавлены `BOUNCED`, `OPTED_OUT`, `DUPLICATE`, `COOLDOWN`
- Нелинейные переходы: `REPLY_RECEIVED` → обратно в `IN_SEQUENCE`
- `COOLDOWN` → `LEAD_FOUND` для re-engagement

---

## 6. Agents

### 6.1 Реестр агентов (8 вместо 11)

| # | Agent | Input | Output | LLM Task | Следующий event |
|---|-------|-------|--------|----------|----------------|
| 1 | `DiscoveryAgent` | SearchParams | EmployerLead[] | extraction | `lead_discovered` |
| 2 | `EnrichmentAgent` | EmployerLead | CompanyProfile + Contact[] | extraction, classification | `lead_enriched` |
| 3 | `ScoringAgent` | Lead + Profile + Contacts | LeadScore + LeadSegment | scoring, segmentation | `lead_scored` |
| 4 | `EmailCopyAgent` | Lead + Profile + Segment + Contact | EmailMessage | email_generation | `email_generated` |
| 5 | `FollowUpAgent` | Lead + Sequence + Previous messages | EmailMessage | email_generation | `followup_generated` |
| 6 | `ResponseAgent` | Reply text + Lead context | LeadSignal | response_analysis | `reply_analyzed` |
| 7 | `QualificationAgent` | Lead + Signals + Score | LeadQualification | qualification | `lead_qualified` |
| 8 | `HandoffAgent` | Lead + Profile + Contact + Qualification | ManagerHandoff | summarization | `handoff_created` |

### 6.2 Почему 8, а не 11

Убраны:
- **PersonalizationAgent** → персонализация — это шаг внутри `EmailCopyAgent`, а не отдельный агент
- **ContactDiscoveryAgent** → объединён с `EnrichmentAgent` (один этап исследования)
- **SegmentationAgent** → объединён с `ScoringAgent` (скоринг и сегментация идут вместе)

Правило: агент = один этап pipeline, который оправдывает отдельную Celery task.

### 6.3 BaseAgent interface

```python
class BaseAgent(ABC):
    agent_name: str
    llm_task_types: list[LLMTaskType]  # какие задачи этот агент отправляет в LLM

    def __init__(self, llm_router: LLMRouter, db: AsyncSession):
        self.llm = llm_router
        self.db = db

    async def execute(self, task: AgentTask) -> AgentResult:
        """Полный lifecycle: валидация → run → аудит."""
        run = self._start_run(task)
        try:
            result = await self.run(task)
            run.complete(result)
            return result
        except Exception as e:
            run.fail(e)
            raise

    @abstractmethod
    async def run(self, task: AgentTask) -> AgentResult:
        """Конкретная логика агента."""
        ...

    async def call_llm(self, task_type: LLMTaskType,
                       system: str, user: str, **kwargs) -> str:
        """Обёртка: Agent → LLM Router → Provider."""
        response = await self.llm.complete(LLMRequest(
            task_type=task_type,
            system_prompt=system,
            user_prompt=user,
            **kwargs,
        ))
        return response.content
```

---

## 7. Email Intelligence Engine

### 7.1 Архитектура модуля

```
EmailCopyAgent
    │
    ▼
EmailIntelligenceEngine
    ├── build_prompt(lead, profile, segment, contact, email_type)
    │       │
    │       ├── SegmentPromptLibrary     # боль, value prop, proof по отраслям
    │       ├── ToneAdapter              # professional / friendly / direct
    │       └── CTAVariator              # разные CTA для разных шагов
    │
    ├── generate(prompt) ──► LLM Router ──► Provider
    │
    ├── QualityGate.validate(subject, body, email_type)
    │       │
    │       ├── spam_word_check
    │       ├── length_check             # M1 ≤ 150 слов, M2-M3 ≤ 80 слов
    │       ├── cta_presence_check
    │       ├── personalization_check    # упомянута компания или отрасль?
    │       ├── subject_length_check     # ≤ 60 символов
    │       └── tone_check              # нет "мы рады предложить"
    │
    └── output: EmailMessage (subject + body + metadata)
```

### 7.2 Сегментные промпты

```python
SEGMENT_PROMPTS = {
    IndustrySegment.RETAIL: SegmentContext(
        pain="Сезонные пики, текучка кассиров и продавцов 80%+, "
             "сложности с графиком в пиковые часы",
        value="Закрываем кассиров и продавцов за 48 часов, "
              "подтверждённая явка 94%",
        proof="Работаем с сетями от 50 точек, "
              "средний срок закрытия позиции — 2 дня",
        angles=["speed", "reliability", "seasonal_scale"],
    ),
    IndustrySegment.HORECA: SegmentContext(
        pain="Постоянная текучка, невыходы 25-30%, "
             "срочные замены в день обращения",
        value="Повара и официанты с рейтингом надёжности, "
              "замена за 4 часа",
        proof="Процент явки — 94% vs 70% по рынку, "
              "подходит для ресторанов и сетевого фастфуда",
        angles=["reliability", "speed", "no_shows"],
    ),
    # ... аналогично для logistics, construction, manufacturing, warehouse, trade
}
```

### 7.3 Структура email-последовательности

| Шаг | День | Тип | Макс. слов | Стратегия |
|-----|------|-----|-----------|-----------|
| 1 | 0 | first_touch | 150 | Боль → контекст → ценность → мягкий CTA |
| 2 | +3 | followup_1 | 80 | Другой угол (social proof, метрика). Короче M1 |
| 3 | +7 | followup_2 | 80 | Ещё один угол или case study |
| 4 | +14 | breakup | 50 | Мягкое закрытие: "Если не актуально — без проблем" |

### 7.4 Quality Gate — обязательные проверки

```python
class QualityGate:
    SPAM_WORDS = [
        "уникальный", "бесплатно", "гарантируем", "эксклюзив",
        "революционный", "не пропустите", "срочно", "только сегодня",
        "специальное предложение", "мы рады предложить",
        "инновационный", "лучший на рынке",
    ]

    def validate(self, subject: str, body: str,
                 email_type: EmailType, lead: EmployerLead) -> QualityResult:
        issues = []

        # 1. Спам-слова
        for word in self.SPAM_WORDS:
            if word in body.lower() or word in subject.lower():
                issues.append(f"spam_word:{word}")

        # 2. Длина
        word_count = len(body.split())
        max_words = 150 if email_type == EmailType.FIRST_TOUCH else 80
        if word_count > max_words:
            issues.append(f"too_long:{word_count}/{max_words}")

        # 3. CTA
        cta_signals = ["?", "актуальн", "обсуд", "созвон", "ответ",
                       "напиш", "подскаж", "имеет смысл"]
        if not any(s in body.lower() for s in cta_signals):
            issues.append("missing_cta")

        # 4. Персонализация — упомянута компания или отрасль
        company_mentioned = lead.company_name.lower() in body.lower()
        if not company_mentioned:
            issues.append("no_company_mention")

        # 5. Subject
        if len(subject) > 60:
            issues.append(f"subject_too_long:{len(subject)}")
        if subject.endswith("!"):
            issues.append("subject_exclamation")

        # 6. Длина (минимум)
        if word_count < 20:
            issues.append(f"too_short:{word_count}")

        return QualityResult(
            passed=len(issues) == 0,
            issues=issues,
            word_count=word_count,
        )
```

### 7.5 Принципы писем (для LLM system prompt)

```
ПРАВИЛА НАПИСАНИЯ ПИСЕМ:

1. КОРОТКОСТЬ: 4-6 предложений для первого письма, 2-3 для follow-up.

2. СТРУКТУРА ПЕРВОГО ПИСЬМА:
   - Строка 1: зацепка, связанная с болью работодателя
   - Строки 2-3: что мы делаем (одно предложение) + доказательство (метрика)
   - Строка 4: мягкий CTA — вопрос, на который легко ответить

3. ЗАПРЕЩЕНО:
   - "Мы рады предложить", "Уникальное решение", "Не пропустите"
   - Перечисление всех фичей продукта
   - Длинные абзацы
   - Вложения и ссылки на лендинг в первом письме
   - Восклицательные знаки в теме

4. CTA — всегда один, всегда вопрос:
   - "Имеет смысл обсудить?"
   - "Актуально для вас сейчас?"
   - "Стоит ли рассказать подробнее?"
   НЕ "Зарегистрируйтесь", НЕ "Скачайте", НЕ "Перейдите по ссылке"

5. ТОН: как умный коллега пишет другому — деловой, но человечный.
   Не маркетолог, не робот, не менеджер по продажам.

6. ЦЕЛЬ: получить ответ, а не продать.

Ответь ТОЛЬКО JSON: {"subject": "...", "body": "..."}
```

---

## 8. LLM Router

### 8.1 Таблица маршрутизации

| Task Type | Предпочтение | Tier | Пример модели | Примерная стоимость |
|-----------|-------------|------|---------------|-------------------|
| classification | Дешёвая | Low | Qwen-Turbo, YandexGPT-Lite | $0.001/req |
| extraction | Дешёвая | Low | GPT-4o-mini, Qwen-Plus | $0.002/req |
| scoring | Средняя | Mid | GPT-4o-mini, Claude Haiku | $0.003/req |
| segmentation | Средняя | Mid | GPT-4o-mini | $0.003/req |
| personalization | Сильная | High | Claude Sonnet, GPT-4o | $0.01/req |
| email_generation | Сильная | High | Claude Sonnet, GPT-4o | $0.015/req |
| response_analysis | Сильная | High | Claude Sonnet | $0.008/req |
| qualification | Премиум | Premium | Claude Opus, GPT-4o | $0.02/req |
| summarization | Средняя | Mid | GPT-4o, Claude Sonnet | $0.008/req |

### 8.2 Fallback chain

```python
ROUTING_TABLE = {
    LLMTaskType.CLASSIFICATION:    ["qwen", "yandexgpt", "openai", "anthropic"],
    LLMTaskType.EXTRACTION:        ["qwen", "openai", "anthropic"],
    LLMTaskType.SCORING:           ["openai", "anthropic", "qwen"],
    LLMTaskType.SEGMENTATION:      ["openai", "qwen", "anthropic"],
    LLMTaskType.PERSONALIZATION:   ["anthropic", "openai"],
    LLMTaskType.EMAIL_GENERATION:  ["anthropic", "openai"],
    LLMTaskType.RESPONSE_ANALYSIS: ["anthropic", "openai"],
    LLMTaskType.QUALIFICATION:     ["anthropic", "openai"],
    LLMTaskType.SUMMARIZATION:     ["openai", "anthropic"],
}
```

Логика: пробуем первый доступный провайдер. Если таймаут/ошибка → следующий. Если все недоступны → exception + retry через Celery.

### 8.3 Cost tracking

Каждый вызов LLM записывает:
- provider, model, task_type
- input_tokens, output_tokens
- latency_ms
- estimated_cost_usd

Это позволяет считать KPI "cost per warm lead".

---

## 9. Источники данных

### 9.1 Discovery sources

| Источник | Метод получения | Что даёт | Приоритет |
|----------|----------------|----------|-----------|
| **hh.ru API** | REST API (вакансии работодателя) | Компания, вакансии, контакты, интенсивность | Основной |
| **Avito** | Парсинг (headless browser) | Компания, вакансии (часто без HR-контактов) | Дополнительный |
| **2GIS API** | REST API | Компании по категории + город, телефоны | Для discovery |
| **CSV-импорт** | Ручной upload | Любые данные (партнёрские списки, выставки) | Ручной |
| **Сайты компаний** | Парсинг (requests/playwright) | Email, телефон, вакансии на сайте | Для enrichment |

### 9.2 Contact enrichment sources

| Источник | Что даёт | Стоимость |
|----------|----------|-----------|
| **hh.ru vacancy contacts** | HR email/телефон из вакансии | Бесплатно (в рамках API) |
| **Hunter.io** | Email по домену компании | $0.01-0.05/email |
| **Сайт компании (парсинг)** | Email, телефон со страницы "контакты" | Бесплатно |
| **LinkedIn (ручной/API)** | Имя + должность + profile URL | На будущее |

### 9.3 Что НЕ используем

- Покупные базы (качество нулевое для mass hiring)
- Scraping личных email (нарушение 152-ФЗ)
- Любые источники без возможности opt-out

---

## 10. Events

### 10.1 Реестр событий

```python
# Discovery
LEAD_DISCOVERED = "lead_discovered"           # новый лид найден

# Enrichment
LEAD_ENRICHED = "lead_enriched"               # профиль + контакты собраны
ENRICHMENT_FAILED = "enrichment_failed"       # не удалось обогатить

# Scoring
LEAD_SCORED = "lead_scored"                   # скор посчитан + сегмент назначен
LEAD_ARCHIVED_LOW_SCORE = "lead_archived_low_score"

# Email
EMAIL_GENERATED = "email_generated"           # письмо создано
EMAIL_QUALITY_FAILED = "email_quality_failed" # не прошло quality gate
EMAIL_SENT = "email_sent"                     # отправлено
EMAIL_DELIVERED = "email_delivered"            # доставлено (ESP webhook)
EMAIL_BOUNCED = "email_bounced"               # bounce (hard/soft)
EMAIL_OPENED = "email_opened"                 # открытие (pixel tracking)

# Follow-up
FOLLOWUP_SCHEDULED = "followup_scheduled"     # follow-up запланирован
FOLLOWUP_SENT = "followup_sent"               # follow-up отправлен
SEQUENCE_COMPLETED = "sequence_completed"     # вся цепочка отправлена

# Response
REPLY_RECEIVED = "reply_received"             # входящий ответ
REPLY_ANALYZED = "reply_analyzed"             # intent определён
INTEREST_DETECTED = "interest_detected"       # тёплый сигнал

# Qualification
LEAD_QUALIFIED = "lead_qualified"             # лид квалифицирован
LEAD_REFUSED = "lead_refused"                 # явный отказ

# Handoff
HANDOFF_CREATED = "handoff_created"           # бриф создан
MANAGER_NOTIFIED = "manager_notified"         # менеджер получил уведомление
HANDOFF_ACCEPTED = "handoff_accepted"         # менеджер взял в работу

# Compliance
LEAD_OPTED_OUT = "lead_opted_out"             # unsubscribe
LEAD_DUPLICATE_FOUND = "lead_duplicate_found"
```

### 10.2 Event → Action mapping

```python
EVENT_HANDLERS = {
    LEAD_DISCOVERED:    [tasks.run_enrichment],
    LEAD_ENRICHED:      [tasks.run_scoring],
    LEAD_SCORED:        [tasks.run_email_generation],  # если score >= threshold
    EMAIL_GENERATED:    [tasks.schedule_send],
    EMAIL_SENT:         [tasks.schedule_followup],     # через 3 дня
    EMAIL_BOUNCED:      [tasks.handle_bounce],
    REPLY_RECEIVED:     [tasks.run_response_analysis],
    INTEREST_DETECTED:  [tasks.run_qualification],
    LEAD_QUALIFIED:     [tasks.run_handoff],
    HANDOFF_CREATED:    [tasks.notify_manager],
    LEAD_OPTED_OUT:     [tasks.process_optout],
}
```

---

## 11. API Endpoints

### 11.1 Leads

```
POST   /api/v1/leads/discover          # запустить discovery по параметрам
POST   /api/v1/leads/import            # импорт из CSV
GET    /api/v1/leads                    # список лидов (фильтры, пагинация)
GET    /api/v1/leads/{id}              # детали лида
PATCH  /api/v1/leads/{id}/status       # ручная смена статуса
POST   /api/v1/leads/{id}/reprocess    # перезапустить pipeline с текущего шага
DELETE /api/v1/leads/{id}              # архивация
```

### 11.2 Campaigns

```
POST   /api/v1/campaigns               # создать кампанию
GET    /api/v1/campaigns                # список кампаний
GET    /api/v1/campaigns/{id}          # детали + статистика
PATCH  /api/v1/campaigns/{id}          # обновить (пауза, возобновление)
POST   /api/v1/campaigns/{id}/launch   # запустить кампанию
```

### 11.3 Emails

```
GET    /api/v1/emails/sequences         # все email-последовательности
GET    /api/v1/emails/messages/{id}    # конкретное письмо
POST   /api/v1/emails/preview          # preview письма без отправки
POST   /api/v1/emails/{id}/approve     # ручное одобрение
```

### 11.4 Handoffs

```
GET    /api/v1/handoffs                 # список для менеджера
GET    /api/v1/handoffs/{id}           # детали handoff'а
PATCH  /api/v1/handoffs/{id}/accept    # менеджер принял
PATCH  /api/v1/handoffs/{id}/result    # результат звонка
```

### 11.5 Analytics

```
GET    /api/v1/analytics/funnel         # воронка по статусам
GET    /api/v1/analytics/campaigns/{id} # статистика кампании
GET    /api/v1/analytics/email-perf     # open rate, reply rate, etc.
GET    /api/v1/analytics/costs          # расходы на LLM по задачам
```

### 11.6 Webhooks (входящие)

```
POST   /api/v1/webhooks/email/reply     # входящий ответ на письмо
POST   /api/v1/webhooks/esp/events      # ESP events (delivered, bounced, opened)
POST   /api/v1/webhooks/unsubscribe     # unsubscribe handler
```

### 11.7 System

```
GET    /api/v1/health                   # liveness + readiness
GET    /api/v1/health/providers         # статус LLM провайдеров
```

---

## 12. Compliance & Security

### 12.1 Email compliance (152-ФЗ + best practices)

| Требование | Реализация |
|-----------|-----------|
| Unsubscribe | Каждое письмо содержит одноклеточный unsubscribe link |
| Opt-out processing | При unsubscribe → статус `OPTED_OUT`, запрет на отправку навсегда |
| List-Unsubscribe header | RFC 8058 `List-Unsubscribe-Post` в каждом письме |
| Bounce handling | Hard bounce → `BOUNCED`, soft bounce × 3 → `BOUNCED` |
| Sender rotation | Несколько sender email'ов для распределения нагрузки |
| Domain warm-up | Первая неделя: 10 писем/день, вторая: 25, третья: 50 |
| SPF/DKIM/DMARC | Обязательная настройка для каждого sender домена |

### 12.2 Rate limits

```python
RATE_LIMITS = {
    "emails_per_sender_per_day": 50,       # лимит на один email-отправитель
    "emails_per_domain_per_day": 5,        # лимит писем на один домен-получатель
    "emails_per_campaign_per_hour": 20,    # антиспам throttle
    "llm_calls_per_minute": 60,            # rate limit на LLM API
    "discovery_per_hour": 100,             # rate limit на парсинг
}
```

### 12.3 Дедупликация

Проверка при каждом новом лиде:
1. По домену компании (`company_domain`)
2. По ИНН (`inn`) если есть
3. По email контакта (`contact_email`)
4. По нормализованному имени + городу (`company_name_normalized + city`)

При совпадении → статус `DUPLICATE`, ссылка на оригинальный лид.

### 12.4 Audit log

Каждое действие системы записывается:
```python
class AuditEntry:
    timestamp: datetime
    actor: str              # "discovery_agent", "manager:ivan", "system"
    action: str             # "status_change", "email_sent", "llm_call"
    lead_id: UUID | None
    details: dict           # произвольные данные
    ip_address: str | None  # для manual actions
```

### 12.5 Ручная проверка

Автоматическая отправка блокируется и требует ручного approve когда:
- Score лида < 40 (low priority, но есть контакт)
- Компания в "watchlist" (конкуренты, крупные бренды, госструктуры)
- Email quality gate нашёл issues но не критичные
- Первые 10 писем новой кампании (для проверки тональности)

---

## 13. KPI & Метрики

### 13.1 Воронка с целевыми значениями

| Метрика | Формула | Целевое значение (v1) |
|---------|---------|----------------------|
| Leads found | count(LEAD_FOUND) за период | 500/неделю |
| Enrichment rate | ENRICHED / LEAD_FOUND | > 80% |
| Contact found rate | leads_with_contacts / ENRICHED | > 60% |
| Score > 40 rate | SCORED(score≥40) / SCORED | > 50% |
| Outreach sent | count(EMAIL_SENT) за период | 200/неделю |
| Open rate | opened / delivered | > 40% |
| Reply rate | replied / delivered | > 5% |
| Positive reply rate | (soft+strong+details+call) / replied | > 30% |
| Qualified leads | count(QUALIFIED) за период | 15/неделю |
| Handoff → call rate | call_scheduled / HANDED_TO_MANAGER | > 60% |
| Cost per warm lead | total_llm_cost / QUALIFIED | < 2000₽ |

### 13.2 Email performance по сегментам

Отслеживаем отдельно для каждого `IndustrySegment`:
- open rate, reply rate, positive reply rate
- лучший subject line (A/B)
- лучший communication_angle

Это позволяет Email Engine учиться: какие углы работают для ритейла vs HoReCa.

---

## 14. Инфраструктура

### 14.1 Docker Compose (dev)

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: otclick_employer
      POSTGRES_USER: otclick
      POSTGRES_PASSWORD: otclick
    ports: ["5432:5432"]
    volumes: ["pg_data:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  app:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [postgres, redis]
    volumes: [".:/app"]

  worker:
    build: .
    command: celery -A workers.celery_app worker -l info -c 4
    env_file: .env
    depends_on: [postgres, redis]
    volumes: [".:/app"]

  beat:
    build: .
    command: celery -A workers.celery_app beat -l info
    env_file: .env
    depends_on: [postgres, redis]

  mailhog:
    image: mailhog/mailhog
    ports: ["1025:1025", "8025:8025"]  # SMTP + Web UI

volumes:
  pg_data:
```

### 14.2 Production (Yandex Cloud / AWS)

| Компонент | Yandex Cloud | AWS |
|-----------|-------------|-----|
| API | Compute Instance / Container | ECS Fargate |
| Workers | Compute Instance | ECS Fargate |
| PostgreSQL | Managed PostgreSQL | RDS |
| Redis | Managed Redis | ElastiCache |
| Email | Собственный SMTP + Mailgun | SES |
| Мониторинг | Monitoring + Logging | CloudWatch |
| CI/CD | GitLab CI | GitHub Actions |

### 14.3 Переменные окружения (.env.example)

```bash
# App
OTCLICK_ENVIRONMENT=development
OTCLICK_DEBUG=true
OTCLICK_SECRET_KEY=change-me

# Database
OTCLICK_DATABASE_URL=postgresql+asyncpg://otclick:otclick@localhost:5432/otclick_employer

# Redis
OTCLICK_REDIS_URL=redis://localhost:6379/0

# Celery
OTCLICK_CELERY_BROKER_URL=redis://localhost:6379/1

# LLM Providers (хотя бы один обязателен)
OTCLICK_OPENAI_API_KEY=
OTCLICK_ANTHROPIC_API_KEY=
OTCLICK_QWEN_API_KEY=
OTCLICK_YANDEXGPT_API_KEY=
OTCLICK_YANDEXGPT_FOLDER_ID=

# Email
OTCLICK_SMTP_HOST=localhost
OTCLICK_SMTP_PORT=1025
OTCLICK_SMTP_USER=
OTCLICK_SMTP_PASSWORD=
OTCLICK_SMTP_FROM_EMAIL=outreach@otclick.ru

# Rate Limits
OTCLICK_MAX_EMAILS_PER_SENDER_PER_DAY=50
OTCLICK_MAX_EMAILS_PER_DOMAIN_PER_DAY=5

# External APIs
OTCLICK_HH_API_TOKEN=
OTCLICK_HUNTER_API_KEY=
```

---

## 15. Порядок разработки

### Phase 1: Фундамент (неделя 1-2)

```
☐ pyproject.toml + зависимости
☐ Docker Compose (postgres, redis, mailhog)
☐ app/config/settings.py
☐ app/models/enums.py — все enum'ы
☐ app/models/domain.py — все Pydantic модели
☐ app/models/db.py — SQLAlchemy ORM модели
☐ app/storage/database.py — async engine
☐ app/storage/redis.py — Redis client
☐ migrations/ — Alembic setup + initial migration
☐ app/core/state_machine.py — LeadStateMachine с валидацией
☐ app/core/exceptions.py
☐ app/main.py — FastAPI app factory
☐ app/api/health.py — /health endpoint
☐ tests/unit/test_state_machine.py
```

### Phase 2: Agents + Tools (неделя 3-4)

```
☐ app/llm/models.py — LLMRequest, LLMResponse
☐ app/llm/providers/ — все 4 провайдера (с mock fallback)
☐ app/llm/router.py — LLMRouter
☐ app/agents/base.py — BaseAgent
☐ app/tools/discovery_tools.py — hh.ru API интеграция
☐ app/tools/enrichment_tools.py
☐ app/tools/scoring_tools.py
☐ app/agents/discovery_agent.py
☐ app/agents/enrichment_agent.py
☐ app/agents/scoring_agent.py
☐ app/storage/repositories/ — все репозитории
☐ app/services/lead_service.py
☐ tests/unit/test_scoring.py
☐ tests/unit/test_llm_router.py
```

### Phase 3: Email Engine (неделя 5-6)

```
☐ app/email/templates.py — сегментные контексты
☐ app/email/prompts.py — system prompts
☐ app/email/quality_gate.py — валидация
☐ app/email/engine.py — EmailIntelligenceEngine
☐ app/email/delivery.py — SMTP отправка
☐ app/agents/email_copy_agent.py
☐ app/agents/followup_agent.py
☐ app/services/email_service.py
☐ app/services/compliance_service.py
☐ tests/unit/test_email_quality_gate.py
☐ scripts/test_email_gen.py — CLI тест генерации
```

### Phase 4: Response + Qualification + Handoff (неделя 7-8)

```
☐ app/tools/analysis_tools.py
☐ app/tools/qualification_tools.py
☐ app/tools/handoff_tools.py
☐ app/agents/response_agent.py
☐ app/agents/qualification_agent.py
☐ app/agents/handoff_agent.py
☐ app/services/analytics_service.py
☐ tests/unit/test_reply_classification.py
```

### Phase 5: Orchestrator + Events + API (неделя 9-10)

```
☐ app/events/definitions.py
☐ app/events/handlers.py
☐ app/orchestrator/engine.py — LeadOrchestrator
☐ app/orchestrator/pipeline.py
☐ workers/celery_app.py
☐ workers/discovery_tasks.py
☐ workers/outreach_tasks.py
☐ workers/analysis_tasks.py
☐ workers/scheduled_tasks.py — Celery Beat
☐ app/api/leads.py
☐ app/api/campaigns.py
☐ app/api/emails.py
☐ app/api/handoffs.py
☐ app/api/analytics.py
☐ app/api/webhooks.py
☐ tests/integration/test_full_lifecycle.py
```

### Phase 6: Production hardening (неделя 11-12)

```
☐ Sentry integration
☐ Structured logging (JSON)
☐ Prometheus metrics endpoint
☐ Rate limiting middleware
☐ API authentication (API keys)
☐ Docker production images
☐ CI/CD pipeline
☐ Load testing (locust)
☐ Deployment docs
```

---

## 16. Ключевые решения (ADR)

### ADR-001: Почему 8 агентов, а не 11

**Контекст**: Исходная спецификация предлагала 11 агентов, включая отдельные PersonalizationAgent, ContactDiscoveryAgent, SegmentationAgent.

**Решение**: Объединить до 8. PersonalizationAgent — это шаг внутри EmailCopyAgent. ContactDiscovery — часть EnrichmentAgent. Segmentation — часть ScoringAgent.

**Причина**: Каждый агент = отдельная Celery task = overhead на сериализацию, scheduling, мониторинг. Агент оправдан, когда его задача самостоятельна и может быть retry'нута независимо.

### ADR-002: Events в PostgreSQL, а не in-memory

**Контекст**: Можно было сделать in-memory EventBus или Redis Streams.

**Решение**: Events — это строки в таблице `events` в PostgreSQL. Обработка через Celery tasks.

**Причина**: Audit trail бесплатно. Replay бесплатно. Не теряем события при рестарте. Redis Streams — overengineering для текущего масштаба (< 1000 лидов/день).

### ADR-003: Нет отдельной Memory-абстракции

**Контекст**: Спецификация просила short-term и long-term memory.

**Решение**: PostgreSQL = long-term memory (вся история). Redis = short-term (кеш активных цепочек, rate limit counters, locks). Нет отдельного Memory-сервиса.

**Причина**: Добавление абстракции поверх двух хранилищ без ясного API — это сложность ради сложности. Если понадобится — добавим позже.

### ADR-004: Один enrichment agent вместо трёх

**Контекст**: Можно было сделать отдельно DiscoveryAgent → EnrichmentAgent → ContactAgent.

**Решение**: DiscoveryAgent находит компании. EnrichmentAgent собирает ВСЁ: профиль, вакансии, контакты. Это одна HTTP-сессия к hh.ru API, одна задача.

**Причина**: Контакты почти всегда находятся в тех же источниках, что и вакансии (hh.ru). Разделять — искусственно.

### ADR-005: Quality gate перед каждой отправкой

**Контекст**: Можно было доверять LLM и отправлять сразу.

**Решение**: Обязательная rule-based валидация каждого письма. LLM генерирует, QualityGate проверяет. Не прошло — retry или human review.

**Причина**: LLM может написать "уникальное предложение" или letter длиной 300 слов. Одно спамное письмо портит домен reputation для всех.

---

## 17. Конвенции для Cursor / Claude Code

### Как давать задачи

```
Формат задачи для Cursor:

"Реализуй [файл] согласно ARCHITECTURE.md, раздел [N].
Используй [зависимости]. Добавь тесты в [test_file]."

Пример:
"Реализуй app/agents/scoring_agent.py согласно ARCHITECTURE.md раздел 6.
Агент должен использовать app/tools/scoring_tools.py для расчёта скора
и app/llm/router.py для LLM-вызовов. Тесты в tests/unit/test_scoring.py."
```

### Что давать в контекст

При работе с любым файлом, Claude Code / Cursor должен видеть:
1. Этот файл (`ARCHITECTURE.md`)
2. `app/models/enums.py` — все enum'ы
3. `app/models/domain.py` — все domain models
4. Файл, который реализуется
5. Файлы зависимостей (tools, services, которые agent использует)

### Паттерн создания агента

```python
# 1. Создай tool в app/tools/
async def score_lead(lead, profile, contacts) -> LeadScore: ...

# 2. Создай агента в app/agents/
class ScoringAgent(BaseAgent):
    agent_name = "scoring"
    async def run(self, task: AgentTask) -> AgentResult:
        score = await scoring_tools.score_lead(...)
        segment = await scoring_tools.segment_lead(...)
        return AgentResult(data={"score": score, "segment": segment})

# 3. Создай Celery task в workers/
@celery_app.task
def run_scoring(lead_id: str):
    agent = ScoringAgent(llm_router, db)
    result = await agent.execute(task)
    orchestrator.transition(lead_id, LeadStatus.SCORED)
    event_repo.save(create_event(LEAD_SCORED, lead_id))

# 4. Зарегистрируй в event handlers
EVENT_HANDLERS[LEAD_ENRICHED] = [run_scoring]

# 5. Добавь тест
async def test_scoring_agent_calculates_score(): ...
```

---

*Документ версия: 1.0*
*Последнее обновление: при создании проекта*
*Автор: система + архитектор*
