"""Outreach Celery tasks.

Задачи для email outreach и follow-up.

IMPORTANT: All status changes MUST go through LeadOrchestrator.
Direct status assignments are prohibited.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

# Python 3.10 compatibility
UTC = timezone.utc

from celery import shared_task

from app.events.definitions import EventType, create_event
from app.models.enums import EmailType, LeadStatus, ReplyIntent
from app.observability import TracedTask, record_step_error
from app.orchestrator.engine import LeadOrchestrator, generate_pipeline_run_id
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _trace_error(lead_id: str, run_id: str, step: str, exc: Exception) -> None:
    """Record error to trace and log."""
    await record_step_error(lead_id, run_id, step, exc)
    logger.error(
        f"Task {step} FAILED | lead_id={lead_id} | run_id={run_id} | "
        f"error={type(exc).__name__}: {exc}",
        exc_info=True,
    )


@shared_task(
    name="workers.outreach_tasks.start_outreach",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def start_outreach(
    self,
    lead_id: str,
    campaign_id: str | None = None,
    pipeline_run_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Start outreach sequence for a qualified lead.

    Args:
        lead_id: Lead ID
        campaign_id: Optional campaign ID
        pipeline_run_id: Pipeline run ID for idempotency

    Returns:
        Outreach start results
    """
    import asyncio

    run_id = pipeline_run_id or generate_pipeline_run_id()
    step_name = "outreach"

    async def _run() -> dict[str, Any]:
        from app.agents.email_copy_agent import EmailCopyAgent
        from app.llm.router import get_router
        from app.observability import record_step_skipped
        from app.services.compliance_service import ComplianceService
        from app.services.email_service import EmailService
        from app.storage.database import async_session_factory
        from app.storage.redis import check_pipeline_step, distributed_lock
        from app.storage.repositories.lead_repo import LeadRepository

        tracer = TracedTask(lead_id, run_id, step_name)

        # Pipeline step idempotency check
        if await check_pipeline_step(lead_id, step_name, run_id):
            await record_step_skipped(lead_id, run_id, step_name, "duplicate_step")
            return {"success": True, "skipped": True, "reason": "duplicate_step", "run_id": run_id}

        await tracer.start()

        # Distributed lock
        async with distributed_lock(f"lead:{lead_id}:outreach") as acquired:
            if not acquired:
                await tracer.skip("lock_not_acquired")
                return {"success": False, "error": "Lock not acquired", "retry": True}

            async with async_session_factory() as db:
                lead_repo = LeadRepository(db)

                # Use SELECT FOR UPDATE
                lead = await lead_repo.get_for_update(lead_id)

                if not lead:
                    await tracer.error("Lead not found")
                    return {"success": False, "error": "Lead not found"}

                if lead.status != LeadStatus.EMAIL_READY:
                    await tracer.skip(f"wrong_status:{lead.status.value}")
                    return {"success": True, "skipped": True, "reason": "wrong_status"}

                # Check compliance
                compliance = ComplianceService()
                if not await compliance.can_send_email(lead_id, lead.contacts[0].email if lead.contacts else None):
                    await tracer.error("Compliance check failed")
                    return {"success": False, "error": "Compliance check failed"}

                # Generate first touch email
                llm_router = get_router()
                email_agent = EmailCopyAgent(llm_router=llm_router, db=db)

                from app.models.domain import AgentTask

                task = AgentTask(
                    agent_name="email_copy",
                    input_data={
                        "lead_id": lead_id,
                        "email_type": EmailType.FIRST_TOUCH.value,
                    },
                )

                result = await email_agent.execute(task)

                if result.success:
                    email_service = EmailService(db=db)

                    # Send email
                    email = await email_service.send_email(
                        lead_id=lead_id,
                        to_email=lead.contacts[0].email if lead.contacts else None,
                        subject=result.data.get("subject", ""),
                        body=result.data.get("body", ""),
                        email_type=EmailType.FIRST_TOUCH,
                        campaign_id=campaign_id,
                    )

                    # Transition lead via orchestrator
                    orchestrator = LeadOrchestrator()
                    lead, event = orchestrator.start_outreach(
                        lead,
                        campaign_id=campaign_id,
                        actor="outreach_task",
                    )
                    await lead_repo.update(lead)
                    await db.commit()

                    # Schedule first follow-up with same run_id
                    schedule_followup.apply_async(
                        kwargs={"lead_id": lead_id, "sequence_number": 1, "pipeline_run_id": run_id},
                        countdown=3 * 24 * 60 * 60,  # 3 days
                    )

                    await tracer.success({
                        "email_id": str(email.id) if email else None,
                        "campaign_id": campaign_id,
                    })

                    return {
                        "success": True,
                        "lead_id": lead_id,
                        "run_id": run_id,
                        "email_id": email.id if email else None,
                        "followup_scheduled": True,
                    }

                await tracer.error(result.error or "Email generation failed")
                return {
                    "success": False,
                    "lead_id": lead_id,
                    "run_id": run_id,
                    "error": result.error,
                }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        asyncio.get_event_loop().run_until_complete(
            _trace_error(lead_id, run_id, step_name, exc)
        )
        raise self.retry(exc=exc)


