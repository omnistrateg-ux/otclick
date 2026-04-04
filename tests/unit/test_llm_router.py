"""Tests for LLM Router."""

import pytest

from app.llm.models import LLMRequest, LLMResponse
from app.llm.providers.mock_provider import MockProvider
from app.llm.router import LLMRouter, ROUTING_TABLE
from app.models.enums import LLMTaskType


class TestLLMRouter:
    """Tests for LLMRouter class."""

    @pytest.fixture
    def mock_router(self) -> LLMRouter:
        """Create router with mock provider only."""
        return LLMRouter(use_mock=True)

    @pytest.fixture
    def llm_request(self) -> LLMRequest:
        """Create sample LLM request."""
        return LLMRequest(
            task_type=LLMTaskType.CLASSIFICATION,
            system_prompt="You are a classifier.",
            user_prompt="Classify this text.",
        )

    def test_router_initializes(self, mock_router: LLMRouter) -> None:
        """Router initializes successfully."""
        assert mock_router is not None

    def test_routing_table_has_all_task_types(self) -> None:
        """Routing table covers all task types."""
        for task_type in LLMTaskType:
            assert task_type in ROUTING_TABLE, f"Missing {task_type}"

    def test_routing_table_has_providers(self) -> None:
        """Each task type has at least one provider."""
        for task_type, providers in ROUTING_TABLE.items():
            assert len(providers) > 0, f"No providers for {task_type}"

    @pytest.mark.asyncio
    async def test_complete_returns_response(
        self,
        mock_router: LLMRouter,
        llm_request: LLMRequest,
    ) -> None:
        """Complete returns LLMResponse."""
        response = await mock_router.complete(llm_request)

        assert isinstance(response, LLMResponse)
        assert response.request_id == llm_request.id
        assert response.provider == "mock"
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_complete_tracks_tokens(
        self,
        mock_router: LLMRouter,
        llm_request: LLMRequest,
    ) -> None:
        """Complete returns token counts."""
        response = await mock_router.complete(llm_request)

        assert response.input_tokens > 0
        assert response.output_tokens > 0
        assert response.total_tokens == response.input_tokens + response.output_tokens

    @pytest.mark.asyncio
    async def test_complete_tracks_latency(
        self,
        mock_router: LLMRouter,
        llm_request: LLMRequest,
    ) -> None:
        """Complete returns latency."""
        response = await mock_router.complete(llm_request)

        assert response.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_mock_provider_returns_task_specific_response(
        self,
        mock_router: LLMRouter,
    ) -> None:
        """Mock provider returns different responses for different tasks."""
        classification_request = LLMRequest(
            task_type=LLMTaskType.CLASSIFICATION,
            system_prompt="Classify",
            user_prompt="Text",
        )
        email_request = LLMRequest(
            task_type=LLMTaskType.EMAIL_GENERATION,
            system_prompt="Generate",
            user_prompt="Email",
        )

        classification_response = await mock_router.complete(classification_request)
        email_response = await mock_router.complete(email_request)

        assert "industry" in classification_response.content
        assert "subject" in email_response.content

    @pytest.mark.asyncio
    async def test_complete_with_provider_uses_specified_provider(
        self,
        mock_router: LLMRouter,
        llm_request: LLMRequest,
    ) -> None:
        """complete_with_provider uses the specified provider."""
        response = await mock_router.complete_with_provider(llm_request, "mock")

        assert response.provider == "mock"

    @pytest.mark.asyncio
    async def test_complete_with_unavailable_provider_raises_error(
        self,
        mock_router: LLMRouter,
        llm_request: LLMRequest,
    ) -> None:
        """complete_with_provider raises error for unavailable provider."""
        from app.core.exceptions import LLMProviderError

        with pytest.raises(LLMProviderError):
            await mock_router.complete_with_provider(llm_request, "nonexistent")

    def test_get_available_providers_returns_list(self, mock_router: LLMRouter) -> None:
        """get_available_providers returns provider list."""
        providers = mock_router.get_available_providers()

        assert isinstance(providers, list)

    def test_is_provider_available_for_mock(self, mock_router: LLMRouter) -> None:
        """is_provider_available returns False for non-configured providers."""
        # Mock router doesn't add real providers to the list
        assert not mock_router.is_provider_available("openai")
        assert not mock_router.is_provider_available("anthropic")


