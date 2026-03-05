"""Protocol interfaces defining service boundaries.

Domain code depends on these abstractions. Infrastructure provides implementations.
No concrete imports from infrastructure in this file.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence
from uuid import UUID

from lintel.contracts.events import EventEnvelope
from lintel.contracts.types import AgentRole, ModelPolicy, ThreadRef


class EventStore(Protocol):
    """Append-only event persistence with optimistic concurrency."""

    async def append(
        self,
        stream_id: str,
        events: Sequence[EventEnvelope],
        expected_version: int | None = None,
    ) -> None: ...

    async def read_stream(
        self,
        stream_id: str,
        from_version: int = 0,
    ) -> list[EventEnvelope]: ...

    async def read_all(
        self,
        from_position: int = 0,
        limit: int = 1000,
    ) -> list[EventEnvelope]: ...

    async def read_by_correlation(
        self,
        correlation_id: UUID,
    ) -> list[EventEnvelope]: ...


class DeidentifyResult(Protocol):
    sanitized_text: str
    entities_detected: list[dict[str, Any]]
    placeholder_count: int
    is_blocked: bool
    risk_score: float


class Deidentifier(Protocol):
    """PII detection and anonymization pipeline."""

    async def analyze_and_anonymize(
        self,
        text: str,
        thread_ref: ThreadRef,
        language: str = "en",
    ) -> DeidentifyResult: ...


class PIIVault(Protocol):
    """Encrypted storage for PII placeholder mappings."""

    async def store_mapping(
        self,
        thread_ref: ThreadRef,
        placeholder: str,
        entity_type: str,
        raw_value: str,
    ) -> None: ...

    async def reveal(
        self,
        thread_ref: ThreadRef,
        placeholder: str,
        revealer_id: str,
    ) -> str: ...


class ChannelAdapter(Protocol):
    """Pluggable channel interface. Slack is the first implementation."""

    async def send_message(
        self,
        channel_id: str,
        thread_ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...

    async def update_message(
        self,
        channel_id: str,
        message_ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...

    async def send_approval_request(
        self,
        channel_id: str,
        thread_ts: str,
        gate_type: str,
        summary: str,
        callback_id: str,
    ) -> dict[str, Any]: ...


class ModelRouter(Protocol):
    """Selects model provider based on agent role and policy."""

    async def select_model(
        self,
        agent_role: AgentRole,
        workload_type: str,
    ) -> ModelPolicy: ...

    async def call_model(
        self,
        policy: ModelPolicy,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...


class CommandResult(Protocol):
    exit_code: int
    stdout: str
    stderr: str


class SandboxManager(Protocol):
    """Manages isolated sandbox containers for code execution."""

    async def create_sandbox(
        self,
        job_id: UUID,
        repo_url: str,
        base_sha: str,
        branch_name: str,
        devcontainer_config: dict[str, Any] | None = None,
    ) -> str: ...

    async def execute_command(
        self,
        container_id: str,
        command: str,
        timeout: int = 300,
    ) -> CommandResult: ...

    async def collect_artifacts(
        self,
        container_id: str,
    ) -> dict[str, Any]: ...

    async def destroy_sandbox(
        self,
        container_id: str,
    ) -> None: ...


class RepoProvider(Protocol):
    """Git and PR operations for a repository host."""

    async def clone_repo(
        self,
        repo_url: str,
        branch: str,
        target_dir: str,
    ) -> None: ...

    async def create_branch(
        self,
        repo_url: str,
        branch_name: str,
        base_sha: str,
    ) -> None: ...

    async def create_pr(
        self,
        repo_url: str,
        branch_name: str,
        title: str,
        body: str,
    ) -> dict[str, Any]: ...


class SkillRegistry(Protocol):
    """Dynamic skill registration and discovery."""

    async def register(
        self,
        skill_id: str,
        version: str,
        name: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        execution_mode: str,
    ) -> None: ...

    async def invoke(
        self,
        skill_id: str,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def list_skills(self) -> list[dict[str, Any]]: ...
