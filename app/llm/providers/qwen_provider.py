"""Qwen (Alibaba Cloud) LLM provider."""

import time

import httpx

from app.config import settings
from app.core.exceptions import LLMProviderError
from app.llm.models import LLMRequest, LLMResponse
from app.llm.providers.base import LLMProvider
from app.models.enums import LLMTaskType

# Model pricing per 1M tokens (input/output) - approximate
MODEL_PRICING = {
    "qwen-plus": (0.80, 2.00),
    "qwen-turbo": (0.30, 0.60),
}

# Task to model mapping
TASK_MODELS = {
    LLMTaskType.CLASSIFICATION: "qwen-turbo",
    LLMTaskType.EXTRACTION: "qwen-plus",
    LLMTaskType.SCORING: "qwen-plus",
    LLMTaskType.SEGMENTATION: "qwen-plus",
    LLMTaskType.PERSONALIZATION: "qwen-plus",
    LLMTaskType.EMAIL_GENERATION: "qwen-plus",
    LLMTaskType.RESPONSE_ANALYSIS: "qwen-plus",
    LLMTaskType.QUALIFICATION: "qwen-plus",
    LLMTaskType.SUMMARIZATION: "qwen-plus",
}


class QwenProvider(LLMProvider):
    """Alibaba Cloud Qwen API provider."""

    name = "qwen"

    def __init__(self) -> None:
        self._api_key = settings.qwen_api_key
        self._base_url = "https://dashscope.aliyuncs.com/api/v1"

    def is_available(self) -> bool:
        """Check if Qwen API key is configured."""
        return self._api_key is not None

    def get_model_for_task(self, task_type: str) -> str:
        """Get appropriate Qwen model for task type."""
        try:
            task = LLMTaskType(task_type)
            return TASK_MODELS.get(task, "qwen-plus")
        except ValueError:
            return "qwen-plus"

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost based on Qwen pricing."""
        pricing = MODEL_PRICING.get(model, (0.80, 2.00))
        input_cost = (input_tokens / 1_000_000) * pricing[0]
        output_cost = (output_tokens / 1_000_000) * pricing[1]
        return input_cost + output_cost

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate completion using Qwen API."""
        if not self.is_available():
            raise LLMProviderError("qwen", "API key not configured")

        model = self.get_model_for_task(request.task_type.value)
        start_time = time.perf_counter()

        payload = {
            "model": model,
            "input": {
                "messages": [
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ]
            },
            "parameters": {
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "result_format": "message",
            },
        }

        headers = {
            "Authorization": f"Bearer {self._api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self._base_url}/services/aigc/text-generation/generation",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            raise LLMProviderError("qwen", "Request timeout")
        except httpx.HTTPStatusError as e:
            raise LLMProviderError("qwen", f"HTTP error: {e.response.status_code}")
        except Exception as e:
            raise LLMProviderError("qwen", str(e))

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Extract content from Qwen response format
        output = data.get("output", {})
        content = ""
        if "choices" in output:
            choices = output["choices"]
            if choices:
                content = choices[0].get("message", {}).get("content", "")
        elif "text" in output:
            content = output["text"]

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
