# Integration Requirements

## Strategy: MCP-First, Then Native Adapters

Lintel uses a two-tier integration strategy:

1. **MCP-first:** For tool access (file search, code context, documentation), link the `Integration` entity to an existing `MCPServer`. MCP provides a universal tool interface that agents can call directly.

2. **Native adapters:** For deep bidirectional sync (Jira ticket ↔ WorkItem, GitHub Actions → Deployment events), build native adapters that implement Lintel-specific protocols.

```
Integration entity
  ├── mcp_server_id → MCPServer (for MCP-based tool access)
  └── credential_id → Credential (for authenticated API access)

Native adapters implement:
  ├── RepoProvider protocol    (Git operations)
  ├── TicketingAdapter protocol (ticket sync)
  └── CI/CD webhook receivers  (deployment tracking)
```

---

## INT-1: Repository Providers (P0)

### INT-1.1: Provider Abstraction

**Current state:** `RepoProvider` protocol (`protocols.py:255`) defines all git operations. `GitHubRepoProvider` (`infrastructure/repos/github_provider.py`) is the only implementation.

**The protocol already supports multi-provider.** It defines: `clone_repo`, `create_branch`, `commit_and_push`, `create_pr`, `add_comment`, `list_branches`, `get_file_content`, `list_commits`.

### INT-1.2: GitLab Provider

Create `infrastructure/repos/gitlab_provider.py`:
- Implements `RepoProvider` protocol
- Uses GitLab REST API v4 (or python-gitlab)
- Credential: `GITLAB_TOKEN` credential type (new, see ENT-M7)

### INT-1.3: RepoProviderFactory

Create `infrastructure/repos/factory.py`:
- Selects provider implementation based on `Repository.provider` field
- Currently: `"github"` → `GitHubRepoProvider`
- Add: `"gitlab"` → `GitLabRepoProvider`

```python
class RepoProviderFactory:
    def get_provider(self, repository: Repository) -> RepoProvider:
        match repository.provider:
            case "github":
                return GitHubRepoProvider(...)
            case "gitlab":
                return GitLabRepoProvider(...)
            case _:
                raise ValueError(f"Unknown provider: {repository.provider}")
```

### INT-1.4: Webhook Receivers

Create API routes for incoming webhooks:

**`POST /webhooks/github`** — Receives GitHub webhook events:
- `push` → `CommitPushed` event
- `pull_request.opened` → `PRCreated` event
- `pull_request.merged` → trigger deployment tracking
- `workflow_run.completed` → `DeploymentSucceeded/Failed` (GitHub Actions)
- Signature verification via `X-Hub-Signature-256`

**`POST /webhooks/gitlab`** — Receives GitLab webhook events:
- `push` → `CommitPushed` event
- `merge_request.opened` → `PRCreated` event
- `pipeline.succeeded/failed` → `DeploymentSucceeded/Failed`
- Token verification via `X-Gitlab-Token`

**Event translation:** Webhooks are translated to Lintel domain events. The webhook handler creates the appropriate `EventEnvelope` and appends it to the event store. The event bus handles fan-out.

---

## INT-2: CI/CD Integration (P1)

### INT-2.1: GitHub Actions

**Ingestion method:** GitHub webhook receiver (INT-1.4) receives `workflow_run` events.

**Event mapping:**
| GitHub Actions Event | Lintel Event | Conditions |
|---|---|---|
| `workflow_run.completed` (conclusion=success) | `DeploymentSucceeded` | Only for deploy workflows (configurable) |
| `workflow_run.completed` (conclusion=failure) | `DeploymentFailed` | Only for deploy workflows |
| `workflow_run.requested` | `DeploymentStarted` | Only for deploy workflows |

**Configuration:** The `Integration` entity with `provider="github_actions"` stores which workflow names map to deployments in its `config` field:

```json
{
  "deploy_workflow_names": ["deploy-production", "deploy-staging"],
  "environment_mapping": {
    "deploy-production": "production",
    "deploy-staging": "staging"
  }
}
```

### INT-2.2: Concourse CI

**Current state:** Lintel already has Concourse-inspired types (`ResourceVersion`, `PassedConstraint`, `JobInput`) at `types.py:674-697`.

**Integration approach:**
- Concourse webhook/resource sends build status
- Map to `DeploymentStarted/Succeeded/Failed` events
- `PassedConstraint` used to track which resources have passed through which jobs

### INT-2.3: Generic Webhook CI/CD

**`POST /webhooks/ci-cd`** — For CI/CD tools without native integration.

The user defines a JSON path mapping in the `Integration.config`:

```json
{
  "status_path": "$.build.status",
  "commit_sha_path": "$.build.commit",
  "environment_path": "$.build.environment",
  "duration_path": "$.build.duration_ms",
  "status_mapping": {
    "success": "succeeded",
    "failure": "failed"
  }
}
```

The webhook handler extracts fields from the payload using the configured paths and creates `DeploymentStarted/Succeeded/Failed` events.

---

## INT-3: Ticketing Integration (P1)

### INT-3.1: TicketingAdapter Protocol

Add to `contracts/protocols.py`:

```python
class TicketingAdapter(Protocol):
    async def sync_work_item(self, work_item: WorkItem) -> str: ...  # returns external ticket ID
    async def import_ticket(self, external_id: str) -> WorkItem: ...
    async def update_status(self, external_id: str, status: str) -> None: ...
    async def list_tickets(self, project_key: str, status: str | None = None) -> list[dict]: ...
```

