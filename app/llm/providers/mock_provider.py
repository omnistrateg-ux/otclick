"""Mock LLM provider for testing."""

import json
import time
from typing import Any

from app.llm.models import LLMRequest, LLMResponse
from app.llm.providers.base import LLMProvider
from app.models.enums import LLMTaskType


# Default mock responses for different task types
DEFAULT_RESPONSES: dict[LLMTaskType, dict[str, Any]] = {
    LLMTaskType.CLASSIFICATION: {
        "industry": "retail",
        "confidence": 0.95,
    },
    LLMTaskType.EXTRACTION: {
        "company_name": "ООО Тест",
        "city": "Москва",
        "vacancies_count": 10,
    },
    LLMTaskType.SCORING: {
        "total_score": 75.0,
        "hiring_intensity_score": 80.0,
        "industry_fit_score": 70.0,
        "contact_quality_score": 75.0,
        "company_size_score": 70.0,
        "recency_score": 80.0,
        "reasoning": "Высокая интенсивность найма в целевой отрасли",
    },
    LLMTaskType.SEGMENTATION: {
        "segment": "retail",
        "sub_segment": "федеральная сеть",
        "communication_angle": "speed",
        "tone": "professional",
        "priority": "high",
    },
    LLMTaskType.EMAIL_GENERATION: {
        "subject": "Кассиры за 48 часов — актуально?",
        "body": (
            "Добрый день.\n\n"
            "Видел, что ваша компания активно ищет кассиров и продавцов. "
            "Знаю, что в ритейле главная боль — скорость закрытия и текучка.\n\n"
            "Мы в Отклике закрываем линейные позиции за 48 часов с подтверждённой явкой 94%. "
            "Работаем с сетями от 50 точек, средний срок закрытия позиции — 2 дня.\n\n"
            "Имеет смысл обсудить?"
        ),
    },
    LLMTaskType.RESPONSE_ANALYSIS: {
        "intent": "soft_interest",
        "confidence": 0.85,
        "summary": "Клиент проявил мягкий интерес, интересуется условиями",
        "key_points": ["интерес к срокам", "вопрос о стоимости"],
    },
    LLMTaskType.QUALIFICATION: {
        "is_qualified": True,
        "reason": "Проявлен интерес, запрошены детали по срокам",
        "confidence": 0.9,
        "next_steps": ["Назначить звонок", "Подготовить КП"],
    },
    LLMTaskType.SUMMARIZATION: {
        "summary": "Компания проявила интерес к услугам найма персонала",
        "key_points": ["активный найм", "интерес к срокам"],
        "talking_points": [
            "Уточнить текущие потребности в персонале",
            "Рассказать о сроках закрытия позиций (48 часов)",
            "Предложить пилотный проект на 10-20 человек",
        ],
    },
    LLMTaskType.PERSONALIZATION: {
        "hooks": ["открытие новых точек", "сезонный пик"],
        "pain_points": ["текучка кадров", "долгий найм"],
    },
}


class MockProvider(LLMProvider):
    """Mock LLM provider for testing and development.

    Returns predefined responses based on task type.
    Can be configured with custom responses.
    """

    name = "mock"

    def __init__(self, responses: dict[LLMTaskType, dict[str, Any]] | None = None) -> None:
        self._responses = responses or DEFAULT_RESPONSES
        self._latency_ms = 50  # Simulated latency

    def is_available(self) -> bool:
        """Mock provider is always available."""
        return True

    def get_model_for_task(self, task_type: str) -> str:
        """Return mock model name."""
        return "mock-model-v1"

    def set_response(self, task_type: LLMTaskType, response: dict[str, Any]) -> None:
        """Set custom response for a task type.

        Args:
            task_type: Type of LLM task
            response: Response data to return
        """
        self._responses[task_type] = response

    def set_latency(self, latency_ms: int) -> None:
        """Set simulated latency.

        Args:
            latency_ms: Latency in milliseconds
        """
        self._latency_ms = latency_ms

    def _personalize_email_response(
        self,
        response_data: dict[str, Any],
        user_prompt: str,
    ) -> dict[str, Any]:
        """Personalize email response with company name from prompt.

        Args:
            response_data: Default response data
            user_prompt: User prompt containing company name

        Returns:
            Personalized response data
        """
        import re

        # Try to extract company name from prompt
        company_match = re.search(r"Компания:\s*(.+?)(?:\n|$)", user_prompt)
        company_name = company_match.group(1).strip() if company_match else None

        # Try to extract contact name
        contact_match = re.search(r"Контакт:\s*(.+?)(?:\n|$)", user_prompt)
        contact_name = contact_match.group(1).strip() if contact_match else None

        # Try to extract city
        city_match = re.search(r"Город:\s*(.+?)(?:\n|$)", user_prompt)
        city = city_match.group(1).strip() if city_match else None

        # Personalize body
        if company_name and "body" in response_data:
            body = response_data["body"]
            body = body.replace("ваша компания", company_name)
            body = body.replace("вы", company_name)

            # Add city if present
            if city:
                body = body.replace("кассиров и продавцов", f"кассиров в {city}")

            response_data["body"] = body

        # Personalize subject
        if company_name and "subject" in response_data:
            subject = response_data["subject"]
            if city:
                subject = f"Кассиры в {city} за 48ч — актуально?"
            response_data["subject"] = subject

        return response_data

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return mock response based on task type."""
        start_time = time.perf_counter()

        # Simulate latency
        import asyncio
        await asyncio.sleep(self._latency_ms / 1000)

        # Get response for task type
        response_data = self._responses.get(
            request.task_type,
            {"result": "mock response"},
        ).copy()

        # For email generation, try to extract company name and inject it
        if request.task_type == LLMTaskType.EMAIL_GENERATION:
            response_data = self._personalize_email_response(
                response_data, request.user_prompt
            )

        content = json.dumps(response_data, ensure_ascii=False)

        # Simulate token counts
        input_tokens = len(request.system_prompt.split()) + len(request.user_prompt.split())
        output_tokens = len(content.split())

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        return LLMResponse(
            request_id=request.id,
            content=content,
            provider=self.name,
            model="mock-model-v1",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=0.0,
            latency_ms=latency_ms,
        )
