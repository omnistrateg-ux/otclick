"""Sales Knowledge Base.

База знаний для B2B sales агента: возражения, отрасли, скрипты продаж.
"""

from dataclasses import dataclass, field
from enum import Enum


class ObjectionType(str, Enum):
    """Types of objections from prospects."""

    PRICE = "price"  # "дорого", "нет бюджета"
    COMPETITOR = "competitor"  # "есть hh", "работаем с другими"
    TIMING = "timing"  # "не сейчас", "позже"
    TRUST = "trust"  # "вы новые", "не знаем вас"
    WHY_FREE = "why_free"  # "почему бесплатно?"
    CANDIDATES = "candidates"  # "много кандидатов?"
    NO_NEED = "no_need"  # "сами справляемся"


class ConversationStage(str, Enum):
    """Stage of the sales conversation."""

    COLD_OUTREACH = "cold_outreach"  # Первое письмо
    FOLLOWUP = "followup"  # Follow-up без ответа
    AFTER_REPLY = "after_reply"  # После получения ответа
    OBJECTION_HANDLING = "objection"  # Обработка возражения
    QUESTION_ANSWERING = "question"  # Ответ на вопрос
    INTEREST_NURTURING = "nurturing"  # Прогрев интереса
    CLOSING = "closing"  # Закрытие на звонок
    HANDOFF_PREP = "handoff"  # Подготовка к передаче менеджеру


@dataclass
class ObjectionHandler:
    """Handler for a specific objection type."""

    objection_type: ObjectionType
    trigger_phrases: list[str]
    response_template: str
    tone: str
    follow_up_cta: str


@dataclass
class IndustryInsight:
    """Industry-specific knowledge for personalization."""

    industry: str
    pain_points: list[str]
    typical_roles: list[str]
    value_angles: list[str]
    proof_points: list[str]


@dataclass
class SalesContact:
    """Manager contact for handoff."""

    name: str
    phone: str
    email: str
    role: str = "Менеджер по работе с клиентами"


# Default objection handlers based on sales scripts
DEFAULT_OBJECTION_HANDLERS: dict[ObjectionType, ObjectionHandler] = {
    ObjectionType.PRICE: ObjectionHandler(
        objection_type=ObjectionType.PRICE,
        trigger_phrases=[
            "дорого",
            "нет бюджета",
            "бюджет не позволяет",
            "слишком дорого",
            "не можем себе позволить",
            "затратно",
            "дороговато",
        ],
        response_template=(
            "Базовое размещение вакансий на Отклике полностью бесплатное — "
            "вы платите только за турбо-продвижение, если нужно срочно закрыть позицию. "
            "Большинство клиентов начинают с бесплатного размещения и подключают турбо по необходимости."
        ),
        tone="supportive",
        follow_up_cta="Попробуете разместить вакансию бесплатно?",
    ),
    ObjectionType.COMPETITOR: ObjectionHandler(
        objection_type=ObjectionType.COMPETITOR,
        trigger_phrases=[
            "есть hh",
            "работаем с hh",
            "hh.ru",
            "headhunter",
            "работаем с другими",
            "уже есть площадка",
            "авито",
            "superjob",
            "используем другой сервис",
        ],
        response_template=(
            "Отлично, что вы уже используете проверенные каналы. "
            "Отклик — дополнительный бесплатный канал именно для линейного персонала: "
            "склад, производство, HoReCa. Наши клиенты используют нас параллельно с hh — "
            "это увеличивает охват без дополнительных затрат."
        ),
        tone="respectful",
        follow_up_cta="Имеет смысл попробовать как дополнительный канал?",
    ),
    ObjectionType.TIMING: ObjectionHandler(
        objection_type=ObjectionType.TIMING,
        trigger_phrases=[
            "не сейчас",
            "позже",
            "через месяц",
            "после нового года",
            "в следующем квартале",
            "не время",
            "сейчас не актуально",
            "вернёмся позже",
            "вернемся позже",
            "пока не планируем",
        ],
        response_template=(
            "Понимаю, сейчас может быть не самое срочное. "
            "Регистрация занимает 2 минуты — аккаунт будет готов, когда понадобится. "
            "Многие клиенты регистрируются заранее, чтобы не терять время, когда вакансия срочная."
        ),
        tone="understanding",
        follow_up_cta="Зарегистрироваться сейчас, чтобы было готово когда нужно?",
    ),
    ObjectionType.TRUST: ObjectionHandler(
        objection_type=ObjectionType.TRUST,
        trigger_phrases=[
            "не знаем вас",
            "вы новые",
            "первый раз слышу",
            "никогда не слышал",
            "не доверяю",
            "нет отзывов",
            "сомневаюсь",
            "не уверен",
        ],
        response_template=(
            "Да, мы молодая платформа, и именно поэтому бьёмся за каждого клиента. "
            "Уже более 500 компаний разместили вакансии за последний месяц. "
            "Среди клиентов — X5 Retail Group, Wildberries, СДЭК. "
            "Вы ничего не теряете — базовое размещение бесплатное."
        ),
        tone="confident",
        follow_up_cta="Готовы попробовать без риска?",
    ),
    ObjectionType.WHY_FREE: ObjectionHandler(
        objection_type=ObjectionType.WHY_FREE,
        trigger_phrases=[
            "почему бесплатно",
            "в чём подвох",
            "что за подвох",
            "где подвох",
            "ничего не бывает бесплатно",
            "за счёт чего",
            "как зарабатываете",
        ],
        response_template=(
            "Базовое размещение бесплатное — мы зарабатываем на турбо-продвижении. "
            "Это когда нужно срочно закрыть вакансию: вакансия поднимается выше в поиске "
            "и попадает в рассылки. Большинство клиентов начинают с бесплатного размещения."
        ),
        tone="transparent",
        follow_up_cta="Хотите попробовать бесплатное размещение?",
    ),
    ObjectionType.CANDIDATES: ObjectionHandler(
        objection_type=ObjectionType.CANDIDATES,
        trigger_phrases=[
            "много кандидатов",
            "есть соискатели",
            "будут отклики",
            "сколько откликов",
            "какой охват",
            "кто у вас",
            "какая аудитория",
        ],
        response_template=(
            "На Отклике зарегистрировано более 2 млн соискателей линейного персонала. "
            "Средний срок закрытия вакансии — 3-5 дней. "
            "Для срочных вакансий есть турбо-продвижение — первые отклики приходят в течение 48 часов."
        ),
        tone="informative",
        follow_up_cta="Хотите разместить вакансию и посмотреть результат?",
    ),
    ObjectionType.NO_NEED: ObjectionHandler(
        objection_type=ObjectionType.NO_NEED,
        trigger_phrases=[
            "сами справляемся",
            "не нужно",
            "справимся сами",
            "есть свои каналы",
            "находим сами",
            "сарафанное радио",
            "знакомые приводят",
        ],
        response_template=(
            "Хорошо, что у вас налажены каналы. "
            "Отклик пригодится когда нужен резерв или срочно закрыть позицию — "
            "мы специализируемся на линейном персонале, где скорость критична. "
            "Регистрация займёт 2 минуты, аккаунт будет на будущее."
        ),
        tone="respectful",
        follow_up_cta="Зарегистрироваться про запас?",
    ),
}


