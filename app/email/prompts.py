"""System prompts for email generation.

Системные промпты для LLM из ARCHITECTURE.md раздел 7.5.
"""

from app.models.enums import EmailType, IndustrySegment

# Базовый системный промпт для генерации писем
BASE_EMAIL_SYSTEM_PROMPT = """Ты — опытный B2B копирайтер, который пишет холодные письма для платформы массового найма «Отклик».

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
   - Эмодзи
   - Слова: "уникальный", "бесплатно", "гарантируем", "эксклюзив", "революционный", "инновационный", "лучший на рынке"

4. CTA — всегда один, всегда вопрос:
   - "Имеет смысл обсудить?"
   - "Актуально для вас сейчас?"
   - "Стоит ли рассказать подробнее?"
   НЕ "Зарегистрируйтесь", НЕ "Скачайте", НЕ "Перейдите по ссылке"

5. ТОН: как умный коллега пишет другому — деловой, но человечный.
   Не маркетолог, не робот, не менеджер по продажам.

6. ЦЕЛЬ: получить ответ, а не продать.

Ответь ТОЛЬКО JSON: {"subject": "...", "body": "..."}"""


# Промпты по типам писем
EMAIL_TYPE_PROMPTS: dict[EmailType, str] = {
    EmailType.FIRST_TOUCH: """
Напиши ПЕРВОЕ письмо (first touch).

Структура:
1. Зацепка про боль компании (1 предложение)
2. Что мы делаем + метрика (1-2 предложения)
3. Proof point (1 предложение)
4. Мягкий CTA-вопрос

Максимум 150 слов. Тема письма до 60 символов, без "!" в конце.
""",
    EmailType.FOLLOWUP_1: """
Напиши ПЕРВЫЙ follow-up (день +3 после первого письма).

Отправлено первое письмо, ответа нет. Нужен другой угол.

Структура:
1. Краткая отсылка к первому письму (1 предложение)
2. Новый угол: social proof или конкретная метрика
3. Мягкий CTA

Максимум 80 слов. Короче первого письма. Тема письма до 60 символов.
""",
    EmailType.FOLLOWUP_2: """
Напиши ВТОРОЙ follow-up (день +7 после первого письма).

Два письма без ответа. Последняя попытка перед breakup.

Структура:
1. Ещё один угол или мини-кейс
2. Альтернатива: может быть, кто-то другой отвечает за подбор?
3. Мягкий CTA

Максимум 80 слов. Тема письма до 60 символов.
""",
    EmailType.BREAKUP: """
Напиши BREAKUP письмо (день +14).

Это последнее письмо в цепочке. Мягкое закрытие.

Структура:
1. Понимаю, что сейчас не до этого
2. Если понадобится — я на связи
3. Без давления

Максимум 50 слов. Самое короткое письмо. Тема письма до 60 символов.
""",
}


# Дополнительный контекст по отраслям
SEGMENT_PROMPTS: dict[IndustrySegment, str] = {
    IndustrySegment.RETAIL: """
Отрасль: РИТЕЙЛ (розничные сети)
Типичные позиции: кассиры, продавцы, мерчандайзеры
Боли: сезонные пики, текучка 80%+, сложности с графиком в пиковые часы
Наш фокус: скорость закрытия (48ч), явка 94%
""",
    IndustrySegment.HORECA: """
Отрасль: HORECA (рестораны, кафе, отели)
Типичные позиции: повара, официанты, бармены
Боли: невыходы 25-30%, срочные замены в день обращения, текучка
Наш фокус: надёжность (рейтинг), замена за 4 часа
""",
    IndustrySegment.LOGISTICS: """
Отрасль: ЛОГИСТИКА (доставка, транспорт)
Типичные позиции: курьеры, водители кат. B/C
Боли: пиковые нагрузки, масштабирование под сезон
Наш фокус: масштабирование за 24ч, 200 курьеров в неделю
""",
    IndustrySegment.WAREHOUSE: """
Отрасль: СКЛАД (складские операторы)
Типичные позиции: комплектовщики, грузчики
Боли: пиковые нагрузки, срочный набор под сезон
Наш фокус: 200 комплектовщиков в неделю, масштабирование за 24ч
""",
    IndustrySegment.CONSTRUCTION: """
Отрасль: СТРОЙКА (строительные компании)
Типичные позиции: разнорабочие, бетонщики
Боли: бригады с документами за 24ч, compliance, допуски
Наш фокус: бригады с документами, формируем под объект
""",
    IndustrySegment.MANUFACTURING: """
Отрасль: ПРОИЗВОДСТВО (заводы, фабрики)
Типичные позиции: операторы линий, упаковщики
Боли: покрытие смен, ночные/выходные, стабильность состава
Наш фокус: операторы под график смен, стабильный пул
""",
    IndustrySegment.TRADE: """
Отрасль: ТОРГОВЛЯ (оптовая и розничная)
Типичные позиции: продавцы-консультанты, кладовщики
Боли: текучка, быстрое закрытие после увольнений
Наш фокус: продавцы за 48ч, закрытие 2 дня
""",
    IndustrySegment.OTHER: """
Отрасль: ДРУГОЕ
Типичные позиции: линейный персонал
Боли: текучка, срочные замены
Наш фокус: линейные позиции за 48ч, явка 94%
""",
}


