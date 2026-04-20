"""Analysis Celery tasks.

Задачи для анализа ответов и квалификации лидов.

IMPORTANT: All status changes MUST go through LeadOrchestrator.
Direct status assignments are prohibited.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from celery import shared_task

from app.events.definitions import EventType, create_event
from app.models.enums import LeadStatus
from app.orchestrator.engine import LeadOrchestrator, generate_pipeline_run_id
from workers.celery_app import celery_app

# Python 3.10 compatibility
UTC = timezone.utc

logger = logging.getLogger(__name__)


def _log_task_failure(task_name: str, identifier: str, exc: Exception, run_id: str | None = None) -> None:
    """Log task failure with structured data."""
    logger.error(
        f"Task {task_name} FAILED | id={identifier} | "
        f"error={type(exc).__name__}: {exc}"
        + (f" | run_id={run_id}" if run_id else ""),
        exc_info=True,
    )


@shared_task(
    name="workers.analysis_tasks.analyze_reply",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def analyze_reply(
    self,
    email_id: str,
    lead_id: str | None = None,
    reply_text: str | None = None,
    pipeline_run_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Analyze email reply.

    Args:
        email_id: Email ID that was replied to
        lead_id: Lead ID
        reply_text: Reply content
        pipeline_run_id: Pipeline run ID for idempotency

    Returns:
        Analysis results
    """
    import asyncio

    run_id = pipeline_run_id or generate_pipeline_run_id()

    async def _run() -> dict[str, Any]:
        from app.agents.response_agent import ResponseAgent
        from app.llm.router import get_router
        from app.storage.database import async_session_factory
        from app.storage.redis import check_pipeline_step, distributed_lock
        from app.storage.repositories.email_repo import EmailRepository
        from app.storage.repositories.lead_repo import LeadRepository

        # Pipeline step idempotency check
        if await check_pipeline_step(email_id, "analyze_reply", run_id):
            logger.info(f"analyze_reply for email {email_id} already processed in run {run_id}")
            return {"success": True, "skipped": True, "reason": "duplicate_step", "run_id": run_id}

        async with async_session_factory() as db:
            # Get email and lead
            email_repo = EmailRepository(db)
            lead_repo = LeadRepository(db)

            email = await email_repo.get(email_id)
            if not email:
                return {"success": False, "error": "Email not found"}

            lead_id_resolved = lead_id or email.lead_id

            async with distributed_lock(f"lead:{lead_id_resolved}:analyze") as acquired:
                if not acquired:
                    return {"success": False, "error": "Lock not acquired", "retry": True}

                # Use SELECT FOR UPDATE
                lead = await lead_repo.get_for_update(lead_id_resolved)
                if not lead:
                    return {"success": False, "error": "Lead not found"}

                # Mark lead as replied via orchestrator
                if lead.status in [LeadStatus.OUTREACH_SENT, LeadStatus.IN_SEQUENCE]:
                    orchestrator = LeadOrchestrator()
                    lead, event = orchestrator.record_reply(
                        lead,
                        email_id=email_id,
                        reply_text=reply_text,
                        actor="analysis_task",
                    )
                    await lead_repo.update(lead)
                    await db.commit()

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

                    # Trigger qualification with same run_id
                    qualify_lead.delay(
                        lead_id=lead_id_resolved,
                        intent=intent,
                        confidence=confidence,
                        pipeline_run_id=run_id,
                    )

                    logger.info(
                        f"Analyzed reply for lead {lead_id_resolved}: "
                        f"intent={intent}, confidence={confidence} | run_id={run_id}"
                    )

                    return {
                        "success": True,
                        "lead_id": lead_id_resolved,
                        "run_id": run_id,
                        "intent": intent,
                        "confidence": confidence,
                        "summary": result.data.get("summary"),
                    }

                return {"success": False, "error": result.error}

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        _log_task_failure("analyze_reply", email_id, exc, run_id)
        raise self.retry(exc=exc)