# Default industry insights
DEFAULT_INDUSTRY_INSIGHTS: dict[str, IndustryInsight] = {
    "retail": IndustryInsight(
        industry="retail",
        pain_points=[
            "Высокая текучка кассиров и продавцов",
            "Сезонные пики (новый год, 8 марта, школьный сезон)",
            "Сложно закрывать позиции в регионах",
            "Нужны люди без опыта, но надёжные",
        ],
        typical_roles=[
            "Кассир",
            "Продавец-консультант",
            "Мерчендайзер",
            "Кладовщик",
            "Администратор магазина",
        ],
        value_angles=[
            "Закрываем кассиров за 48 часов",
            "Проверенные соискатели без негативного опыта",
            "Бесплатное размещение без лимитов",
        ],
        proof_points=[
            "X5 Retail Group — клиент с 2024 года",
            "Wildberries закрывает 80% вакансий через Отклик",
            "Средний срок закрытия в ритейле — 3 дня",
        ],
    ),
    "horeca": IndustryInsight(
        industry="horeca",
        pain_points=[
            "Официанты не выходят на смену",
            "Сезонность (лето, праздники)",
            "Нужны люди в ночные смены",
            "Высокая конкуренция за поваров",
        ],
        typical_roles=[
            "Официант",
            "Повар",
            "Бармен",
            "Администратор",
            "Хостес",
            "Мойщик посуды",
        ],
        value_angles=[
            "Срочные позиции за 24 часа",
            "База соискателей с опытом в HoReCa",
            "Отклики на ночные смены",
        ],
        proof_points=[
            "Coffemania закрывает официантов за 2 дня",
            "2000+ ресторанов в Москве используют Отклик",
            "Средний срок закрытия повара — 5 дней",
        ],
    ),
    "logistics": IndustryInsight(
        industry="logistics",
        pain_points=[
            "Водители уходят к конкурентам",
            "Сезон e-commerce (ноябрь-декабрь)",
            "Нужны курьеры с личным авто",
            "Склады открываются в новых локациях",
        ],
        typical_roles=[
            "Курьер",
            "Водитель категории B/C",
            "Экспедитор",
            "Оператор склада",
            "Грузчик",
        ],
        value_angles=[
            "База курьеров с личным транспортом",
            "Срочное закрытие к сезону",
            "Фильтрация по категориям прав",
        ],
        proof_points=[
            "СДЭК закрывает 70% вакансий через Отклик",
            "DPD — клиент с 2023 года",
            "2 дня — среднее время закрытия курьера",
        ],
    ),
    "warehouse": IndustryInsight(
        industry="warehouse",
        pain_points=[
            "Текучка комплектовщиков",
            "Ночные смены никто не хочет",
            "Удалённые склады — никто не едет",
            "Нужно много людей на пик сезона",
        ],
        typical_roles=[
            "Комплектовщик",
            "Кладовщик",
            "Оператор ричтрака",
            "Грузчик",
            "Приёмщик товара",
        ],
        value_angles=[
            "Массовый подбор на склады",
            "Соискатели, готовые на сменный график",
            "Охват по области и пригородам",
        ],
        proof_points=[
            "Ozon закрывает склады за неделю",
            "Wildberries — 500+ вакансий в месяц через нас",
            "Комплектовщик — 2 дня до первого отклика",
        ],
    ),
    "manufacturing": IndustryInsight(
        industry="manufacturing",
        pain_points=[
            "Дефицит рабочих специальностей",
            "Конкуренция за операторов ЧПУ",
            "Вахта — сложно найти людей",
            "Обучаем на месте, но нет кандидатов",
        ],
        typical_roles=[
            "Оператор станка",
            "Сборщик",
            "Упаковщик",
            "Контролёр ОТК",
            "Рабочий на линию",
        ],
        value_angles=[
            "Соискатели без опыта, готовые учиться",
            "Фильтрация по готовности к вахте",
            "Кандидаты из регионов",
        ],
        proof_points=[
            "Северсталь — клиент с 2023 года",
            "ОМК — 200+ закрытых вакансий",
            "4 дня — среднее время закрытия рабочего",
        ],
    ),
}