def build_email_prompt(
    email_type: EmailType,
    segment: IndustrySegment,
    company_name: str,
    contact_name: str | None,
    city: str | None,
    pain_statement: str | None,
    value_proposition: str | None,
    proof_point: str | None,
    personalization_hooks: list[str] | None = None,
    previous_emails: list[dict] | None = None,
) -> tuple[str, str]:
    """Build system and user prompts for email generation.

    Args:
        email_type: Type of email to generate
        segment: Industry segment
        company_name: Company name
        contact_name: Contact person name
        city: City
        pain_statement: Custom pain statement
        value_proposition: Custom value proposition
        proof_point: Custom proof point
        personalization_hooks: Hooks for personalization
        previous_emails: Previous emails in sequence (for follow-ups)

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = BASE_EMAIL_SYSTEM_PROMPT

    # Build user prompt
    user_parts = [
        EMAIL_TYPE_PROMPTS.get(email_type, EMAIL_TYPE_PROMPTS[EmailType.FIRST_TOUCH]),
        SEGMENT_PROMPTS.get(segment, SEGMENT_PROMPTS[IndustrySegment.OTHER]),
    ]

    user_parts.append(f"\nКомпания: {company_name}")

    if contact_name:
        user_parts.append(f"Контакт: {contact_name}")

    if city:
        user_parts.append(f"Город: {city}")

    if pain_statement:
        user_parts.append(f"\nКастомная боль: {pain_statement}")

    if value_proposition:
        user_parts.append(f"Ценностное предложение: {value_proposition}")

    if proof_point:
        user_parts.append(f"Proof point: {proof_point}")

    if personalization_hooks:
        hooks_str = "; ".join(personalization_hooks[:3])
        user_parts.append(f"\nФакты для персонализации: {hooks_str}")

    if previous_emails and email_type != EmailType.FIRST_TOUCH:
        user_parts.append("\n--- Предыдущие письма ---")
        for i, email in enumerate(previous_emails, 1):
            user_parts.append(f"\nПисьмо {i}:")
            user_parts.append(f"Тема: {email.get('subject', '')}")
            user_parts.append(f"Текст: {email.get('body', '')[:200]}...")

    user_parts.append("\n\nСгенерируй письмо в формате JSON: {\"subject\": \"...\", \"body\": \"...\"}")

    user_prompt = "\n".join(user_parts)

    return system_prompt, user_prompt


def build_response_analysis_prompt(reply_text: str) -> tuple[str, str]:
    """Build prompt for analyzing email reply.

    Args:
        reply_text: Text of the reply

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = """Ты — эксперт по анализу email-ответов в B2B продажах.

Твоя задача — классифицировать ответ по намерению (intent).

Возможные intent:
- "auto_reply": автоответ (отпуск, командировка, не работаю)
- "neutral": нейтральный ответ без явного интереса или отказа ("спасибо, посмотрим")
- "refusal": явный отказ ("не интересно", "не актуально")
- "soft_interest": мягкий интерес ("интересно, но не сейчас", "может быть позже")
- "request_details": запрос деталей ("сколько стоит?", "как это работает?")
- "strong_interest": сильный интерес ("расскажите подробнее", "интересно")
- "ready_to_call": готов к звонку ("давайте созвонимся", "когда удобно позвонить?")
- "unsubscribe": просьба отписать ("отпишите меня", "не пишите больше")
- "wrong_person": не тот человек ("это не ко мне", "напишите X")

Ответь JSON: {"intent": "...", "confidence": 0.0-1.0, "summary": "краткое резюме"}"""

    user_prompt = f"""Проанализируй этот ответ на холодное письмо:

---
{reply_text}
---

Определи intent и уверенность. Ответь JSON."""

    return system_prompt, user_prompt
