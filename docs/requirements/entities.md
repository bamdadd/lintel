# Entity Model Requirements

All entities are frozen dataclasses in `src/lintel/contracts/types.py`. All stores in `src/lintel/infrastructure/persistence/stores.py`.

---

## Existing Entity Audit

### Entities That Stay As-Is

| Entity | Location | Purpose |
|---|---|---|
| `ThreadRef` | types.py:12 | Canonical workflow instance ID (workspace/channel/thread) |
| `ActorType` | types.py:27 | `human` / `agent` / `system` — reused for TeamMember |
| `AgentCategory` | types.py:33 | 6 agent categories (engineering, quality, ops, etc.) |
| `AgentRole` | types.py:42 | 14 agent roles (planner, coder, reviewer, etc.) |
| `AIProvider` | types.py:100 | Configured AI model provider |
| `Credential` | types.py:119 | SSH key or API token for repo/tool access |
| `SandboxJob` | types.py:225 | Command to execute in sandbox |
| `SandboxResult` | types.py:234 | Sandbox execution output |
| `ModelPolicy` | types.py:145 | Model selection policy per agent role |
| `ModelAssignment` | types.py:181 | Binds model to usage context |
| `SkillDescriptor` | types.py:192 | Runtime skill contract (protocol-level) |
| `SkillResult` | types.py:204 | Skill invocation result |
| `Stage` | types.py:322 | Individual step in a workflow run |
| `WorkflowRun` | types.py:340 | Workflow execution instance with stages (renamed from `PipelineRun`) |
| `Environment` | types.py:365 | Target deployment context (dev/staging/prod/sandbox) |
| `Variable` | types.py:375 | Runtime variable scoped to environment |
| `Trigger` | types.py:397 | What starts a workflow run |
| `CodeArtifact` | types.py:412 | File changes produced by agents |
| `TestResult` | types.py:431 | Structured test execution output |
| `AgentSession` | types.py:477 | Agent execution tracking (messages, tool_calls, token_usage) |
| `SkillDefinition` | types.py:600 | User-editable skill definition |
| `AgentDefinitionRecord` | types.py:620 | User-editable agent definition |
| `WorkflowStepConfig` | types.py:638 | Per-step agent/model/provider binding |
| `WorkflowDefinitionRecord` | types.py:651 | Workflow template with graph structure |
| `ResourceVersion` | types.py:675 | Concourse-inspired versioned resource |
| `PassedConstraint` | types.py:684 | Upstream job requirements |
| `JobInput` | types.py:691 | Pipeline job input spec |
| `MCPServer` | types.py:701 | Configured MCP tool server |
| `ChatSession` | types.py:713 | Chat session linked to project + MCP servers |
| `ApprovalRequest` | types.py:460 | Human-in-the-loop gate |
| `AuditEntry` | types.py:569 | Immutable action record |
| `Tag` | types.py:307 | Label attached to work items for grouping/filtering |
| `BoardColumn` | types.py:317 | Column within a board (name, position, status mapping) |
| `Board` | types.py:327 | Kanban board organising work items into columns |

### Entities That Need Modification

#### ENT-M1: Team (P0)

**Current** (`types.py:556`):
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

**Current** (`types.py:282`):
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

**Current** (`types.py:156`): No pricing information.

**Add fields:**
- `cost_per_1k_input_tokens: float = 0.0`
- `cost_per_1k_output_tokens: float = 0.0`

**Why:** Cost guardrails (GRD-4) need pricing data to compute real-time spend from `ModelCallCompleted` events.

#### ENT-M4: SandboxConfig (P1)

**Current** (`types.py:214`): Basic resource limits only.

**Add fields:**
- `max_disk_mb: int = 1024`
- `max_processes: int = 64`
- `seccomp_profile: str = "default"`

**Why:** Sandbox hardening (GRD-3).

#### ENT-M5: WorkItemType Enum (P1)

**Current** (`types.py:274`): `FEATURE`, `BUG`, `REFACTOR`, `TASK`

