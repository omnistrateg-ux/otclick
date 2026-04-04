"""Base agent interface.

Реализует интерфейс агента из ARCHITECTURE.md раздел 6.3.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.models import LLMRequest, LLMResponse
from app.llm.router import LLMRouter
from app.models.domain import AgentRun, AgentTask
from app.models.enums import LLMTaskType


class AgentResult(BaseModel):
    """Result returned by an agent."""

    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    llm_calls: int = 0
    llm_tokens: int = 0
    llm_cost_usd: float = 0.0


class BaseAgent(ABC):
    """Abstract base class for all agents.

    Агент решает ЧТО делать. Tool делает КАК.
    Агент никогда не вызывает внешний API напрямую.
    """

    agent_name: str
    llm_task_types: list[LLMTaskType]

    def __init__(self, llm_router: LLMRouter, db: AsyncSession) -> None:
        """Initialize agent with dependencies.

        Args:
            llm_router: Router for LLM calls
            db: Database session
        """
        self.llm = llm_router
        self.db = db
        self._current_run: AgentRun | None = None
        self._llm_calls = 0
        self._llm_tokens = 0
        self._llm_cost = 0.0

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute task with full lifecycle management.

        Handles: validation -> run -> audit logging.

        Args:
            task: Task to execute

        Returns:
            Agent result

        Raises:
            Exception: If agent fails
        """
        run = self._start_run(task)

        try:
            # Reset counters
            self._llm_calls = 0
            self._llm_tokens = 0
            self._llm_cost = 0.0

            # Execute agent logic
            result = await self.run(task)

            # Update result with LLM stats
            result.llm_calls = self._llm_calls
            result.llm_tokens = self._llm_tokens
            result.llm_cost_usd = self._llm_cost

            # Complete run
            self._complete_run(run, result)

            return result

        except Exception as e:
            self._fail_run(run, e)
            raise

    @abstractmethod
    async def run(self, task: AgentTask) -> AgentResult:
        """Execute agent-specific logic.

        Must be implemented by concrete agents.

        Args:
            task: Task with input data

        Returns:
            Agent result with output data
        """
        ...

    async def call_llm(
        self,
        task_type: LLMTaskType,
        system: str,
        user: str,
        **kwargs: Any,
    ) -> str:
        """Make LLM call through router.

        Tracks usage statistics.

        Args:
            task_type: Type of LLM task
            system: System prompt
            user: User prompt
            **kwargs: Additional LLM parameters

        Returns:
            Generated content
        """
        request = LLMRequest(
            task_type=task_type,
            system_prompt=system,
            user_prompt=user,
            agent_name=self.agent_name,
            **kwargs,
        )

        response = await self.llm.complete(request)

        # Track usage
        self._llm_calls += 1
        self._llm_tokens += response.total_tokens
        self._llm_cost += response.estimated_cost_usd

        return response.content

    async def call_llm_json(
        self,
        task_type: LLMTaskType,
        system: str,
        user: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make LLM call expecting JSON response.

        Args:
            task_type: Type of LLM task
            system: System prompt
            user: User prompt
            **kwargs: Additional LLM parameters

        Returns:
            Parsed JSON response
        """
        import json

        content = await self.call_llm(
            task_type=task_type,
            system=system,
            user=user,
            json_mode=True,
            **kwargs,
        )

        # Try to parse JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from content
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())

    def _start_run(self, task: AgentTask) -> AgentRun:
        """Start a new agent run.

        Args:
            task: Task being executed

        Returns:
            New agent run record
        """
        run = AgentRun(
            task_id=task.id,
            agent_name=self.agent_name,
        )
        self._current_run = run
        return run

    def _complete_run(self, run: AgentRun, result: AgentResult) -> None:
        """Mark run as completed.

        Args:
            run: Agent run to complete
            result: Result of execution
        """
        now = datetime.now(UTC)
        run.completed_at = now
        run.duration_ms = int((now - run.started_at).total_seconds() * 1000)
        run.success = result.success
        run.output_data = result.data
        run.llm_calls_count = result.llm_calls
        run.llm_tokens_used = result.llm_tokens
        run.llm_cost_usd = result.llm_cost_usd

    def _fail_run(self, run: AgentRun, error: Exception) -> None:
        """Mark run as failed.

        Args:
            run: Agent run that failed
            error: Exception that caused failure
        """
        now = datetime.now(UTC)
        run.completed_at = now
        run.duration_ms = int((now - run.started_at).total_seconds() * 1000)
        run.success = False
        run.error_message = str(error)
