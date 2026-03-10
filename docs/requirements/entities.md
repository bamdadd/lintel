# Entity Model Requirements

All entities are frozen dataclasses in `src/lintel/contracts/types.py`. All stores in `src/lintel/infrastructure/persistence/stores.py`.

---

## Existing Entity Audit

### Entities That Stay As-Is

#### Dataclasses

| Entity | Location | Purpose |
|---|---|---|
| `ThreadRef` | types.py:15 | Canonical workflow instance ID (workspace/channel/thread) |
| `Repository` | types.py:80 | Git repository configuration |
| `AIProvider` | types.py:103 | Configured AI model provider |
| `Credential` | types.py:122 | SSH key or API token for repo/tool access |
| `ModelPolicy` | types.py:148 | Model selection policy per agent role |
| `Model` | types.py:159 | Specific AI model available through a provider |
| `ModelAssignment` | types.py:184 | Binds model to usage context |
| `SkillDescriptor` | types.py:195 | Runtime skill contract (protocol-level) |
| `SkillResult` | types.py:208 | Skill invocation result |
| `SandboxConfig` | types.py:217 | Sandbox resource limits |
| `SandboxJob` | types.py:229 | Command to execute in sandbox |
| `SandboxResult` | types.py:238 | Sandbox execution output |
| `Project` | types.py:256 | Product/project definition |
| `WorkItem` | types.py:285 | Unit of work (feature, bug, task, etc.) |
| `Tag` | types.py:307 | Label attached to work items for grouping/filtering |
| `BoardColumn` | types.py:317 | Column within a board (name, position, status mapping) |
| `Board` | types.py:327 | Kanban board organising work items into columns |
| `Stage` | types.py:361 | Individual step in a workflow run |
| `PipelineRun` | types.py:379 | Workflow execution instance with stages |
| `Environment` | types.py:405 | Target deployment context (dev/staging/prod/sandbox) |
| `Variable` | types.py:415 | Runtime variable scoped to environment |
| `Trigger` | types.py:437 | What starts a workflow run |
| `WorkflowHook` | types.py:455 | Binds an event pattern to a workflow trigger |
| `CodeArtifact` | types.py:474 | File changes produced by agents |
| `TestResult` | types.py:494 | Structured test execution output |
| `ApprovalRequest` | types.py:522 | Human-in-the-loop gate |
| `AgentSession` | types.py:539 | Agent execution tracking (messages, tool_calls, token_usage) |
| `NotificationRule` | types.py:562 | When/how to notify users |
| `Policy` | types.py:584 | Governance rule for workflow behavior |
| `User` | types.py:606 | User identity |
| `Team` | types.py:618 | Group of users with shared permissions |
| `AuditEntry` | types.py:631 | Immutable action record |
| `SkillDefinition` | types.py:662 | User-editable skill definition |
| `AgentDefinitionRecord` | types.py:682 | User-editable agent definition |
| `WorkflowStepConfig` | types.py:700 | Per-step agent/model/provider binding |
| `WorkflowDefinitionRecord` | types.py:713 | Workflow template with graph structure |
| `ResourceVersion` | types.py:737 | Concourse-inspired versioned resource |
| `PassedConstraint` | types.py:746 | Upstream job requirements |
| `JobInput` | types.py:754 | Pipeline job input spec |
| `MCPServer` | types.py:763 | Configured MCP tool server |
| `ChatSession` | types.py:775 | Chat session linked to project + MCP servers |
| `PhaseTransitionRecord` | types.py:797 | Records a single phase transition in delivery loop |
| `DeliveryLoop` | types.py:807 | Tracks the full delivery lifecycle for a work item |

#### Enums

