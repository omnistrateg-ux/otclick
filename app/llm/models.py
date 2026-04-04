"""LLM request and response models."""

from datetime import datetime, timezone

UTC = timezone.utc
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models.enums import LLMTaskType


class LLMRequest(BaseModel):
    """Request to LLM provider."""

    id: UUID = Field(default_factory=uuid4)
    task_type: LLMTaskType
    system_prompt: str
    user_prompt: str

    # Optional parameters
    temperature: float = 0.7
    max_tokens: int = 2000
    json_mode: bool = False

    # Context
    lead_id: UUID | None = None
    agent_name: str | None = None

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LLMResponse(BaseModel):
    """Response from LLM provider."""

    request_id: UUID
    content: str
    provider: str
    model: str

    # Usage
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Cost tracking
    estimated_cost_usd: float = 0.0

    # Performance
    latency_ms: int = 0

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_json(self) -> bool:
        """Check if content looks like JSON."""
        content = self.content.strip()
        return content.startswith("{") or content.startswith("[")


class LLMUsageStats(BaseModel):
    """Aggregated LLM usage statistics."""

    provider: str
    model: str
    task_type: LLMTaskType
    total_requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0
