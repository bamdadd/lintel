"""Domain types.

Defines all general domain types that don't belong to a specific
infrastructure package. Types for workflows/pipelines live in
lintel.workflows.types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

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
    repo_descriptions: dict[str, str] = field(default_factory=dict)
    default_branch: str = "main"
    credential_ids: tuple[str, ...] = ()
    status: ProjectStatus = ProjectStatus.ACTIVE
    workflow_execution_enabled: bool = True
    max_review_cycles: int = 3


class WorkItemStatus(StrEnum):
    BACKLOG = "backlog"
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
    work_item_statuses: tuple[str, ...] = ()
    wip_limit: int = 0  # 0 = unlimited

    @property
    def work_item_status(self) -> str:
        """Backward compat — returns first status or empty string."""
        return self.work_item_statuses[0] if self.work_item_statuses else ""


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


class FrontendPlatform(StrEnum):
    """Supported frontend target platforms."""

    WEB = "web"
    IOS = "ios"
    ANDROID = "android"
    ELECTRON = "electron"


@dataclass(frozen=True)
class FrontendTarget:
    """A frontend target platform within a project."""

    target_id: str
    project_id: str
    platform: str
    label: str = ""
    config: dict[str, object] = field(default_factory=dict)


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


class HookActionType(StrEnum):
    """What a hook does when it fires."""

    TRIGGER_WORKFLOW = "trigger_workflow"
    WEBHOOK = "webhook"


@dataclass(frozen=True)
class WorkflowHook:
    """Binds an event pattern to a workflow trigger."""

    hook_id: str
    project_id: str
    name: str
    event_pattern: str  # glob-style, e.g. "pipeline.stage.completed", "*.succeeded"
    hook_type: HookType = HookType.POST
    action_type: HookActionType = HookActionType.TRIGGER_WORKFLOW
    workflow_id: str = ""  # workflow definition to trigger
    webhook_url: str = ""  # URL for webhook action type
    conditions: dict[str, object] | None = None  # filter on event payload
    params_template: dict[str, str] | None = None  # map event fields to workflow params
    enabled: bool = True
    max_chain_depth: int = 5  # prevent infinite hook loops


class PreHookDecision(StrEnum):
    """Result of a pre-hook evaluation."""

    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class HookResult:
    """Outcome of evaluating a single hook against an event."""

    hook_id: str
    hook_name: str
    hook_type: HookType
    decision: PreHookDecision = PreHookDecision.ALLOW
    reason: str = ""


# Backward-compat re-exports — canonical definitions live in lintel.automations.types
from lintel.automations.types import AutomationDefinition as AutomationDefinition  # noqa: E402
from lintel.automations.types import AutomationTriggerType as AutomationTriggerType  # noqa: E402
from lintel.automations.types import ConcurrencyPolicy as ConcurrencyPolicy  # noqa: E402

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
    WEB_PUSH = "web_push"
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
    gdrive_source_url: str = ""  # Google Drive URL when imported from GDrive


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


@dataclass(frozen=True)
class RunMetric:
    """A single metric captured during a pipeline run."""

    run_metric_id: str
    run_id: str
    experiment_id: str = ""
    metric_name: str = ""
    value: float = 0.0
    unit: str = ""
    timestamp: str = ""
    tags: tuple[str, ...] = ()


class MutationStrategy(StrEnum):
    """How a strategy config should be mutated on failure."""

    INCREASE_TIMEOUT = "increase_timeout"
    REDUCE_CONCURRENCY = "reduce_concurrency"
    SWITCH_MODEL = "switch_model"
    ADD_RETRY = "add_retry"
    CUSTOM = "custom"


@dataclass(frozen=True)
class StrategyMutation:
    """A suggested config mutation after a failed run."""

    mutation_id: str
    experiment_id: str
    source_run_id: str
    strategy: MutationStrategy = MutationStrategy.CUSTOM
    description: str = ""
    config_patch: dict[str, object] | None = None
    applied: bool = False
    created_at: str = ""


@dataclass(frozen=True)
class TournamentResult:
    """Result of comparing runs for the same task to select best strategy."""

    tournament_id: str
    experiment_id: str
    task_key: str = ""  # identifies the repeated task
    run_ids: tuple[str, ...] = ()
    winning_run_id: str = ""
    metric_name: str = ""  # metric used for comparison
    scores: dict[str, float] | None = None  # run_id -> score
    selected_at: str = ""


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
    previous_hash: str | None = None


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
class MCPTool:
    """A tool exposed by an MCP server, catalogued for agent use."""

    tool_id: str
    server_id: str
    name: str
    description: str = ""
    security_classification: str = "standard"
    enabled: bool = True


@dataclass(frozen=True)
class MCPToolAllowlist:
    """Per-project allowlist restricting which MCP tools agents may use."""

    allowlist_id: str
    project_id: str
    tool_ids: tuple[str, ...] = ()
    description: str = ""


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


# --- Codebase Index Types (REQ-026) ---


class IndexStatus(StrEnum):
    """Status of a codebase index."""

    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
    STALE = "stale"


@dataclass(frozen=True)
class CodebaseIndex:
    """A codebase index representing an ingested and embedded repository."""

    index_id: str
    project_id: str
    repository_url: str
    branch: str = "main"
    name: str = ""
    description: str = ""
    status: IndexStatus = IndexStatus.PENDING
    file_count: int = 0
    chunk_count: int = 0
    last_indexed_at: str = ""
    last_commit_sha: str = ""
    created_at: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class IndexEntry:
    """A single indexed chunk from a codebase."""

    entry_id: str
    index_id: str
    file_path: str
    chunk_index: int = 0
    content: str = ""
    language: str = ""
    start_line: int = 0
    end_line: int = 0
    embedding: tuple[float, ...] = ()


@dataclass(frozen=True)
class SearchResult:
    """A semantic search result from a codebase index."""

    entry_id: str
    index_id: str
    file_path: str
    content: str = ""
    score: float = 0.0
    language: str = ""
    start_line: int = 0
    end_line: int = 0


# --- Drift Detection Types ---


class DriftType(StrEnum):
    """Category of drift between layers."""

    CODE_INVALIDATES_ARCHITECTURE = "code_invalidates_architecture"
    SPEC_NOT_REFLECTED_IN_PLAN = "spec_not_reflected_in_plan"
    ARCHITECTURE_CONFLICTS_IMPLEMENTATION = "architecture_conflicts_implementation"
    FOUNDATION_DRIFT = "foundation_drift"


class DriftSeverity(StrEnum):
    """Severity level for drift alerts."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DriftAlertStatus(StrEnum):
    """Status of a drift alert."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class DriftScanStatus(StrEnum):
    """Status of a drift scan."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class DriftRule:
    """Configuration for a drift detection rule."""

    rule_id: str
    project_id: str
    name: str
    description: str = ""
    drift_type: DriftType = DriftType.CODE_INVALIDATES_ARCHITECTURE
    severity: DriftSeverity = DriftSeverity.MEDIUM
    enabled: bool = True
    source_layer: str = ""
    target_layer: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class DriftAlert:
    """A detected drift between layers."""

    alert_id: str
    project_id: str
    rule_id: str
    drift_type: DriftType = DriftType.CODE_INVALIDATES_ARCHITECTURE
    severity: DriftSeverity = DriftSeverity.MEDIUM
    status: DriftAlertStatus = DriftAlertStatus.OPEN
    title: str = ""
    description: str = ""
    source_ref: str = ""
    target_ref: str = ""
    remediation: str = ""
    scan_id: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class DriftScan:
    """A drift detection scan run."""

    scan_id: str
    project_id: str
    status: DriftScanStatus = DriftScanStatus.PENDING
    alerts_found: int = 0
    started_at: str = ""
    completed_at: str = ""
    trigger: str = ""
    tags: tuple[str, ...] = ()


