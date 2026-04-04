"""Discovery Agent - finds employers from various sources.

Агент обнаружения компаний согласно ARCHITECTURE.md раздел 6.
"""

from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.models.domain import AgentTask, EmployerLead
from app.models.enums import LLMTaskType
from app.tools.discovery_tools import (
    create_lead_from_hh,
    find_employers_hh,
    parse_hh_employer,
)


class DiscoveryAgent(BaseAgent):
    """Agent for discovering potential employer leads.

    Input: SearchParams (query, area, industry filters)
    Output: List of EmployerLead objects
    """

    agent_name = "discovery"
    llm_task_types = [LLMTaskType.EXTRACTION, LLMTaskType.CLASSIFICATION]

    async def run(self, task: AgentTask) -> AgentResult:
        """Execute discovery based on search parameters.

        Args:
            task: Task with input_data containing search params:
                - query: Search query (optional)
                - area: Region ID (optional, default: Moscow)
                - industry: Industry filter (optional)
                - source: Data source (default: "hh.ru")
                - max_results: Max leads to return (default: 20)

        Returns:
            AgentResult with leads list
        """
        input_data = task.input_data
        source = input_data.get("source", "hh.ru")
        max_results = input_data.get("max_results", 20)

        leads: list[EmployerLead] = []

        if source == "hh.ru":
            leads = await self._discover_from_hh(input_data, max_results)
        # TODO: Add other sources (avito, 2gis, csv)

        return AgentResult(
            success=True,
            data={
                "leads": [lead.model_dump(mode="json") for lead in leads],
                "count": len(leads),
                "source": source,
            },
        )

    async def _discover_from_hh(
        self,
        params: dict[str, Any],
        max_results: int,
    ) -> list[EmployerLead]:
        """Discover employers from hh.ru.

        Args:
            params: Search parameters
            max_results: Maximum results to return

        Returns:
            List of EmployerLead objects
        """
        # Fetch employers from hh.ru API
        employers = await find_employers_hh(
            query=params.get("query"),
            area=params.get("area", 1),
            industry=params.get("industry"),
            per_page=min(max_results, 100),
        )

        leads: list[EmployerLead] = []

        for employer_data in employers[:max_results]:
            # Get detailed employer info if needed
            employer_id = str(employer_data.get("id", ""))

            # Create lead from employer data
            lead = create_lead_from_hh(employer_data)
            leads.append(lead)

        # Use LLM to classify/filter if many results
        if len(leads) > 10 and params.get("use_llm_filter", False):
            leads = await self._filter_with_llm(leads, params)

        return leads

    async def _filter_with_llm(
        self,
        leads: list[EmployerLead],
        params: dict[str, Any],
    ) -> list[EmployerLead]:
        """Use LLM to filter/prioritize leads.

        Args:
            leads: Leads to filter
            params: Original search params

        Returns:
            Filtered/prioritized leads
        """
        # Prepare companies summary for LLM
        companies_text = "\n".join([
            f"- {lead.company_name} ({lead.city or 'unknown'})"
            for lead in leads
        ])

        target_industry = params.get("target_industry", "массовый найм")

        system_prompt = """Ты эксперт по B2B продажам в сфере HR-услуг.
Твоя задача — выбрать компании, которые наиболее вероятно нуждаются в услугах массового найма.

Критерии хорошего лида:
- Ритейл, HoReCa, логистика, склад, производство
- Сетевые компании (несколько точек)
- Активно нанимают линейный персонал

Ответь JSON списком индексов компаний (начиная с 0), которые стоит взять в работу.
Например: {"selected": [0, 2, 5, 7]}"""

        user_prompt = f"""Выбери компании для работы в сфере "{target_industry}":

{companies_text}

Верни JSON с индексами выбранных компаний."""

        try:
            response = await self.call_llm_json(
                task_type=LLMTaskType.CLASSIFICATION,
                system=system_prompt,
                user=user_prompt,
                temperature=0.3,
            )

            selected_indices = response.get("selected", [])
            return [
                leads[i] for i in selected_indices
                if isinstance(i, int) and 0 <= i < len(leads)
            ]

        except Exception:
            # If LLM fails, return all leads
            return leads