# Manager contact for handoff
DEFAULT_MANAGER_CONTACT = SalesContact(
    name="Владислав Наков",
    phone="+7 (964) 710-25-72",
    email="team@otclick-hr.ru",
    role="Менеджер по работе с клиентами",
)


class SalesKnowledgeBase:
    """Knowledge base for sales conversations.

    Provides objection handling, industry insights, and manager contacts.
    """

    def __init__(
        self,
        objection_handlers: dict[ObjectionType, ObjectionHandler] | None = None,
        industry_insights: dict[str, IndustryInsight] | None = None,
        manager_contact: SalesContact | None = None,
    ) -> None:
        """Initialize knowledge base.

        Args:
            objection_handlers: Custom objection handlers (uses defaults if None)
            industry_insights: Custom industry insights (uses defaults if None)
            manager_contact: Manager contact for handoff (uses default if None)
        """
        self._objection_handlers = objection_handlers or DEFAULT_OBJECTION_HANDLERS
        self._industry_insights = industry_insights or DEFAULT_INDUSTRY_INSIGHTS
        self._manager_contact = manager_contact or DEFAULT_MANAGER_CONTACT

    def detect_objection(self, text: str) -> ObjectionType | None:
        """Detect objection type from reply text.

        Args:
            text: Reply text from prospect

        Returns:
            Detected objection type or None if no objection detected
        """
        text_lower = text.lower()

        # Check each objection type's trigger phrases
        for objection_type, handler in self._objection_handlers.items():
            for phrase in handler.trigger_phrases:
                if phrase.lower() in text_lower:
                    return objection_type

        return None

    def get_objection_handler(self, objection_type: ObjectionType) -> ObjectionHandler:
        """Get handler for a specific objection type.

        Args:
            objection_type: Type of objection

        Returns:
            Objection handler with response template and CTA
        """
        return self._objection_handlers[objection_type]

    def get_industry_insight(self, industry: str) -> IndustryInsight | None:
        """Get industry-specific insights.

        Args:
            industry: Industry name (lowercase)

        Returns:
            Industry insight or None if not found
        """
        return self._industry_insights.get(industry.lower())

    def get_all_industries(self) -> list[str]:
        """Get list of all available industries.

        Returns:
            List of industry names
        """
        return list(self._industry_insights.keys())

    def get_manager_contact(self) -> SalesContact:
        """Get manager contact for handoff.

        Returns:
            Manager contact information
        """
        return self._manager_contact

    def get_all_objection_types(self) -> list[ObjectionType]:
        """Get list of all objection types.

        Returns:
            List of objection types
        """
        return list(self._objection_handlers.keys())

    def search_objection_by_keyword(self, keyword: str) -> list[ObjectionType]:
        """Search objections by keyword.

        Args:
            keyword: Keyword to search for

        Returns:
            List of matching objection types
        """
        keyword_lower = keyword.lower()
        matches = []

        for objection_type, handler in self._objection_handlers.items():
            for phrase in handler.trigger_phrases:
                if keyword_lower in phrase.lower():
                    if objection_type not in matches:
                        matches.append(objection_type)
                    break

        return matches


# Singleton instance
sales_knowledge_base = SalesKnowledgeBase()
