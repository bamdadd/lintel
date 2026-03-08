"""Model router: selects provider + model per agent role and workload type."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

import structlog

from lintel.contracts.types import ModelPolicy

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lintel.contracts.types import AgentRole

logger = structlog.get_logger()

FALLBACK_POLICY = ModelPolicy("ollama", "llama3.1:8b", 4096, 0.0)


class DefaultModelRouter:
    """Implements ModelRouter protocol with a routing table."""

    def __init__(
        self,
        default_policy: ModelPolicy | None = None,
        routing_table: dict[tuple[str, str], ModelPolicy] | None = None,
        fallback: ModelPolicy = FALLBACK_POLICY,
        ollama_api_base: str | None = None,
        model_store: Any = None,  # noqa: ANN401
        ai_provider_store: Any = None,  # noqa: ANN401
        model_assignment_store: Any = None,  # noqa: ANN401
        enable_cache: bool = True,
        cache_max_size: int = 256,
    ) -> None:
        self._default = default_policy
        self._routing = routing_table or {}
        self._fallback = fallback
        self._ollama_api_base = ollama_api_base
        self._model_store = model_store
        self._ai_provider_store = ai_provider_store
        self._model_assignment_store = model_assignment_store
        self._cached_default: ModelPolicy | None = None
        # Response cache: hash(model+messages+tools) → result dict
        self._enable_cache = enable_cache
        self._cache_max_size = cache_max_size
        self._response_cache: dict[str, dict[str, Any]] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    async def _model_to_policy(self, model: Any) -> ModelPolicy | None:  # noqa: ANN401
        """Convert a Model dataclass to a ModelPolicy via its provider."""
        if self._ai_provider_store is None:
            return None
        provider = await self._ai_provider_store.get(model.provider_id)
        if provider is None:
            return None
        extra: dict[str, object] = {}
        if provider.config:
            extra.update(provider.config)
        if getattr(model, "config", None):
            extra.update(model.config)
        extra_params: dict[str, object] | None = extra or None
        return ModelPolicy(
            provider=provider.provider_type.value,
            model_name=model.model_name,
            max_tokens=model.max_tokens,
            temperature=model.temperature,
            extra_params=extra_params,
        )

    async def _resolve_from_assignment(self, agent_role: str) -> ModelPolicy | None:
        """Look up a model assigned to a specific agent role."""
        if self._model_assignment_store is None or self._model_store is None:
            return None
        try:
            from lintel.contracts.types import ModelAssignmentContext

            assignments = await self._model_assignment_store.list_by_context(
                ModelAssignmentContext.AGENT_ROLE,
                agent_role,
            )
            if not assignments:
                return None
            # Pick highest priority assignment
            best = max(assignments, key=lambda a: a.priority)
            model = await self._model_store.get(best.model_id)
            if model is None:
                return None
            policy = await self._model_to_policy(model)
            if policy:
                logger.info(
                    "model_resolved_from_assignment",
                    agent_role=agent_role,
                    model=policy.model_name,
                    provider=policy.provider,
                )
            return policy
        except Exception:
            logger.warning("assignment_resolution_failed", agent_role=agent_role, exc_info=True)
            return None

    async def _resolve_default_from_store(self) -> ModelPolicy | None:
        """Look up the user-configured default model and build a ModelPolicy."""
        if self._model_store is None:
            return None
        try:
            models = await self._model_store.list_all()
            default_model = next((m for m in models if m.is_default), None)
            if default_model is None:
                return None
            policy = await self._model_to_policy(default_model)
            if policy:
                self._cached_default = policy
                logger.info(
                    "default_model_resolved",
                    provider=policy.provider,
                    model=policy.model_name,
                )
            return policy
        except Exception:
            logger.warning("default_model_resolution_failed", exc_info=True)
            return None

    async def select_model(
        self,
        agent_role: AgentRole,
        workload_type: str,
    ) -> ModelPolicy:
        # 1. Explicit routing table (code-level override)
        key = (agent_role.value, workload_type)
        policy = self._routing.get(key)
        # 2. User-configured assignment for this agent role
        if policy is None:
            policy = await self._resolve_from_assignment(agent_role.value)
        # 3. Explicit default_policy (constructor arg)
        if policy is None:
            policy = self._default
        # 4. User-configured default model from store
        if policy is None:
            policy = self._cached_default or await self._resolve_default_from_store()
        # 5. Hardcoded fallback
        if policy is None:
            policy = self._fallback
        logger.info(
            "model_selected",
            agent_role=agent_role.value,
            workload_type=workload_type,
            provider=policy.provider,
            model=policy.model_name,
        )
        return policy

    def _cache_key(
        self,
        model_string: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None,
    ) -> str:
        """Compute a deterministic hash for a model call."""
        payload = json.dumps(
            {"model": model_string, "messages": messages, "tools": tools},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    @property
    def cache_stats(self) -> dict[str, int]:
        """Return cache hit/miss statistics."""
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "size": len(self._response_cache),
        }

    async def call_model(
        self,
        policy: ModelPolicy,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        api_base: str | None = None,
    ) -> dict[str, Any]:
        import litellm

        model_string = f"{policy.provider}/{policy.model_name}"

        # Check cache for exact match (only for non-tool calls with temperature 0)
        cache_key = ""
        if self._enable_cache and policy.temperature == 0.0 and not tools:
            cache_key = self._cache_key(model_string, messages, tools)
            cached = self._response_cache.get(cache_key)
            if cached is not None:
                self._cache_hits += 1
                logger.debug("llm_cache_hit", model=model_string, key=cache_key[:12])
                return cached

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
        # Store in cache
        if cache_key:
            self._cache_misses += 1
            if len(self._response_cache) >= self._cache_max_size:
                # Evict oldest entry
                oldest = next(iter(self._response_cache))
                del self._response_cache[oldest]
            # result is stored after tool_calls extraction below

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

        # Store in cache (after tool_calls extraction)
        if cache_key:
            self._response_cache[cache_key] = result

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
