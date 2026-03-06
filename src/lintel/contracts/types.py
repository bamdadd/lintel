"""Core domain types for Lintel. Immutable, no I/O dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType
from uuid import UUID


@dataclass(frozen=True)
class ThreadRef:
    """Canonical identifier for a workflow instance (Slack thread)."""

    workspace_id: str
    channel_id: str
    thread_ts: str

    @property
    def stream_id(self) -> str:
        return f"thread:{self.workspace_id}:{self.channel_id}:{self.thread_ts}"

    def __str__(self) -> str:
        return self.stream_id


class ActorType(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class AgentRole(StrEnum):
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    PM = "pm"
    DESIGNER = "designer"
    SUMMARIZER = "summarizer"


class WorkflowPhase(StrEnum):
    INGESTING = "ingesting"
    PLANNING = "planning"
    AWAITING_SPEC_APPROVAL = "awaiting_spec_approval"
    IMPLEMENTING = "implementing"
    REVIEWING = "reviewing"
    AWAITING_MERGE_APPROVAL = "awaiting_merge_approval"
    MERGING = "merging"
    CLOSED = "closed"


class RepoStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    ERROR = "error"


@dataclass(frozen=True)
class Repository:
    """A registered git repository that workflows can operate on."""

    repo_id: str
    name: str
    url: str
    default_branch: str = "main"
    owner: str = ""
    provider: str = "github"
    status: RepoStatus = RepoStatus.ACTIVE


class AIProviderType(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    GOOGLE = "google"
    OLLAMA = "ollama"
    BEDROCK = "bedrock"
    CUSTOM = "custom"


@dataclass(frozen=True)
class AIProvider:
    """A configured AI model provider with API credentials."""

    provider_id: str
    provider_type: AIProviderType
    name: str
    api_base: str = ""
    is_default: bool = False
    models: tuple[str, ...] = ()
    config: dict[str, object] | None = None


class CredentialType(StrEnum):
    SSH_KEY = "ssh_key"
    GITHUB_TOKEN = "github_token"
    AI_PROVIDER_API_KEY = "ai_provider_api_key"


@dataclass(frozen=True)
class Credential:
    """A stored credential (SSH key or GitHub token) for repo access."""

    credential_id: str
    credential_type: CredentialType
    name: str
    repo_ids: frozenset[str] = frozenset()  # empty = applies to all repos


class SandboxStatus(StrEnum):
    PENDING = "pending"
    CREATING = "creating"
    RUNNING = "running"
    COLLECTING = "collecting"
    COMPLETED = "completed"
    FAILED = "failed"
    DESTROYED = "destroyed"


class SkillExecutionMode(StrEnum):
    INLINE = "inline"
    ASYNC_JOB = "async_job"
    SANDBOX = "sandbox"


@dataclass(frozen=True)
class ModelPolicy:
    """Policy for model selection per agent role."""

    provider: str
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.0


@dataclass(frozen=True)
class SkillDescriptor:
    """Metadata describing a registered skill."""

    name: str
    version: str
    description: str = ""
    input_schema: dict[str, object] | None = None
    output_schema: dict[str, object] | None = None
    execution_mode: SkillExecutionMode = SkillExecutionMode.INLINE
    allowed_agent_roles: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SkillResult:
    """Result of a skill invocation."""

    success: bool
    output: dict[str, object] | None = None
    error: str | None = None


@dataclass(frozen=True)
class SandboxConfig:
    """Configuration for creating a sandbox container."""

    image: str = "python:3.12-slim"
    memory_limit: str = "512m"
    cpu_quota: int = 50000


@dataclass(frozen=True)
class SandboxJob:
    """A command to execute in a sandbox."""

    command: str
    workdir: str | None = None


@dataclass(frozen=True)
class SandboxResult:
    """Result of a sandbox command execution."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""


# --- Project & Work Items ---


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class Project:
    """Links a repo, Slack channel, workflow config, and credentials together."""

    project_id: str
    name: str
    repo_id: str
    channel_id: str = ""
    workspace_id: str = ""
    workflow_definition_id: str = "feature_to_pr"
    default_branch: str = "main"
    credential_ids: tuple[str, ...] = ()
    ai_provider_id: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE


class WorkItemStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    MERGED = "merged"
    CLOSED = "closed"
    FAILED = "failed"


class WorkItemType(StrEnum):
    FEATURE = "feature"
    BUG = "bug"
    REFACTOR = "refactor"
    TASK = "task"


@dataclass(frozen=True)
class WorkItem:
    """Individual unit of work tracked through the pipeline."""

    work_item_id: str
    project_id: str
    title: str
    description: str = ""
    work_type: WorkItemType = WorkItemType.TASK
    status: WorkItemStatus = WorkItemStatus.OPEN
    assignee_agent_role: str = ""
    thread_ref_str: str = ""
    branch_name: str = ""
    pr_url: str = ""


