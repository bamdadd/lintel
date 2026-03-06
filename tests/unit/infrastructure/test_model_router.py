"""Tests for the model router."""

from __future__ import annotations

from lintel.contracts.types import AgentRole, ModelPolicy
from lintel.infrastructure.models.router import (
    DEFAULT_ROUTING,
    FALLBACK_POLICY,
    DefaultModelRouter,
)


class TestDefaultModelRouter:
    """Tests for model selection logic."""

    async def test_select_known_role_and_workload(self) -> None:
        router = DefaultModelRouter()
        policy = await router.select_model(AgentRole.PLANNER, "planning")
        assert policy.provider == "anthropic"
        assert "claude" in policy.model_name

    async def test_select_unknown_workload_returns_fallback(self) -> None:
        router = DefaultModelRouter()
        policy = await router.select_model(AgentRole.PLANNER, "unknown_workload")
        assert policy == FALLBACK_POLICY

    async def test_custom_routing_table(self) -> None:
        custom = {
            ("planner", "planning"): ModelPolicy("openai", "gpt-4o", 4096, 0.0),
        }
        router = DefaultModelRouter(routing_table=custom)
        policy = await router.select_model(AgentRole.PLANNER, "planning")
        assert policy.provider == "openai"

    async def test_custom_fallback(self) -> None:
        fallback = ModelPolicy("test", "test-model", 1024, 0.5)
        router = DefaultModelRouter(routing_table={}, fallback=fallback)
        policy = await router.select_model(AgentRole.CODER, "coding")
        assert policy == fallback

    async def test_default_routing_covers_key_roles(self) -> None:
        expected_keys = {
            ("planner", "planning"),
            ("coder", "coding"),
            ("reviewer", "review"),
            ("summarizer", "summarize"),
        }
        assert expected_keys == set(DEFAULT_ROUTING.keys())
