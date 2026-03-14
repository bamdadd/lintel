# Automations Design Spec

**Date:** 2026-03-14
**Status:** Approved
**REQ:** REQ-032 (Scheduled and Triggered Jobs)

## Overview

Add an **Automations** system that allows teams to define server-side automation rules that execute workflows on a cron schedule, in response to internal domain events, or on manual trigger. Each automation execution creates a PipelineRun — no separate run entity needed.

## Domain Term

"Automation" was chosen over "Job" to avoid collision with "Work Item" and "Workflow". An `AutomationDefinition` is the rule; a `PipelineRun` is the execution.

## Data Model

### New Types (contracts/types.py)

```python
class AutomationTriggerType(str, Enum):
    CRON = "cron"        # time-based via cron expression
    EVENT = "event"      # internal domain events via EventBus
    MANUAL = "manual"    # API/UI/MCP triggered

class ConcurrencyPolicy(str, Enum):
    ALLOW = "allow"      # run all simultaneously
    QUEUE = "queue"      # FIFO, one at a time
    SKIP = "skip"        # drop if already running
    CANCEL = "cancel"    # cancel in-flight, start new

@dataclass(frozen=True)
class AutomationDefinition:
    automation_id: str
    name: str
    project_id: str
    workflow_definition_id: str
    trigger_type: AutomationTriggerType
    trigger_config: dict[str, object]
    input_parameters: dict[str, object] = field(default_factory=dict)
    concurrency_policy: ConcurrencyPolicy = ConcurrencyPolicy.QUEUE
    enabled: bool = True
    created_at: datetime
    updated_at: datetime
```

### trigger_config shapes

- **cron:** `{"schedule": "0 2 * * *", "timezone": "UTC"}`
- **event:** `{"event_types": ["PipelineRunCompleted", "WorkItemCreated"]}`
- **manual:** `{}`

### PipelineRun linkage

Each automation execution creates a `PipelineRun` with `trigger_type="automation:{automation_id}"`. This follows the existing pattern (`"chat:{conversation_id}"`). No separate `AutomationRun` entity.

## Events

Stream ID: `automation:{automation_id}`

| Event | Payload | When |
|-------|---------|------|
| `AutomationCreated` | automation_id, name, project_id, workflow_definition_id, trigger_type | Automation created |
| `AutomationUpdated` | automation_id, changed fields | Config updated |
| `AutomationRemoved` | automation_id | Deleted |
| `AutomationEnabled` | automation_id | Toggled on |
| `AutomationDisabled` | automation_id | Toggled off |
| `AutomationFired` | automation_id, trigger_type, pipeline_run_id | Execution started |
| `AutomationSkipped` | automation_id, reason | Concurrency policy skipped a trigger |
| `AutomationCancelled` | automation_id, cancelled_run_id, new_run_id | Cancel policy killed in-flight run |

## Scheduler & Concurrency

### AutomationScheduler

Asyncio background task started in app lifespan, following the `SchedulerLoop` pattern.

- **Cron tick:** Every 60 seconds, query enabled cron automations, evaluate via `croniter`, fire those due. Tracks `last_fired_at` per automation to prevent double-firing.
- **Event subscriptions:** On startup, subscribe to EventBus for event types referenced by enabled event automations. When an event matches, fire the automation.
- **Resubscription:** When an automation is created/updated/removed, update EventBus subscriptions accordingly.

### Concurrency Enforcement

Before creating a PipelineRun, check active runs for that automation:

| Policy | Active run exists? | Action |
|--------|-------------------|--------|
| `allow` | doesn't matter | Create run immediately |
| `queue` | yes | Enqueue; start when current completes |
| `queue` | no | Create run immediately |
| `skip` | yes | Emit `AutomationSkipped`, do nothing |
| `skip` | no | Create run immediately |
| `cancel` | yes | Cancel active run, emit `AutomationCancelled`, create new |
| `cancel` | no | Create run immediately |

**Queue implementation:** In-memory queue per automation. Subscribe to `PipelineRunCompleted`/`PipelineRunFailed` to dequeue next. Queued-but-not-started runs are lost on server restart (acceptable for v1).

**Cancel implementation:** Mark the active PipelineRun as `cancelled` and let the workflow executor check for cancellation.

## API Routes

`packages/app/src/lintel/api/routes/automations.py`

```
POST   /automations                           → create automation
GET    /automations                           → list (filter by project_id)
GET    /automations/{automation_id}           → get details
PATCH  /automations/{automation_id}           → update config
DELETE /automations/{automation_id}           → remove
POST   /automations/{automation_id}/trigger   → manual fire
GET    /automations/{automation_id}/runs      → list PipelineRuns for this automation
```

### Pydantic Schemas

`packages/app/src/lintel/api/schemas/automations.py`

```python
class CreateAutomationRequest(BaseModel):
    name: str
    project_id: str
    workflow_definition_id: str
    trigger_type: AutomationTriggerType
    trigger_config: dict[str, object] = {}
    input_parameters: dict[str, object] = {}
    concurrency_policy: ConcurrencyPolicy = ConcurrencyPolicy.QUEUE
    enabled: bool = True

class UpdateAutomationRequest(BaseModel):
    name: str | None = None
    trigger_config: dict[str, object] | None = None
    input_parameters: dict[str, object] | None = None
    concurrency_policy: ConcurrencyPolicy | None = None
    enabled: bool | None = None
```

## MCP Tools

```
automations_create_automation
automations_list_automations
automations_get_automation
automations_update_automation
automations_delete_automation
automations_trigger_automation
automations_list_automation_runs
```

## Package Layout

| Component | Location |
|-----------|----------|
| `AutomationDefinition`, `AutomationTriggerType`, `ConcurrencyPolicy` | `packages/contracts/src/lintel/contracts/types.py` |
| Automation events | `packages/contracts/src/lintel/contracts/events.py` |
| `AutomationScheduler`, concurrency logic | `packages/domain/src/lintel/domain/automation_scheduler.py` |
| `InMemoryAutomationStore` | `packages/app/src/lintel/api/routes/automations.py` |
| `PostgresAutomationStore` | `packages/infrastructure/src/lintel/infrastructure/persistence/stores.py` |
| API routes | `packages/app/src/lintel/api/routes/automations.py` |
| Pydantic schemas | `packages/app/src/lintel/api/schemas/automations.py` |
| MCP tools | `packages/infrastructure/src/lintel/infrastructure/mcp/tools/automations.py` |

## Dependencies

- `croniter` — added to domain package for cron expression parsing
- No new infrastructure dependencies
- No projection needed for v1 (store is the read model)

## Relationship to Existing Entities

- **Trigger** — stays as-is. Lightweight "event source registration" on PipelineRun. Automations are a higher-level concept.
- **WorkflowDefinition** — referenced by automation. Automation says "run this workflow."
- **PipelineRun** — execution record. Linked via `trigger_type="automation:{id}"`.
- **EventBus** — used for event-triggered automations and concurrency queue management.

## Scope (v1)

**In scope:**
- Cron, event, and manual trigger types
- All 4 concurrency policies (allow, queue, skip, cancel)
- CRUD API + MCP tools
- In-memory + Postgres stores
- Background scheduler in app lifespan
- Audit trail via events

**Out of scope (future):**
- External webhook triggers (depends on REQ-026)
- Retry policies for failed runs
- System-level max concurrent automations limit
- Job definition versioning
- Domain-level package restructure (work item created)