| Enum | Location | Values |
|---|---|---|
| `ActorType` | types.py:30 | `human`, `agent`, `system` |
| `AgentCategory` | types.py:36 | 6 categories (engineering, quality, ops, etc.) |
| `AgentRole` | types.py:45 | 14 agent roles (planner, coder, reviewer, etc.) |
| `WorkflowPhase` | types.py:62 | Pipeline execution state (ingesting→closed) |
| `RepoStatus` | types.py:73 | `active`, `archived`, `error` |
| `AIProviderType` | types.py:92 | `openai`, `anthropic`, `google`, `aws_bedrock`, `ollama`, `litellm` |
| `CredentialType` | types.py:115 | `ssh_key`, `github_token`, `ai_provider_api_key` |
| `SandboxStatus` | types.py:131 | `pending`, `creating`, `running`, `collecting`, `completed`, `failed`, `destroyed` |
| `SkillExecutionMode` | types.py:141 | `inline`, `async_job`, `sandbox` |
| `ModelAssignmentContext` | types.py:173 | Where a model can be used |
| `ProjectStatus` | types.py:249 | `active`, `archived`, `deleted` |
| `WorkItemStatus` | types.py:267 | Work item lifecycle states |
| `WorkItemType` | types.py:277 | `feature`, `bug`, `refactor`, `task` |
| `PipelineStatus` | types.py:339 | Pipeline run lifecycle states |
| `StageStatus` | types.py:349 | Stage execution states |
| `EnvironmentType` | types.py:397 | `development`, `staging`, `production`, `sandbox` |
| `TriggerType` | types.py:428 | `slack_message`, `webhook`, `schedule`, `pr_event`, `manual` |
| `HookType` | types.py:448 | `pre`, `post`, `scheduled` |
| `TestVerdict` | types.py:486 | `passed`, `failed`, `error`, `skipped` |
| `ApprovalStatus` | types.py:514 | `pending`, `approved`, `rejected`, `expired` |
| `NotificationChannel` | types.py:555 | `slack`, `email`, `webhook` |
| `PolicyAction` | types.py:576 | `require_approval`, `auto_approve`, `block`, `notify` |
| `UserRole` | types.py:599 | `admin`, `member`, `viewer` |
| `SkillCategory` | types.py:647 | Skill categorization |

### Entities That Need Modification

#### ENT-M1: Team (P0)

**Current** (`types.py:618`):
```python
@dataclass(frozen=True)
class Team:
    team_id: str
    name: str
    member_ids: tuple[str, ...] = ()     # PROBLEM: humans only
    project_ids: tuple[str, ...] = ()
```

**Required changes:**
- Drop `member_ids` — replaced by `TeamMember` entity (ENT-1)
- Add `channel_ids: tuple[str, ...]` — links to Channel entity (ENT-2)

**Migration:** Existing `member_ids` entries become `TeamMember` records with `member_type=HUMAN`.

#### ENT-M2: WorkItem (P0)

**Current** (`types.py:285`):
```python
assignee_agent_role: str = ""  # PROBLEM: role only, no specific assignee
```

**Add fields:**
- `assignee_id: str = ""` — user_id or agent_id
- `assignee_type: ActorType = ActorType.SYSTEM` — who is assigned
- `external_ticket_id: str = ""` — linked Jira/Linear ticket ID
- `external_ticket_url: str = ""` — URL to external ticket
- `delivery_loop_id: str = ""` — link to DeliveryLoop

#### ENT-M3: Model (P0)

**Current** (`types.py:159`): No pricing information.

**Add fields:**
- `cost_per_1k_input_tokens: float = 0.0`
- `cost_per_1k_output_tokens: float = 0.0`

**Why:** Cost guardrails (GRD-4) need pricing data to compute real-time spend from `ModelCallCompleted` events.

#### ENT-M4: SandboxConfig (P1)

**Current** (`types.py:217`): Basic resource limits only.

**Add fields:**
- `max_disk_mb: int = 1024`
- `max_processes: int = 64`
- `seccomp_profile: str = "default"`

**Why:** Sandbox hardening (GRD-3).

#### ENT-M5: WorkItemType Enum (P1)

**Current** (`types.py:277`): `FEATURE`, `BUG`, `REFACTOR`, `TASK`

