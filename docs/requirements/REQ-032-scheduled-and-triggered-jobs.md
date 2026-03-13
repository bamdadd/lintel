# REQ-032: Scheduled and Triggered Jobs

**Status:** Proposed
**Priority:** High
**Category:** Workflow Orchestration / Automation

## Problem

Lintel workflows are currently triggered manually (via chat or API). Teams need shared automation — jobs that run on a schedule (e.g., nightly code review, weekly dependency audit) or in response to events (e.g., PR opened, branch pushed). Tools like Codex CLI offer local automations, but these run on individual machines and don't work in a team setting where visibility, shared configuration, and centralised execution are required.

## Example Use Cases

1. **PR review on PR-raised trigger** — automatically run the review workflow when a pull request is opened or updated, providing immediate AI-powered code review feedback.
2. **Hourly tech-debt find and fix** — scheduled job that scans the codebase for code smells, outdated patterns, or TODO items, and creates work items or auto-fix PRs.
3. **Weekly larger refactor identification** — weekly scan that analyses code structure, dependency graphs, and complexity metrics to surface refactoring opportunities that span multiple files or modules.
4. **Nightly dependency audit** — check for outdated or vulnerable dependencies and open PRs with updates.
5. **Daily documentation drift check** — compare code changes against docs to flag stale documentation.

## Proposed Solution

Add a **Jobs** system that allows teams to define shared, server-side jobs that execute workflows on a schedule (cron) or in response to triggers (webhooks, git events, API calls).

### Requirements

1. **Job definition:** A job combines a workflow definition, a project, input parameters, and a schedule or trigger configuration.
2. **Cron scheduling:** Jobs can be scheduled using cron expressions (e.g., `0 2 * * *` for nightly at 2am). The server evaluates cron expressions and dispatches workflow runs at the appropriate time.
3. **Event triggers:** Jobs can be triggered by external events:
   - Git events (push, PR opened/merged, tag created) — via existing webhook infrastructure (REQ-026)
   - API call (POST to a job-specific endpoint)
   - Manual dispatch (UI or MCP tool)
4. **Shared visibility:** All team members can see job definitions, execution history, and logs through the UI and MCP tools.
5. **Job management:** CRUD operations for jobs via API and MCP tools:
   - `create_job`, `get_job`, `list_jobs`, `update_job`, `delete_job`
   - `list_job_runs`, `get_job_run` for execution history
6. **Concurrency control:** Configurable concurrency policy per job:
   - `allow` — multiple runs can execute simultaneously
   - `queue` — runs are queued and execute sequentially
   - `skip` — if a run is in progress, new triggers are skipped
   - `cancel` — cancel the in-progress run and start a new one
7. **Input parameters:** Jobs can define input parameters with defaults. Triggers can override parameters (e.g., a git push trigger passes the commit SHA).
8. **Enabled/disabled:** Jobs can be paused without deleting them.
9. **Execution context:** Each job run creates a pipeline run, inheriting the job's project, workflow definition, and parameters. Existing pipeline tracking, stage progression, and notifications apply.
10. **Audit trail:** Job creation, updates, manual triggers, and schedule-triggered runs are recorded in the audit log.

### Data Model

```python
@dataclass(frozen=True)
class JobSchedule:
    cron: str  # cron expression, e.g. "0 2 * * 1-5"
    timezone: str = "UTC"

@dataclass(frozen=True)
class JobTrigger:
    trigger_type: str  # "cron" | "webhook" | "git_event" | "manual" | "api"
    config: dict[str, Any] = field(default_factory=dict)
    # For git_event: {"events": ["push", "pull_request.opened"], "branches": ["main"]}
    # For cron: {"schedule": "0 2 * * *", "timezone": "UTC"}

@dataclass(frozen=True)
class JobDefinition:
    job_id: str
    name: str
    project_id: str
    workflow_definition_id: str
    triggers: list[JobTrigger]
    input_parameters: dict[str, Any] = field(default_factory=dict)
    concurrency_policy: str = "queue"  # allow | queue | skip | cancel
    enabled: bool = True
    created_at: datetime
    updated_at: datetime

@dataclass(frozen=True)
class JobRun:
    run_id: str
    job_id: str
    pipeline_run_id: str
    trigger_type: str  # which trigger fired
    trigger_metadata: dict[str, Any]  # e.g. commit SHA, PR number
    status: str  # pending | running | completed | failed | cancelled
    started_at: datetime | None
    completed_at: datetime | None
```

### MCP Tools

- `jobs_create_job` — create a new job definition
- `jobs_get_job` — get job details
- `jobs_list_jobs` — list all jobs (filterable by project)
- `jobs_update_job` — update job configuration
- `jobs_delete_job` — delete a job
- `jobs_trigger_job` — manually trigger a job run
- `jobs_list_job_runs` — list execution history for a job
- `jobs_get_job_run` — get details of a specific run

### Implementation Sketch

```
src/lintel/
├── contracts/jobs.py          # JobDefinition, JobRun, JobTrigger dataclasses
├── domain/jobs.py             # Job scheduling logic, concurrency enforcement
├── infrastructure/
│   ├── scheduler/             # Cron evaluation, job dispatch loop
│   │   ├── __init__.py
│   │   └── cron_scheduler.py  # APScheduler or custom asyncio cron
│   └── mcp/tools/jobs.py      # MCP tool handlers
├── api/routes/jobs.py         # REST API endpoints
└── projections/jobs.py        # Read-side projection for job listing
```

### Dependencies

- REQ-026 (Git Event Listeners) — for git-event triggered jobs
- REQ-028 (Workflow Node Classes) — jobs dispatch workflow definitions
- REQ-029 (Pipeline Step Timeout) — timeouts apply to job-triggered pipeline runs

### Open Questions

1. Should jobs support retry policies (e.g., retry failed runs up to N times)?
2. Should there be a max concurrent jobs limit at the system level?
3. Should job definitions be versioned (so in-flight runs use the config at trigger time)?
