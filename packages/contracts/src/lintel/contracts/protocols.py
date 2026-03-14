"""Protocol interfaces defining service boundaries.

Domain code depends on these abstractions. Infrastructure provides implementations.
No concrete imports from infrastructure in this file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from datetime import datetime
    from uuid import UUID

    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.types import (
        AgentRole,
        Credential,
        ModelPolicy,
        Repository,
        SandboxConfig,
        SandboxJob,
        SandboxResult,
        SandboxStatus,
        SkillDescriptor,
        SkillResult,
        ThreadRef,
    )


class EventHandler(Protocol):
    """Handles a single event delivered by the EventBus."""

    async def handle(self, event: EventEnvelope) -> None: ...


class EventBus(Protocol):
    """Publish-subscribe bus for domain events."""

    async def publish(self, event: EventEnvelope) -> None: ...

    async def subscribe(
        self,
        event_types: frozenset[str],
        handler: EventHandler,
    ) -> str: ...

    async def unsubscribe(self, subscription_id: str) -> None: ...


class CommandDispatcher(Protocol):
    """Routes commands to registered handlers."""

    async def dispatch(self, command: object) -> object: ...


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

    async def read_by_event_type(
        self,
        event_type: str,
        from_position: int = 0,
        limit: int = 1000,
    ) -> list[EventEnvelope]: ...

    async def read_by_time_range(
        self,
        from_time: datetime,
        to_time: datetime,
        event_types: frozenset[str] | None = None,
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
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> dict[str, Any]: ...

    async def stream_model(
        self,
        policy: ModelPolicy,
        messages: list[dict[str, Any]],
        api_base: str | None = None,
    ) -> AsyncIterator[str]:
        yield ""  # pragma: no cover


class SandboxManager(Protocol):
    """Manages isolated sandbox environments for agent code execution."""

    async def create(
        self,
        config: SandboxConfig,
        thread_ref: ThreadRef,
    ) -> str: ...

    async def execute(
        self,
        sandbox_id: str,
        job: SandboxJob,
    ) -> SandboxResult: ...

    async def execute_stream(
        self,
        sandbox_id: str,
        job: SandboxJob,
    ) -> AsyncIterator[str]:
        """Execute a command and yield stdout/stderr lines as they arrive.

        Returns an async iterator of output lines (combined stdout+stderr).
        The final yielded item is a sentinel ``__EXIT:<code>__`` carrying the
        exit code so callers can detect success/failure without a separate call.
        """
        yield ""  # pragma: no cover

    async def read_file(
        self,
        sandbox_id: str,
        path: str,
    ) -> str: ...

    async def write_file(
        self,
        sandbox_id: str,
        path: str,
        content: str,
    ) -> None: ...

    async def list_files(
        self,
        sandbox_id: str,
        path: str = "/workspace",
    ) -> list[str]: ...

    async def get_status(
        self,
        sandbox_id: str,
    ) -> SandboxStatus: ...

    async def get_logs(
        self,
        sandbox_id: str,
        tail: int = 200,
    ) -> str: ...

    async def collect_artifacts(
        self,
        sandbox_id: str,
        workdir: str = "/workspace",
    ) -> dict[str, Any]: ...

    async def reconnect_network(
        self,
        sandbox_id: str,
    ) -> None: ...

    async def disconnect_network(
        self,
        sandbox_id: str,
    ) -> None: ...

    async def destroy(
        self,
        sandbox_id: str,
    ) -> None: ...


class CredentialStore(Protocol):
    """Secure storage for SSH keys and GitHub tokens."""

    async def store(
        self,
        credential_id: str,
        credential_type: str,
        name: str,
        secret: str,
        repo_ids: list[str] | None = None,
    ) -> Credential: ...

    async def get(self, credential_id: str) -> Credential | None: ...

    async def list_all(self) -> list[Credential]: ...

    async def list_by_repo(self, repo_id: str) -> list[Credential]: ...

    async def get_secret(self, credential_id: str) -> str | None: ...

    async def revoke(self, credential_id: str) -> None: ...


class RepositoryStore(Protocol):
    """Persistence for registered repositories."""

    async def add(self, repository: Repository) -> None: ...

    async def get(self, repo_id: str) -> Repository | None: ...

    async def get_by_url(self, url: str) -> Repository | None: ...

    async def list_all(self) -> list[Repository]: ...

    async def update(self, repository: Repository) -> None: ...

    async def remove(self, repo_id: str) -> None: ...


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

    async def commit_and_push(
        self,
        workdir: str,
        message: str,
        branch: str,
    ) -> str: ...

    async def create_pr(
        self,
        repo_url: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> str: ...

    async def add_comment(
        self,
        repo_url: str,
        pr_number: int,
        body: str,
    ) -> None: ...

    async def list_branches(
        self,
        repo_url: str,
    ) -> list[str]: ...

    async def get_file_content(
        self,
        repo_url: str,
        path: str,
        ref: str = "HEAD",
    ) -> str: ...

    async def list_commits(
        self,
        repo_url: str,
        branch: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]: ...

    async def list_pull_requests(
        self,
        repo_url: str,
        state: str = "open",
        limit: int = 20,
    ) -> list[dict[str, Any]]: ...


class StepMetricsRecorder(Protocol):
    """Records per-step OTel metrics for workflow execution."""

    def record_step_duration(
        self,
        workflow_id: str,
        step_type: str,
        tool_name: str,
        status: str,
        duration_s: float,
    ) -> None: ...

    def record_step_tokens(
        self,
        workflow_id: str,
        step_type: str,
        model_id: str,
        tokens: int,
    ) -> None: ...


class Skill(Protocol):
    """A single executable skill."""

    @property
    def descriptor(self) -> SkillDescriptor: ...

    async def execute(
        self,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult: ...


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
