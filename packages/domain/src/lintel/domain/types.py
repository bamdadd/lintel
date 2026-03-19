"""Domain types.

Defines all general domain types that don't belong to a specific
infrastructure package. Types for workflows/pipelines live in
lintel.workflows.types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime


# --- Project & Work Items ---


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class Project:
    """A project groups repositories, credentials, and work items."""

    project_id: str
    name: str
    description: str = ""
    repo_ids: tuple[str, ...] = ()
    default_branch: str = "main"
    credential_ids: tuple[str, ...] = ()
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
    tags: tuple[str, ...] = ()
    column_id: str = ""
    column_position: int = 0


# --- Task Board ---


@dataclass(frozen=True)
class Tag:
    """Label that can be attached to work items for grouping and filtering."""

    tag_id: str
    project_id: str
    name: str
    color: str = "#6b7280"


@dataclass(frozen=True)
class BoardColumn:
    """A column within a board (e.g. To Do, In Progress, Done)."""

    column_id: str
    name: str
    position: int = 0
    work_item_status: str = ""
    wip_limit: int = 0  # 0 = unlimited


@dataclass(frozen=True)
class Board:
    """A task board that organises work items into columns."""

    board_id: str
    project_id: str
    name: str
    columns: tuple[BoardColumn, ...] = ()
    auto_move: bool = False


# --- Environment & Variables ---


class EnvironmentType(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    SANDBOX = "sandbox"


@dataclass(frozen=True)
class Environment:
    """Target deployment context with variables passed to workflow steps."""

    environment_id: str
    name: str
    env_type: EnvironmentType = EnvironmentType.DEVELOPMENT
    config: dict[str, object] | None = None


@dataclass(frozen=True)
class Variable:
    """Runtime variable scoped to an environment."""

    variable_id: str
    key: str
    value: str
    environment_id: str = ""
    is_secret: bool = False


# --- Triggers ---


class TriggerType(StrEnum):
    SLACK_MESSAGE = "slack_message"
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    PR_EVENT = "pr_event"
    MANUAL = "manual"
    WORK_ITEM = "work_item"
    CHAT = "chat"


@dataclass(frozen=True)
class Trigger:
    """What starts a pipeline."""

    trigger_id: str
    project_id: str
    trigger_type: TriggerType
    name: str
    config: dict[str, object] | None = None
    enabled: bool = True


class HookType(StrEnum):
    PRE = "pre"
    POST = "post"
    SCHEDULED = "scheduled"


@dataclass(frozen=True)
class WorkflowHook:
    """Binds an event pattern to a workflow trigger."""

    hook_id: str
    project_id: str
    name: str
    event_pattern: str  # glob-style, e.g. "pipeline.stage.completed", "*.succeeded"
    hook_type: HookType = HookType.POST
    workflow_id: str = ""  # workflow definition to trigger
    conditions: dict[str, object] | None = None  # filter on event payload
    params_template: dict[str, str] | None = None  # map event fields to workflow params
    enabled: bool = True
    max_chain_depth: int = 5  # prevent infinite hook loops


class AutomationTriggerType(StrEnum):
    CRON = "cron"
    EVENT = "event"
    MANUAL = "manual"


class ConcurrencyPolicy(StrEnum):
    ALLOW = "allow"
    QUEUE = "queue"
    SKIP = "skip"
    CANCEL = "cancel"


@dataclass(frozen=True)
class AutomationDefinition:
    """Server-side automation rule that executes workflows on schedule or event."""

    automation_id: str
    name: str
    project_id: str
    workflow_definition_id: str
    trigger_type: AutomationTriggerType
    trigger_config: dict[str, object]
    input_parameters: dict[str, object] = field(default_factory=dict)
    concurrency_policy: ConcurrencyPolicy = ConcurrencyPolicy.QUEUE
    enabled: bool = True
    max_chain_depth: int = 3
    created_at: str = ""
    updated_at: str = ""


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
    storage_backend: Literal["postgres", "s3"] = "postgres"
    storage_location: str | None = None
    size_bytes: int | None = None
    content_type: str | None = None


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
    gate_type: str  # spec_approval, pr_approval
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_by: str = ""
    decided_by: str = ""
    reason: str = ""
    expires_at: str = ""


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


# --- Compliance & Governance ---


class ComplianceStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    DEPRECATED = "deprecated"
    NON_COMPLIANT = "non_compliant"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Regulation:
    """External regulation that applies to a project (e.g. HIPAA, GDPR, IEC 62304)."""

    regulation_id: str
    project_id: str
    name: str
    description: str = ""
    authority: str = ""  # e.g. "EU", "FDA", "ISO"
    reference_url: str = ""
    version: str = ""
    status: ComplianceStatus = ComplianceStatus.ACTIVE
    risk_level: RiskLevel = RiskLevel.MEDIUM
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompliancePolicy:
    """Internal policy interpreting a regulation (e.g. ISO 27001 coding standards)."""

    policy_id: str
    project_id: str
    name: str
    description: str = ""
    regulation_ids: tuple[str, ...] = ()  # links to parent regulations
    owner: str = ""
    status: ComplianceStatus = ComplianceStatus.DRAFT
    risk_level: RiskLevel = RiskLevel.MEDIUM
    review_date: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Procedure:
    """Step-by-step implementation of a policy (maps to a workflow definition)."""

    procedure_id: str
    project_id: str
    name: str
    description: str = ""
    policy_ids: tuple[str, ...] = ()  # links to parent policies
    workflow_definition_id: str = ""  # optional link to a workflow
    steps: tuple[str, ...] = ()  # ordered step descriptions
    owner: str = ""
    status: ComplianceStatus = ComplianceStatus.DRAFT
    risk_level: RiskLevel = RiskLevel.MEDIUM
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Practice:
    """Concrete practice implementing a procedure, derived from strategy."""

    practice_id: str
    project_id: str
    name: str
    description: str = ""
    procedure_ids: tuple[str, ...] = ()  # links to parent procedures
    strategy_ids: tuple[str, ...] = ()  # links to parent strategies
    evidence_type: str = ""  # e.g. "test_results", "code_review", "audit_log"
    automation_status: str = ""  # "manual", "semi_automated", "fully_automated"
    status: ComplianceStatus = ComplianceStatus.ACTIVE
    risk_level: RiskLevel = RiskLevel.LOW
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Strategy:
    """High-level strategy (e.g. testing strategy, security strategy)."""

    strategy_id: str
    project_id: str
    name: str
    description: str = ""
    objectives: tuple[str, ...] = ()
    owner: str = ""
    status: ComplianceStatus = ComplianceStatus.ACTIVE
    tags: tuple[str, ...] = ()


class PolicyGenerationStatus(StrEnum):
    PENDING = "pending"
    ANALYSING = "analysing"
    GENERATING = "generating"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class PolicyGenerationRun:
    """Tracks a regulation-to-policy generation workflow run.

    Captures the AI-generated policies, plus assumptions made, questions
    requiring human input, and action items for the user to resolve.
    """

    run_id: str
    project_id: str
    regulation_ids: tuple[str, ...] = ()
    status: PolicyGenerationStatus = PolicyGenerationStatus.PENDING
    industry_context: str = ""  # e.g. "healthcare", "finance", "it"
    project_description: str = ""  # snapshot of project description at run time
    additional_context: str = ""  # user-provided context for this run
    generated_policy_ids: tuple[str, ...] = ()  # IDs of CompliancePolicy created
    generated_procedure_ids: tuple[str, ...] = ()  # IDs of Procedure created
    assumptions: tuple[str, ...] = ()  # AI assumptions (e.g. "Data retention: 7 years")
    questions: tuple[str, ...] = ()  # questions for user to answer
    action_items: tuple[str, ...] = ()  # things user needs to work out
    summary: str = ""  # overall summary of what was generated
    error: str = ""
    started_at: str = ""
    completed_at: str = ""


class KPIDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    MAINTAIN = "maintain"


@dataclass(frozen=True)
class KPI:
    """Key performance indicator tied to a project."""

    kpi_id: str
    project_id: str
    name: str
    description: str = ""
    target_value: str = ""
    current_value: str = ""
    unit: str = ""
    direction: KPIDirection = KPIDirection.INCREASE
    strategy_ids: tuple[str, ...] = ()
    threshold_warning: str = ""
    threshold_critical: str = ""
    status: ComplianceStatus = ComplianceStatus.ACTIVE
    tags: tuple[str, ...] = ()


class ExperimentStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Experiment:
    """Tracked experiment within a project."""

    experiment_id: str
    project_id: str
    name: str
    hypothesis: str = ""
    description: str = ""
    strategy_ids: tuple[str, ...] = ()
    kpi_ids: tuple[str, ...] = ()  # KPIs being measured
    status: ExperimentStatus = ExperimentStatus.PLANNED
    start_date: str = ""
    end_date: str = ""
    outcome: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComplianceMetric:
    """Measurable metric for compliance tracking."""

    metric_id: str
    project_id: str
    name: str
    description: str = ""
    value: str = ""
    unit: str = ""
    source: str = ""  # "automated", "manual", "agent"
    kpi_ids: tuple[str, ...] = ()
    collected_at: str = ""
    tags: tuple[str, ...] = ()


class KnowledgeEntryType(StrEnum):
    LOGIC_FLOW = "logic_flow"
    EVENT_HANDLER = "event_handler"
    INTEGRATION = "integration"
    DATA_MODEL = "data_model"
    API_ENDPOINT = "api_endpoint"
    BUSINESS_RULE = "business_rule"
    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    STALE = "stale"


@dataclass(frozen=True)
class KnowledgeEntry:
    """Extracted knowledge from a codebase."""

    entry_id: str
    project_id: str
    name: str
    entry_type: KnowledgeEntryType = KnowledgeEntryType.LOGIC_FLOW
    description: str = ""
    source_file: str = ""
    source_repo: str = ""
    source_lines: str = ""  # e.g. "10-50"
    dependencies: tuple[str, ...] = ()  # other entry IDs
    code_snippet: str = ""
    extracted_at: str = ""
    status: ExtractionStatus = ExtractionStatus.COMPLETED
    tags: tuple[str, ...] = ()


class ADRStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class ArchitectureDecision:
    """Architecture Decision Record (ADR) linked to a project."""

    decision_id: str
    project_id: str
    title: str
    status: ADRStatus = ADRStatus.PROPOSED
    context: str = ""
    decision: str = ""
    consequences: str = ""
    alternatives: str = ""
    superseded_by: str = ""
    regulation_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    date_proposed: str = ""
    date_decided: str = ""
    deciders: tuple[str, ...] = ()


@dataclass(frozen=True)
class KnowledgeExtractionRun:
    """A run of the knowledge extraction process."""

    run_id: str
    project_id: str
    repo_id: str = ""
    status: ExtractionStatus = ExtractionStatus.PENDING
    total_files: int = 0
    processed_files: int = 0
    entries_found: int = 0
    started_at: str = ""
    completed_at: str = ""
    error: str = ""


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


@dataclass(frozen=True)
class MCPServer:
    """A configured MCP server that provides tools to chat sessions."""

    server_id: str
    name: str
    url: str
    enabled: bool = True
    description: str = ""
    config: dict[str, object] | None = None


@dataclass(frozen=True)
class ChatSession:
    """A chat session that can trigger workflows and access MCP servers."""

    session_id: str
    project_id: str
    thread_ref_str: str = ""
    mcp_server_ids: tuple[str, ...] = ()


# --- Delivery Loop ---

DEFAULT_DELIVERY_PHASES: tuple[str, ...] = (
    "desire",
    "develop",
    "review",
    "deploy",
    "observe",
    "learn",
)


@dataclass(frozen=True)
class PhaseTransitionRecord:
    """Records a single phase transition in the delivery loop."""

    from_phase: str
    to_phase: str
    occurred_at: datetime
    is_rework: bool = False


@dataclass(frozen=True)
class DeliveryLoop:
    """Tracks the full delivery lifecycle for a work item."""

    loop_id: str
    work_item_id: str
    project_id: str
    phase_sequence: tuple[str, ...] = DEFAULT_DELIVERY_PHASES
    current_phase: str = ""
    phase_history: tuple[PhaseTransitionRecord, ...] = ()
    started_at: datetime | None = None
    completed_at: datetime | None = None
    learnings: dict[str, object] | None = None


# --- Resource Versions ---


@dataclass(frozen=True)
class ResourceVersion:
    """A versioned resource output from a pipeline job."""

    resource_name: str
    version: dict[str, str]
    metadata: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class PassedConstraint:
    """Requires a resource version to have passed through specific upstream jobs."""

    resource_name: str
    jobs: tuple[str, ...] = ()


@dataclass(frozen=True)
class JobInput:
    """Input specification for a pipeline job."""

    resource_name: str
    trigger: bool = True
    passed_constraints: tuple[PassedConstraint, ...] = ()