# --- Agent Action Governance (REQ-030) ---


class GovernanceDecision(StrEnum):
    """Three-state decision for governance policy evaluation."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass(frozen=True)
class ActionScope:
    """Scope for a governance policy rule."""

    action: str = ""
    resource: str = ""


@dataclass(frozen=True)
class GovernancePolicy:
    """A governance policy defining per-agent/per-scope action rules."""

    policy_id: str = ""
    name: str = ""
    description: str = ""
    agent_role: str = ""
    scopes: tuple[ActionScope, ...] = ()
    default_decision: GovernanceDecision = GovernanceDecision.DENY
    active: bool = True
    project_id: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class GovernanceAuditEntry:
    """An audit entry recording a governance decision."""

    entry_id: str = ""
    policy_id: str = ""
    agent_id: str = ""
    action: str = ""
    resource: str = ""
    decision: GovernanceDecision = GovernanceDecision.DENY
    reason: str = ""
    project_id: str = ""
    timestamp: str = ""


# --- Privacy Controls (REQ-008) ---


class PrivacyLevel(StrEnum):
    """Privacy level for individual metric visibility."""

    PUBLIC = "public"
    TEAM_ONLY = "team_only"
    PRIVATE = "private"


@dataclass(frozen=True)
class MetricVisibility:
    """Controls visibility of a specific metric type for a user."""

    visibility_id: str = ""
    user_id: str = ""
    metric_type: str = ""
    privacy_level: PrivacyLevel = PrivacyLevel.PRIVATE
    allowed_viewers: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class PrivacyPreference:
    """Default privacy preferences for a user."""

    preference_id: str = ""
    user_id: str = ""
    default_privacy_level: PrivacyLevel = PrivacyLevel.PRIVATE
    opt_out_metrics: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# --- AI Firewall Types (REQ-025) ---


class FirewallAction(StrEnum):
    """Action to take when a firewall rule matches."""

    ALLOW = "allow"
    DENY = "deny"
    LOG_ONLY = "log_only"


@dataclass(frozen=True)
class FirewallRule:
    """A network-boundary firewall rule for agent traffic."""

    rule_id: str = ""
    name: str = ""
    description: str = ""
    pattern: str = ""
    action: FirewallAction = FirewallAction.DENY
    agent_roles: tuple[str, ...] = ()
    priority: int = 100
    active: bool = True
    project_id: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class FirewallLogEntry:
    """A log entry recording a firewall decision."""

    log_id: str = ""
    rule_id: str = ""
    agent_id: str = ""
    url: str = ""
    action_taken: FirewallAction = FirewallAction.ALLOW
    blocked: bool = False
    timestamp: str = ""
    project_id: str = ""


# --- Coding Rules Types ---


class RuleSeverity(StrEnum):
    """Severity level for a coding rule."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class RuleScope:
    """Scoping for a coding rule — directory and file pattern matching."""

    directory_pattern: str = "**"
    file_pattern: str = "*"
    language: str = ""