**Add:** `REARCHITECT = "rearchitect"`

**Why:** Delivery loop rearchitecting triggers (DL-4).

#### ENT-M6: TriggerType Enum (P1)

**Current** (`types.py:388`): `SLACK_MESSAGE`, `WEBHOOK`, `SCHEDULE`, `PR_EVENT`, `MANUAL`

**Add:**
- `CI_CD_EVENT = "ci_cd_event"`
- `TICKET_EVENT = "ticket_event"`
- `GUARDRAIL_ESCALATION = "guardrail_escalation"`

#### ENT-M7: CredentialType Enum (P1)

**Current** (`types.py:112`): `SSH_KEY`, `GITHUB_TOKEN`, `AI_PROVIDER_API_KEY`

**Add:** `GITLAB_TOKEN = "gitlab_token"`

#### ENT-M8: NotificationChannel Enum (P1)

**Current** (`types.py:493`): `SLACK`, `EMAIL`, `WEBHOOK`

**Add:** `DISCORD = "discord"`, `TEAMS = "teams"`, `WEB = "web"`

#### ENT-M9: Project (P1)

**Current** (`types.py:253`): No team ownership, no delivery configuration.

**Conceptual shift:** Projects are ongoing products, maintained forever. No start/end dates.

**Add fields:**
- `team_id: str = ""` — owner team
- `portfolio_id: str = ""` — parent portfolio
- `delivery_phase_sequence: tuple[str, ...] = ("desire", "develop", "review", "deploy", "observe", "learn")` — configurable phases

#### ENT-M10: User (P2)

**Current** (`types.py:544`): Basic identity.

**Add fields:**
- `avatar_url: str = ""`
- `external_ids: dict[str, str] | None = None` — `{"github": "...", "gitlab": "...", "jira": "..."}`

#### ENT-M11: WorkflowDefinitionRecord (P1)

**Current** (`types.py:651`): No delivery phase mapping.

**Add field:**
- `delivery_phases: tuple[str, ...] = ()` — which delivery phases this workflow covers

### Policy vs GuardrailRule

`Policy` (`types.py:522`) stays for simple "on event X, do Y" approval rules. `GuardrailRule` (ENT-8) extends the concept with thresholds, cooldowns, and escalation tiers. Both coexist. Migration path: convert `Policy` rules to `GuardrailRule` over time.

### SkillDescriptor vs SkillDefinition

`SkillDescriptor` (`types.py:192`) is the runtime protocol-level contract. `SkillDefinition` (`types.py:600`) is the user-editable persisted version. This is intentional CQRS separation — no change needed.

### WorkflowPhase vs DeliveryPhase

`WorkflowPhase` (`types.py:59`) tracks internal pipeline execution state (ingesting→planning→implementing→closed). Delivery phases (desire→develop→review→deploy→observe→learn) operate at a higher level — they track where the work item is in the product lifecycle. Both coexist at different abstraction levels.

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

### ENT-9: DeliveryLoop (P1)

**Problem:** No concept of the full software delivery lifecycle for a work item.

```python
@dataclass(frozen=True)
class DeliveryLoop:
    loop_id: str
    project_id: str
    work_item_id: str
    phase_sequence: tuple[str, ...]      # fully configurable per project/workflow
    current_phase: str = ""
    phase_history: tuple[dict[str, object], ...] = ()   # timestamps and transitions
    started_at: str = ""
    completed_at: str = ""
    learnings: tuple[str, ...] = ()
```

**Fully configurable.** `phase_sequence` is defined per project (via `Project.delivery_phase_sequence`) or per workflow definition (via `WorkflowDefinitionRecord.delivery_phases`). Default: `("desire", "develop", "review", "deploy", "observe", "learn")`.
**Store:** `PostgresDeliveryLoopStore` (new)
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
                     └──1:N──> Experiment
```

Metrics are cross-cutting read models:
```
Events ──> MetricsProjection ──> DeliveryMetric
                              ──> AgentPerformanceRecord
                              ──> HumanPerformanceRecord
```