### INT-3.2: Jira Adapter

Create `infrastructure/integrations/ticketing/jira_adapter.py`:
- Implements `TicketingAdapter`
- Uses Jira REST API v3
- Bidirectional sync: WorkItem changes → Jira issue updates, Jira issue changes → WorkItem updates
- **Sync strategy:** Webhook for real-time + periodic poll every 5 minutes for catch-up
- Field mapping stored in `Integration.config`

**Event flow:**
```
Jira webhook → POST /webhooks/jira → TicketSynced event → WorkItem update
WorkItem status change → TicketingAdapter.update_status() → Jira issue updated
```

### INT-3.3: Linear Adapter

Similar to Jira. Linear's API is GraphQL-based.
Create `infrastructure/integrations/ticketing/linear_adapter.py`

### INT-3.4: Ticket-WorkItem Mapping

`WorkItem` gains `external_ticket_id` and `external_ticket_url` fields (see ENT-M2).

Sync rules:
- When a WorkItem is created in Lintel → create ticket in external system (if auto-sync enabled)
- When a ticket is created externally → import as WorkItem (if webhook configured)
- Status mapping is configurable per integration

---

## INT-4: Observability Integration (P1)

### INT-4.1: Datadog Export

Create `infrastructure/integrations/observability/datadog_exporter.py`:
- Export Lintel metrics as Datadog custom metrics via DogStatsD protocol
- Metrics exported: all DORA metrics, agent accuracy, team velocity
- Configurable via `Integration.config`: metric prefix, tags, flush interval

### INT-4.2: Datadog Alert Ingestion

- Receive Datadog webhook alerts → `IncidentDetected` event (see REQ-007 in `future-requirements.md`)
- Used for: triggering the "Observe" phase of the delivery loop when production issues are detected

### INT-4.3: OpenTelemetry Enhancement

**Current state:** Basic OTel setup at `infrastructure/observability/metrics.py` and `step_metrics.py`. Records `lintel_step_duration_seconds` and `lintel_step_tokens_total`.

**Add:**
- Metric export for all DORA and agent metrics via OTel Metrics SDK
- Trace propagation from Lintel workflows through sandbox execution
- Custom OTel attributes for project_id, team_id, agent_role

---

## INT-5: Channel Expansion (P0)

### INT-5.1: Channel Adapter Architecture

**Current state:** `ChannelAdapter` protocol (`protocols.py:101`) with `SlackChannelAdapter` implementation. Supports `send_message`, `update_message`, `send_approval_request`.

**Add:**

| Adapter | Location | Protocol Support |
|---|---|---|
| `DiscordChannelAdapter` | `infrastructure/channels/discord/adapter.py` | Discord API via webhooks or bot |
| `TeamsChannelAdapter` | `infrastructure/channels/teams/adapter.py` | Microsoft Teams via Bot Framework |
| `WebChannelAdapter` | `infrastructure/channels/web/adapter.py` | WebSocket-based for Lintel UI |

### INT-5.2: ChannelAdapterFactory

Create `infrastructure/channels/factory.py`:

```python
class ChannelAdapterFactory:
    def get_adapter(self, channel: Channel) -> ChannelAdapter:
        match channel.channel_type:
            case ChannelType.SLACK:
                return SlackChannelAdapter(...)
            case ChannelType.DISCORD:
                return DiscordChannelAdapter(...)
            case ChannelType.TEAMS:
                return TeamsChannelAdapter(...)
            case ChannelType.WEB:
                return WebChannelAdapter(...)
```

### INT-5.3: Channel Routing

When a workflow needs to send a notification or approval request:
1. Resolve the project's team via `project.team_id`
2. Get the team's channels via `team.channel_ids`
3. Use `ChannelAdapterFactory` to get the right adapter per channel
4. Send to all enabled channels (or primary channel based on notification rule)

---

## INT-6: Experimentation / Feature Flags (P2)

### INT-6.1: Internal Feature Flag System

Simple key-value flag store:
- Boolean flags (on/off)
- Percentage rollout (0-100%)
- User/team targeting rules

**Primary use case:** Progressive rollout of new agent configurations, workflow changes.

### INT-6.2: Experiment Engine

- A/B test different agent prompts, models, or workflow configurations
- Primary metric tied to `DeliveryMetric` (e.g., agent accuracy, cycle time)
- Sequential testing with automated significance detection
- Events: `ExperimentStarted`, `VariantAssigned`, `ExperimentCompleted`

---

## Integration Entity Summary

Each external tool connection is an `Integration` entity:

```python
Integration(
    integration_id="int-github-001",
    name="GitHub - Lintel Repo",
    integration_type=IntegrationType.REPO_PROVIDER,
    provider="github",
    credential_id="cred-gh-token",
    project_ids=("proj-001",),
    mcp_server_id="",           # not MCP-based
    config={"webhook_secret": "..."},
)

Integration(
    integration_id="int-jira-001",
    name="Jira - Engineering Board",
    integration_type=IntegrationType.TICKETING,
    provider="jira",
    credential_id="cred-jira-token",
    project_ids=("proj-001", "proj-002"),
    mcp_server_id="mcp-jira",   # MCP server for agent tool access
    config={"project_key": "ENG", "auto_sync": true},
)
```
