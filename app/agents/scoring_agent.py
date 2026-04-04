"""Scoring Agent - scores and segments leads.

Агент скоринга и сегментации согласно ARCHITECTURE.md раздел 6.
"""

from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.models.domain import (
    AgentTask,
    CompanyProfile,
    EmployerContact,
    EmployerLead,
    LeadScore,
    LeadSegment,
)
from app.models.enums import LLMTaskType
from app.tools.scoring_tools import calculate_score, determine_segment


class ScoringAgent(BaseAgent):
    """Agent for scoring and segmenting leads.

    Input: Lead + Profile + Contacts
    Output: LeadScore + LeadSegment
    """

    agent_name = "scoring"
    llm_task_types = [LLMTaskType.SCORING, LLMTaskType.SEGMENTATION]

    async def run(self, task: AgentTask) -> AgentResult:
        """Score and segment a lead.

        Args:
            task: Task with input_data containing:
                - lead: EmployerLead data dict
                - profile: CompanyProfile data dict (optional)
                - contacts: List of EmployerContact data dicts

        Returns:
            AgentResult with score and segment
        """
        input_data = task.input_data

        # Parse input data
        lead = EmployerLead.model_validate(input_data.get("lead", {}))

        profile = None
        if input_data.get("profile"):
            profile = CompanyProfile.model_validate(input_data["profile"])

        contacts = [
            EmployerContact.model_validate(c)
            for c in input_data.get("contacts", [])
        ]

        # Calculate base score using rules
        score = calculate_score(lead, profile, contacts)

        # Optionally enhance scoring with LLM
        if input_data.get("use_llm_scoring", False):
            score = await self._enhance_score_with_llm(lead, profile, contacts, score)

        # Determine segment
        segment = determine_segment(lead, profile, score)

        # Optionally enhance segment with LLM
        if input_data.get("use_llm_segmentation", False):
            segment = await self._enhance_segment_with_llm(lead, profile, segment)

        return AgentResult(
            success=True,
            data={
                "score": score.model_dump(mode="json"),
                "segment": segment.model_dump(mode="json"),
                "total_score": score.total_score,
                "priority": segment.priority.value,
            },
        )

    async def _enhance_score_with_llm(
        self,
        lead: EmployerLead,
        profile: CompanyProfile | None,
        contacts: list[EmployerContact],
        base_score: LeadScore,
    ) -> LeadScore:
        """Use LLM to provide additional scoring insights.

        Args:
            lead: Lead being scored
            profile: Company profile
            contacts: Lead contacts
            base_score: Rule-based score

        Returns:
            Enhanced score with LLM reasoning
        """
        # Build context
        context_parts = [
            f"Компания: {lead.company_name}",
            f"Источник: {lead.source}",
        ]

        if profile:
            context_parts.extend([
                f"Отрасль: {profile.industry.value}",
                f"Вакансий: {profile.active_vacancies_count or 'неизвестно'}",
                f"Интенсивность найма: {profile.hiring_intensity.value}",
            ])
            if profile.typical_roles:
                context_parts.append(f"Роли: {', '.join(profile.typical_roles)}")

        if contacts:
            context_parts.append(f"Контактов: {len(contacts)}")
            has_hr = any(c.role.value.startswith("hr") for c in contacts)
            context_parts.append(f"Есть HR контакт: {'да' if has_hr else 'нет'}")

        context_parts.append(f"\nТекущий скор: {base_score.total_score}")

        context = "\n".join(context_parts)

        system_prompt = """Ты эксперт по квалификации B2B лидов в сфере HR/рекрутинга.
Оцени качество лида и объясни свою оценку.

Критерии хорошего лида:
- Целевая отрасль (ритейл, HoReCa, логистика, склад, производство)
- Высокая интенсивность найма
- Есть HR контакт с email
- Средний/крупный размер компании

Ответь JSON:
{
    "score_adjustment": число от -20 до +20 (корректировка базового скора),
    "reasoning": "краткое объяснение на русском"
}"""

        user_prompt = f"""Оцени этот лид:

{context}

Нужно ли скорректировать скор?"""

        try:
            response = await self.call_llm_json(
                task_type=LLMTaskType.SCORING,
                system=system_prompt,
                user=user_prompt,
                temperature=0.3,
            )

            adjustment = response.get("score_adjustment", 0)
            if isinstance(adjustment, (int, float)):
                # Apply adjustment within bounds
                new_total = max(0, min(100, base_score.total_score + adjustment))
                base_score.total_score = round(new_total, 1)

            if "reasoning" in response:
                base_score.reasoning = response["reasoning"]

        except Exception:
            pass

        return base_score

    async def _enhance_segment_with_llm(
        self,
        lead: EmployerLead,
        profile: CompanyProfile | None,
        base_segment: LeadSegment,
    ) -> LeadSegment:
        """Use LLM to refine communication strategy.

        Args:
            lead: Lead being segmented
            profile: Company profile
            base_segment: Rule-based segment

        Returns:
            Enhanced segment with refined strategy
        """
        context_parts = [
            f"Компания: {lead.company_name}",
            f"Сегмент: {base_segment.segment.value}",
        ]

        if profile:
            if profile.pain_points:
                context_parts.append(f"Боли: {', '.join(profile.pain_points)}")
            if profile.personalization_hooks:
                context_parts.append(f"Зацепки: {', '.join(profile.personalization_hooks)}")

        context = "\n".join(context_parts)

        system_prompt = """Ты эксперт по B2B email-коммуникации в сфере HR.
На основе данных о компании, предложи персонализированную стратегию коммуникации.

Ответь JSON:
{
    "pain_statement": "конкретная боль этой компании (1 предложение)",
    "value_proposition": "что мы предлагаем именно им (1 предложение)",
    "suggested_cta": "вопрос-CTA для первого письма"
}"""

        user_prompt = f"""Персонализируй стратегию для этой компании:

{context}

Текущая стратегия:
- Боль: {base_segment.pain_statement}
- Ценность: {base_segment.value_proposition}"""

        try:
            response = await self.call_llm_json(
                task_type=LLMTaskType.SEGMENTATION,
                system=system_prompt,
                user=user_prompt,
                temperature=0.6,
            )

            if "pain_statement" in response:
                base_segment.pain_statement = response["pain_statement"]
            if "value_proposition" in response:
                base_segment.value_proposition = response["value_proposition"]
            if "suggested_cta" in response:
                base_segment.suggested_cta = response["suggested_cta"]

        except Exception:
            pass

        return base_segment
