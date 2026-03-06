"""Tests for protocol interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from lintel.contracts.events import EventEnvelope


class TestProtocolsAreImportable:
    def test_all_protocols_importable(self) -> None:
        protocols = [
            EventStore,
            Deidentifier,
            DeidentifyResult,
            PIIVault,
            ChannelAdapter,
            ModelRouter,
            CommandResult,
            SandboxManager,
            RepoProvider,
            SkillRegistry,
        ]
        assert len(protocols) == 10


class TestEventStoreConformance:
    def test_conformance(self) -> None:
        class FakeStore:
            async def append(
                self,
                stream_id: str,
                events: Sequence[EventEnvelope],
                expected_version: int | None = None,
            ) -> None:
                pass

            async def read_stream(
                self,
                stream_id: str,
                from_version: int = 0,
            ) -> list[EventEnvelope]:
                return []

            async def read_all(
                self,
                from_position: int = 0,
                limit: int = 1000,
            ) -> list[EventEnvelope]:
                return []

            async def read_by_correlation(
                self,
                correlation_id: UUID,
            ) -> list[EventEnvelope]:
                return []

        store: EventStore = FakeStore()  # type: ignore[assignment]
        assert store is not None


class TestChannelAdapterConformance:
    def test_conformance(self) -> None:
        class FakeChannel:
            async def send_message(
                self,
                channel_id: str,
                thread_ts: str,
                text: str,
                blocks: list[dict[str, Any]] | None = None,
            ) -> dict[str, Any]:
                return {}

            async def update_message(
                self,
                channel_id: str,
                message_ts: str,
                text: str,
                blocks: list[dict[str, Any]] | None = None,
            ) -> dict[str, Any]:
                return {}

            async def send_approval_request(
                self,
                channel_id: str,
                thread_ts: str,
                gate_type: str,
                summary: str,
                callback_id: str,
            ) -> dict[str, Any]:
                return {}

        channel: ChannelAdapter = FakeChannel()  # type: ignore[assignment]
        assert channel is not None


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


class TestDeidentifierConformance:
    def test_conformance(self) -> None:
        @dataclass
        class FakeResult:
            sanitized_text: str = ""
            entities_detected: list[dict[str, Any]] = None  # type: ignore[assignment]
            placeholder_count: int = 0
            is_blocked: bool = False
            risk_score: float = 0.0

            def __post_init__(self) -> None:
                if self.entities_detected is None:
                    self.entities_detected = []

        class FakeDeidentifier:
            async def analyze_and_anonymize(
                self,
                text: str,
                thread_ref: ThreadRef,
                language: str = "en",
            ) -> FakeResult:
                return FakeResult(sanitized_text=text)

        deidentifier: Deidentifier = FakeDeidentifier()  # type: ignore[assignment]
        assert deidentifier is not None


class TestPIIVaultConformance:
    def test_conformance(self) -> None:
        class FakeVault:
            async def store_mapping(
                self,
                thread_ref: ThreadRef,
                placeholder: str,
                entity_type: str,
                raw_value: str,
            ) -> None:
                pass

            async def reveal(
                self,
                thread_ref: ThreadRef,
                placeholder: str,
                revealer_id: str,
            ) -> str:
                return "revealed"

        vault: PIIVault = FakeVault()  # type: ignore[assignment]
        assert vault is not None


class TestSandboxManagerConformance:
    def test_conformance(self) -> None:
        @dataclass
        class FakeCommandResult:
            exit_code: int = 0
            stdout: str = ""
            stderr: str = ""

        class FakeSandbox:
            async def create_sandbox(
                self,
                job_id: UUID,
                repo_url: str,
                base_sha: str,
                branch_name: str,
                devcontainer_config: dict[str, Any] | None = None,
            ) -> str:
                return "container-123"

            async def execute_command(
                self,
                container_id: str,
                command: str,
                timeout: int = 300,
            ) -> FakeCommandResult:
                return FakeCommandResult()

            async def collect_artifacts(
                self,
                container_id: str,
            ) -> dict[str, Any]:
                return {}

            async def destroy_sandbox(
                self,
                container_id: str,
            ) -> None:
                pass

        sandbox: SandboxManager = FakeSandbox()  # type: ignore[assignment]
        assert sandbox is not None


class TestRepoProviderConformance:
    def test_conformance(self) -> None:
        class FakeRepo:
            async def clone_repo(
                self,
                repo_url: str,
                branch: str,
                target_dir: str,
            ) -> None:
                pass

            async def create_branch(
                self,
                repo_url: str,
                branch_name: str,
                base_sha: str,
            ) -> None:
                pass

            async def create_pr(
                self,
                repo_url: str,
                branch_name: str,
                title: str,
                body: str,
            ) -> dict[str, Any]:
                return {"pr_number": 1}

        repo: RepoProvider = FakeRepo()  # type: ignore[assignment]
        assert repo is not None


class TestSkillRegistryConformance:
    def test_conformance(self) -> None:
        class FakeRegistry:
            async def register(
                self,
                skill_id: str,
                version: str,
                name: str,
                input_schema: dict[str, Any],
                output_schema: dict[str, Any],
                execution_mode: str,
            ) -> None:
                pass

            async def invoke(
                self,
                skill_id: str,
                input_data: dict[str, Any],
                context: dict[str, Any],
            ) -> dict[str, Any]:
                return {"result": "ok"}

            async def list_skills(self) -> list[dict[str, Any]]:
                return []

        registry: SkillRegistry = FakeRegistry()  # type: ignore[assignment]
        assert registry is not None


class TestCommandResultConformance:
    def test_conformance(self) -> None:
        @dataclass
        class FakeResult:
            exit_code: int = 0
            stdout: str = ""
            stderr: str = ""

        result: CommandResult = FakeResult()  # type: ignore[assignment]
        assert result is not None
        assert result.exit_code == 0
