"""YandexGPT LLM provider."""

import time

import httpx

from app.config import settings
from app.core.exceptions import LLMProviderError
from app.llm.models import LLMRequest, LLMResponse
from app.llm.providers.base import LLMProvider
from app.models.enums import LLMTaskType

# Model pricing per 1M tokens (input/output) - approximate in USD
MODEL_PRICING = {
    "yandexgpt-lite": (0.20, 0.40),
    "yandexgpt": (0.80, 1.60),
}

# Task to model mapping
TASK_MODELS = {
    LLMTaskType.CLASSIFICATION: "yandexgpt-lite",
    LLMTaskType.EXTRACTION: "yandexgpt-lite",
    LLMTaskType.SCORING: "yandexgpt",
    LLMTaskType.SEGMENTATION: "yandexgpt",
    LLMTaskType.PERSONALIZATION: "yandexgpt",
    LLMTaskType.EMAIL_GENERATION: "yandexgpt",
    LLMTaskType.RESPONSE_ANALYSIS: "yandexgpt",
    LLMTaskType.QUALIFICATION: "yandexgpt",
    LLMTaskType.SUMMARIZATION: "yandexgpt",
}


class YandexGPTProvider(LLMProvider):
    """Yandex Cloud YandexGPT API provider."""

    name = "yandexgpt"

    def __init__(self) -> None:
        self._api_key = settings.yandexgpt_api_key
        self._folder_id = settings.yandexgpt_folder_id
        self._base_url = "https://llm.api.cloud.yandex.net/foundationModels/v1"

    def is_available(self) -> bool:
        """Check if YandexGPT API key and folder ID are configured."""
        return self._api_key is not None and self._folder_id is not None

    def get_model_for_task(self, task_type: str) -> str:
        """Get appropriate YandexGPT model for task type."""
        try:
            task = LLMTaskType(task_type)
            return TASK_MODELS.get(task, "yandexgpt")
        except ValueError:
            return "yandexgpt"

    def _get_model_uri(self, model: str) -> str:
        """Get full model URI for YandexGPT."""
        return f"gpt://{self._folder_id}/{model}/latest"

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost based on YandexGPT pricing."""
        pricing = MODEL_PRICING.get(model, (0.80, 1.60))
        input_cost = (input_tokens / 1_000_000) * pricing[0]
        output_cost = (output_tokens / 1_000_000) * pricing[1]
        return input_cost + output_cost

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate completion using YandexGPT API."""
        if not self.is_available():
            raise LLMProviderError("yandexgpt", "API key or folder ID not configured")

        model = self.get_model_for_task(request.task_type.value)
        model_uri = self._get_model_uri(model)
        start_time = time.perf_counter()

        payload = {
            "modelUri": model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": request.temperature,
                "maxTokens": str(request.max_tokens),
            },
            "messages": [
                {"role": "system", "text": request.system_prompt},
                {"role": "user", "text": request.user_prompt},
            ],
        }

        headers = {
            "Authorization": f"Api-Key {self._api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self._base_url}/completion",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            raise LLMProviderError("yandexgpt", "Request timeout")
        except httpx.HTTPStatusError as e:
            raise LLMProviderError("yandexgpt", f"HTTP error: {e.response.status_code}")
        except Exception as e:
            raise LLMProviderError("yandexgpt", str(e))

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Extract content from YandexGPT response
        result = data.get("result", {})
        alternatives = result.get("alternatives", [])
        content = ""
        if alternatives:
            content = alternatives[0].get("message", {}).get("text", "")

        usage = result.get("usage", {})
        input_tokens = int(usage.get("inputTextTokens", 0))
        output_tokens = int(usage.get("completionTokens", 0))

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