**Add:** `REARCHITECT = "rearchitect"`

**Why:** Delivery loop rearchitecting triggers (DL-4).

#### ENT-M6: TriggerType Enum (P1)

**Current** (`types.py:428`): `SLACK_MESSAGE`, `WEBHOOK`, `SCHEDULE`, `PR_EVENT`, `MANUAL`

**Add:**
- `PUSH_EVENT = "push_event"` — commits pushed to a branch (REQ-026)
- `CI_CD_EVENT = "ci_cd_event"`
- `TICKET_EVENT = "ticket_event"`
- `GUARDRAIL_ESCALATION = "guardrail_escalation"`

#### ENT-M7: CredentialType Enum (P1)

**Current** (`types.py:115`): `SSH_KEY`, `GITHUB_TOKEN`, `AI_PROVIDER_API_KEY`

**Add:** `GITLAB_TOKEN = "gitlab_token"`

#### ENT-M8: NotificationChannel Enum (P1)

**Current** (`types.py:555`): `SLACK`, `EMAIL`, `WEBHOOK`

**Add:** `DISCORD = "discord"`, `TEAMS = "teams"`, `WEB = "web"`

#### ENT-M9: Project (P1)

**Current** (`types.py:256`): No team ownership, no delivery configuration.

**Conceptual shift:** Projects are ongoing products, maintained forever. No start/end dates.

**Add fields:**
- `team_id: str = ""` — owner team
- `portfolio_id: str = ""` — parent portfolio
- `delivery_phase_sequence: tuple[str, ...] = ("desire", "develop", "review", "deploy", "observe", "learn")` — configurable phases

#### ENT-M10: User (P2)

**Current** (`types.py:606`): Basic identity.

**Add fields:**
- `avatar_url: str = ""`
- `external_ids: dict[str, str] | None = None` — `{"github": "...", "gitlab": "...", "jira": "..."}`

#### ENT-M11: WorkflowDefinitionRecord (P1)

**Current** (`types.py:713`): No delivery phase mapping.

**Add field:**
- `delivery_phases: tuple[str, ...] = ()` — which delivery phases this workflow covers

### Policy vs GuardrailRule

`Policy` (`types.py:584`) stays for simple "on event X, do Y" approval rules. `GuardrailRule` (ENT-8) extends the concept with thresholds, cooldowns, and escalation tiers. Both coexist. Migration path: convert `Policy` rules to `GuardrailRule` over time.

### SkillDescriptor vs SkillDefinition

`SkillDescriptor` (`types.py:195`) is the runtime protocol-level contract. `SkillDefinition` (`types.py:662`) is the user-editable persisted version. This is intentional CQRS separation — no change needed.

### WorkflowPhase vs DeliveryPhase

`WorkflowPhase` (`types.py:62`) tracks internal pipeline execution state (ingesting→planning→implementing→closed). Delivery phases (desire→develop→review→deploy→observe→learn) operate at a higher level — they track where the work item is in the product lifecycle. Both coexist at different abstraction levels.

---

## New Entities

### ENT-1: TeamMember (P0)

**Problem:** `Team.member_ids` only holds human user IDs. Agents cannot be team members.

```python
class MemberType(StrEnum):
    HUMAN = "human"
    AGENT = "agent"

class TeamRole(StrEnum):
    LEAD = "lead"
    MEMBER = "member"
    REVIEWER = "reviewer"
    OBSERVER = "observer"

@dataclass(frozen=True)
class TeamMember:
    member_id: str
    team_id: str
    member_type: MemberType       # human or agent — mirrors ActorType pattern
    ref_id: str                   # user_id or agent_id
    role: TeamRole
    joined_at: str = ""
    permissions: tuple[str, ...] = ()  # "trigger_workflow", "approve_gate", "view_metrics"
```

**Design decision:** Agents are first-class team members. Same permission model as humans. An agent with `role=LEAD` and `permissions=("approve_gate",)` can approve work items.

