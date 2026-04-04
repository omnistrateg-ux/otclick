"""Discovery and enrichment Celery tasks.

Задачи для обнаружения, обогащения и скоринга лидов.
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
from app.orchestrator.engine import LeadOrchestrator
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


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

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(
    name="workers.discovery_tasks.enrich_lead",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def enrich_lead(
    self,
    lead_id: str,
    event_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Enrich a discovered lead.

    Args:
        lead_id: Lead ID to enrich
        event_id: Triggering event ID

    Returns:
        Enrichment results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.llm.router import get_router
        from app.storage.database import async_session_factory
        from app.storage.repositories.lead_repo import LeadRepository

        async with async_session_factory() as db:
            lead_repo = LeadRepository(db)
            lead = await lead_repo.get(lead_id)

            if not lead:
                logger.error(f"Lead {lead_id} not found")
                return {"success": False, "error": "Lead not found"}

            if lead.status != LeadStatus.DISCOVERED:
                logger.info(f"Lead {lead_id} already enriched, skipping")
                return {"success": True, "skipped": True}

            llm_router = get_router()
            agent = EnrichmentAgent(llm_router=llm_router, db=db)

            task = AgentTask(
                agent_name="enrichment",
                input_data={"lead_id": lead_id},
            )

            result = await agent.execute(task)

            if result.success:
                # Transition lead
                orchestrator = LeadOrchestrator()
                lead, event = orchestrator.enrich_lead(
                    lead,
                    actor="enrichment_agent",
                    enrichment_data=result.data,
                )
                await lead_repo.update(lead)

                logger.info(f"Enriched lead {lead_id}")

                # Trigger scoring
                score_lead.delay(lead_id)

            return {
                "success": result.success,
                "lead_id": lead_id,
                "contacts_found": result.data.get("contacts_count", 0),
            }

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(
    name="workers.discovery_tasks.score_lead",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def score_lead(
    self,
    lead_id: str,
    event_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Score an enriched lead.

    Args:
        lead_id: Lead ID to score
        event_id: Triggering event ID

    Returns:
        Scoring results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.llm.router import get_router
        from app.storage.database import async_session_factory
        from app.storage.repositories.lead_repo import LeadRepository

        async with async_session_factory() as db:
            lead_repo = LeadRepository(db)
            lead = await lead_repo.get(lead_id)

            if not lead:
                logger.error(f"Lead {lead_id} not found")
                return {"success": False, "error": "Lead not found"}

            if lead.status != LeadStatus.ENRICHED:
                logger.info(f"Lead {lead_id} not ready for scoring")
                return {"success": True, "skipped": True}

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

                # Transition lead
                orchestrator = LeadOrchestrator()
                lead, event = orchestrator.score_lead(
                    lead,
                    score=score,
                    actor="scoring_agent",
                    segment=segment,
                )
                await lead_repo.update(lead)

                logger.info(f"Scored lead {lead_id}: {score}")

                # If qualified, trigger outreach
                if lead.status == LeadStatus.QUALIFIED:
                    from workers.outreach_tasks import start_outreach

                    start_outreach.delay(lead_id)

            return {
                "success": result.success,
                "lead_id": lead_id,
                "score": result.data.get("score"),
                "segment": result.data.get("segment"),
                "qualified": result.data.get("score", 0) >= 50,
            }

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(
    name="workers.discovery_tasks.qualify_lead",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def qualify_lead_task(
    self,
    lead_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Qualify a scored lead for outreach.

    Args:
        lead_id: Lead ID to qualify

    Returns:
        Qualification results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.storage.database import async_session_factory
        from app.storage.repositories.lead_repo import LeadRepository
        from app.tools.qualification_tools import qualify_lead

        async with async_session_factory() as db:
            lead_repo = LeadRepository(db)
            lead = await lead_repo.get(lead_id)

            if not lead:
                return {"success": False, "error": "Lead not found"}

            result = await qualify_lead(lead)

            if result.is_qualified:
                orchestrator = LeadOrchestrator()
                lead.status = LeadStatus.QUALIFIED
                await lead_repo.update(lead)

                logger.info(f"Lead {lead_id} qualified: {result.reason}")

            return {
                "success": True,
                "lead_id": lead_id,
                "qualified": result.is_qualified,
                "score": result.score,
                "reason": result.reason,
            }

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(name="workers.discovery_tasks.batch_discover")
def batch_discover(
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