@dataclass(frozen=True)
class CodingRule:
    """A directory-scoped coding rule that agents must follow."""

    rule_id: str = ""
    name: str = ""
    description: str = ""
    content: str = ""
    severity: RuleSeverity = RuleSeverity.WARNING
    scope: RuleScope = field(default_factory=RuleScope)
    active: bool = True
    project_id: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class RuleViolation:
    """A detected violation of a coding rule."""

    violation_id: str = ""
    rule_id: str = ""
    pipeline_run_id: str = ""
    file_path: str = ""
    line_number: int | None = None
    message: str = ""
    agent_id: str = ""
    resolved: bool = False
    created_at: str = ""


# --- Workflow Blueprint Types ---


class BlueprintNodeType(StrEnum):
    """Type of node in a workflow blueprint."""

    DETERMINISTIC = "deterministic"
    AGENTIC = "agentic"
    HUMAN_REVIEW = "human_review"
    CONDITIONAL = "conditional"
    PARALLEL = "parallel"


@dataclass(frozen=True)
class BlueprintNode:
    """A single node in a workflow blueprint."""

    node_id: str
    name: str
    node_type: BlueprintNodeType = BlueprintNodeType.DETERMINISTIC
    description: str = ""
    config: dict[str, object] | None = None
    depends_on: tuple[str, ...] = ()
    timeout_seconds: int = 300
    retry_count: int = 0


@dataclass(frozen=True)
class WorkflowBlueprint:
    """A team-definable workflow blueprint mixing deterministic and agentic nodes."""

    blueprint_id: str
    name: str
    description: str = ""
    team_id: str = ""
    nodes: tuple[BlueprintNode, ...] = ()
    version: str = "1.0"
    active: bool = True
    project_id: str = ""
    created_at: str = ""
    updated_at: str = ""


# --- Slack Notification Types ---


class SlackNotificationStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"


@dataclass(frozen=True)
class SlackNotificationTemplate:
    """Block Kit template for a pipeline stage notification."""

    template_id: str
    name: str
    stage_name: str
    block_kit_template: str = ""
    active: bool = True
    project_id: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class SlackNotificationRecord:
    """Record of a notification sent to a Slack thread."""

    record_id: str
    pipeline_run_id: str
    stage_name: str
    slack_channel_id: str = ""
    slack_thread_ts: str = ""
    slack_message_ts: str = ""
    status: SlackNotificationStatus = SlackNotificationStatus.SENT
    error_message: str = ""
    created_at: str = ""


# --- Slack Invocation Types ---


class SlackInvocationStatus(StrEnum):
    """Status of a Slack-triggered invocation."""

    PENDING = "pending"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class SlackInvocation:
    """Tracks a workflow invocation triggered via Slack @mention."""

    invocation_id: str
    slack_channel_id: str
    slack_thread_ts: str
    slack_user_id: str
    prompt: str
    project_id: str
    lintel_user_id: str = ""
    thread_context: tuple[dict[str, object], ...] = ()
    linked_urls: tuple[str, ...] = ()
    pipeline_run_id: str = ""
    status: SlackInvocationStatus = SlackInvocationStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# --- Sandbox Pool Types ---


class SandboxPoolStatus(StrEnum):
    """Status of a pooled sandbox."""

    WARMING = "warming"
    READY = "ready"
    IN_USE = "in_use"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass(frozen=True)
