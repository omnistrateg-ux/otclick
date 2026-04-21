"""Discovery and enrichment Celery tasks.

Задачи для обнаружения, обогащения и скоринга лидов.

IMPORTANT: All status changes MUST go through LeadOrchestrator.
Direct status assignments are prohibited.
"""

import logging
from typing import Any

from celery import shared_task

from app.agents.discovery_agent import DiscoveryAgent
from app.agents.enrichment_agent import EnrichmentAgent
from app.agents.scoring_agent import ScoringAgent
from app.events.definitions import EventType, create_event
from app.models.domain import AgentTask
from app.models.enums import LeadStatus
from app.observability import TracedTask, record_step_error
from app.orchestrator.engine import LeadOrchestrator, generate_pipeline_run_id
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _trace_error(lead_id: str, run_id: str, step: str, exc: Exception) -> None:
    """Record error to trace and log.

    Args:
        lead_id: Lead ID
        run_id: Pipeline run ID
        step: Step name
        exc: Exception
    """
    await record_step_error(lead_id, run_id, step, exc)
    logger.error(
        f"Task {step} FAILED | lead_id={lead_id} | run_id={run_id} | "
        f"error={type(exc).__name__}: {exc}",
        exc_info=True,
    )


@shared_task(
    name="workers.discovery_tasks.discover_employers",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def discover_employers(
    self,
    search_params: dict[str, Any] | None = None,
    campaign_id: str | None = None,
) -> dict[str, Any]:
    """Discover employers from hh.ru.

    Args:
        search_params: Search parameters (industry, region, etc.)
        campaign_id: Optional campaign ID

    Returns:
        Discovery results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.llm.router import get_router
        from app.storage.database import async_session_factory

        async with async_session_factory() as db:
            llm_router = get_router()
            agent = DiscoveryAgent(llm_router=llm_router, db=db)

            task = AgentTask(
                agent_name="discovery",
                input_data={
                    "search_params": search_params or {},
                    "campaign_id": campaign_id,
                },
            )

            result = await agent.execute(task)

            if result.success:
                leads_discovered = result.data.get("leads_count", 0)
                logger.info(f"Discovered {leads_discovered} employers")

                # Emit events for each discovered lead
                for lead_id in result.data.get("lead_ids", []):
                    event = create_event(
                        EventType.LEAD_DISCOVERED,
                        lead_id=lead_id,
                        campaign_id=campaign_id,
                        actor="discovery_agent",
                    )
                    # Event will trigger enrichment

            return {
                "success": result.success,
                "leads_discovered": result.data.get("leads_count", 0),
                "lead_ids": result.data.get("lead_ids", []),
            }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.exception(f"discover_employers failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name="workers.discovery_tasks.enrich_lead",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def enrich_lead(
    self,
    lead_id: str,
    event_id: str | None = None,
    pipeline_run_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Enrich a discovered lead.

    Args:
        lead_id: Lead ID to enrich
        event_id: Triggering event ID
        pipeline_run_id: Pipeline run ID for idempotency

    Returns:
        Enrichment results
    """
    import asyncio

    run_id = pipeline_run_id or generate_pipeline_run_id()
    step_name = "enrich"

    async def _run() -> dict[str, Any]:
        from app.llm.router import get_router
        from app.observability import record_step_skipped
        from app.storage.database import async_session_factory
        from app.storage.redis import check_pipeline_step, distributed_lock
        from app.storage.repositories.lead_repo import LeadRepository

        tracer = TracedTask(lead_id, run_id, step_name)

        # Pipeline step idempotency check
        if await check_pipeline_step(lead_id, step_name, run_id):
            await record_step_skipped(lead_id, run_id, step_name, "duplicate_step")
            return {"success": True, "skipped": True, "reason": "duplicate_step", "run_id": run_id}

        await tracer.start()

        # Distributed lock to prevent concurrent processing
        async with distributed_lock(f"lead:{lead_id}:enrich") as acquired:
            if not acquired:
                await tracer.skip("lock_not_acquired")
                return {"success": False, "error": "Lock not acquired", "retry": True}

            async with async_session_factory() as db:
                lead_repo = LeadRepository(db)

                # Use SELECT FOR UPDATE for critical section
                lead = await lead_repo.get_for_update(lead_id)

                if not lead:
                    await tracer.error("Lead not found")
                    return {"success": False, "error": "Lead not found"}

                if lead.status != LeadStatus.LEAD_FOUND:
                    await tracer.skip(f"wrong_status:{lead.status.value}")
                    return {"success": True, "skipped": True, "reason": "wrong_status"}

                llm_router = get_router()
                agent = EnrichmentAgent(llm_router=llm_router, db=db)

                task = AgentTask(
                    agent_name="enrichment",
                    input_data={"lead_id": lead_id},
                )

                result = await agent.execute(task)

                if result.success:
                    # Transition lead via orchestrator (NEVER assign status directly)
                    orchestrator = LeadOrchestrator()
                    lead, event = orchestrator.enrich_lead(
                        lead,
                        actor="enrichment_agent",
                        enrichment_data=result.data,
                    )
                    await lead_repo.update(lead)
                    await db.commit()

                    contacts_found = result.data.get("contacts_count", 0)
                    await tracer.success({"contacts_found": contacts_found})

                    # Trigger scoring with same run_id
                    score_lead.delay(lead_id, pipeline_run_id=run_id)

                    return {
                        "success": True,
                        "lead_id": lead_id,
                        "run_id": run_id,
                        "contacts_found": contacts_found,
                    }

                await tracer.error(result.error or "Agent execution failed")
                return {
                    "success": False,
                    "lead_id": lead_id,
                    "run_id": run_id,
                    "error": result.error,
                }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        asyncio.run(_trace_error(lead_id, run_id, step_name, exc))
        raise self.retry(exc=exc)


@shared_task(
    name="workers.discovery_tasks.score_lead",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def score_lead(
    self,
    lead_id: str,
    event_id: str | None = None,
    pipeline_run_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Score an enriched lead.

    Args:
        lead_id: Lead ID to score
        event_id: Triggering event ID
        pipeline_run_id: Pipeline run ID for idempotency

    Returns:
        Scoring results
    """
    import asyncio

    run_id = pipeline_run_id or generate_pipeline_run_id()
    step_name = "score"

    async def _run() -> dict[str, Any]:
        from app.llm.router import get_router
        from app.observability import record_step_skipped
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
        async with distributed_lock(f"lead:{lead_id}:score") as acquired:
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

                if lead.status != LeadStatus.ENRICHED:
                    await tracer.skip(f"wrong_status:{lead.status.value}")
                    return {"success": True, "skipped": True, "reason": "wrong_status"}

                llm_router = get_router()
                agent = ScoringAgent(llm_router=llm_router, db=db)

                task = AgentTask(
                    agent_name="scoring",
                    input_data={"lead_id": lead_id},
                )

                result = await agent.execute(task)

                if result.success:
                    score = result.data.get("score", 0)
                    segment = result.data.get("segment")

                    # Transition lead via orchestrator (NEVER assign status directly)
                    orchestrator = LeadOrchestrator()
                    lead, event = orchestrator.score_lead(
                        lead,
                        score=score,
                        actor="scoring_agent",
                        segment=segment,
                    )
                    await lead_repo.update(lead)
                    await db.commit()

                    await tracer.success({"score": score, "segment": segment})

                    # If scored (not archived), trigger qualification
                    if lead.status == LeadStatus.SCORED:
                        qualify_lead_task.delay(lead_id, pipeline_run_id=run_id)

                    return {
                        "success": True,
                        "lead_id": lead_id,
                        "run_id": run_id,
                        "score": score,
                        "segment": segment,
                        "qualified": score >= 50,
                    }

                await tracer.error(result.error or "Scoring failed")
                return {
                    "success": False,
                    "lead_id": lead_id,
                    "run_id": run_id,
                    "error": result.error,
                }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        asyncio.run(_trace_error(lead_id, run_id, step_name, exc))
        raise self.retry(exc=exc)


@shared_task(
    name="workers.discovery_tasks.qualify_lead",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def qualify_lead_task(
    self,
    lead_id: str,
    pipeline_run_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Qualify a scored lead for outreach.

    Args:
        lead_id: Lead ID to qualify
        pipeline_run_id: Pipeline run ID for idempotency

    Returns:
        Qualification results
    """
    import asyncio

    run_id = pipeline_run_id or generate_pipeline_run_id()
    step_name = "qualify"

    async def _run() -> dict[str, Any]:
        from app.observability import record_step_skipped
        from app.storage.database import async_session_factory
        from app.storage.redis import check_pipeline_step, distributed_lock
        from app.storage.repositories.lead_repo import LeadRepository
        from app.tools.qualification_tools import qualify_lead

        tracer = TracedTask(lead_id, run_id, step_name)

        # Pipeline step idempotency check
        if await check_pipeline_step(lead_id, step_name, run_id):
            await record_step_skipped(lead_id, run_id, step_name, "duplicate_step")
            return {"success": True, "skipped": True, "reason": "duplicate_step", "run_id": run_id}

        await tracer.start()

        async with distributed_lock(f"lead:{lead_id}:qualify") as acquired:
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

                if lead.status != LeadStatus.SCORED:
                    await tracer.skip(f"wrong_status:{lead.status.value}")
                    return {"success": True, "skipped": True, "reason": "wrong_status"}

                result = await qualify_lead(lead)

                orchestrator = LeadOrchestrator()

                if result.is_qualified:
                    # FIXED: Use orchestrator instead of direct status assignment
                    lead, event = orchestrator.qualify_lead(
                        lead,
                        score=result.score,
                        reason=result.reason,
                        actor="qualification_task",
                        pipeline_run_id=run_id,
                    )
                    await lead_repo.update(lead)
                    await db.commit()

                    await tracer.success({
                        "qualified": True,
                        "score": result.score,
                        "reason": result.reason,
                    })

                    # Trigger outreach with same run_id
                    from workers.outreach_tasks import start_outreach
                    start_outreach.delay(lead_id, pipeline_run_id=run_id)
                else:
                    # Disqualify and archive
                    lead, event = orchestrator.disqualify_lead(
                        lead,
                        reason=result.reason,
                        actor="qualification_task",
                        pipeline_run_id=run_id,
                    )
                    await lead_repo.update(lead)
                    await db.commit()

                    await tracer.success({
                        "qualified": False,
                        "score": result.score,
                        "reason": result.reason,
                    })

                return {
                    "success": True,
                    "lead_id": lead_id,
                    "run_id": run_id,
                    "qualified": result.is_qualified,
                    "score": result.score,
                    "reason": result.reason,
                }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        asyncio.run(_trace_error(lead_id, run_id, step_name, exc))
        raise self.retry(exc=exc)


@shared_task(
    name="workers.discovery_tasks.batch_discover",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def batch_discover(
    self,
    industries: list[str] | None = None,
    regions: list[str] | None = None,
    limit_per_industry: int = 100,
) -> dict[str, Any]:
    """Batch discovery of employers.

    Args:
        industries: Industries to search
        regions: Regions to search
        limit_per_industry: Max leads per industry

    Returns:
        Batch results
    """
    total_discovered = 0
    results = []

    industries = industries or ["retail", "logistics", "horeca"]
    regions = regions or ["Москва", "Санкт-Петербург"]

    for industry in industries:
        for region in regions:
            result = discover_employers.delay(
                search_params={
                    "industry": industry,
                    "region": region,
                    "limit": limit_per_industry,
                }
            )
            results.append(
                {
                    "industry": industry,
                    "region": region,
                    "task_id": result.id,
                }
            )

    logger.info(f"Started {len(results)} discovery tasks")

    return {
        "tasks_started": len(results),
        "industries": industries,
        "regions": regions,
        "results": results,
    }
