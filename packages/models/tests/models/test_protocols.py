"""Tests for model protocol interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lintel.models.types import ModelPolicy

if TYPE_CHECKING:
    from lintel.agents.types import AgentRole
    from lintel.models.protocols import ModelRouter


class TestModelRouterConformance:
    def test_conformance(self) -> None:
        class FakeRouter:
            async def select_model(
                self,
                agent_role: AgentRole,
                workload_type: str,
            ) -> ModelPolicy:
                return ModelPolicy(provider="test", model_name="test")

            async def call_model(
                self,
                policy: ModelPolicy,
                messages: list[dict[str, str]],
                tools: list[dict[str, Any]] | None = None,
            ) -> dict[str, Any]:
                return {}

        router: ModelRouter = FakeRouter()  # type: ignore[assignment]
        assert router is not None
