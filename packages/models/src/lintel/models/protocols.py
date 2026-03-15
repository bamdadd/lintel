"""Model-related protocol interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lintel.agents.types import AgentRole
    from lintel.models.types import ModelPolicy


class ModelRouter(Protocol):
    """Selects model provider based on agent role and policy."""

    async def select_model(
        self,
        agent_role: AgentRole,
        workload_type: str,
    ) -> ModelPolicy: ...

    async def call_model(
        self,
        policy: ModelPolicy,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> dict[str, Any]: ...

    async def stream_model(
        self,
        policy: ModelPolicy,
        messages: list[dict[str, Any]],
        api_base: str | None = None,
    ) -> AsyncIterator[str]:
        yield ""  # pragma: no cover
