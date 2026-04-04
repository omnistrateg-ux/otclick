"""LLM Router - routes requests to appropriate providers.

Реализует таблицу маршрутизации из ARCHITECTURE.md раздел 8.
"""

from app.core.exceptions import LLMProviderError
from app.llm.models import LLMRequest, LLMResponse
from app.llm.providers.anthropic_provider import AnthropicProvider
from app.llm.providers.base import LLMProvider
from app.llm.providers.mock_provider import MockProvider
from app.llm.providers.openai_provider import OpenAIProvider
from app.llm.providers.qwen_provider import QwenProvider
from app.llm.providers.yandexgpt_provider import YandexGPTProvider
from app.models.enums import LLMTaskType

# Routing table: task type -> ordered list of preferred providers
ROUTING_TABLE: dict[LLMTaskType, list[str]] = {
    LLMTaskType.CLASSIFICATION: ["qwen", "yandexgpt", "openai", "anthropic"],
    LLMTaskType.EXTRACTION: ["qwen", "openai", "anthropic"],
    LLMTaskType.SCORING: ["openai", "anthropic", "qwen"],
    LLMTaskType.SEGMENTATION: ["openai", "qwen", "anthropic"],
    LLMTaskType.PERSONALIZATION: ["anthropic", "openai"],
    LLMTaskType.EMAIL_GENERATION: ["anthropic", "openai"],
    LLMTaskType.RESPONSE_ANALYSIS: ["anthropic", "openai"],
    LLMTaskType.QUALIFICATION: ["anthropic", "openai"],
    LLMTaskType.SUMMARIZATION: ["openai", "anthropic"],
}


class LLMRouter:
    """Routes LLM requests to appropriate providers.

    Выбирает провайдера на основе:
    1. Типа задачи (routing table)
    2. Доступности провайдера (API key configured)
    3. Fallback chain при ошибках
    """

    def __init__(self, use_mock: bool = False) -> None:
        """Initialize router with providers.

        Args:
            use_mock: If True, use mock provider for all requests
        """
        self._use_mock = use_mock
        self._providers: dict[str, LLMProvider] = {}
        self._mock_provider = MockProvider()

        # Initialize real providers
        self._init_providers()

    def _init_providers(self) -> None:
        """Initialize all available providers."""
        providers = [
            OpenAIProvider(),
            AnthropicProvider(),
            QwenProvider(),
            YandexGPTProvider(),
        ]

        for provider in providers:
            if provider.is_available():
                self._providers[provider.name] = provider

    def get_available_providers(self) -> list[str]:
        """Get list of available provider names."""
        return list(self._providers.keys())

    def is_provider_available(self, provider_name: str) -> bool:
        """Check if specific provider is available."""
        return provider_name in self._providers

    def _get_provider_chain(self, task_type: LLMTaskType) -> list[str]:
        """Get ordered provider chain for task type."""
        return ROUTING_TABLE.get(task_type, ["openai", "anthropic"])

    def _select_provider(self, task_type: LLMTaskType) -> LLMProvider:
        """Select first available provider for task type.

        Args:
            task_type: Type of LLM task

        Returns:
            Selected provider

        Raises:
            LLMProviderError: If no providers available
        """
        if self._use_mock:
            return self._mock_provider

        chain = self._get_provider_chain(task_type)

        for provider_name in chain:
            if provider_name in self._providers:
                return self._providers[provider_name]

        # Fallback to any available provider
        if self._providers:
            return next(iter(self._providers.values()))

        # No real providers, use mock
        return self._mock_provider

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Route request to appropriate provider.

        Tries providers in order of preference, falling back on errors.

        Args:
            request: LLM request

        Returns:
            LLM response

        Raises:
            LLMProviderError: If all providers fail
        """
        if self._use_mock:
            return await self._mock_provider.complete(request)

        chain = self._get_provider_chain(request.task_type)
        errors: list[str] = []

        # Try providers in order
        for provider_name in chain:
            if provider_name not in self._providers:
                continue

            provider = self._providers[provider_name]
            try:
                return await provider.complete(request)
            except LLMProviderError as e:
                errors.append(f"{provider_name}: {e.message}")
                continue
            except Exception as e:
                errors.append(f"{provider_name}: {str(e)}")
                continue

        # Try any remaining providers not in chain
        for provider_name, provider in self._providers.items():
            if provider_name in chain:
                continue
            try:
                return await provider.complete(request)
            except Exception as e:
                errors.append(f"{provider_name}: {str(e)}")
                continue

        # All real providers failed, try mock as last resort
        if not self._use_mock:
            try:
                return await self._mock_provider.complete(request)
            except Exception:
                pass

        raise LLMProviderError(
            provider="router",
            reason=f"All providers failed: {'; '.join(errors)}",
        )

    async def complete_with_provider(
        self,
        request: LLMRequest,
        provider_name: str,
    ) -> LLMResponse:
        """Route request to specific provider.

        Args:
            request: LLM request
            provider_name: Name of provider to use

        Returns:
            LLM response

        Raises:
            LLMProviderError: If provider not available or fails
        """
        if provider_name == "mock":
            return await self._mock_provider.complete(request)

        if provider_name not in self._providers:
            raise LLMProviderError(
                provider=provider_name,
                reason="Provider not available",
            )

        return await self._providers[provider_name].complete(request)
