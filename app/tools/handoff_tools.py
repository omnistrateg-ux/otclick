"""Handoff tools for manager handoff.

Инструменты передачи квалифицированных лидов менеджеру.
"""

import json
import logging
from datetime import datetime, timezone

UTC = timezone.utc

from app.llm.models import LLMRequest
from app.llm.router import LLMRouter
from app.models.domain import (
    CompanyProfile,
    EmailMessage,
    EmployerContact,
    EmployerLead,
    LeadQualification,
    LeadScore,
    LeadSegment,
    LeadSignal,
    ManagerHandoff,
)
from app.models.enums import LLMTaskType, ReplyIntent

logger = logging.getLogger(__name__)


def build_email_summary(emails: list[EmailMessage]) -> list[str]:
    """Build summary of sent emails.

    Args:
        emails: List of sent emails

    Returns:
        List of email summaries
    """
    summaries = []

    for email in emails:
        status_parts = []
        if email.sent_at:
            status_parts.append("отправлено")
        if email.opened:
            status_parts.append(f"открыто {email.open_count}x")
        if email.replied:
            status_parts.append("ответ получен")

        status = ", ".join(status_parts) if status_parts else "не отправлено"
        summary = f"[{email.email_type.value}] {email.subject[:50]}... ({status})"
        summaries.append(summary)

    return summaries


def build_interest_signals(signals: list[LeadSignal]) -> list[str]:
    """Build human-readable interest signals.

    Args:
        signals: Lead signals

    Returns:
        List of signal descriptions
    """
    descriptions = []

    signal_texts = {
        ReplyIntent.READY_TO_CALL: "Готов к звонку",
        ReplyIntent.STRONG_INTEREST: "Сильный интерес",
        ReplyIntent.REQUEST_DETAILS: "Запросил детали/цены",
        ReplyIntent.SOFT_INTEREST: "Мягкий интерес",
    }

    for signal in signals:
        if signal.intent in signal_texts:
            text = signal_texts[signal.intent]
            if signal.raw_text:
                text += f": \"{signal.raw_text[:50]}...\""
            descriptions.append(text)

    return descriptions


def build_company_size_string(profile: CompanyProfile | None) -> str | None:
    """Build human-readable company size.

    Args:
        profile: Company profile

    Returns:
        Size string or None
    """
    if not profile or not profile.employee_count:
        return None

    count = profile.employee_count
    if count < 50:
        return "до 50 сотрудников"
    elif count < 200:
        return "50-200 сотрудников"
    elif count < 500:
        return "200-500 сотрудников"
    elif count < 1000:
        return "500-1000 сотрудников"
    else:
        return "1000+ сотрудников"


async def generate_why_matters(
    lead: EmployerLead,
    profile: CompanyProfile | None,
    score: LeadScore | None,
    signals: list[LeadSignal],
    llm_router: LLMRouter,
) -> str:
    """Generate "why this lead matters" text using LLM.

    Args:
        lead: Lead
        profile: Company profile
        score: Lead score
        signals: Lead signals
        llm_router: LLM router

    Returns:
        Why this lead matters text
    """
    system_prompt = """Ты — помощник менеджера по продажам.
Напиши 2-3 предложения о том, почему этот лид важен и заслуживает внимания.
Будь конкретен, используй факты о компании и сигналы интереса.
Не используй общие фразы типа "перспективный клиент"."""

    signals_text = ", ".join([s.intent.value for s in signals])

    user_prompt = f"""Компания: {lead.company_name}
Город: {lead.city or 'Не указан'}
Отрасль: {profile.industry.value if profile else 'Не определена'}
Размер: {build_company_size_string(profile) or 'Не указан'}
Вакансий: {profile.active_vacancies_count if profile else 'Не указано'}
Скор: {score.total_score if score else 'Не рассчитан'}
Сигналы: {signals_text}

Почему этот лид важен? (2-3 предложения)"""

    request = LLMRequest(
        task_type=LLMTaskType.SUMMARIZATION,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        agent_name="handoff_tools",
    )

    try:
        response = await llm_router.complete(request)
        return response.content.strip()
    except Exception as e:
        logger.warning(f"Failed to generate why_matters: {e}")
        # Fallback
        return f"Компания {lead.company_name} проявила интерес к услугам найма персонала."


