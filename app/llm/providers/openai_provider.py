"""OpenAI LLM provider."""

import time

import httpx

from app.config import settings
from app.core.exceptions import LLMProviderError
from app.llm.models import LLMRequest, LLMResponse
from app.llm.providers.base import LLMProvider
from app.models.enums import LLMTaskType

# Model pricing per 1M tokens (input/output)
MODEL_PRICING = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}

# Task to model mapping
TASK_MODELS = {
    LLMTaskType.CLASSIFICATION: "gpt-4o-mini",
    LLMTaskType.EXTRACTION: "gpt-4o-mini",
    LLMTaskType.SCORING: "gpt-4o-mini",
    LLMTaskType.SEGMENTATION: "gpt-4o-mini",
    LLMTaskType.PERSONALIZATION: "gpt-4o",
    LLMTaskType.EMAIL_GENERATION: "gpt-4o",
    LLMTaskType.RESPONSE_ANALYSIS: "gpt-4o",
    LLMTaskType.QUALIFICATION: "gpt-4o",
    LLMTaskType.SUMMARIZATION: "gpt-4o",
}


class OpenAIProvider(LLMProvider):
    """OpenAI API provider (GPT-4o, GPT-4o-mini)."""

    name = "openai"

    def __init__(self) -> None:
        self._api_key = settings.openai_api_key
        self._base_url = "https://api.openai.com/v1"

    def is_available(self) -> bool:
        """Check if OpenAI API key is configured."""
        return self._api_key is not None

    def get_model_for_task(self, task_type: str) -> str:
        """Get appropriate GPT model for task type."""
        try:
            task = LLMTaskType(task_type)
            return TASK_MODELS.get(task, "gpt-4o-mini")
        except ValueError:
            return "gpt-4o-mini"

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost based on OpenAI pricing."""
        pricing = MODEL_PRICING.get(model, (0.15, 0.60))
        input_cost = (input_tokens / 1_000_000) * pricing[0]
        output_cost = (output_tokens / 1_000_000) * pricing[1]
        return input_cost + output_cost

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate completion using OpenAI API."""
        if not self.is_available():
            raise LLMProviderError("openai", "API key not configured")

        model = self.get_model_for_task(request.task_type.value)
        start_time = time.perf_counter()

        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ]

        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            raise LLMProviderError("openai", "Request timeout")
        except httpx.HTTPStatusError as e:
            raise LLMProviderError("openai", f"HTTP error: {e.response.status_code}")
        except Exception as e:
            raise LLMProviderError("openai", str(e))

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return LLMResponse(
            request_id=request.id,
            content=content,
            provider=self.name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=self.estimate_cost(input_tokens, output_tokens, model),
            latency_ms=latency_ms,
        )