@shared_task(
    name="workers.analysis_tasks.qualify_lead",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def qualify_lead(
    self,
    lead_id: str,
    intent: str | None = None,
    confidence: float | None = None,
    pipeline_run_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Qualify lead based on reply analysis.

    Args:
        lead_id: Lead ID
        intent: Detected intent
        confidence: Confidence score
        pipeline_run_id: Pipeline run ID for idempotency

    Returns:
        Qualification results
    """
    import asyncio

    run_id = pipeline_run_id or generate_pipeline_run_id()

    async def _run() -> dict[str, Any]:
        from app.agents.qualification_agent import QualificationAgent
        from app.llm.router import get_router
        from app.storage.database import async_session_factory
        from app.storage.redis import check_pipeline_step, distributed_lock
        from app.storage.repositories.lead_repo import LeadRepository

        # Pipeline step idempotency check
        if await check_pipeline_step(lead_id, "analysis_qualify", run_id):
            logger.info(f"qualify_lead (analysis) for {lead_id} already processed in run {run_id}")
            return {"success": True, "skipped": True, "reason": "duplicate_step", "run_id": run_id}

        async with distributed_lock(f"lead:{lead_id}:analysis_qualify") as acquired:
            if not acquired:
                return {"success": False, "error": "Lock not acquired", "retry": True}

            async with async_session_factory() as db:
                lead_repo = LeadRepository(db)

                # Use SELECT FOR UPDATE
                lead = await lead_repo.get_for_update(lead_id)

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

                    # Trigger next action with same run_id
                    from workers.outreach_tasks import handle_qualification_result

                    handle_qualification_result.delay(
                        lead_id=lead_id,
                        intent=intent or "neutral",
                        confidence=confidence or 0.5,
                        pipeline_run_id=run_id,
                    )

                    logger.info(
                        f"Qualified lead {lead_id}: qualified={is_qualified} | run_id={run_id}"
                    )

                    return {
                        "success": True,
                        "lead_id": lead_id,
                        "run_id": run_id,
                        "is_qualified": is_qualified,
                        "reason": result.data.get("reason"),
                        "next_steps": result.data.get("next_steps"),
                    }

                return {"success": False, "error": result.error}

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        _log_task_failure("qualify_lead", lead_id, exc, run_id)
        raise self.retry(exc=exc)


@shared_task(
    name="workers.analysis_tasks.track_email_delivery",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def track_email_delivery(
    self,
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
        from app.storage.redis import check_idempotency
        from app.storage.repositories.email_repo import EmailRepository

        # Idempotency check
        if await check_idempotency(f"email_delivery:{status}", email_id):
            logger.info(f"track_email_delivery {status} for {email_id} already processed")
            return {"success": True, "skipped": True, "reason": "idempotency"}

        async with async_session_factory() as db:
            email_repo = EmailRepository(db)
            email = await email_repo.get(email_id)

            if not email:
                return {"success": False, "error": "Email not found"}

            # Update email status
            email.delivery_status = status
            await email_repo.update(email)
            await db.commit()

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

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        _log_task_failure("track_email_delivery", email_id, exc)
        raise self.retry(exc=exc)


@shared_task(
    name="workers.analysis_tasks.track_email_open",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def track_email_open(
    self,
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
        from app.storage.redis import check_idempotency
        from app.storage.repositories.email_repo import EmailRepository

        # Idempotency - only track first open
        if await check_idempotency("email_open", email_id, ttl=86400 * 7):
            return {"success": True, "skipped": True, "reason": "already_opened"}

        async with async_session_factory() as db:
            email_repo = EmailRepository(db)
            email = await email_repo.get(email_id)

            if not email:
                return {"success": False, "error": "Email not found"}

            # Update email
            if not email.opened_at:
                email.opened_at = datetime.now(UTC)
                await email_repo.update(email)
                await db.commit()

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

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        _log_task_failure("track_email_open", email_id, exc)
        raise self.retry(exc=exc)


@shared_task(
    name="workers.analysis_tasks.track_email_click",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def track_email_click(
    self,
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
        from app.storage.redis import check_idempotency
        from app.storage.repositories.email_repo import EmailRepository

        # Idempotency - only track first click
        if await check_idempotency("email_click", email_id, ttl=86400 * 7):
            return {"success": True, "skipped": True, "reason": "already_clicked"}

        async with async_session_factory() as db:
            email_repo = EmailRepository(db)
            email = await email_repo.get(email_id)

            if not email:
                return {"success": False, "error": "Email not found"}

            # Update email
            if not email.clicked_at:
                email.clicked_at = datetime.now(UTC)
                await email_repo.update(email)
                await db.commit()

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

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        _log_task_failure("track_email_click", email_id, exc)
        raise self.retry(exc=exc)


@shared_task(
    name="workers.analysis_tasks.process_bounce",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def process_bounce(
    self,
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
        from app.storage.redis import check_idempotency, distributed_lock
        from app.storage.repositories.email_repo import EmailRepository
        from app.storage.repositories.lead_repo import LeadRepository

        # Idempotency check
        if await check_idempotency("email_bounce", email_id):
            logger.info(f"process_bounce for {email_id} already processed")
            return {"success": True, "skipped": True, "reason": "idempotency"}

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

            # Update lead if needed - transition to BOUNCED status
            if email.lead_id:
                lead_repo = LeadRepository(db)

                async with distributed_lock(f"lead:{email.lead_id}:bounce") as acquired:
                    if acquired:
                        lead = await lead_repo.get_for_update(email.lead_id)

                        if lead and bounce_type == "hard":
                            # Mark lead as bounced via orchestrator
                            orchestrator = LeadOrchestrator()
                            if lead.status in [LeadStatus.OUTREACH_SENT, LeadStatus.IN_SEQUENCE]:
                                lead, event = orchestrator.transition(
                                    lead,
                                    LeadStatus.BOUNCED,
                                    actor="bounce_handler",
                                    reason=f"Hard bounce: {bounce_reason}",
                                )
                                await lead_repo.update(lead)

            await db.commit()

            logger.warning(
                f"Email {email_id} bounced ({bounce_type}): {bounce_reason}"
            )

            return {
                "success": True,
                "email_id": email_id,
                "bounce_type": bounce_type,
                "bounce_reason": bounce_reason,
            }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        _log_task_failure("process_bounce", email_id, exc)
        raise self.retry(exc=exc)