# --- Pipeline & Stages ---


class PipelineStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class Stage:
    """A single step in a pipeline execution."""

    stage_id: str
    name: str
    stage_type: str  # ingest, plan, approve, implement, test, review, merge
    status: StageStatus = StageStatus.PENDING
    inputs: dict[str, object] | None = None
    outputs: dict[str, object] | None = None
    error: str = ""
    duration_ms: int = 0


@dataclass(frozen=True)
class PipelineRun:
    """A specific execution of a workflow/pipeline."""

    run_id: str
    project_id: str
    work_item_id: str
    workflow_definition_id: str
    status: PipelineStatus = PipelineStatus.PENDING
    stages: tuple[Stage, ...] = ()
    trigger_type: str = ""
    trigger_id: str = ""


# --- Environment & Variables ---


class EnvironmentType(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    SANDBOX = "sandbox"


@dataclass(frozen=True)
class Environment:
    """Target deployment context."""

    environment_id: str
    name: str
    env_type: EnvironmentType = EnvironmentType.DEVELOPMENT
    project_id: str = ""
    config: dict[str, object] | None = None


@dataclass(frozen=True)
class Variable:
    """Runtime variable scoped to project/environment."""

    variable_id: str
    key: str
    value: str
    project_id: str = ""
    environment_id: str = ""
    is_secret: bool = False


# --- Triggers ---


class TriggerType(StrEnum):
    SLACK_MESSAGE = "slack_message"
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    PR_EVENT = "pr_event"
    MANUAL = "manual"


@dataclass(frozen=True)
class Trigger:
    """What starts a pipeline."""

    trigger_id: str
    project_id: str
    trigger_type: TriggerType
    name: str
    config: dict[str, object] | None = None
    enabled: bool = True


# --- Artifacts & Test Results ---


@dataclass(frozen=True)
class CodeArtifact:
    """Stores file changes produced by an agent."""

    artifact_id: str
    work_item_id: str
    run_id: str
    artifact_type: str  # diff, file, log
    path: str = ""
    content: str = ""
    metadata: dict[str, object] | None = None


class TestVerdict(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class TestResult:
    """Structured test execution output."""

    result_id: str
    run_id: str
    stage_id: str
    verdict: TestVerdict
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_ms: int = 0
    output: str = ""
    failures: tuple[str, ...] = ()


# --- Approval Requests ---


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ApprovalRequest:
    """Tracks a pending approval with state and metadata."""

    approval_id: str
    run_id: str
    gate_type: str  # spec_approval, merge_approval
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_by: str = ""
    decided_by: str = ""
    reason: str = ""
    expires_at: str = ""


# --- Agent Sessions ---


@dataclass(frozen=True)
class AgentSession:
    """Tracks an agent's execution within a pipeline stage."""

    session_id: str
    run_id: str
    stage_id: str
    agent_role: str
    messages: tuple[dict[str, object], ...] = ()
    tool_calls: tuple[dict[str, object], ...] = ()
    token_usage: dict[str, int] | None = None
    model_used: str = ""


# --- Notifications ---


class NotificationChannel(StrEnum):
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"


@dataclass(frozen=True)
class NotificationRule:
    """When/how to notify users."""

    rule_id: str
    project_id: str
    event_types: tuple[str, ...] = ()
    channel: NotificationChannel = NotificationChannel.SLACK
    target: str = ""  # channel_id, email, webhook_url
    enabled: bool = True


# --- Governance / Policy ---


class PolicyAction(StrEnum):
    REQUIRE_APPROVAL = "require_approval"
    AUTO_APPROVE = "auto_approve"
    BLOCK = "block"
    NOTIFY = "notify"


@dataclass(frozen=True)
class Policy:
    """Governance rule for workflow behavior."""

    policy_id: str
    name: str
    event_type: str = ""  # when this event occurs
    condition: str = ""  # expression to evaluate
    action: PolicyAction = PolicyAction.REQUIRE_APPROVAL
    approvers: tuple[str, ...] = ()
    project_id: str = ""


# --- Users & Teams ---


class UserRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


@dataclass(frozen=True)
class User:
    """Platform user."""

    user_id: str
    name: str
    email: str = ""
    role: UserRole = UserRole.MEMBER
    slack_user_id: str = ""
    team_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Team:
    """Group of users with shared permissions."""

    team_id: str
    name: str
    member_ids: tuple[str, ...] = ()
    project_ids: tuple[str, ...] = ()


# --- Audit ---


@dataclass(frozen=True)
class AuditEntry:
    """Who did what, when."""

    entry_id: str
    actor_id: str
    actor_type: str  # user, agent, system
    action: str
    resource_type: str
    resource_id: str
    details: dict[str, object] | None = None
    timestamp: str = ""


CorrelationId = NewType("CorrelationId", UUID)
EventId = NewType("EventId", UUID)