**Store:** `PostgresTeamMemberStore` (new)
**Events:** `TeamMemberAdded`, `TeamMemberRemoved`, `TeamMemberRoleChanged`
**API:** CRUD routes at `/api/v1/teams/{team_id}/members`

### ENT-2: Channel (P0)

**Problem:** Only Slack threads tied to individual workflows. No concept of a team communication channel.

```python
class ChannelType(StrEnum):
    SLACK = "slack"
    DISCORD = "discord"
    TEAMS = "teams"
    WEB = "web"

@dataclass(frozen=True)
class Channel:
    channel_id: str
    team_id: str
    channel_type: ChannelType
    external_id: str        # Slack channel ID, Discord channel ID, etc.
    name: str
    config: dict[str, object] | None = None
    enabled: bool = True
```

**Relationship:** Channel belongs to Team. Workflows discover notification channel via: WorkItem → Project → Team → Channel.
**Reuses:** Existing `ChannelAdapter` protocol (`protocols.py:101`) for runtime communication.
**Store:** `PostgresChannelStore` (new)
**Events:** `ChannelRegistered`, `ChannelUpdated`, `ChannelDisabled`
**API:** CRUD routes at `/api/v1/teams/{team_id}/channels`

### ENT-3: Deployment (P0)

**Problem:** No way to track deployments. Without this, DORA metrics are impossible.

```python
class DeploymentStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

@dataclass(frozen=True)
class Deployment:
    deployment_id: str
    project_id: str
    environment_id: str
    commit_sha: str
    deployed_by: str
    deployed_by_type: ActorType
    deployed_at: str
    status: DeploymentStatus
    duration_ms: int = 0
    workflow_run_id: str = ""
    metadata: dict[str, object] | None = None
```

**Reuses:** `Environment` entity (`types.py:365`), `WorkflowRun` linkage.
**Store:** `PostgresDeploymentStore` (new)
**Events:** `DeploymentStarted`, `DeploymentSucceeded`, `DeploymentFailed`, `DeploymentRolledBack`
**API:** CRUD + query routes at `/api/v1/deployments`

### ENT-4: DeliveryMetric (P0)

**Problem:** No materialized metric snapshots. Metrics must be computed and stored for querying.

```python
class MetricType(StrEnum):
    DEPLOYMENT_FREQUENCY = "deployment_frequency"
    LEAD_TIME = "lead_time"
    CHANGE_FAILURE_RATE = "change_failure_rate"
    MTTR = "mttr"
    CYCLE_TIME = "cycle_time"
    AGENT_ACCURACY = "agent_accuracy"
    AGENT_REWORK_RATE = "agent_rework_rate"
    TEAM_VELOCITY = "team_velocity"
    CUSTOM = "custom"

@dataclass(frozen=True)
class DeliveryMetric:
    metric_id: str
    project_id: str
    team_id: str
    metric_type: MetricType
    value: float
    unit: str                  # "per_day", "hours", "percentage", "ratio"
    period_start: str
    period_end: str
    dimensions: dict[str, str] | None = None   # {"environment": "production"}
    computed_at: str = ""
```

**Not event-sourced.** This is a read model materialized by metrics projection engine.
**Store:** `PostgresDeliveryMetricStore` (new)
**Event:** `DeliveryMetricComputed`
**API:** Query routes at `/api/v1/metrics`

### ENT-5: AgentPerformanceRecord (P0)

**Problem:** No aggregated view of agent accuracy, cost, or rework patterns.

```python
@dataclass(frozen=True)
class AgentPerformanceRecord:
    record_id: str
    agent_id: str
    agent_role: str
    project_id: str
    period_start: str
    period_end: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    accuracy_rate: float = 0.0       # (completed - reworked) / completed
    rework_count: int = 0
    avg_tokens_per_task: int = 0
    avg_duration_ms: int = 0
    total_cost_usd: float = 0.0
    error_categories: dict[str, int] | None = None  # {"test_failure": 3, "review_rejection": 1}
```

