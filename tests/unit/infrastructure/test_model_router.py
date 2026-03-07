"""Tests for the model router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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

    async def test_ollama_api_base_passed_to_litellm(self) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.model = "ollama/llama3.1:8b"

        router = DefaultModelRouter(ollama_api_base="http://localhost:11434")
        policy = ModelPolicy("ollama", "llama3.1:8b", 4096, 0.0)

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            import litellm

            await router.call_model(policy, [{"role": "user", "content": "hi"}])
            litellm.acompletion.assert_called_once()
            call_kwargs = litellm.acompletion.call_args[1]
            assert call_kwargs["api_base"] == "http://localhost:11434"

    async def test_non_ollama_provider_no_api_base(self) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.model = "anthropic/claude-sonnet-4-20250514"

        router = DefaultModelRouter(ollama_api_base="http://localhost:11434")
        policy = ModelPolicy("anthropic", "claude-sonnet-4-20250514", 8192, 0.1)

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            import litellm

            await router.call_model(policy, [{"role": "user", "content": "hi"}])
            litellm.acompletion.assert_called_once()
            call_kwargs = litellm.acompletion.call_args[1]
            assert "api_base" not in call_kwargs
