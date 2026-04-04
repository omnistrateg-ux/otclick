"""Anthropic LLM provider."""

import time

import httpx

from app.config import settings
from app.core.exceptions import LLMProviderError
from app.llm.models import LLMRequest, LLMResponse
from app.llm.providers.base import LLMProvider
from app.models.enums import LLMTaskType

# Model pricing per 1M tokens (input/output)
MODEL_PRICING = {
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-opus-4-20250514": (15.00, 75.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
}

# Task to model mapping
TASK_MODELS = {
    LLMTaskType.CLASSIFICATION: "claude-3-5-haiku-20241022",
    LLMTaskType.EXTRACTION: "claude-3-5-haiku-20241022",
    LLMTaskType.SCORING: "claude-3-5-haiku-20241022",
    LLMTaskType.SEGMENTATION: "claude-3-5-haiku-20241022",
    LLMTaskType.PERSONALIZATION: "claude-sonnet-4-20250514",
    LLMTaskType.EMAIL_GENERATION: "claude-sonnet-4-20250514",
    LLMTaskType.RESPONSE_ANALYSIS: "claude-sonnet-4-20250514",
    LLMTaskType.QUALIFICATION: "claude-sonnet-4-20250514",
    LLMTaskType.SUMMARIZATION: "claude-sonnet-4-20250514",
}


class AnthropicProvider(LLMProvider):
    """Anthropic API provider (Claude Sonnet, Opus, Haiku)."""

    name = "anthropic"

    def __init__(self) -> None:
        self._api_key = settings.anthropic_api_key
        self._base_url = "https://api.anthropic.com/v1"

    def is_available(self) -> bool:
        """Check if Anthropic API key is configured."""
        return self._api_key is not None

    def get_model_for_task(self, task_type: str) -> str:
        """Get appropriate Claude model for task type."""
        try:
            task = LLMTaskType(task_type)
            return TASK_MODELS.get(task, "claude-sonnet-4-20250514")
        except ValueError:
            return "claude-sonnet-4-20250514"

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost based on Anthropic pricing."""
        pricing = MODEL_PRICING.get(model, (3.00, 15.00))
        input_cost = (input_tokens / 1_000_000) * pricing[0]
        output_cost = (output_tokens / 1_000_000) * pricing[1]
        return input_cost + output_cost

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate completion using Anthropic API."""
        if not self.is_available():
            raise LLMProviderError("anthropic", "API key not configured")

        model = self.get_model_for_task(request.task_type.value)
        start_time = time.perf_counter()

        payload = {
            "model": model,
            "max_tokens": request.max_tokens,
            "system": request.system_prompt,
            "messages": [{"role": "user", "content": request.user_prompt}],
        }

        # Anthropic doesn't have temperature=0, use 0.01 instead
        if request.temperature > 0:
            payload["temperature"] = request.temperature

        headers = {
            "x-api-key": self._api_key.get_secret_value(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self._base_url}/messages",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            raise LLMProviderError("anthropic", "Request timeout")
        except httpx.HTTPStatusError as e:
            raise LLMProviderError("anthropic", f"HTTP error: {e.response.status_code}")
        except Exception as e:
            raise LLMProviderError("anthropic", str(e))

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Extract content from response
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

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