**Source data:** Aggregates from existing `AgentSession.token_usage` (`types.py:486`) and existing events (`AgentStepCompleted`, `HumanApprovalRejected`).
**Store:** `PostgresAgentPerformanceStore` (new)
**Event:** `AgentPerformanceComputed`
**API:** Query routes at `/api/v1/agents/{agent_id}/performance`

### ENT-6: HumanPerformanceRecord (P1)

```python
@dataclass(frozen=True)
class HumanPerformanceRecord:
    record_id: str
    user_id: str
    project_id: str
    period_start: str
    period_end: str
    reviews_given: int = 0
    avg_review_time_ms: int = 0
    approvals_granted: int = 0
    approvals_rejected: int = 0
    avg_approval_latency_ms: int = 0
    work_items_created: int = 0
    contributions: dict[str, int] | None = None  # {"commits": 5, "prs_merged": 2}
```

**Privacy:** Individual metrics are private by default (per REQ-008 in `future-requirements.md`). Only the user themselves and team leads can view.
**Store:** `PostgresHumanPerformanceStore` (new)
**Event:** `HumanPerformanceComputed`

### ENT-7: Integration (P1)

**Problem:** No framework for connecting external tools (Jira, GitHub Actions, Datadog, etc.).

```python
class IntegrationType(StrEnum):
    REPO_PROVIDER = "repo_provider"
    CI_CD = "ci_cd"
    TICKETING = "ticketing"
    OBSERVABILITY = "observability"
    ANALYTICS = "analytics"
    CHANNEL = "channel"
    MCP = "mcp"

@dataclass(frozen=True)
class Integration:
    integration_id: str
    name: str
    integration_type: IntegrationType
    provider: str                    # "github", "gitlab", "jira", "linear", "datadog", etc.
    config: dict[str, object] | None = None
    credential_id: str = ""          # link to Credential for auth
    project_ids: tuple[str, ...] = ()
    mcp_server_id: str = ""          # MCP-first: link to MCPServer for MCP-based integrations
    enabled: bool = True
    last_sync_at: str = ""
```

**MCP-first strategy:** For tools with MCP servers, `Integration` links to existing `MCPServer` entity. For deep bidirectional sync (Jira ticket ↔ WorkItem), native adapters are used.
**Store:** `PostgresIntegrationStore` (new)
**Events:** `IntegrationRegistered`, `IntegrationSynced`, `IntegrationFailed`

### ENT-8: GuardrailRule (P0)

**Problem:** `Policy` is too simple — no thresholds, cooldowns, or escalation tiers.

```python
class GuardrailAction(StrEnum):
    WARN = "warn"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"
    ESCALATE = "escalate"
    AUTO_REMEDIATE = "auto_remediate"

@dataclass(frozen=True)
class GuardrailRule:
    rule_id: str
    name: str
    description: str = ""
    project_id: str = ""                    # empty = global rule
    trigger_event_type: str = ""            # which event triggers evaluation
    condition: str = ""                     # expression: "payload.token_usage > 100000"
    threshold: dict[str, object] | None = None  # {"metric": "agent_rework_rate", "operator": ">", "value": 0.3}
    action: GuardrailAction = GuardrailAction.WARN
    escalation_target: str = ""             # user_id, team_id, or channel_id
    cooldown_seconds: int = 300             # prevent repeated firing
    enabled: bool = True
```

**Coexists with `Policy`.** Policy = simple "on event X, do Y". GuardrailRule = threshold-based with cooldowns and escalation.
**Store:** `PostgresGuardrailRuleStore` (new)
**Events:** `GuardrailTriggered`, `GuardrailEscalated`, `GuardrailResolved`

### ENT-9: DeliveryLoop (P1) — IMPLEMENTED

**Status:** Already in `types.py:807` with `PhaseTransitionRecord` (`types.py:797`).

