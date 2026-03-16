# Process Mining — Data Flow Diagrams

Reference diagrams showing how data flows through the Lintel platform.
Each diagram covers one flow type. The process mining workflow auto-generates
these per-repository; the diagrams below document the **platform itself**.

---

## 1. HTTP Request Flow

How a REST request arrives, passes through middleware, hits a route handler,
persists to a store, and optionally emits a domain event.

```mermaid
sequenceDiagram
    participant Client
    participant CORS as CORSMiddleware
    participant Corr as CorrelationMiddleware
    participant Router as FastAPI Router
    participant Handler as Route Handler
    participant SP as StoreProvider
    participant Store as CrudStore / DictStore
    participant DB as PostgreSQL
    participant ED as dispatch_event
    participant ES as EventStore

    Client->>+CORS: HTTP request
    CORS->>+Corr: forward
    Corr->>Corr: bind correlation_id
    Corr->>+Router: resolve route
    Router->>+Handler: Depends(StoreProvider)
    Handler->>+SP: .get()
    SP-->>-Handler: store instance
    Handler->>+Store: add / get / update
    Store->>+DB: INSERT / SELECT
    DB-->>-Store: rows
    Store-->>-Handler: entity
    Handler->>+ED: dispatch_event(request, envelope)
    ED->>+ES: append(stream_id, events)
    ES->>DB: INSERT INTO events
    ES-->>-ED: ok
    ED-->>-Handler: ok
    Handler-->>-Router: JSON response
    Router-->>-Corr: response
    Corr-->>-CORS: add X-Correlation-ID
    CORS-->>-Client: HTTP response
```

---

## 2. Event Sourcing Flow

How an event is created, persisted with hash-chain validation, published
to the in-memory event bus, and delivered to subscribers.

```mermaid
sequenceDiagram
    participant Producer as Event Producer
    participant ES as EventStore
    participant DB as PostgreSQL
    participant EB as InMemoryEventBus
    participant PE as ProjectionEngine
    participant Proj as Projection
    participant HM as HookManager
    participant DL as DeliveryLoopManager

    Producer->>+ES: append(stream_id, events)
    ES->>ES: check optimistic concurrency
    ES->>ES: compute payload_hash + prev_hash
    ES->>+DB: INSERT INTO events (in TX)
    DB-->>-ES: committed
    ES->>+EB: publish(event) [after TX]
    EB->>EB: match subscribers by event_type
    par Projection delivery
        EB->>+PE: handle(event)
        PE->>+Proj: project(event)
        Proj->>Proj: update read model
        Proj-->>-PE: ok
        PE-->>-EB: ok
    and Hook delivery
        EB->>+HM: handle(event)
        HM->>HM: pattern-match hooks
        HM-->>-EB: fire matching hooks
    and Delivery loop
        EB->>+DL: handle(event)
        DL->>DL: advance phase
        DL-->>-EB: ok
    end
    EB-->>-ES: ok
    ES-->>-Producer: ok
```

---

## 3. Command Dispatch Flow

How a command (e.g. `StartWorkflow`) is dispatched, handled by the executor,
and results in pipeline events.

```mermaid
sequenceDiagram
    participant Chat as ChatService
    participant CD as CommandDispatcher
    participant WE as WorkflowExecutor
    participant ES as EventStore
    participant LG as LangGraph
    participant Node as Graph Node
    participant ST as StageTracker
    participant PS as PipelineStore

    Chat->>+CD: dispatch(StartWorkflow)
    CD->>+WE: execute(command)
    WE->>+ES: append PipelineRunStarted
    ES-->>-WE: ok
    WE->>+LG: astream(initial_state, config)
    loop each graph node
        LG->>+Node: invoke
        Node->>+ST: mark_running(stage)
        ST->>+PS: update stage status
        PS-->>-ST: ok
        ST-->>-Node: ok
        Node->>Node: do work
        Node->>+ST: mark_completed(stage)
        ST->>PS: update stage status
        ST-->>-Node: ok
        Node-->>-LG: state update
        LG->>+ES: append PipelineStageCompleted
        ES-->>-LG: ok
    end
    LG-->>-WE: final state
    WE->>+ES: append PipelineRunCompleted
    ES-->>-WE: ok
    WE-->>-CD: ok
    CD-->>-Chat: ok
```

---

## 4. Background Job / Automation Flow

How cron-scheduled and event-triggered automations fire workflows.