class TestMockProvider:
    """Tests for MockProvider class."""

    @pytest.fixture
    def provider(self) -> MockProvider:
        """Create mock provider."""
        return MockProvider()

    def test_is_always_available(self, provider: MockProvider) -> None:
        """Mock provider is always available."""
        assert provider.is_available()

    def test_returns_mock_model(self, provider: MockProvider) -> None:
        """Returns mock model name."""
        model = provider.get_model_for_task("classification")
        assert "mock" in model

    @pytest.mark.asyncio
    async def test_returns_json_content(self, provider: MockProvider) -> None:
        """Returns valid JSON content."""
        import json

        request = LLMRequest(
            task_type=LLMTaskType.SCORING,
            system_prompt="Score",
            user_prompt="Lead",
        )

        response = await provider.complete(request)

        # Should be valid JSON
        parsed = json.loads(response.content)
        assert isinstance(parsed, dict)

    @pytest.mark.asyncio
    async def test_set_custom_response(self, provider: MockProvider) -> None:
        """Can set custom response for task type."""
        custom_response = {"custom": "data", "value": 42}
        provider.set_response(LLMTaskType.EXTRACTION, custom_response)

        request = LLMRequest(
            task_type=LLMTaskType.EXTRACTION,
            system_prompt="Extract",
            user_prompt="Data",
        )

        response = await provider.complete(request)

        import json
        parsed = json.loads(response.content)
        assert parsed == custom_response

    @pytest.mark.asyncio
    async def test_simulates_latency(self, provider: MockProvider) -> None:
        """Provider simulates configurable latency."""
        provider.set_latency(100)

        request = LLMRequest(
            task_type=LLMTaskType.CLASSIFICATION,
            system_prompt="Test",
            user_prompt="Test",
        )

        response = await provider.complete(request)

        # Should have latency close to configured value
        assert response.latency_ms >= 50  # Allow some variance

    def test_zero_cost(self, provider: MockProvider) -> None:
        """Mock provider has zero cost."""
        cost = provider.estimate_cost(1000, 500, "mock-model")
        assert cost == 0.0


class TestLLMRequest:
    """Tests for LLMRequest model."""

    def test_request_has_id(self) -> None:
        """Request generates UUID."""
        request = LLMRequest(
            task_type=LLMTaskType.CLASSIFICATION,
            system_prompt="System",
            user_prompt="User",
        )

        assert request.id is not None

    def test_request_defaults(self) -> None:
        """Request has sensible defaults."""
        request = LLMRequest(
            task_type=LLMTaskType.CLASSIFICATION,
            system_prompt="System",
            user_prompt="User",
        )

        assert request.temperature == 0.7
        assert request.max_tokens == 2000
        assert request.json_mode is False

    def test_request_custom_params(self) -> None:
        """Request accepts custom parameters."""
        request = LLMRequest(
            task_type=LLMTaskType.EMAIL_GENERATION,
            system_prompt="System",
            user_prompt="User",
            temperature=0.3,
            max_tokens=1000,
            json_mode=True,
        )

        assert request.temperature == 0.3
        assert request.max_tokens == 1000
        assert request.json_mode is True


class TestLLMResponse:
    """Tests for LLMResponse model."""

    def test_is_json_for_json_content(self) -> None:
        """is_json returns True for JSON content."""
        from uuid import uuid4

        response = LLMResponse(
            request_id=uuid4(),
            content='{"key": "value"}',
            provider="test",
            model="test-model",
        )

        assert response.is_json

    def test_is_json_for_non_json_content(self) -> None:
        """is_json returns False for non-JSON content."""
        from uuid import uuid4

        response = LLMResponse(
            request_id=uuid4(),
            content="This is just text",
            provider="test",
            model="test-model",
        )

        assert not response.is_json

    def test_is_json_for_array(self) -> None:
        """is_json returns True for JSON array."""
        from uuid import uuid4

        response = LLMResponse(
            request_id=uuid4(),
            content='[1, 2, 3]',
            provider="test",
            model="test-model",
        )

        assert response.is_json
