"""Tests for the model router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from lintel.contracts.types import (
    AgentRole,
    AIProvider,
    AIProviderType,
    Model,
    ModelAssignment,
    ModelAssignmentContext,
    ModelPolicy,
)
from lintel.infrastructure.models.router import (
    FALLBACK_POLICY,
    DefaultModelRouter,
)


class TestDefaultModelRouter:
    """Tests for model selection logic."""

    async def test_select_uses_default_policy_when_set(self) -> None:
        default = ModelPolicy("ollama", "mistral:7b", 4096, 0.0)
        router = DefaultModelRouter(default_policy=default)
        policy = await router.select_model(AgentRole.PLANNER, "planning")
        assert policy == default

    async def test_select_falls_back_when_no_default(self) -> None:
        router = DefaultModelRouter()
        policy = await router.select_model(AgentRole.PLANNER, "planning")
        assert policy == FALLBACK_POLICY

    async def test_custom_routing_table_takes_precedence(self) -> None:
        custom = {
            ("planner", "planning"): ModelPolicy("openai", "gpt-4o", 4096, 0.0),
        }
        default = ModelPolicy("ollama", "mistral:7b", 4096, 0.0)
        router = DefaultModelRouter(default_policy=default, routing_table=custom)
        policy = await router.select_model(AgentRole.PLANNER, "planning")
        assert policy.provider == "openai"

    async def test_routing_miss_uses_default_not_fallback(self) -> None:
        custom = {
            ("planner", "planning"): ModelPolicy("openai", "gpt-4o", 4096, 0.0),
        }
        default = ModelPolicy("ollama", "mistral:7b", 4096, 0.0)
        router = DefaultModelRouter(default_policy=default, routing_table=custom)
        policy = await router.select_model(AgentRole.CODER, "coding")
        assert policy == default

    async def test_custom_fallback(self) -> None:
        fallback = ModelPolicy("test", "test-model", 1024, 0.5)
        router = DefaultModelRouter(fallback=fallback)
        policy = await router.select_model(AgentRole.CODER, "coding")
        assert policy == fallback

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
        mock_response.model = "openai/gpt-4o"

        router = DefaultModelRouter(ollama_api_base="http://localhost:11434")
        policy = ModelPolicy("openai", "gpt-4o", 8192, 0.1)

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            import litellm

            await router.call_model(policy, [{"role": "user", "content": "hi"}])
            litellm.acompletion.assert_called_once()
            call_kwargs = litellm.acompletion.call_args[1]
            assert "api_base" not in call_kwargs

    async def test_select_resolves_default_from_store(self) -> None:
        """When no routing table or default_policy, resolve from model store."""
        from lintel.api.routes.ai_providers import InMemoryAIProviderStore
        from lintel.api.routes.models import InMemoryModelStore

        provider_store = InMemoryAIProviderStore()
        model_store = InMemoryModelStore()

        provider = AIProvider(
            provider_id="p1",
            provider_type=AIProviderType.OLLAMA,
            name="Local Ollama",
        )
        await provider_store.add(provider)

        model = Model(
            model_id="m1",
            provider_id="p1",
            name="Qwen Coder",
            model_name="qwen2.5-coder:7b",
            max_tokens=8192,
            temperature=0.2,
            is_default=True,
        )
        await model_store.add(model)

        router = DefaultModelRouter(
            model_store=model_store,
            ai_provider_store=provider_store,
        )
        policy = await router.select_model(AgentRole.PLANNER, "planning")
        assert policy.provider == "ollama"
        assert policy.model_name == "qwen2.5-coder:7b"
        assert policy.max_tokens == 8192

    async def test_select_falls_back_when_no_default_in_store(self) -> None:
        """When store has models but none marked default, use fallback."""
        from lintel.api.routes.ai_providers import InMemoryAIProviderStore
        from lintel.api.routes.models import InMemoryModelStore

        provider_store = InMemoryAIProviderStore()
        model_store = InMemoryModelStore()

        provider = AIProvider(
            provider_id="p1",
            provider_type=AIProviderType.OLLAMA,
            name="Local Ollama",
        )
        await provider_store.add(provider)

        model = Model(
            model_id="m1",
            provider_id="p1",
            name="Some Model",
            model_name="llama3:8b",
            is_default=False,
        )
        await model_store.add(model)

        router = DefaultModelRouter(
            model_store=model_store,
            ai_provider_store=provider_store,
        )
        policy = await router.select_model(AgentRole.CODER, "coding")
        assert policy == FALLBACK_POLICY

    async def test_store_default_refreshes_on_change(self) -> None:
        """Default model is always resolved from store (no stale cache)."""
        from lintel.api.routes.ai_providers import InMemoryAIProviderStore
        from lintel.api.routes.models import InMemoryModelStore

        provider_store = InMemoryAIProviderStore()
        model_store = InMemoryModelStore()

        await provider_store.add(
            AIProvider(
                provider_id="p1",
                provider_type=AIProviderType.OLLAMA,
                name="Ollama",
            )
        )
        await model_store.add(
            Model(
                model_id="m1",
                provider_id="p1",
                name="Qwen",
                model_name="qwen2.5-coder:7b",
                is_default=True,
            )
        )

        router = DefaultModelRouter(
            model_store=model_store,
            ai_provider_store=provider_store,
        )
        # First call resolves from store
        p1 = await router.select_model(AgentRole.PLANNER, "planning")
        assert p1.model_name == "qwen2.5-coder:7b"

        # Change default model — router should pick up the new one
        await model_store.remove("m1")
        await model_store.add(
            Model(
                model_id="m2",
                provider_id="p1",
                name="New Model",
                model_name="llama3:8b",
                is_default=True,
            )
        )
        p2 = await router.select_model(AgentRole.CODER, "coding")
        assert p2.model_name == "llama3:8b"

    async def test_assignment_takes_precedence_over_default(self) -> None:
        """A model assigned to an agent role overrides the default model."""
        from lintel.api.routes.ai_providers import InMemoryAIProviderStore
        from lintel.api.routes.models import InMemoryModelAssignmentStore, InMemoryModelStore

        provider_store = InMemoryAIProviderStore()
        model_store = InMemoryModelStore()
        assignment_store = InMemoryModelAssignmentStore()

        await provider_store.add(
            AIProvider(
                provider_id="p1",
                provider_type=AIProviderType.OLLAMA,
                name="Ollama",
            )
        )
        # Default model
        await model_store.add(
            Model(
                model_id="m-default",
                provider_id="p1",
                name="Default",
                model_name="llama3.1:8b",
                is_default=True,
            )
        )
        # Coder-specific model
        await model_store.add(
            Model(
                model_id="m-coder",
                provider_id="p1",
                name="Qwen Coder",
                model_name="qwen2.5-coder:7b",
                max_tokens=8192,
                temperature=0.2,
            )
        )
        await assignment_store.add(
            ModelAssignment(
                assignment_id="a1",
                model_id="m-coder",
                context=ModelAssignmentContext.AGENT_ROLE,
                context_id="coder",
            )
        )

        router = DefaultModelRouter(
            model_store=model_store,
            ai_provider_store=provider_store,
            model_assignment_store=assignment_store,
        )

        # Coder gets the assigned model
        coder_policy = await router.select_model(AgentRole.CODER, "implement")
        assert coder_policy.model_name == "qwen2.5-coder:7b"
        assert coder_policy.max_tokens == 8192

        # Planner gets the default (no assignment)
        planner_policy = await router.select_model(AgentRole.PLANNER, "planning")
        assert planner_policy.model_name == "llama3.1:8b"

    async def test_highest_priority_assignment_wins(self) -> None:
        """When multiple assignments exist for a role, highest priority wins."""
        from lintel.api.routes.ai_providers import InMemoryAIProviderStore
        from lintel.api.routes.models import InMemoryModelAssignmentStore, InMemoryModelStore

        provider_store = InMemoryAIProviderStore()
        model_store = InMemoryModelStore()
        assignment_store = InMemoryModelAssignmentStore()

        await provider_store.add(
            AIProvider(
                provider_id="p1",
                provider_type=AIProviderType.OLLAMA,
                name="Ollama",
            )
        )
        await model_store.add(
            Model(
                model_id="m1",
                provider_id="p1",
                name="Low Priority",
                model_name="llama3:8b",
            )
        )
        await model_store.add(
            Model(
                model_id="m2",
                provider_id="p1",
                name="High Priority",
                model_name="qwen2.5-coder:7b",
            )
        )
        await assignment_store.add(
            ModelAssignment(
                assignment_id="a1",
                model_id="m1",
                context=ModelAssignmentContext.AGENT_ROLE,
                context_id="coder",
                priority=0,
            )
        )
        await assignment_store.add(
            ModelAssignment(
                assignment_id="a2",
                model_id="m2",
                context=ModelAssignmentContext.AGENT_ROLE,
                context_id="coder",
                priority=10,
            )
        )

        router = DefaultModelRouter(
            model_store=model_store,
            ai_provider_store=provider_store,
            model_assignment_store=assignment_store,
        )
        policy = await router.select_model(AgentRole.CODER, "implement")
        assert policy.model_name == "qwen2.5-coder:7b"
