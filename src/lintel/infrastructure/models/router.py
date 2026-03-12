"""Model router: selects provider + model per agent role and workload type."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
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
        cache_db_path: str = "",
        ollama_keep_alive: str = "30m",
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
        # SQLite persistent cache (Layer 1 from REQ-001)
        self._sqlite_cache: sqlite3.Connection | None = None
        if enable_cache and cache_db_path:
            self._init_sqlite_cache(cache_db_path)
        # Ollama KV cache warmth (Layer 2 from REQ-001)
        self._ollama_keep_alive = ollama_keep_alive

    def _init_sqlite_cache(self, db_path: str) -> None:
        """Initialize SQLite persistent response cache."""
        try:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS llm_cache (cache_key TEXT PRIMARY KEY, response TEXT)"
            )
            conn.commit()
            self._sqlite_cache = conn
            logger.info("sqlite_cache_initialized", path=db_path)
        except Exception:
            logger.warning("sqlite_cache_init_failed", path=db_path, exc_info=True)

    def _sqlite_get(self, key: str) -> dict[str, Any] | None:
        """Look up a cached response from SQLite."""
        if self._sqlite_cache is None:
            return None
        try:
            row = self._sqlite_cache.execute(
                "SELECT response FROM llm_cache WHERE cache_key = ?", (key,)
            ).fetchone()
            if row:
                result: dict[str, Any] = json.loads(row[0])
                return result
        except Exception:
            logger.debug("sqlite_cache_read_error", key=key[:12])
        return None

    def _sqlite_put(self, key: str, value: dict[str, Any]) -> None:
        """Store a response in the SQLite cache."""
        if self._sqlite_cache is None:
            return
        try:
            self._sqlite_cache.execute(
                "INSERT OR REPLACE INTO llm_cache (cache_key, response) VALUES (?, ?)",
                (key, json.dumps(value, default=str)),
            )
            self._sqlite_cache.commit()
        except Exception:
            logger.debug("sqlite_cache_write_error", key=key[:12])

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
            policy = await self._resolve_default_from_store()
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
        messages: list[dict[str, Any]],
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
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        # Claude Code provider — delegate to CLI instead of litellm
        if policy.provider == "claude_code":
            sandbox_mgr = kwargs.get("sandbox_manager")
            sandbox_id = kwargs.get("sandbox_id")
            if sandbox_mgr is not None and sandbox_id is not None:
                return await self._call_claude_code(
                    policy,
                    messages,
                    sandbox_mgr,
                    sandbox_id,
                    on_activity=kwargs.get("on_activity"),
                )
            # No sandbox available — fall back to litellm with the model name
            logger.warning(
                "claude_code_no_sandbox_fallback",
                model=policy.model_name,
                msg="No sandbox available for Claude Code, falling back to litellm",
            )
            # Remap provider to anthropic for litellm
            from dataclasses import replace as _replace

            policy = _replace(policy, provider="anthropic")

        api_base: str | None = kwargs.get("api_base")
        import litellm

        model_string = f"{policy.provider}/{policy.model_name}"

        # Check cache for exact match (only for non-tool calls with temperature 0)
        cache_key = ""
        if self._enable_cache and policy.temperature == 0.0 and not tools:
            cache_key = self._cache_key(model_string, messages, tools)
            cached = self._response_cache.get(cache_key)
            if cached is None:
                cached = self._sqlite_get(cache_key)
            if cached is not None:
                self._cache_hits += 1
                logger.debug("llm_cache_hit", model=model_string, key=cache_key[:12])
                return cached

        call_kwargs: dict[str, Any] = {
            "model": model_string,
            "messages": messages,
            "max_tokens": policy.max_tokens,
            "temperature": policy.temperature,
        }
        if tools:
            call_kwargs["tools"] = tools
        if policy.extra_params:
            call_kwargs.update(policy.extra_params)
        # Ollama KV cache warmth — keep model loaded between requests
        if policy.provider == "ollama" and self._ollama_keep_alive:
            call_kwargs["keep_alive"] = self._ollama_keep_alive

        effective_base = api_base or (
            self._ollama_api_base if policy.provider == "ollama" else None
        )
        if effective_base:
            call_kwargs["api_base"] = effective_base.rstrip("/")

        response = await litellm.acompletion(**call_kwargs)
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
            self._sqlite_put(cache_key, result)

        return result

    async def _call_claude_code(
        self,
        policy: ModelPolicy,
        messages: list[dict[str, Any]],
        sandbox_manager: Any,  # noqa: ANN401
        sandbox_id: str | None,
        on_activity: Any = None,  # noqa: ANN401
    ) -> dict[str, Any]:
        """Route a call to Claude Code CLI in the sandbox."""
        from lintel.infrastructure.models.claude_code import ClaudeCodeProvider

        if sandbox_manager is None or sandbox_id is None:
            msg = "Claude Code provider requires a sandbox — no sandbox available"
            raise RuntimeError(msg)

        provider = ClaudeCodeProvider(sandbox_manager)

        # Extract system prompt and user prompt from messages
        system_prompt = ""
        user_prompt = ""
        for msg_item in messages:
            if msg_item.get("role") == "system":
                system_prompt += msg_item.get("content", "") + "\n"
            elif msg_item.get("role") == "user":
                user_prompt += msg_item.get("content", "") + "\n"

        max_turns = (
            int(str(policy.extra_params.get("max_turns", 20))) if policy.extra_params else 20
        )

        # Use streaming invoke if an activity callback is provided
        if on_activity is not None:
            result = await provider.invoke_streaming(
                user_prompt.strip(),
                sandbox_id=sandbox_id,
                system_prompt=system_prompt.strip(),
                max_turns=max_turns,
                on_activity=on_activity,
            )
        else:
            result = await provider.invoke(
                user_prompt.strip(),
                sandbox_id=sandbox_id,
                system_prompt=system_prompt.strip(),
                max_turns=max_turns,
            )

        return {
            "content": result.get("content", ""),
            "usage": result.get("usage", {}),
            "model": "claude-code",
        }

    async def stream_model(
        self,
        policy: ModelPolicy,
        messages: list[dict[str, Any]],
        api_base: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream model response token by token.

        After iteration completes, ``self.last_stream_usage`` contains token
        counts from the final chunk (if the provider supports it).
        """
        import litellm

        model_string = f"{policy.provider}/{policy.model_name}"
        kwargs: dict[str, Any] = {
            "model": model_string,
            "messages": messages,
            "max_tokens": policy.max_tokens,
            "temperature": policy.temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if policy.extra_params:
            kwargs.update(policy.extra_params)
        if policy.provider == "ollama" and self._ollama_keep_alive:
            kwargs["keep_alive"] = self._ollama_keep_alive

        effective_base = api_base or (
            self._ollama_api_base if policy.provider == "ollama" else None
        )
        if effective_base:
            kwargs["api_base"] = effective_base.rstrip("/")

        self.last_stream_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            # Capture usage from the final chunk (provider-dependent)
            if hasattr(chunk, "usage") and chunk.usage:
                usage = chunk.usage
                if hasattr(usage, "prompt_tokens") and usage.prompt_tokens:
                    self.last_stream_usage["input_tokens"] = usage.prompt_tokens
                if hasattr(usage, "completion_tokens") and usage.completion_tokens:
                    self.last_stream_usage["output_tokens"] = usage.completion_tokens
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content
