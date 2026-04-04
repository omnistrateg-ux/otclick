"""Enrichment Agent - enriches leads with company data and contacts.

Агент обогащения согласно ARCHITECTURE.md раздел 6.
"""

from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.models.domain import AgentTask, CompanyProfile, EmployerContact, EmployerLead
from app.models.enums import IndustrySegment, LLMTaskType
from app.tools.enrichment_tools import enrich_company, find_contacts


class EnrichmentAgent(BaseAgent):
    """Agent for enriching leads with company profile and contacts.

    Input: EmployerLead
    Output: CompanyProfile + list of EmployerContact
    """

    agent_name = "enrichment"
    llm_task_types = [LLMTaskType.EXTRACTION, LLMTaskType.CLASSIFICATION]

    async def run(self, task: AgentTask) -> AgentResult:
        """Enrich lead with company data and contacts.

        Args:
            task: Task with input_data containing:
                - lead: EmployerLead data dict

        Returns:
            AgentResult with profile and contacts
        """
        lead_data = task.input_data.get("lead", {})
        lead = EmployerLead.model_validate(lead_data)

        # Enrich company profile
        profile = await enrich_company(lead)

        # Find contacts
        contacts = await find_contacts(lead, profile)

        # Use LLM to enhance profile if needed
        if profile:
            profile = await self._enhance_profile_with_llm(lead, profile)

        # Determine industry with LLM if unknown
        if profile and profile.industry == IndustrySegment.OTHER:
            profile = await self._classify_industry(lead, profile)

        return AgentResult(
            success=True,
            data={
                "profile": profile.model_dump(mode="json") if profile else None,
                "contacts": [c.model_dump(mode="json") for c in contacts],
                "contacts_count": len(contacts),
                "has_verified_email": any(c.email_verified for c in contacts),
            },
        )

    async def _enhance_profile_with_llm(
        self,
        lead: EmployerLead,
        profile: CompanyProfile,
    ) -> CompanyProfile:
        """Use LLM to extract additional insights for personalization.

        Args:
            lead: Original lead
            profile: Profile to enhance

        Returns:
            Enhanced profile
        """
        # Skip if we already have personalization hooks
        if profile.personalization_hooks:
            return profile

        # Build context for LLM
        context_parts = [
            f"Компания: {lead.company_name}",
        ]
        if profile.industry != IndustrySegment.OTHER:
            context_parts.append(f"Отрасль: {profile.industry.value}")
        if profile.active_vacancies_count:
            context_parts.append(f"Активных вакансий: {profile.active_vacancies_count}")
        if profile.typical_roles:
            context_parts.append(f"Типичные роли: {', '.join(profile.typical_roles)}")
        if profile.city:
            context_parts.append(f"Город: {profile.city}")

        context = "\n".join(context_parts)

        system_prompt = """Ты эксперт по B2B персонализации в сфере HR.
На основе данных о компании, определи:
1. Вероятные боли работодателя (pain_points) — максимум 3
2. Зацепки для персонализации (hooks) — конкретные факты для письма

Ответь JSON:
{
    "pain_points": ["боль 1", "боль 2"],
    "hooks": ["зацепка 1", "зацепка 2"]
}"""

        user_prompt = f"""Проанализируй компанию и найди зацепки для персонализированного письма:

{context}"""

        try:
            response = await self.call_llm_json(
                task_type=LLMTaskType.EXTRACTION,
                system=system_prompt,
                user=user_prompt,
                temperature=0.5,
            )

            if "pain_points" in response:
                profile.pain_points = response["pain_points"][:3]
            if "hooks" in response:
                profile.personalization_hooks = response["hooks"][:3]

        except Exception:
            # If LLM fails, continue without enhancement
            pass

        return profile

    async def _classify_industry(
        self,
        lead: EmployerLead,
        profile: CompanyProfile,
    ) -> CompanyProfile:
        """Use LLM to classify company industry.

        Args:
            lead: Lead with company name
            profile: Profile to update

        Returns:
            Profile with classified industry
        """
        context_parts = [f"Название: {lead.company_name}"]
        if profile.typical_roles:
            context_parts.append(f"Вакансии: {', '.join(profile.typical_roles)}")
        if profile.sub_industry:
            context_parts.append(f"Описание: {profile.sub_industry}")

        context = "\n".join(context_parts)

        system_prompt = """Классифицируй компанию по отрасли для массового найма.

Возможные отрасли:
- retail (розница, магазины, сети)
- horeca (рестораны, кафе, отели)
- logistics (доставка, курьеры, транспорт)
- warehouse (склады, распределительные центры)
- construction (строительство)
- manufacturing (производство)
- trade (оптовая торговля)
- other (другое)

Ответь JSON: {"industry": "код_отрасли", "confidence": 0.0-1.0}"""

        user_prompt = f"""Определи отрасль компании:

{context}"""

        try:
            response = await self.call_llm_json(
                task_type=LLMTaskType.CLASSIFICATION,
                system=system_prompt,
                user=user_prompt,
                temperature=0.2,
            )

            industry_code = response.get("industry", "other")
            try:
                profile.industry = IndustrySegment(industry_code)
            except ValueError:
                profile.industry = IndustrySegment.OTHER

        except Exception:
            pass

        return profile
