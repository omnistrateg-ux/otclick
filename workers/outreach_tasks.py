"""Outreach Celery tasks.

Задачи для email outreach и follow-up.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task

from app.events.definitions import EventType, create_event
from app.models.enums import EmailType, LeadStatus, ReplyIntent
from app.orchestrator.engine import LeadOrchestrator
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@shared_task(
    name="workers.outreach_tasks.start_outreach",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def start_outreach(
    self,
    lead_id: str,
    campaign_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Start outreach sequence for a qualified lead.

    Args:
        lead_id: Lead ID
        campaign_id: Optional campaign ID

    Returns:
        Outreach start results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.agents.email_copy_agent import EmailCopyAgent
        from app.llm.router import get_router
        from app.services.compliance_service import ComplianceService
        from app.services.email_service import EmailService
        from app.storage.database import async_session_factory
        from app.storage.repositories.lead_repo import LeadRepository

        async with async_session_factory() as db:
            lead_repo = LeadRepository(db)
            lead = await lead_repo.get(lead_id)

            if not lead:
                return {"success": False, "error": "Lead not found"}

            if lead.status not in [LeadStatus.QUALIFIED, LeadStatus.SCORED]:
                logger.info(f"Lead {lead_id} not ready for outreach")
                return {"success": True, "skipped": True}

            # Check compliance
            compliance = ComplianceService()
            if not await compliance.can_send_email(lead_id, lead.contacts[0].email if lead.contacts else None):
                logger.warning(f"Cannot send to lead {lead_id}: compliance check failed")
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

                # Transition lead
                orchestrator = LeadOrchestrator()
                lead, event = orchestrator.start_outreach(
                    lead,
                    campaign_id=campaign_id,
                    actor="outreach_task",
                )
                await lead_repo.update(lead)

                # Schedule first follow-up
                schedule_followup.apply_async(
                    kwargs={"lead_id": lead_id, "sequence_number": 1},
                    countdown=3 * 24 * 60 * 60,  # 3 days
                )

                logger.info(f"Started outreach for lead {lead_id}")

                return {
                    "success": True,
                    "lead_id": lead_id,
                    "email_id": email.id if email else None,
                    "followup_scheduled": True,
                }

            return {
                "success": False,
                "lead_id": lead_id,
                "error": result.error,
            }

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(
    name="workers.outreach_tasks.schedule_followup",
    bind=True,
    max_retries=2,
)
def schedule_followup(
    self,
    lead_id: str,
    sequence_number: int = 1,
    **kwargs: Any,
) -> dict[str, Any]:
    """Schedule a follow-up email.

    Args:
        lead_id: Lead ID
        sequence_number: Sequence number (1-3)

    Returns:
        Scheduling results
    """
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
        },
        countdown=delay,
    )

    send_at = datetime.now(UTC) + timedelta(seconds=delay)

    logger.info(
        f"Scheduled followup #{sequence_number} for lead {lead_id} at {send_at}"
    )

    return {
        "success": True,
        "lead_id": lead_id,
        "sequence_number": sequence_number,
        "scheduled_at": send_at.isoformat(),
    }


@shared_task(
    name="workers.outreach_tasks.send_followup",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_followup(
    self,
    lead_id: str,
    sequence_number: int,
    **kwargs: Any,
) -> dict[str, Any]:
    """Send a follow-up email.

    Args:
        lead_id: Lead ID
        sequence_number: Sequence number

    Returns:
        Send results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.agents.followup_agent import FollowUpAgent
        from app.llm.router import get_router
        from app.services.compliance_service import ComplianceService
        from app.services.email_service import EmailService
        from app.storage.database import async_session_factory
        from app.storage.repositories.lead_repo import LeadRepository

        async with async_session_factory() as db:
            lead_repo = LeadRepository(db)
            lead = await lead_repo.get(lead_id)

            if not lead:
                return {"success": False, "error": "Lead not found"}

            # Check if lead already replied or not in outreach
            if lead.status not in [LeadStatus.OUTREACH_STARTED]:
                logger.info(f"Lead {lead_id} no longer in outreach, skipping followup")
                return {"success": True, "skipped": True, "reason": "Lead status changed"}

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
                    3: EmailType.FOLLOWUP_3,
                }.get(sequence_number, EmailType.FOLLOWUP_3)

                email_service = EmailService(db=db)
                email = await email_service.send_email(
                    lead_id=lead_id,
                    to_email=lead.contacts[0].email if lead.contacts else None,
                    subject=result.data.get("subject", ""),
                    body=result.data.get("body", ""),
                    email_type=email_type,
                )

                # Schedule next follow-up if not last
                if sequence_number < 3:
                    schedule_followup.delay(
                        lead_id=lead_id,
                        sequence_number=sequence_number + 1,
                    )

                logger.info(
                    f"Sent followup #{sequence_number} to lead {lead_id}"
                )

                return {
                    "success": True,
                    "lead_id": lead_id,
                    "email_id": email.id if email else None,
                    "sequence_number": sequence_number,
                }

            return {
                "success": False,
                "error": result.error,
            }

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(
    name="workers.outreach_tasks.handle_qualification_result",
    bind=True,
)
def handle_qualification_result(
    self,
    lead_id: str,
    intent: str,
    confidence: float,
    **kwargs: Any,
) -> dict[str, Any]:
    """Handle qualification result and decide next action.

    Args:
        lead_id: Lead ID
        intent: Detected intent
        confidence: Confidence score

    Returns:
        Action results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.storage.database import async_session_factory
        from app.storage.repositories.lead_repo import LeadRepository
        from app.tools.analysis_tools import is_positive_intent

        async with async_session_factory() as db:
            lead_repo = LeadRepository(db)
            lead = await lead_repo.get(lead_id)

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

                # Trigger handoff
                create_handoff.delay(lead_id=lead_id)

                return {
                    "success": True,
                    "action": "handoff_created",
                    "lead_id": lead_id,
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

                return {
                    "success": True,
                    "action": "marked_not_interested",
                    "lead_id": lead_id,
                }

            else:
                # Neutral or auto-reply - continue sequence
                return {
                    "success": True,
                    "action": "continue_sequence",
                    "lead_id": lead_id,
                }

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(
    name="workers.outreach_tasks.create_handoff",
    bind=True,
    max_retries=2,
)
def create_handoff(
    self,
    lead_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create handoff for interested lead.

    Args:
        lead_id: Lead ID

    Returns:
        Handoff results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.agents.handoff_agent import HandoffAgent
        from app.llm.router import get_router
        from app.storage.database import async_session_factory
        from app.storage.repositories.lead_repo import LeadRepository

        async with async_session_factory() as db:
            lead_repo = LeadRepository(db)
            lead = await lead_repo.get(lead_id)

            if not lead:
                return {"success": False, "error": "Lead not found"}

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

                # Update lead
                orchestrator = LeadOrchestrator()
                lead, event = orchestrator.handoff_to_manager(
                    lead,
                    manager_id=manager_id,
                    handoff_id=handoff_id,
                    actor="handoff_task",
                )
                await lead_repo.update(lead)

                # Notify manager
                notify_manager.delay(
                    handoff_id=handoff_id,
                    manager_id=manager_id,
                    lead_id=lead_id,
                )

                logger.info(f"Created handoff {handoff_id} for lead {lead_id}")

                return {
                    "success": True,
                    "lead_id": lead_id,
                    "handoff_id": handoff_id,
                    "manager_id": manager_id,
                }

            return {"success": False, "error": result.error}

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(name="workers.outreach_tasks.notify_manager")
def notify_manager(
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


@shared_task(name="workers.outreach_tasks.pause_outreach")
def pause_outreach(
    lead_id: str,
    reason: str = "Manual pause",
    **kwargs: Any,
) -> dict[str, Any]:
    """Pause outreach for a lead.

    Args:
        lead_id: Lead ID
        reason: Pause reason

    Returns:
        Pause results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.storage.database import async_session_factory
        from app.storage.repositories.lead_repo import LeadRepository

        async with async_session_factory() as db:
            lead_repo = LeadRepository(db)
            lead = await lead_repo.get(lead_id)

            if not lead:
                return {"success": False, "error": "Lead not found"}

            if lead.status == LeadStatus.OUTREACH_STARTED:
                orchestrator = LeadOrchestrator()
                lead, event = orchestrator.transition(
                    lead,
                    LeadStatus.OUTREACH_PAUSED,
                    actor="outreach_task",
                    reason=reason,
                )
                await lead_repo.update(lead)

                logger.info(f"Paused outreach for lead {lead_id}: {reason}")

            return {
                "success": True,
                "lead_id": lead_id,
                "status": lead.status.value,
            }

    return asyncio.get_event_loop().run_until_complete(_run())
