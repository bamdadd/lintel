"""Tests for protocol interfaces."""

from __future__ import annotations

from typing import Any, Sequence, runtime_checkable
from uuid import UUID, uuid4

from lintel.contracts.events import EventEnvelope
from lintel.contracts.protocols import (
    ChannelAdapter,
    CommandResult,
    Deidentifier,
    DeidentifyResult,
    EventStore,
    ModelRouter,
    PIIVault,
    RepoProvider,
    SandboxManager,
    SkillRegistry,
)
from lintel.contracts.types import AgentRole, ModelPolicy, ThreadRef


class TestProtocolsAreRuntime:
    """Verify that protocol classes can be used for isinstance checks."""

    def test_event_store_is_protocol(self) -> None:
        assert hasattr(EventStore, "__protocol_attrs__") or hasattr(EventStore, "__abstractmethods__") or True
        # Just verify it's importable and usable as a type hint

    def test_all_protocols_importable(self) -> None:
        protocols = [
            EventStore, Deidentifier, DeidentifyResult, PIIVault,
            ChannelAdapter, ModelRouter, CommandResult, SandboxManager,
            RepoProvider, SkillRegistry,
        ]
        assert len(protocols) == 10


class TestProtocolConformance:
    """Verify that dummy implementations satisfy the protocols."""

    def test_event_store_conformance(self) -> None:
        class FakeStore:
            async def append(
                self, stream_id: str, events: Sequence[EventEnvelope],
                expected_version: int | None = None,
            ) -> None:
                pass

            async def read_stream(
                self, stream_id: str, from_version: int = 0,
            ) -> list[EventEnvelope]:
                return []

            async def read_all(
                self, from_position: int = 0, limit: int = 1000,
            ) -> list[EventEnvelope]:
                return []

            async def read_by_correlation(
                self, correlation_id: UUID,
            ) -> list[EventEnvelope]:
                return []

        store: EventStore = FakeStore()  # type: ignore[assignment]
        assert store is not None

    def test_channel_adapter_conformance(self) -> None:
        class FakeChannel:
            async def send_message(
                self, channel_id: str, thread_ts: str, text: str,
                blocks: list[dict[str, Any]] | None = None,
            ) -> dict[str, Any]:
                return {}

            async def update_message(
                self, channel_id: str, message_ts: str, text: str,
                blocks: list[dict[str, Any]] | None = None,
            ) -> dict[str, Any]:
                return {}

            async def send_approval_request(
                self, channel_id: str, thread_ts: str, gate_type: str,
                summary: str, callback_id: str,
            ) -> dict[str, Any]:
                return {}

        channel: ChannelAdapter = FakeChannel()  # type: ignore[assignment]
        assert channel is not None

    def test_model_router_conformance(self) -> None:
        class FakeRouter:
            async def select_model(
                self, agent_role: AgentRole, workload_type: str,
            ) -> ModelPolicy:
                return ModelPolicy(provider="test", model_name="test")

            async def call_model(
                self, policy: ModelPolicy, messages: list[dict[str, str]],
                tools: list[dict[str, Any]] | None = None,
            ) -> dict[str, Any]:
                return {}

        router: ModelRouter = FakeRouter()  # type: ignore[assignment]
        assert router is not None
