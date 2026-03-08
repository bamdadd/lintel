# Event System Requirements

## Current State

Lintel has an event-sourced architecture with 50+ event types (expanding to ~115 with PR #1's audit events). All events extend `EventEnvelope` (`contracts/events.py:17`) with shared metadata:

| Field | Type | Description |
|---|---|---|
| `event_id` | UUID | Unique event identifier |
| `event_type` | str | Discriminator (class name) |
| `schema_version` | int | For upcasting on schema changes |
| `occurred_at` | datetime | UTC timestamp |
| `actor_type` | ActorType | `human`, `agent`, or `system` |
| `actor_id` | str | Who triggered the event |
| `thread_ref` | ThreadRef? | Associated thread (if any) |
| `correlation_id` | UUID | Groups related events |
| `causation_id` | UUID? | Direct cause event |
| `payload` | dict | Event-specific data |
| `idempotency_key` | str? | Deduplication key |

### Current Problem

Events are stored in the event store and projected synchronously. The `event_dispatcher.py` (PR #1) calls `event_store.append()` then `engine.project()` sequentially. There is no pub/sub — adding a new consumer means modifying the dispatcher. The projection engine (`infrastructure/projections/engine.py`) iterates over registered projections synchronously.

This is the **foundation gap** — everything else (metrics, guardrails, integration sync) needs reactive event delivery.

---

## EVT-1: Event Bus Protocol (P0)

**The single most important requirement.** Everything else is a subscriber.

### EVT-1.1: EventBus Protocol

Add to `contracts/protocols.py`:

```python
class EventHandler(Protocol):
    async def handle(self, event: EventEnvelope) -> None: ...

class EventBus(Protocol):
    async def publish(self, event: EventEnvelope) -> None: ...
    async def subscribe(
        self,
        event_types: frozenset[str],
        handler: EventHandler,
    ) -> str: ...  # returns subscription_id
    async def unsubscribe(self, subscription_id: str) -> None: ...
```

### EVT-1.2: InMemoryEventBus Implementation

Create `infrastructure/event_bus/in_memory.py`:

- One `asyncio.Queue` per subscriber
- Filtered by event type at publish time
- Non-blocking publish (fire-and-forget to queues, log errors)
- Thread-safe via asyncio locks
- Subscriber IDs for lifecycle management

Inspired by EventStoreDB persistent subscriptions and the EventStore project's catch-up subscription pattern.

### EVT-1.3: Wire EventBus into EventStore

Modify `infrastructure/event_store/postgres.py` (and `in_memory.py`):

- After successful `append()`, call `bus.publish(event)` for each event in the batch
- The event store owns the "after-persist publish" contract
- If bus publish fails, log warning but don't fail the append (events are already persisted)

**Migration from PR #1:** The `dispatch_event()` function in `domain/event_dispatcher.py` currently calls `event_store.append()` then `engine.project()`. After this change, the `engine.project()` call is removed — the projection engine subscribes to the bus instead. The dispatcher simplifies to just `event_store.append()` (which internally publishes to the bus).

### EVT-1.4: Migrate ProjectionEngine to EventBus Subscriber

Refactor `infrastructure/projections/engine.py`:

- `InMemoryProjectionEngine` subscribes to the EventBus on startup
- Remove manual `project()` calls from the event dispatcher and all API routes
- The `project()` method becomes an internal handler called by the bus subscription
- Projections become reactive instead of synchronous

### EVT-1.5: NATS-Backed EventBus (P2)

For multi-process deployments. NATS is already a dependency (`nats-py>=2.9` in `pyproject.toml`).

Create `infrastructure/event_bus/nats.py`:
- JetStream for durable subscriptions
- Consumer groups for horizontal scaling
- Dead letter queue for failed deliveries

---

## EVT-2: Subscription Patterns (P0)

### EVT-2.1: Catch-up Subscription

Read all historical events from the store, then switch to live events from the bus.

```python
async def catch_up_subscribe(
    event_store: EventStore,
    event_bus: EventBus,
    event_types: frozenset[str],
    handler: EventHandler,
    from_position: int = 0,
) -> str:
    # 1. Read historical events
    for event in await event_store.read_by_event_type(event_types, from_position):
        await handler.handle(event)
    # 2. Switch to live
    return await event_bus.subscribe(event_types, handler)
```

Used for: projection rebuilds, metrics backfill.

### EVT-2.2: Live Subscription

Only receive new events from the point of subscription.

Used for: real-time notifications, guardrail evaluation, Slack message updates.

### EVT-2.3: Filtered Subscription

Subscribe to specific event types only.

Used for: specialized projections (e.g., deployment metrics projection only cares about `DeploymentStarted/Succeeded/Failed`).

---

## EVT-3: EventStore Query Extensions (P1)

### EVT-3.1: Read by Event Type

Add to `EventStore` protocol:
```python
async def read_by_event_type(
    self,
    event_type: str,
    from_position: int = 0,
    limit: int = 1000,
) -> list[EventEnvelope]: ...
```

Required for catch-up subscriptions and metrics backfill.

### EVT-3.2: Read by Time Range

Add to `EventStore` protocol:
```python
async def read_by_time_range(
    self,
    from_time: datetime,
    to_time: datetime,
    event_types: frozenset[str] | None = None,
) -> list[EventEnvelope]: ...
```

Required for metrics computation windows (e.g., "deployment frequency in the last 30 days").

### EVT-3.3: Global Position

Add `global_position` column to the Postgres events table:
- Monotonically increasing, gap-free
- Required for consistent ordering across streams
- Used by catch-up subscriptions to track "where I left off"

---

## EVT-4: New Event Types (by layer)

### Layer 2 — Collaboration Events

| Event | Payload | When |
|---|---|---|
| `TeamMemberAdded` | `{team_id, member_id, member_type, ref_id, role}` | Human or agent joins team |
| `TeamMemberRemoved` | `{team_id, member_id}` | Member leaves team |
| `TeamMemberRoleChanged` | `{team_id, member_id, old_role, new_role}` | Role updated |
| `ChannelRegistered` | `{channel_id, team_id, channel_type, external_id}` | Channel bound to team |
| `ChannelUpdated` | `{channel_id, changes}` | Channel config changed |
| `ChannelDisabled` | `{channel_id}` | Channel deactivated |
| `IntegrationRegistered` | `{integration_id, integration_type, provider}` | External tool connected |
| `IntegrationSynced` | `{integration_id, items_synced, sync_duration_ms}` | Sync completed |
| `IntegrationFailed` | `{integration_id, error}` | Sync or connection failed |

### Layer 3 — Guardrail Events

| Event | Payload | When |
|---|---|---|
| `GuardrailTriggered` | `{rule_id, trigger_event_id, condition_matched, action}` | Rule condition met |
| `GuardrailEscalated` | `{rule_id, escalation_target, reason}` | Escalated to human |
| `GuardrailResolved` | `{rule_id, resolved_by, resolution}` | Issue resolved |

### Layer 4 — Deployment Events

| Event | Payload | When |
|---|---|---|
| `DeploymentStarted` | `{deployment_id, project_id, environment_id, commit_sha}` | Deployment begins |
| `DeploymentSucceeded` | `{deployment_id, duration_ms}` | Deployment completes |
| `DeploymentFailed` | `{deployment_id, error, duration_ms}` | Deployment fails |
| `DeploymentRolledBack` | `{deployment_id, rollback_to_deployment_id}` | Rollback executed |
| `ExperimentStarted` | `{experiment_id, feature_flag_key, variants}` | Experiment begins |
| `VariantAssigned` | `{experiment_id, subject_id, variant_name}` | Subject assigned variant |
| `ExperimentCompleted` | `{experiment_id, results}` | Experiment concludes |

### Layer 5 — Metrics Events

| Event | Payload | When |
|---|---|---|
| `DeliveryMetricComputed` | `{metric_id, metric_type, value, project_id}` | Metric snapshot created |
| `AgentPerformanceComputed` | `{record_id, agent_id, accuracy_rate}` | Agent perf aggregated |
| `HumanPerformanceComputed` | `{record_id, user_id}` | Human perf aggregated |

### Layer 6 — Delivery Loop Events

| Event | Payload | When |
|---|---|---|
| `DeliveryLoopStarted` | `{loop_id, project_id, work_item_id, phase_sequence}` | Work item enters loop |
| `DeliveryLoopPhaseTransitioned` | `{loop_id, from_phase, to_phase}` | Phase transition |
| `LearningCaptured` | `{loop_id, learning_text, category}` | Insight recorded |
| `DeliveryLoopCompleted` | `{loop_id, total_duration_ms}` | Loop finishes |

**Total: ~26 new event types** added to existing ~115 (after PR #1 merge).

All follow the existing pattern: frozen dataclasses extending `EventEnvelope`, registered in `EVENT_TYPE_MAP`.

---

## EVT-5: Design Rules

### EVT-5.1: Events Describe What Happened

Events are past-tense facts. They record what already occurred. They are never rejected.

### EVT-5.2: Commands Express Intent

Commands may fail. A guardrail detecting "cost over budget" emits a `PauseWorkflow` command — not an event. The command handler decides whether to pause and emits the resulting event.

### EVT-5.3: No Circular Event Chains

```
Command → Handler → (State Change + Event) → EventBus → Guardrail → (New Command) → Handler
```

Guardrails and projections NEVER emit events directly. They emit commands that go through handlers.

### EVT-5.4: Event Payloads Are Self-Contained

An event's `payload` must contain all data needed to process it without querying external state. This ensures events can be replayed independently.

### EVT-5.5: Schema Versioning

Every event has a `schema_version` field (default 1). When event payloads change, increment the version. Implement upcasters to transform old versions to new versions during deserialization.

---

## EVT-6: Compatibility with PR #1

PR #1 (`claude/add-audit-events-I8lJa`) introduces:

1. **`event_dispatcher.py`** — `dispatch_event()` calls `event_store.append()` then `engine.project()` synchronously. This is the precursor to the EventBus. After EVT-1 is implemented, the dispatcher simplifies to just `event_store.append()` (the bus handles the rest).

2. **Audit projection** — Maps events to `AuditEntry` records. This becomes the first EventBus subscriber.

3. **~66 new CRUD events** — `UserUpdated`, `TeamRemoved`, `AIProviderCreated`, etc. These are additive and compatible with all requirements.

4. **Pipeline events** — `PipelineRunCancelled`, `PipelineStageApproved/Rejected/Retried`. These will be renamed when `PipelineRun` → `WorkflowRun` rename happens.

The migration path is clear:
1. Merge PR #1 (audit events + dispatcher)
2. Implement EventBus (EVT-1)
3. Wire EventBus into event store (EVT-1.3)
4. Migrate projection engine to bus subscriber (EVT-1.4)
5. Migrate `dispatch_event()` to just call `event_store.append()` (bus handles fan-out)
6. Add new subscribers: guardrail engine, metrics projections, integration sync