async def generate_talking_points(
    lead: EmployerLead,
    profile: CompanyProfile | None,
    segment: LeadSegment | None,
    signals: list[LeadSignal],
    llm_router: LLMRouter,
) -> list[str]:
    """Generate talking points for manager call.

    Args:
        lead: Lead
        profile: Company profile
        segment: Lead segment
        signals: Lead signals
        llm_router: LLM router

    Returns:
        List of talking points
    """
    system_prompt = """Ты — тренер по продажам.
Напиши 3-5 конкретных пунктов для разговора с клиентом.
Каждый пункт — одно предложение.
Фокусируйся на болях клиента и как мы можем помочь.
Ответь JSON: {"talking_points": ["пункт 1", "пункт 2", ...]}"""

    pain = segment.pain_statement if segment else "типичные проблемы найма"
    value = segment.value_proposition if segment else "быстрое закрытие позиций"

    user_prompt = f"""Компания: {lead.company_name}
Отрасль: {profile.industry.value if profile else 'общая'}
Боль: {pain}
Наше предложение: {value}
Сигналы интереса: {', '.join([s.intent.value for s in signals])}

Сгенерируй talking points для звонка."""

    request = LLMRequest(
        task_type=LLMTaskType.SUMMARIZATION,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_mode=True,
        agent_name="handoff_tools",
    )

    try:
        response = await llm_router.complete(request)
        result = json.loads(response.content)
        return result.get("talking_points", [])
    except Exception as e:
        logger.warning(f"Failed to generate talking points: {e}")
        # Fallback
        return [
            f"Уточнить текущие потребности {lead.company_name} в персонале",
            "Рассказать о наших сроках закрытия позиций (48 часов)",
            "Предложить пилотный проект на 10-20 человек",
        ]


def suggest_next_step(
    signals: list[LeadSignal],
    qualification: LeadQualification,
) -> str:
    """Suggest next step for manager.

    Args:
        signals: Lead signals
        qualification: Qualification decision

    Returns:
        Suggested next step
    """
    # Check for ready to call signal
    for signal in signals:
        if signal.intent == ReplyIntent.READY_TO_CALL:
            return "Позвонить как можно скорее — клиент сам просил созвониться"

    # Check for price request
    for signal in signals:
        if signal.intent == ReplyIntent.REQUEST_DETAILS:
            return "Позвонить и предложить короткую презентацию условий и цен"

    # Check for strong interest
    for signal in signals:
        if signal.intent == ReplyIntent.STRONG_INTEREST:
            return "Позвонить, уточнить потребности и предложить демо"

    # Default for soft interest
    return "Позвонить, квалифицировать потребность, предложить следующий шаг"


async def create_handoff(
    lead: EmployerLead,
    profile: CompanyProfile | None,
    contact: EmployerContact,
    segment: LeadSegment | None,
    score: LeadScore | None,
    qualification: LeadQualification,
    signals: list[LeadSignal],
    emails: list[EmailMessage],
    llm_router: LLMRouter | None = None,
) -> ManagerHandoff:
    """Create manager handoff brief.

    Args:
        lead: Lead
        profile: Company profile
        contact: Primary contact
        segment: Lead segment
        score: Lead score
        qualification: Qualification decision
        signals: Lead signals
        emails: Sent emails
        llm_router: LLM router

    Returns:
        Manager handoff
    """
    # Build basic fields
    email_summaries = build_email_summary(emails)
    interest_signals = build_interest_signals(signals)
    company_size = build_company_size_string(profile)
    next_step = suggest_next_step(signals, qualification)

    # Get reply summary
    employer_reply = None
    for signal in signals:
        if signal.raw_text:
            employer_reply = signal.raw_text[:500]
            break

    # Generate LLM content if available
    if llm_router:
        why_matters = await generate_why_matters(
            lead, profile, score, signals, llm_router
        )
        talking_points = await generate_talking_points(
            lead, profile, segment, signals, llm_router
        )
    else:
        why_matters = f"Компания {lead.company_name} проявила интерес к услугам."
        talking_points = [
            "Уточнить потребности в персонале",
            "Рассказать о сроках и условиях",
            "Предложить пилотный проект",
        ]

    return ManagerHandoff(
        lead_id=lead.id,
        qualification_id=qualification.id,
        company_name=lead.company_name,
        contact_name=contact.full_name,
        contact_email=contact.email,
        contact_phone=contact.phone,
        contact_role=contact.role.value,
        segment=profile.industry if profile else segment.segment if segment else None,
        city=lead.city or profile.city if profile else None,
        company_size=company_size,
        hiring_intensity=profile.hiring_intensity.value if profile else None,
        why_this_lead_matters=why_matters,
        lead_score=score.total_score if score else 0.0,
        interest_signals=interest_signals,
        emails_sent_summary=email_summaries,
        employer_reply_summary=employer_reply,
        conversation_history=None,  # TODO: build full conversation
        suggested_next_step=next_step,
        talking_points=talking_points,
    )