```mermaid
sequenceDiagram
    participant Cron as Cron Ticker (60s)
    participant AS as AutomationScheduler
    participant AR as AutomationStore
    participant EB as EventBus
    participant HM as HookManager
    participant CD as CommandDispatcher

    rect rgb(245, 245, 255)
        Note over Cron,AS: Cron-triggered path
        Cron->>+AS: tick_cron()
        AS->>+AR: list enabled CRON automations
        AR-->>-AS: automations
        AS->>AS: evaluate cron expressions
        AS->>AS: check concurrency policy
        AS->>+CD: dispatch(StartWorkflow)
        CD-->>-AS: ok
        AS-->>-Cron: fired IDs
    end

    rect rgb(255, 245, 245)
        Note over EB,HM: Event-triggered path
        EB->>+HM: handle(event)
        HM->>HM: fnmatch event_type vs patterns
        HM->>HM: check chain depth (loop guard)
        HM->>+CD: dispatch(StartWorkflow)
        CD-->>-HM: ok
        HM-->>-EB: ok
    end
```

---

## 5. External Integration Flow (Slack / Telegram)

How external messages arrive, get translated to domain commands, and
trigger chat routing or workflow dispatch.

```mermaid
sequenceDiagram
    participant Slack as Slack Webhook
    participant ET as EventTranslator
    participant CR as ChatRouter
    participant CS as ChatStore
    participant CD as CommandDispatcher
    participant WE as WorkflowExecutor

    Slack->>+ET: message event (JSON)
    ET->>ET: filter bot msgs, extract ThreadRef
    ET->>+CR: ProcessIncomingMessage
    CR->>CR: classify (chat_reply vs start_workflow)

    alt chat_reply
        CR->>+CS: store message
        CS-->>-CR: ok
        CR->>CR: generate AI response
        CR->>Slack: post reply
    else start_workflow
        CR->>CR: create WorkItem + Trigger + PipelineRun
        CR->>+CD: dispatch(StartWorkflow)
        CD->>+WE: execute
        WE-->>-CD: ok
        CD-->>-CR: ok
    end
    CR-->>-ET: ok
    ET-->>-Slack: ack
```

---

## 6. Projection Rebuild / Catch-up Flow

How projections restore state on startup and subscribe with gap-free delivery.

```mermaid
sequenceDiagram
    participant Engine as ProjectionEngine
    participant PS as ProjectionStore
    participant ES as EventStore
    participant EB as EventBus
    participant Proj as Projection

    Engine->>+PS: load(projection.name)
    PS-->>-Engine: saved state + global_position

    Engine->>+Proj: restore_state(saved)
    Proj-->>-Engine: ok

    Note over Engine,EB: catch_up_subscribe (gap-free)

    Engine->>+EB: subscribe with BufferingHandler
    EB-->>-Engine: subscription_id

    Engine->>+ES: read_all(from_position)
    ES-->>-Engine: historical events

    loop replay historical
        Engine->>+Proj: project(event)
        Proj-->>-Engine: ok
    end

    Engine->>Engine: drain buffer, deduplicate
    Engine->>Engine: switch to pass-through

    Note over Engine: Now receiving live events
    EB->>+Engine: handle(new_event)
    Engine->>+Proj: project(new_event)
    Proj-->>-Engine: ok
    Engine-->>-EB: ok
```

---

## 7. Process Mining Workflow

The workflow that auto-generates diagrams 1-6 for any target repository.

```mermaid
flowchart TD
    A[Ingest] --> B[Setup Workspace]
    B --> C[Discover Endpoints]
    C -->|continue| D[Trace Flows]
    C -->|error| E[Error]
    D --> F[Classify Flows]
    F --> G[Generate Diagrams]
    G --> H[Persist Results]
    H --> I((END))
    E --> I

    style A fill:#e1f5fe
    style B fill:#e1f5fe
    style C fill:#fff3e0
    style D fill:#fff3e0
    style F fill:#f3e5f5
    style G fill:#f3e5f5
    style H fill:#e8f5e9
    style E fill:#ffebee
```

### What gets discovered

| Flow Type | Detection Method | Example |
|-----------|-----------------|---------|
| HTTP Request | `@router.get/post/put/delete` decorators | `POST /api/v1/users` |
| Event Sourcing | `event_bus.subscribe`, `@event_handler` | `WorkItemCreated -> AuditProjection` |
| Command Dispatch | `dispatcher.register` | `StartWorkflow -> WorkflowExecutor` |
| Background Job | `@celery_app.task`, `create_task`, cron patterns | `AutomationScheduler.tick_cron` |
| External Integration | `httpx`, `aiohttp`, `requests` calls | `SlackAdapter.post_message` |

### Other mining approaches to consider

- **AST-based import graph** — follow `import` statements to build module dependency trees
- **OpenTelemetry trace replay** — replay recorded spans to reconstruct real production flows
- **Database query log analysis** — parse `pg_stat_statements` to map which endpoints hit which tables
- **Git blame correlation** — map code paths to change frequency and ownership
- **Runtime instrumentation** — inject middleware that logs every function entry/exit during a test run