@shared_task(
    name="workers.outreach_tasks.schedule_followup",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def schedule_followup(
    self,
    lead_id: str,
    sequence_number: int = 1,
    pipeline_run_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Schedule a follow-up email.

    Args:
        lead_id: Lead ID
        sequence_number: Sequence number (1-3)
        pipeline_run_id: Pipeline run ID for idempotency

    Returns:
        Scheduling results
    """
    run_id = pipeline_run_id or generate_pipeline_run_id()

    # Calculate delay based on sequence number
    delays = {
        1: 3 * 24 * 60 * 60,  # 3 days
        2: 7 * 24 * 60 * 60,  # 7 days
        3: 14 * 24 * 60 * 60,  # 14 days
    }

    delay = delays.get(sequence_number, delays[3])

    send_followup.apply_async(
        kwargs={
            "lead_id": lead_id,
            "sequence_number": sequence_number,
            "pipeline_run_id": run_id,
        },
        countdown=delay,
    )

    send_at = datetime.now(UTC) + timedelta(seconds=delay)

    logger.info(
        f"Scheduled followup #{sequence_number} for lead {lead_id} at {send_at} | run_id={run_id}"
    )

    return {
        "success": True,
        "lead_id": lead_id,
        "run_id": run_id,
        "sequence_number": sequence_number,
        "scheduled_at": send_at.isoformat(),
    }


@shared_task(
    name="workers.outreach_tasks.send_followup",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def send_followup(
    self,
    lead_id: str,
    sequence_number: int,
    pipeline_run_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Send a follow-up email.

    Args:
        lead_id: Lead ID
        sequence_number: Sequence number
        pipeline_run_id: Pipeline run ID for idempotency

    Returns:
        Send results
    """
    import asyncio

    run_id = pipeline_run_id or generate_pipeline_run_id()
    step_name = f"followup_{sequence_number}"

    async def _run() -> dict[str, Any]:
        from app.agents.followup_agent import FollowUpAgent
        from app.llm.router import get_router
        from app.services.compliance_service import ComplianceService
        from app.services.email_service import EmailService
        from app.storage.database import async_session_factory
        from app.storage.redis import check_pipeline_step, distributed_lock
        from app.storage.repositories.lead_repo import LeadRepository

        # Pipeline step idempotency check
        if await check_pipeline_step(lead_id, step_name, run_id):
            logger.info(f"send_followup #{sequence_number} for {lead_id} already processed in run {run_id}")
            return {"success": True, "skipped": True, "reason": "duplicate_step", "run_id": run_id}

        async with distributed_lock(f"lead:{lead_id}:followup:{sequence_number}") as acquired:
            if not acquired:
                logger.warning(f"Could not acquire lock for lead {lead_id} followup #{sequence_number}")
                return {"success": False, "error": "Lock not acquired", "retry": True}

            async with async_session_factory() as db:
                lead_repo = LeadRepository(db)

                # Use SELECT FOR UPDATE
                lead = await lead_repo.get_for_update(lead_id)

                if not lead:
                    return {"success": False, "error": "Lead not found"}

                # Check if lead already replied or not in outreach
                if lead.status not in [LeadStatus.OUTREACH_SENT, LeadStatus.IN_SEQUENCE]:
                    logger.info(f"Lead {lead_id} status is {lead.status}, no longer in outreach, skipping")
                    return {"success": True, "skipped": True, "reason": "wrong_status"}

                # Check compliance
                compliance = ComplianceService()
                if not await compliance.can_send_email(lead_id, lead.contacts[0].email if lead.contacts else None):
                    return {"success": False, "error": "Compliance check failed"}

                # Generate follow-up
                llm_router = get_router()
                followup_agent = FollowUpAgent(llm_router=llm_router, db=db)

                from app.models.domain import AgentTask

                task = AgentTask(
                    agent_name="followup",
                    input_data={
                        "lead_id": lead_id,
                        "sequence_number": sequence_number,
                    },
                )

                result = await followup_agent.execute(task)

                if result.success:
                    email_type = {
                        1: EmailType.FOLLOWUP_1,
                        2: EmailType.FOLLOWUP_2,
                        3: EmailType.BREAKUP,
                    }.get(sequence_number, EmailType.BREAKUP)

                    email_service = EmailService(db=db)
                    email = await email_service.send_email(
                        lead_id=lead_id,
                        to_email=lead.contacts[0].email if lead.contacts else None,
                        subject=result.data.get("subject", ""),
                        body=result.data.get("body", ""),
                        email_type=email_type,
                    )

                    # If first followup, transition to IN_SEQUENCE
                    if sequence_number == 1 and lead.status == LeadStatus.OUTREACH_SENT:
                        orchestrator = LeadOrchestrator()
                        lead, event = orchestrator.transition(
                            lead,
                            LeadStatus.IN_SEQUENCE,
                            actor="followup_task",
                            reason=f"Followup #{sequence_number} sent",
                            pipeline_run_id=run_id,
                        )
                        await lead_repo.update(lead)
                        await db.commit()

                    # Schedule next follow-up if not last
                    if sequence_number < 3:
                        schedule_followup.delay(
                            lead_id=lead_id,
                            sequence_number=sequence_number + 1,
                            pipeline_run_id=run_id,
                        )

                    logger.info(f"Sent followup #{sequence_number} to lead {lead_id} | run_id={run_id}")

                    return {
                        "success": True,
                        "lead_id": lead_id,
                        "run_id": run_id,
                        "email_id": email.id if email else None,
                        "sequence_number": sequence_number,
                    }

                return {
                    "success": False,
                    "error": result.error,
                }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        _log_task_failure("send_followup", lead_id, exc, run_id)
        raise self.retry(exc=exc)


@shared_task(
    name="workers.outreach_tasks.handle_qualification_result",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def handle_qualification_result(
    self,
    lead_id: str,
    intent: str,
    confidence: float,
    pipeline_run_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Handle qualification result and decide next action.

    Args:
        lead_id: Lead ID
        intent: Detected intent
        confidence: Confidence score
        pipeline_run_id: Pipeline run ID for idempotency

    Returns:
        Action results
    """
    import asyncio

    run_id = pipeline_run_id or generate_pipeline_run_id()

    async def _run() -> dict[str, Any]:
        from app.storage.database import async_session_factory
        from app.storage.redis import check_pipeline_step, distributed_lock
        from app.storage.repositories.lead_repo import LeadRepository
        from app.tools.analysis_tools import is_positive_intent

        # Pipeline step idempotency check
        if await check_pipeline_step(lead_id, "handle_qualification", run_id):
            logger.info(f"handle_qualification for {lead_id} already processed in run {run_id}")
            return {"success": True, "skipped": True, "reason": "duplicate_step", "run_id": run_id}

        async with distributed_lock(f"lead:{lead_id}:handle_qualification") as acquired:
            if not acquired:
                return {"success": False, "error": "Lock not acquired", "retry": True}

            async with async_session_factory() as db:
                lead_repo = LeadRepository(db)

                # Use SELECT FOR UPDATE
                lead = await lead_repo.get_for_update(lead_id)

                if not lead:
                    return {"success": False, "error": "Lead not found"}

                reply_intent = ReplyIntent(intent)
                orchestrator = LeadOrchestrator()

                if is_positive_intent(reply_intent):
                    # Positive intent - mark interested and create handoff
                    lead, event = orchestrator.mark_interested(
                        lead,
                        intent=intent,
                        confidence=confidence,
                        actor="qualification_handler",
                    )
                    await lead_repo.update(lead)
                    await db.commit()

                    # Trigger handoff with same run_id
                    create_handoff.delay(lead_id=lead_id, pipeline_run_id=run_id)

                    logger.info(f"Lead {lead_id} marked interested | intent={intent} | run_id={run_id}")

                    return {
                        "success": True,
                        "action": "handoff_created",
                        "lead_id": lead_id,
                        "run_id": run_id,
                    }

                elif reply_intent in [ReplyIntent.REFUSAL, ReplyIntent.UNSUBSCRIBE]:
                    # Negative intent - mark not interested
                    lead, event = orchestrator.mark_not_interested(
                        lead,
                        intent=intent,
                        confidence=confidence,
                        actor="qualification_handler",
                    )
                    await lead_repo.update(lead)
                    await db.commit()

                    logger.info(f"Lead {lead_id} marked not interested | intent={intent} | run_id={run_id}")

                    return {
                        "success": True,
                        "action": "marked_not_interested",
                        "lead_id": lead_id,
                        "run_id": run_id,
                    }

                else:
                    # Neutral or auto-reply - continue sequence
                    logger.info(f"Lead {lead_id} neutral intent, continuing sequence | run_id={run_id}")
                    return {
                        "success": True,
                        "action": "continue_sequence",
                        "lead_id": lead_id,
                        "run_id": run_id,
                    }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        _log_task_failure("handle_qualification_result", lead_id, exc, run_id)
        raise self.retry(exc=exc)


@shared_task(
    name="workers.outreach_tasks.create_handoff",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def create_handoff(
    self,
    lead_id: str,
    pipeline_run_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create handoff for interested lead.

    Args:
        lead_id: Lead ID
        pipeline_run_id: Pipeline run ID for idempotency

    Returns:
        Handoff results
    """
    import asyncio

    run_id = pipeline_run_id or generate_pipeline_run_id()

    async def _run() -> dict[str, Any]:
        from app.agents.handoff_agent import HandoffAgent
        from app.llm.router import get_router
        from app.storage.database import async_session_factory
        from app.storage.redis import check_pipeline_step, distributed_lock
        from app.storage.repositories.lead_repo import LeadRepository

        # Pipeline step idempotency check
        if await check_pipeline_step(lead_id, "handoff", run_id):
            logger.info(f"create_handoff for {lead_id} already processed in run {run_id}")
            return {"success": True, "skipped": True, "reason": "duplicate_step", "run_id": run_id}

        async with distributed_lock(f"lead:{lead_id}:handoff") as acquired:
            if not acquired:
                return {"success": False, "error": "Lock not acquired", "retry": True}

            async with async_session_factory() as db:
                lead_repo = LeadRepository(db)

                # Use SELECT FOR UPDATE
                lead = await lead_repo.get_for_update(lead_id)

                if not lead:
                    return {"success": False, "error": "Lead not found"}

                # Check status - must be INTEREST_DETECTED or QUALIFIED
                if lead.status not in [LeadStatus.INTEREST_DETECTED, LeadStatus.QUALIFIED]:
                    logger.info(f"Lead {lead_id} status is {lead.status}, not ready for handoff")
                    return {"success": True, "skipped": True, "reason": "wrong_status"}

                llm_router = get_router()
                handoff_agent = HandoffAgent(llm_router=llm_router, db=db)

                from app.models.domain import AgentTask

                task = AgentTask(
                    agent_name="handoff",
                    input_data={"lead_id": lead_id},
                )

                result = await handoff_agent.execute(task)

                if result.success:
                    handoff_id = result.data.get("handoff_id")
                    manager_id = result.data.get("manager_id")

                    # Update lead via orchestrator
                    orchestrator = LeadOrchestrator()
                    lead, event = orchestrator.handoff_to_manager(
                        lead,
                        manager_id=manager_id,
                        handoff_id=handoff_id,
                        actor="handoff_task",
                    )
                    await lead_repo.update(lead)
                    await db.commit()

                    # Notify manager
                    notify_manager.delay(
                        handoff_id=handoff_id,
                        manager_id=manager_id,
                        lead_id=lead_id,
                    )

                    logger.info(f"Created handoff {handoff_id} for lead {lead_id} | run_id={run_id}")

                    return {
                        "success": True,
                        "lead_id": lead_id,
                        "run_id": run_id,
                        "handoff_id": handoff_id,
                        "manager_id": manager_id,
                    }

                return {"success": False, "error": result.error}

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        _log_task_failure("create_handoff", lead_id, exc, run_id)
        raise self.retry(exc=exc)


@shared_task(
    name="workers.outreach_tasks.notify_manager",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def notify_manager(
    self,
    handoff_id: str,
    manager_id: str,
    lead_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Notify manager about new handoff.

    Args:
        handoff_id: Handoff ID
        manager_id: Manager ID
        lead_id: Lead ID

    Returns:
        Notification results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.storage.database import async_session_factory
        from app.storage.repositories.lead_repo import LeadRepository
        from app.tools.handoff_tools import notify_manager_slack

        async with async_session_factory() as db:
            lead_repo = LeadRepository(db)
            lead = await lead_repo.get(lead_id)

            if not lead:
                return {"success": False, "error": "Lead not found"}

            result = await notify_manager_slack(
                handoff_id=handoff_id,
                lead=lead,
                manager_id=manager_id,
            )

            logger.info(f"Notified manager {manager_id} about handoff {handoff_id}")

            return {
                "success": result.get("success", False),
                "handoff_id": handoff_id,
                "notification_sent": True,
            }

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(
    name="workers.outreach_tasks.pause_outreach",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def pause_outreach(
    self,
    lead_id: str,
    reason: str = "Manual pause",
    pipeline_run_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Pause outreach for a lead.

    Args:
        lead_id: Lead ID
        reason: Pause reason
        pipeline_run_id: Pipeline run ID for tracking

    Returns:
        Pause results
    """
    import asyncio

    run_id = pipeline_run_id or generate_pipeline_run_id()

    async def _run() -> dict[str, Any]:
        from app.storage.database import async_session_factory
        from app.storage.redis import distributed_lock
        from app.storage.repositories.lead_repo import LeadRepository

        async with distributed_lock(f"lead:{lead_id}:pause") as acquired:
            if not acquired:
                return {"success": False, "error": "Lock not acquired", "retry": True}

            async with async_session_factory() as db:
                lead_repo = LeadRepository(db)

                # Use SELECT FOR UPDATE
                lead = await lead_repo.get_for_update(lead_id)

                if not lead:
                    return {"success": False, "error": "Lead not found"}

                if lead.status in [LeadStatus.OUTREACH_SENT, LeadStatus.IN_SEQUENCE]:
                    orchestrator = LeadOrchestrator()
                    lead, event = orchestrator.transition(
                        lead,
                        LeadStatus.COOLDOWN,
                        actor="outreach_task",
                        reason=reason,
                        pipeline_run_id=run_id,
                    )
                    await lead_repo.update(lead)
                    await db.commit()

                    logger.info(f"Paused outreach for lead {lead_id}: {reason} | run_id={run_id}")

                return {
                    "success": True,
                    "lead_id": lead_id,
                    "run_id": run_id,
                    "status": lead.status.value,
                }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        _log_task_failure("pause_outreach", lead_id, exc, run_id)
        raise self.retry(exc=exc)