class SandboxImage:
    """Pre-built repository image for warm sandbox creation."""

    image_id: str
    repository_url: str
    branch: str = "main"
    commit_sha: str = ""
    image_tag: str = ""
    size_mb: int = 0
    build_duration_seconds: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class PooledSandbox:
    """A pre-warmed sandbox instance from the pool."""

    sandbox_id: str
    image_id: str
    status: SandboxPoolStatus = SandboxPoolStatus.WARMING
    assigned_pipeline_run_id: str = ""
    project_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class SandboxPoolConfig:
    """Configuration for a project's sandbox pool."""

    config_id: str
    project_id: str
    min_warm: int = 2
    max_warm: int = 5
    ttl_seconds: int = 3600
    auto_rebuild_on_push: bool = True
    rebuild_interval_seconds: int = 1800
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ImageRebuildStatus(StrEnum):
    """Status of a sandbox image rebuild."""

    PENDING = "pending"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageRebuildTrigger(StrEnum):
    """What triggered a sandbox image rebuild."""

    SCHEDULED = "scheduled"
    MANUAL = "manual"


@dataclass(frozen=True)
class ImageRebuildRecord:
    """Tracks a single sandbox image rebuild attempt."""

    rebuild_id: str
    image_id: str
    project_id: str
    trigger: ImageRebuildTrigger = ImageRebuildTrigger.SCHEDULED
    status: ImageRebuildStatus = ImageRebuildStatus.PENDING
    commit_sha: str = ""
    branch: str = "main"
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error_message: str = ""


class SandboxSnapshotStatus(StrEnum):
    """Status of a sandbox session snapshot."""

    PENDING = "pending"
    COMPLETED = "completed"
    RESTORING = "restoring"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass(frozen=True)
class SandboxSnapshot:
    """A captured snapshot of a sandbox filesystem state."""

    snapshot_id: str
    sandbox_id: str
    pipeline_run_id: str = ""
    project_id: str = ""
    status: SandboxSnapshotStatus = SandboxSnapshotStatus.PENDING
    commit_sha: str = ""
    image_tag: str = ""
    size_mb: int = 0
    ttl_seconds: int = 86400
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    restored_sandbox_id: str = ""


# --- CI/CD Deployment ---


class DeploymentStatus(StrEnum):
    """Status of a CI/CD deployment."""

    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class DeploymentEvent:
    """Normalized CI/CD deployment event from GitHub Actions, GitLab CI, or generic webhook."""

    deployment_id: str
    repo_name: str
    repo_url: str = ""
    status: DeploymentStatus = DeploymentStatus.STARTED
    workflow_name: str = ""
    branch: str = ""
    commit_sha: str = ""
    sender: str = ""
    provider: str = ""  # github, gitlab, generic
    started_at: str = ""
    finished_at: str = ""
    url: str = ""


# --- Tech Specs ---


class TechSpecStatus(StrEnum):
    """Status of a tech spec."""

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class Milestone:
    """A milestone within a tech spec."""

    name: str
    description: str = ""
    estimated_effort: str = ""


@dataclass(frozen=True)
class TechSpec:
    """A technical specification document."""

    id: str
    project_id: str
    title: str
    problem_statement: str = ""
    proposed_solution: str = ""
    alternatives: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    milestones: tuple[Milestone, ...] = ()
    status: TechSpecStatus = TechSpecStatus.DRAFT
    created_at: str = ""
    updated_at: str = ""


# --- Bot ---


class BotPlatform(StrEnum):
    SLACK = "slack"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    CUSTOM = "custom"


class BotStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


@dataclass(frozen=True)
class Bot:
    bot_id: str
    name: str
    platform: BotPlatform = BotPlatform.CUSTOM
    scopes: tuple[str, ...] = ()
    status: BotStatus = BotStatus.ACTIVE
    project_ids: tuple[str, ...] = ()
    workflow_ids: tuple[str, ...] = ()
    agent_ids: tuple[str, ...] = ()


# --- Workflow ACL ---


@dataclass(frozen=True)
class AclRule:
    """Access control rule for workflow execution per connection."""

    rule_id: str
    connection_id: str
    workflow_types: tuple[str, ...] = ()
    project_id: str = ""
    effect: str = "deny"


# --- Multiplayer Sessions ---


class SessionStatus(StrEnum):
    """Status of a multiplayer agent session."""

    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Participant:
    """A participant in a multiplayer session."""

    user_id: str
    role: str = "member"
    joined_at: str = ""


@dataclass(frozen=True)
class Session:
    """A multiplayer agent session."""

    session_id: str
    name: str
    created_by: str
    participants: tuple[Participant, ...] = ()
    status: str = "active"