```python
@dataclass(frozen=True)
class PhaseTransitionRecord:
    from_phase: str
    to_phase: str
    occurred_at: datetime
    is_rework: bool = False

@dataclass(frozen=True)
class DeliveryLoop:
    loop_id: str
    work_item_id: str
    project_id: str
    phase_sequence: tuple[str, ...] = DEFAULT_DELIVERY_PHASES
    current_phase: str = ""
    phase_history: tuple[PhaseTransitionRecord, ...] = ()
    started_at: datetime | None = None
    completed_at: datetime | None = None
    learnings: dict[str, object] | None = None
```

**Note:** Implementation uses `PhaseTransitionRecord` dataclass (not raw dicts) and `datetime` (not strings). `learnings` is a dict (not tuple of strings).
**Store:** `PostgresDeliveryLoopStore` (new — not yet implemented)
**Events:** `DeliveryLoopStarted`, `DeliveryLoopPhaseTransitioned`, `LearningCaptured`, `DeliveryLoopCompleted`

### ENT-10: Portfolio (P2)

```python
@dataclass(frozen=True)
class Portfolio:
    portfolio_id: str
    name: str
    description: str = ""
    project_ids: tuple[str, ...] = ()
    owner_team_id: str = ""
    tags: tuple[str, ...] = ()
```

Groups products (projects) for cross-product analytics. Projects are ongoing products maintained forever — Portfolio is the organizational layer above them.

### ENT-11: Experiment (P2)

```python
class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"

@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    name: str
    description: str = ""
    project_id: str = ""
    feature_flag_key: str = ""
    status: ExperimentStatus = ExperimentStatus.DRAFT
    variants: tuple[dict[str, object], ...] = ()
    targeting_rules: dict[str, object] | None = None
    primary_metric: str = ""
    start_date: str = ""
    end_date: str = ""
```

Feature flags separate deployment from release. A/B test agent prompts, models, or workflow configurations.

### ENT-12: EngineeringPrinciple (P2)

