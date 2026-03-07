"""Model router: selects provider + model per agent role and workload type."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from lintel.contracts.types import ModelPolicy

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lintel.contracts.types import AgentRole

logger = structlog.get_logger()

DEFAULT_ROUTING: dict[tuple[str, str], ModelPolicy] = {
    ("planner", "planning"): ModelPolicy(
        "anthropic",
        "claude-sonnet-4-20250514",
        8192,
        0.1,
    ),
    ("coder", "coding"): ModelPolicy(
        "anthropic",
        "claude-sonnet-4-20250514",
        16384,
        0.0,
    ),
    ("reviewer", "review"): ModelPolicy(
        "anthropic",
        "claude-sonnet-4-20250514",
        8192,
        0.0,
    ),
    ("summarizer", "summarize"): ModelPolicy(
        "anthropic",
        "claude-haiku-35-20241022",
        4096,
        0.0,
    ),
}

FALLBACK_POLICY = ModelPolicy("ollama", "llama3.1:8b", 4096, 0.0)


class DefaultModelRouter:
    """Implements ModelRouter protocol with a routing table."""

    def __init__(
        self,
        routing_table: dict[tuple[str, str], ModelPolicy] | None = None,
        fallback: ModelPolicy = FALLBACK_POLICY,
        ollama_api_base: str | None = None,
    ) -> None:
        self._routing = DEFAULT_ROUTING if routing_table is None else routing_table
        self._fallback = fallback
        self._ollama_api_base = ollama_api_base

    async def select_model(
        self,
        agent_role: AgentRole,
        workload_type: str,
    ) -> ModelPolicy:
        key = (agent_role.value, workload_type)
        policy = self._routing.get(key, self._fallback)
        logger.info(
            "model_selected",
            agent_role=agent_role.value,
            workload_type=workload_type,
            provider=policy.provider,
            model=policy.model_name,
        )
        return policy

    async def call_model(
        self,
        policy: ModelPolicy,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        api_base: str | None = None,
    ) -> dict[str, Any]:
        import litellm

        model_string = f"{policy.provider}/{policy.model_name}"
        kwargs: dict[str, Any] = {
            "model": model_string,
            "messages": messages,
            "max_tokens": policy.max_tokens,
            "temperature": policy.temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if policy.extra_params:
            kwargs.update(policy.extra_params)

        effective_base = api_base or (
            self._ollama_api_base if policy.provider == "ollama" else None
        )
        if effective_base:
            kwargs["api_base"] = effective_base.rstrip("/")

        response = await litellm.acompletion(**kwargs)
        result: dict[str, Any] = {
            "content": response.choices[0].message.content,
            "usage": {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
            "model": response.model,
        }
        # Propagate tool calls if present
        msg = response.choices[0].message
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        return result

    async def stream_model(
        self,
        policy: ModelPolicy,
        messages: list[dict[str, str]],
        api_base: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream model response token by token."""
        import litellm

        model_string = f"{policy.provider}/{policy.model_name}"
        kwargs: dict[str, Any] = {
            "model": model_string,
            "messages": messages,
            "max_tokens": policy.max_tokens,
            "temperature": policy.temperature,
            "stream": True,
        }
        if policy.extra_params:
            kwargs.update(policy.extra_params)

        effective_base = api_base or (
            self._ollama_api_base if policy.provider == "ollama" else None
        )
        if effective_base:
            kwargs["api_base"] = effective_base.rstrip("/")

        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