async def notify_manager_slack(
    handoff: ManagerHandoff,
    webhook_url: str,
) -> bool:
    """Send handoff notification to Slack.

    Args:
        handoff: Handoff to notify about
        webhook_url: Slack webhook URL

    Returns:
        True if notification sent
    """
    import httpx

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🔥 Новый квалифицированный лид: {handoff.company_name}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Контакт:*\n{handoff.contact_name}"},
                {"type": "mrkdwn", "text": f"*Должность:*\n{handoff.contact_role}"},
                {"type": "mrkdwn", "text": f"*Город:*\n{handoff.city or 'Не указан'}"},
                {"type": "mrkdwn", "text": f"*Скор:*\n{handoff.lead_score:.0f}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Почему важен:*\n{handoff.why_this_lead_matters}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Следующий шаг:*\n{handoff.suggested_next_step}",
            },
        },
    ]

    if handoff.contact_email:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📧 {handoff.contact_email}" +
                        (f" | 📞 {handoff.contact_phone}" if handoff.contact_phone else ""),
            },
        })

    payload = {"blocks": blocks}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=payload,
                timeout=10.0,
            )
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False


async def notify_manager_email(
    handoff: ManagerHandoff,
    manager_email: str,
    smtp_config: dict,
) -> bool:
    """Send handoff notification via email.

    Args:
        handoff: Handoff to notify about
        manager_email: Manager email
        smtp_config: SMTP configuration

    Returns:
        True if notification sent
    """
    from app.email.delivery import EmailDelivery

    delivery = EmailDelivery(**smtp_config)

    subject = f"Новый лид: {handoff.company_name} (скор {handoff.lead_score:.0f})"

    body = f"""Квалифицированный лид готов к звонку.

Компания: {handoff.company_name}
Контакт: {handoff.contact_name} ({handoff.contact_role})
Email: {handoff.contact_email or 'Не указан'}
Телефон: {handoff.contact_phone or 'Не указан'}
Город: {handoff.city or 'Не указан'}
Скор: {handoff.lead_score:.0f}

{handoff.why_this_lead_matters}

Следующий шаг: {handoff.suggested_next_step}

Talking points:
{chr(10).join('• ' + p for p in handoff.talking_points)}
"""

    # Create mock email message for delivery
    from app.models.domain import EmailMessage, EmployerContact
    from app.models.enums import EmailType
    from uuid import uuid4

    email = EmailMessage(
        id=uuid4(),
        sequence_id=uuid4(),
        lead_id=handoff.lead_id,
        contact_id=uuid4(),
        email_type=EmailType.FIRST_TOUCH,
        subject=subject,
        body=body,
        step_number=1,
    )

    contact = EmployerContact(
        id=uuid4(),
        lead_id=handoff.lead_id,
        full_name="Manager",
        email=manager_email,
    )

    try:
        result = await delivery.send_email(email, contact)
        return result.success
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        return False
