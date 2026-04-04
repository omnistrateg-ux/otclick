"""Base LLM provider interface."""

from abc import ABC, abstractmethod

from app.llm.models import LLMRequest, LLMResponse


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All LLM providers must implement this interface.
    """

    name: str  # Provider name (e.g., "openai", "anthropic")

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate completion for the request.

        Args:
            request: LLM request with prompts and parameters

        Returns:
            LLM response with generated content

        Raises:
            LLMProviderError: If the provider fails
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and available.

        Returns:
            True if provider can be used
        """
        ...

    @abstractmethod
    def get_model_for_task(self, task_type: str) -> str:
        """Get appropriate model for task type.

        Args:
            task_type: Type of LLM task

        Returns:
            Model identifier to use
        """
        ...

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost for token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model identifier

        Returns:
            Estimated cost in USD
        """
        return 0.0
