# Metrics Framework Requirements

## Architecture

Metrics are specialized projections subscribing to the event bus. They aggregate event data into materialized `DeliveryMetric` records queryable via API.

```
EventStore → EventBus → MetricsProjection → DeliveryMetric (stored)
                                                  |
                                                  v
                                          MetricsQueryService (API)
```

Each metric projection implements the existing `Projection` protocol (`domain/projections/protocols.py`). It subscribes to specific event types, maintains in-memory aggregates, and periodically snapshots into `DeliveryMetric` records.

**Dependency:** Requires EventBus (EVT-1) before any metrics projection can run reactively.

---

## MET-1: Agent Metrics (P0)

**Why first:** These can be computed from events that already exist today. No new infrastructure needed beyond the EventBus.

### MET-1.1: Agent Accuracy Rate

- **Formula:** `(tasks_completed - tasks_reworked) / tasks_completed`
- **Source events:**
  - `AgentStepCompleted` — task completed
  - `HumanApprovalRejected` — rework trigger (rejection means agent output was inadequate)
  - `WorkItemUpdated` — status reversal (e.g., `IN_REVIEW` → `IN_PROGRESS`) indicates rework
- **Detection logic:** Rework is detected when:
  1. `HumanApprovalRejected` is followed by new `AgentStepScheduled` for the same work item
  2. Work item status regresses (moves backward in the status chain)
  3. Same branch receives multiple `CommitPushed` events after a review comment
- **Dimensions:** agent_id, agent_role, project_id, period
- **Projection:** `AgentAccuracyProjection` in `domain/metrics/agent_metrics.py`

### MET-1.2: Agent Rework Rate

- **Formula:** `COUNT(rework_events) / COUNT(task_completion_events)` per work item
- **Source events:** Same as MET-1.1
- **Output:** ratio (0.0 = no rework, 1.0 = every task reworked)

### MET-1.3: Token Efficiency

- **Formula:** `total_tokens / tasks_completed` per agent role
- **Source events:** `ModelCallCompleted` (payload contains token counts), `AgentStepCompleted`
- **Reuses:** Existing `step_tokens_counter` at `infrastructure/observability/step_metrics.py:15`
- **Dimensions:** agent_role, model_id, project_id

### MET-1.4: Agent Time to Complete

- **Formula:** `AVG(AgentStepCompleted.occurred_at - AgentStepScheduled.occurred_at)` per agent role
- **Source events:** `AgentStepScheduled`, `AgentStepCompleted`
- **Correlation:** Match via `correlation_id` or `payload.stage_id`

### MET-1.5: Agent Cost

- **Formula:** `(input_tokens × cost_per_1k_input / 1000) + (output_tokens × cost_per_1k_output / 1000)`
- **Source events:** `ModelCallCompleted` (token counts in payload)
- **Requires:** `Model.cost_per_1k_input_tokens` and `Model.cost_per_1k_output_tokens` (see ENT-M3)
- **Aggregation:** Per-agent, per-project, per-period snapshots into `AgentPerformanceRecord`

### MET-1.6: Agent Error Categories

- **Source events:** `AgentStepCompleted` (with failure info), `SkillFailed`, `SandboxCommandExecuted` (non-zero exit code)
- **Categories:** `test_failure`, `review_rejection`, `sandbox_timeout`, `model_error`, `tool_error`
- **Output:** `error_categories: dict[str, int]` on `AgentPerformanceRecord`

---

## MET-2: DORA Metrics (P0 — requires Deployment entity from Layer 4)

**Why after agent metrics:** DORA requires `Deployment` events which don't exist until Layer 4 is built. Agent metrics can start with Layer 1 alone.

### MET-2.1: Deployment Frequency

- **Formula:** `COUNT(DeploymentSucceeded events) / time_period`
- **Source events:** `DeploymentSucceeded`
- **Dimensions:** project_id, team_id, environment_id
- **DORA classification:**
  - Elite: Multiple deploys per day
  - High: Between once per day and once per week
  - Medium: Between once per week and once per month
  - Low: Less than once per month
- **Projection:** `DeploymentFrequencyProjection` in `domain/metrics/dora.py`

### MET-2.2: Lead Time for Changes

- **Formula:** `AVG(deployment.deployed_at - first_commit.occurred_at)` for all commits in a deployment
- **Source events:** `CommitPushed`, `DeploymentSucceeded`
- **Correlation:** Link commits to deployments via `commit_sha` chain. Walk back from deployment SHA to find first commit on the branch.
- **DORA classification:**
  - Elite: Less than one hour
  - High: Between one day and one week
  - Medium: Between one week and one month
  - Low: More than one month

### MET-2.3: Change Failure Rate

- **Formula:** `COUNT(DeploymentFailed + DeploymentRolledBack) / COUNT(all deployment outcomes)`
- **Source events:** `DeploymentSucceeded`, `DeploymentFailed`, `DeploymentRolledBack`
- **DORA classification:**
  - Elite: 0-5%
  - High: 5-10%
  - Medium: 10-15%
  - Low: 15%+

### MET-2.4: Mean Time to Recovery (MTTR)

- **Formula:** `AVG(recovery_deployment.deployed_at - failure_deployment.deployed_at)`
- **Source events:** `DeploymentFailed` followed by `DeploymentSucceeded` for the same project/environment
- **Logic:** For each `DeploymentFailed`, find the next `DeploymentSucceeded` for the same (project_id, environment_id). The delta is the recovery time.
- **DORA classification:**
  - Elite: Less than one hour
  - High: Less than one day
  - Medium: Less than one week
  - Low: More than one week

