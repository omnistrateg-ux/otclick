"""Analysis Celery tasks.

Задачи для анализа ответов и квалификации лидов.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from celery import shared_task

from app.events.definitions import EventType, create_event
from app.models.enums import LeadStatus
from app.orchestrator.engine import LeadOrchestrator
from workers.celery_app import celery_app

# Python 3.10 compatibility
UTC = timezone.utc

logger = logging.getLogger(__name__)


@shared_task(
    name="workers.analysis_tasks.analyze_reply",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def analyze_reply(
    self,
    email_id: str,
    lead_id: str | None = None,
    reply_text: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Analyze email reply.

    Args:
        email_id: Email ID that was replied to
        lead_id: Lead ID
        reply_text: Reply content

    Returns:
        Analysis results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.agents.response_agent import ResponseAgent
        from app.llm.router import get_router
        from app.storage.database import async_session_factory
        from app.storage.repositories.email_repo import EmailRepository
        from app.storage.repositories.lead_repo import LeadRepository

        async with async_session_factory() as db:
            # Get email and lead
            email_repo = EmailRepository(db)
            lead_repo = LeadRepository(db)

            email = await email_repo.get(email_id)
            if not email:
                return {"success": False, "error": "Email not found"}

            lead_id_resolved = lead_id or email.lead_id
            lead = await lead_repo.get(lead_id_resolved)
            if not lead:
                return {"success": False, "error": "Lead not found"}

            # Mark lead as replied
            if lead.status == LeadStatus.OUTREACH_STARTED:
                orchestrator = LeadOrchestrator()
                lead, event = orchestrator.record_reply(
                    lead,
                    email_id=email_id,
                    reply_text=reply_text,
                    actor="analysis_task",
                )
                await lead_repo.update(lead)

            # Analyze reply
            llm_router = get_router()
            response_agent = ResponseAgent(llm_router=llm_router, db=db)

            from app.models.domain import AgentTask

            task = AgentTask(
                agent_name="response",
                input_data={
                    "email_id": email_id,
                    "lead_id": lead_id_resolved,
                    "reply_text": reply_text,
                },
            )

            result = await response_agent.execute(task)

            if result.success:
                intent = result.data.get("intent", "neutral")
                confidence = result.data.get("confidence", 0.5)

                # Trigger qualification
                qualify_lead.delay(
                    lead_id=lead_id_resolved,
                    intent=intent,
                    confidence=confidence,
                )

                logger.info(
                    f"Analyzed reply for lead {lead_id_resolved}: "
                    f"intent={intent}, confidence={confidence}"
                )

                return {
                    "success": True,
                    "lead_id": lead_id_resolved,
                    "intent": intent,
                    "confidence": confidence,
                    "summary": result.data.get("summary"),
                }

            return {"success": False, "error": result.error}

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(
    name="workers.analysis_tasks.qualify_lead",
    bind=True,
    max_retries=2,
)
def qualify_lead(
    self,
    lead_id: str,
    intent: str | None = None,
    confidence: float | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Qualify lead based on reply analysis.

    Args:
        lead_id: Lead ID
        intent: Detected intent
        confidence: Confidence score

    Returns:
        Qualification results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.agents.qualification_agent import QualificationAgent
        from app.llm.router import get_router
        from app.storage.database import async_session_factory
        from app.storage.repositories.lead_repo import LeadRepository

        async with async_session_factory() as db:
            lead_repo = LeadRepository(db)
            lead = await lead_repo.get(lead_id)

            if not lead:
                return {"success": False, "error": "Lead not found"}

            llm_router = get_router()
            qual_agent = QualificationAgent(llm_router=llm_router, db=db)

            from app.models.domain import AgentTask

            task = AgentTask(
                agent_name="qualification",
                input_data={
                    "lead_id": lead_id,
                    "intent": intent,
                    "confidence": confidence,
                },
            )

            result = await qual_agent.execute(task)

            if result.success:
                is_qualified = result.data.get("is_qualified", False)

                # Trigger next action
                from workers.outreach_tasks import handle_qualification_result

                handle_qualification_result.delay(
                    lead_id=lead_id,
                    intent=intent or "neutral",
                    confidence=confidence or 0.5,
                )

                logger.info(
                    f"Qualified lead {lead_id}: "
                    f"qualified={is_qualified}"
                )

                return {
                    "success": True,
                    "lead_id": lead_id,
                    "is_qualified": is_qualified,
                    "reason": result.data.get("reason"),
                    "next_steps": result.data.get("next_steps"),
                }

            return {"success": False, "error": result.error}

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(name="workers.analysis_tasks.track_email_delivery")
def track_email_delivery(
    email_id: str,
    status: str = "delivered",
    **kwargs: Any,
) -> dict[str, Any]:
    """Track email delivery status.

    Args:
        email_id: Email ID
        status: Delivery status

    Returns:
        Tracking results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.storage.database import async_session_factory
        from app.storage.repositories.email_repo import EmailRepository

        async with async_session_factory() as db:
            email_repo = EmailRepository(db)
            email = await email_repo.get(email_id)

            if not email:
                return {"success": False, "error": "Email not found"}

            # Update email status
            email.delivery_status = status
            await email_repo.update(email)

            # Emit event
            event_type = {
                "delivered": EventType.EMAIL_DELIVERED,
                "bounced": EventType.EMAIL_BOUNCED,
                "failed": EventType.EMAIL_FAILED,
            }.get(status, EventType.EMAIL_DELIVERED)

            event = create_event(
                event_type,
                email_id=email_id,
                lead_id=email.lead_id,
                data={"status": status},
            )

            logger.info(f"Email {email_id} delivery status: {status}")

            return {
                "success": True,
                "email_id": email_id,
                "status": status,
            }

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(name="workers.analysis_tasks.track_email_open")
def track_email_open(
    email_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Track email open event.

    Args:
        email_id: Email ID

    Returns:
        Tracking results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.storage.database import async_session_factory
        from app.storage.repositories.email_repo import EmailRepository

        async with async_session_factory() as db:
            email_repo = EmailRepository(db)
            email = await email_repo.get(email_id)

            if not email:
                return {"success": False, "error": "Email not found"}

            # Update email
            if not email.opened_at:
                email.opened_at = datetime.utcnow()
                await email_repo.update(email)

                event = create_event(
                    EventType.EMAIL_OPENED,
                    email_id=email_id,
                    lead_id=email.lead_id,
                )

                logger.info(f"Email {email_id} opened")

            return {
                "success": True,
                "email_id": email_id,
                "opened": True,
            }

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(name="workers.analysis_tasks.track_email_click")
def track_email_click(
    email_id: str,
    link_url: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Track email link click.

    Args:
        email_id: Email ID
        link_url: Clicked URL

    Returns:
        Tracking results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.storage.database import async_session_factory
        from app.storage.repositories.email_repo import EmailRepository

        async with async_session_factory() as db:
            email_repo = EmailRepository(db)
            email = await email_repo.get(email_id)

            if not email:
                return {"success": False, "error": "Email not found"}

            # Update email
            if not email.clicked_at:
                email.clicked_at = datetime.utcnow()
                await email_repo.update(email)

            event = create_event(
                EventType.EMAIL_CLICKED,
                email_id=email_id,
                lead_id=email.lead_id,
                data={"link_url": link_url},
            )

            logger.info(f"Email {email_id} link clicked: {link_url}")

            return {
                "success": True,
                "email_id": email_id,
                "clicked": True,
                "link_url": link_url,
            }

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(name="workers.analysis_tasks.process_bounce")
def process_bounce(
    email_id: str,
    bounce_type: str = "hard",
    bounce_reason: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Process email bounce.

    Args:
        email_id: Email ID
        bounce_type: Bounce type (hard/soft)
        bounce_reason: Bounce reason

    Returns:
        Processing results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.services.compliance_service import ComplianceService
        from app.storage.database import async_session_factory
        from app.storage.repositories.email_repo import EmailRepository
        from app.storage.repositories.lead_repo import LeadRepository

        async with async_session_factory() as db:
            email_repo = EmailRepository(db)
            email = await email_repo.get(email_id)

            if not email:
                return {"success": False, "error": "Email not found"}

            # Update email status
            email.delivery_status = "bounced"
            email.bounce_type = bounce_type
            email.bounce_reason = bounce_reason
            await email_repo.update(email)

            # For hard bounces, add to blacklist
            if bounce_type == "hard" and email.to_email:
                compliance = ComplianceService()
                await compliance.add_to_blacklist(
                    email.to_email,
                    reason=f"Hard bounce: {bounce_reason}",
                )

            # Update lead if needed
            if email.lead_id:
                lead_repo = LeadRepository(db)
                lead = await lead_repo.get(email.lead_id)

                if lead and bounce_type == "hard":
                    # Mark lead as having invalid contact
                    lead.contact_valid = False
                    await lead_repo.update(lead)

            logger.warning(
                f"Email {email_id} bounced ({bounce_type}): {bounce_reason}"
            )

            return {
                "success": True,
                "email_id": email_id,
                "bounce_type": bounce_type,
                "bounce_reason": bounce_reason,
            }

    return asyncio.get_event_loop().run_until_complete(_run())
