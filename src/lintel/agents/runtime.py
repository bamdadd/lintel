"""Agent runtime: executes agent steps with model + tools + event emission."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from lintel.contracts.events import (
    AgentStepCompleted,
    AgentStepStarted,
    ModelCallCompleted,
    ModelSelected,
)
from lintel.contracts.types import ActorType

if TYPE_CHECKING:
    from uuid import UUID

    from lintel.contracts.protocols import EventStore, ModelRouter
    from lintel.contracts.types import AgentRole, ThreadRef

logger = structlog.get_logger()


class AgentRuntime:
    """Executes agent steps, routing to models and emitting events."""

    def __init__(
        self,
        event_store: EventStore,
        model_router: ModelRouter,
    ) -> None:
        self._event_store = event_store
        self._model_router = model_router

    async def execute_step(
        self,
        thread_ref: ThreadRef,
        agent_role: AgentRole,
        step_name: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        correlation_id: UUID | None = None,
    ) -> dict[str, Any]:
        cid = correlation_id or uuid4()

        await self._event_store.append(
            thread_ref.stream_id,
            [
                AgentStepStarted(
                    actor_type=ActorType.AGENT,
                    actor_id=agent_role.value,
                    thread_ref=thread_ref,
                    correlation_id=cid,
                    payload={
                        "agent_role": agent_role.value,
                        "step_name": step_name,
                    },
                )
            ],
        )

        policy = await self._model_router.select_model(agent_role, step_name)
        await self._event_store.append(
            thread_ref.stream_id,
            [
                ModelSelected(
                    actor_type=ActorType.SYSTEM,
                    actor_id="model_router",
                    thread_ref=thread_ref,
                    correlation_id=cid,
                    payload={
                        "agent_role": agent_role.value,
                        "provider": policy.provider,
                        "model_name": policy.model_name,
                    },
                )
            ],
        )

        result = await self._model_router.call_model(policy, messages, tools)

        await self._event_store.append(
            thread_ref.stream_id,
            [
                ModelCallCompleted(
                    actor_type=ActorType.SYSTEM,
                    actor_id="model_router",
                    thread_ref=thread_ref,
                    correlation_id=cid,
                    payload={
                        "provider": policy.provider,
                        "model": result.get("model", policy.model_name),
                        "input_tokens": result.get("usage", {}).get("input_tokens", 0),
                        "output_tokens": result.get("usage", {}).get("output_tokens", 0),
                    },
                )
            ],
        )

        await self._event_store.append(
            thread_ref.stream_id,
            [
                AgentStepCompleted(
                    actor_type=ActorType.AGENT,
                    actor_id=agent_role.value,
                    thread_ref=thread_ref,
                    correlation_id=cid,
                    payload={
                        "agent_role": agent_role.value,
                        "step_name": step_name,
                        "output_summary": result.get("content", "")[:500],
                    },
                )
            ],
        )

        return result