---

## MET-3: Human Metrics (P1)

**Privacy:** Individual metrics are private by default (per REQ-008 in `future-requirements.md`). Only the user themselves and team leads can view individual records.

### MET-3.1: Review Time

- **Formula:** `AVG(HumanApprovalGranted.occurred_at - ApprovalRequested.occurred_at)`
- **Source events:** `ApprovalRequested`, `HumanApprovalGranted`, `HumanApprovalRejected`
- **Correlation:** Match via `payload.approval_id` or `correlation_id`

### MET-3.2: Approval Latency

- **Formula:** Same as review time but scoped per gate type (spec_approval, merge_approval, etc.)
- **Useful for:** Identifying which approval gates are bottlenecks

### MET-3.3: Contribution Patterns

- **Source events:** `CommitPushed` (actor_id), `PRCreated`, `HumanApprovalGranted`, `WorkItemCreated`
- **Output:** `contributions: dict[str, int]` on `HumanPerformanceRecord` — e.g., `{"commits": 5, "prs_merged": 2, "reviews_given": 8}`
- **Aggregation:** Per user, per project, per period

---

## MET-4: Team Metrics (P1)

### MET-4.1: Team Velocity

- **Formula:** `COUNT(WorkItemCompleted) / period` per team
- **Source events:** `WorkItemCompleted`
- **Team resolution:** WorkItem → Project → Team (via `project.team_id`)
- **Requires:** TeamMember entity (ENT-1) for team membership

### MET-4.2: Team Throughput

- **Formula:** `COUNT(WorkflowRunCompleted where status=succeeded) / period` per team
- **Source events:** `PipelineRunCompleted` (will become `WorkflowRunCompleted` after rename)

### MET-4.3: Collaboration Index

- **Formula:** Cross-pollination score based on how many team members review each other's work
- **Source events:** `HumanApprovalGranted` actor pairs, `PRCommentAdded` actor pairs
- **Calculation:** For each team, count unique (author, reviewer) pairs. Higher diversity = higher collaboration index.

### MET-4.4: Human-Agent Collaboration Ratio

- **Formula:** `agent_completions / (human_completions + agent_completions)` per team
- **Source events:** `AgentStepCompleted`, `WorkItemCompleted` (with actor_type discrimination)
- **Useful for:** Understanding how much of a team's output comes from agents vs humans

---

## MET-5: Quality Metrics (P2)

### MET-5.1: Test Coverage Delta

- **Source events:** `TestRunCompleted` with coverage data in payload
- **Formula:** `coverage_after - coverage_before` per PR/commit
- **Requires:** Test runners reporting coverage percentages in `TestResult` payload

### MET-5.2: Defect Density

- **Formula:** `COUNT(WorkItemCreated where work_type=BUG) / lines_of_code_changed`
- **Source events:** `WorkItemCreated`, `CommitPushed` (with diff stats in payload)
- **Window:** Rolling 30/60/90 day periods

### MET-5.3: Rework Ratio

- **Formula:** `SUM(rework_commit_LOC) / SUM(total_commit_LOC)`
- **Definition of rework commit:** A commit that touches the same files changed in a recent PR, within a configurable window (default: 7 days after merge)
- **Source events:** `CommitPushed` with file paths in payload

---

## MET-6: Metrics Computation Engine

### MET-6.1: Projection-Based Computation

Each metric category has a dedicated projection:

| Projection | Location | Subscribes To |
|---|---|---|
| `AgentAccuracyProjection` | `domain/metrics/agent_metrics.py` | `AgentStepCompleted`, `HumanApprovalRejected`, `WorkItemUpdated` |
| `AgentCostProjection` | `domain/metrics/agent_metrics.py` | `ModelCallCompleted`, `AgentStepCompleted` |
| `DORAProjection` | `domain/metrics/dora.py` | `DeploymentStarted/Succeeded/Failed/RolledBack`, `CommitPushed` |
| `HumanMetricsProjection` | `domain/metrics/human_metrics.py` | `ApprovalRequested`, `HumanApprovalGranted/Rejected`, `CommitPushed`, `PRCreated` |
| `TeamMetricsProjection` | `domain/metrics/team_metrics.py` | `WorkItemCompleted`, `WorkflowRunCompleted`, `HumanApprovalGranted` |

### MET-6.2: Snapshot Schedule

Metrics projections maintain in-memory aggregates and snapshot to `DeliveryMetric` records:
- **Real-time aggregates:** Updated on every event (for dashboard display)
- **Daily snapshots:** Persisted at end of day for historical trending
- **On-demand compute:** API can request a fresh computation for any time range

### MET-6.3: Time Windows

All metrics support configurable time windows:
- Last 24 hours
- Last 7 days
- Last 30 days
- Last 90 days
- Custom range

### MET-6.4: API Surface

```
GET /api/v1/metrics?project_id=X&metric_type=deployment_frequency&period=30d
GET /api/v1/metrics/dora?project_id=X&period=30d  (all 4 DORA metrics)
GET /api/v1/metrics/agents?agent_id=X&period=30d
GET /api/v1/metrics/team?team_id=X&period=30d
GET /api/v1/agents/{agent_id}/performance?period=30d
```