**Problem:** Projects have no way to codify engineering principles that guide decision-making. Teams need a shared, queryable set of principles — like [JLP Engineering Principles](https://engineering-principles.jlp.engineering/) — that agents and humans can reference during planning, review, and architecture decisions.

**Structure:** Each principle follows the TOGAF architectural principles format: statement, rationale, and implications.

```python
class PrincipleCategory(StrEnum):
    DESIGN = "design"
    OPERATIONAL = "operational"
    ORGANISATION = "organisation"
    PRACTICES = "practices"
    CUSTOM = "custom"

@dataclass(frozen=True)
class EngineeringPrinciple:
    principle_id: str
    project_id: str                          # scoped to project (empty = org-wide)
    name: str                                # e.g. "Build Differentiators"
    category: PrincipleCategory = PrincipleCategory.CUSTOM
    statement: str = ""                      # the principle itself (1-2 sentences)
    rationale: str = ""                      # why this principle matters
    implications: tuple[str, ...] = ()       # actionable consequences of adopting this principle
    position: int = 0                        # display order within category
    enabled: bool = True
    created_by: str = ""                     # user_id who added it
    created_at: str = ""
    updated_at: str = ""
```

**All fields optional except `principle_id`, `project_id`, and `name`.** A principle can be as minimal as a name, or as detailed as a full TOGAF-style entry with rationale and implications.

**Usage:**
- Agents can query project principles during planning/review to align recommendations with team values
- Principles surface in workflow context (e.g. reviewer agent checks code against "Secure by Design")
- UI shows principles as a reference page per project, editable by team members

**Example principles for Lintel itself (placeholders):**

#### Design

| # | Name | Statement | Implications |
|---|------|-----------|--------------|
| 1 | **Event-Sourced by Default** | All state changes are recorded as immutable events; current state is derived by replaying them. | Store events, not mutable rows. Projections build read models. Never update an event after append. |
| 2 | **Contracts Over Implementations** | Domain code depends on Protocol interfaces in `contracts/`, never on infrastructure. | New infrastructure (e.g. swap Postgres for DynamoDB) requires zero domain changes. Import direction is always inward. |
| 3 | **Agents Are First-Class Actors** | AI agents have the same identity, permissions, and auditability as human users. | Every agent action produces an `AuditEntry`. Agents can be team members, assignees, and reviewers. |
| 4 | **Small, Composable Workflows** | Workflows are graphs of small, single-responsibility nodes — not monolithic scripts. | Each node does one thing (research, implement, review). Nodes are testable in isolation. New workflows are assembled from existing nodes. |

#### Operational

| # | Name | Statement | Implications |
|---|------|-----------|--------------|
| 5 | **Observable by Default** | Every workflow run, agent call, and stage transition emits structured traces and metrics. | OpenTelemetry spans wrap all async operations. Dashboards and alerts derive from trace data, not ad-hoc logging. |
| 6 | **Sandbox Everything** | Agent-generated code executes in isolated sandboxes with resource limits — never on the host. | Sandbox failures are safe failures. Resource caps (CPU, memory, disk, processes) are configurable per project. |

#### Organisation

| # | Name | Statement | Implications |
|---|------|-----------|--------------|
| 7 | **Human-in-the-Loop at Trust Boundaries** | Humans approve at meaningful gates (deploy, merge, escalation) — not at every step. | Approval requests are explicit entities with expiry. Agents operate autonomously within guardrails between gates. |
| 8 | **Learn from Every Delivery** | Every completed work item feeds back learnings that improve future workflows. | Delivery loops capture phase transitions and rework counts. Metrics projections surface patterns (rework rate, cycle time). |

#### Practices

| # | Name | Statement | Implications |
|---|------|-----------|--------------|
| 9 | **Test What You Ship** | Every feature includes tests. Agents write tests before implementation (TDD). | CI gates on test coverage. Agent implement nodes run tests in-sandbox and fix until green. |
| 10 | **Automate the Toil** | If a human does it more than twice, an agent or workflow should do it. | Slack threads trigger workflows. PR events trigger reviews. Guardrails auto-remediate known patterns. |
| 11 | **Secure by Design** | Security is built into contracts, not bolted on after. PII is detected and anonymized at ingestion. | Presidio scans all inbound text. Credentials live in vault, never in event payloads. Sandbox seccomp profiles are enforced. |
| 12 | **MCP-First Integration** | External tools integrate through MCP servers before building custom adapters. | Every UI feature has a corresponding MCP tool. Third-party integrations prefer MCP when available. |

**Store:** `PostgresEngineeringPrincipleStore` (new)
**Events:** `PrincipleAdded`, `PrincipleUpdated`, `PrincipleRemoved`
**API:** CRUD routes at `/api/v1/projects/{project_id}/principles`

---

## Entity Relationship Summary

```
Portfolio ──1:N──> Project (product)
                     │
                     ├── team_id ──> Team ──1:N──> TeamMember (human or agent)
                     │                  └──1:N──> Channel (slack/discord/teams/web)
                     │
                     ├──1:N──> Board ──1:N──> BoardColumn (status mapping)
                     │            └── WorkItems placed by column_id or status
                     │
                     ├──1:N──> Tag ──M:N──> WorkItem (via tags list)
                     │
                     ├──1:N──> WorkItem ──1:1──> DeliveryLoop
                     │            └──1:N──> WorkflowRun ──1:N──> Stage
                     │                        └──1:N──> AgentSession
                     │
                     ├──1:N──> Integration (repo/ci_cd/ticketing/observability)
                     │            └── credential_id ──> Credential
                     │            └── mcp_server_id ──> MCPServer
                     │
                     ├──1:N──> Deployment ──> Environment
                     │
                     ├──1:N──> GuardrailRule
                     │
                     ├──1:N──> EngineeringPrinciple (by category)
                     │
                     └──1:N──> Experiment
```

Metrics are cross-cutting read models:
```
Events ──> MetricsProjection ──> DeliveryMetric
                              ──> AgentPerformanceRecord
                              ──> HumanPerformanceRecord
```
