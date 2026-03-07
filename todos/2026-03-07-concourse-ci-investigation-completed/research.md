# Concourse CI Investigation — Research

**EXECUTIVE SUMMARY**

Concourse CI is a container-based CI/CD platform built around three primitives: resources (versioned external artifacts), jobs (build plans), and tasks (containerized work). Its ATC orchestrator, backed solely by PostgreSQL, proves that a single-node scheduler with DB-level coordination scales to hundreds of pipelines without message queues or distributed coordinators. Lintel's existing event-sourced CQRS architecture maps remarkably well onto Concourse's model — but with LangGraph's code-first graph model replacing YAML pipelines, and Slack threads replacing resource polling as the primary trigger mechanism.

- **Recommended Approach**: Option B — LangGraph-native scheduler with Concourse-inspired primitives
- **Why**: Leverages Lintel's existing LangGraph + event store infrastructure while adopting Concourse's proven scheduling patterns (version-flow, step modifiers, PostgreSQL coordination)
- **Trade-offs**: More upfront design work than pure Concourse-clone, but avoids impedance mismatch between YAML pipelines and AI agent workflows
- **Confidence**: High — strong architectural alignment between Lintel's existing patterns and Concourse's proven design
- **Next Step**: User decision required — review options below

---

## 1. Problem Statement

- **Original Task**: Investigate Concourse CI's architecture and scheduling model to inform Lintel's pipeline/scheduling design as "Concourse for AI"
- **Success Criteria**: Understand what Concourse patterns transfer to AI agent orchestration, what's missing, and design a single-node architecture
- **Key Questions**: How does Concourse schedule work? What UI patterns enable build visibility? How does LangGraph replace YAML pipelines? What gaps exist for AI workloads?
- **Constraints**: Single-node first; LangGraph preferred over YAML; Slack-triggered; must support live streaming and per-step timing

## 2. Investigation Summary

- **Codebase survey**: Analyzed ~100 Python files across contracts, workflows, infrastructure, and API layers
- **Concourse architecture**: Researched 9 topics including ATC internals, scheduling algorithm, resource interface, task execution, single vs multi-node
- **Concourse UI/UX**: Researched 9 topics including SSE streaming, event types, pipeline visualization, build metadata, Prometheus metrics
- **LangGraph pipelines**: Researched 11 topics including StateGraph model, checkpointing, HITL interrupts, streaming modes, parallel execution, observability

**Evidence collected**: 100+ source files, 20+ web sources, 4 tech area appendices

## 3. Key Findings

### Finding 1: Lintel's Domain Model Already Maps to Concourse Concepts
- **Discovery**: `PipelineRun`, `Stage`, `StageStatus`, `Trigger`, `TriggerType`, `WorkItem`, and approval gates are already modeled as frozen dataclasses in `contracts/types.py`. 50+ event types cover the full pipeline lifecycle.
- **Evidence**: [REPO-01, REPO-10] — `src/lintel/contracts/types.py:248-350`, `src/lintel/contracts/events.py`
- **Implication**: No new domain modeling needed for scheduling primitives — wire existing types to an execution engine.

### Finding 2: Concourse's PostgreSQL-Only Coordination is Sufficient
- **Discovery**: Concourse runs hundreds of pipelines (BOSH: 4 ATC nodes, 34 workers, 534 pipelines) using only PostgreSQL row-level locks for scheduler coordination. No message queue, no ZooKeeper, no etcd.
- **Evidence**: [WEB-01, WEB-13] — Concourse internals docs
- **Implication**: Lintel can drop NATS from the critical scheduling path. The existing PostgreSQL event store provides all coordination needed for single-node and eventual multi-node.

### Finding 3: Concourse's SSE Event Stream Maps Directly to LangGraph Node Lifecycle
- **Discovery**: Concourse streams typed events (`initialize-task`, `start-task`, `finish-task`, `log`, `status`, `end`) via SSE. LangGraph has equivalent lifecycle points (node entry, LLM call, tool call, node exit) and 5 streaming modes.
- **Evidence**: [WEB-06 UI, WEB-06 LG] — Event stream API docs, LangGraph streaming docs
- **Implication**: Define a `WorkflowEvent` SSE stream that combines Concourse's proven event taxonomy with LangGraph's streaming infrastructure. Add `tool-call` and `tool-result` event types that Concourse doesn't have.

### Finding 4: Concourse Lacks Per-Step Execution Metrics — Lintel Can Fill This Gap
- **Discovery**: Concourse exposes `concourse_builds_duration_seconds` but has NO per-step execution duration metric (only queue wait time). Community has been requesting this since 2022 (Discussion #5671).
- **Evidence**: [WEB-13 UI, WEB-14 UI] — Prometheus metrics docs, GitHub discussion
- **Implication**: `lintel_step_duration_seconds{workflow, step_type, tool_name, status}` should be a day-one metric. Combined with OTel spans, this gives both aggregate and per-run timing.

### Finding 5: The Resource Interface (check/in/out) Maps to Lintel's Skills
- **Discovery**: Concourse's resource type is a container with three executables — `check` (discover versions), `in` (fetch), `out` (push). JSON over stdin/stdout. This narrow contract enabled 100+ community resource types.
- **Evidence**: [WEB-07] — Resource implementation docs
- **Implication**: Formalize Lintel's `skills/` as a similar narrow interface: `check` (does this skill apply?), `in` (fetch context), `out` (produce outputs). Enables a skill ecosystem.

### Finding 6: Routes and Workflow Nodes Are Stubs — Wiring Is the First Task
- **Discovery**: API routes build command objects but return `asdict(command)` without dispatching. Event endpoints return empty lists. Most workflow nodes are hardcoded stubs. The visual editor saves graphs but nothing compiles them.
- **Evidence**: [REPO-14, REPO-15, REPO-16] — Route files, workflow nodes
- **Implication**: Before adding scheduling, wire the existing command bus to the LangGraph executor. This is prerequisite to everything else.

### Finding 7: LangGraph's `interrupt()` + Slack = Native HITL Approval
- **Discovery**: LangGraph's `interrupt(payload)` pauses execution, persists full state indefinitely, and resumes via `Command(resume=value)`. This maps perfectly to Lintel's Slack-based approval flow: pause agent → post approval prompt to thread → wait for user reply → resume.
- **Evidence**: [WEB-04 LG] — LangGraph interrupts docs
- **Implication**: Approval gates are already modeled in Lintel's domain and supported by LangGraph. Implementation is wiring, not design.

## 4. Analysis & Synthesis

### Current State
Lintel has a rich domain model with 50+ event types, 13 commands, 9 protocol interfaces, and a visual workflow editor. The single compiled `feature_to_pr` graph demonstrates the LangGraph pattern works. However, the system is largely unwired — routes don't dispatch commands, nodes are stubs, and there's no trigger scheduler or streaming output.

### Constraints & Opportunities
- **PostgreSQL is already the event store** — adding scheduler coordination via advisory locks is incremental, not architectural
- **LangGraph's checkpoint system shares the same Postgres** — `AsyncPostgresSaver` needs only the existing asyncpg pool
- **`ThreadRef` ties everything to Slack** — Concourse-style scheduled/webhook triggers need an extended identifier (e.g., `run:{pipeline_id}:{run_number}`)
- **The visual editor saves graph definitions** — compiling stored `{ nodes, edges }` into executable `StateGraph` at runtime would give users a visual pipeline editor equivalent to `fly set-pipeline`

### Design Principles
1. **Version-flow model adapted for AI events**: Slack messages, LLM responses, and tool outputs are "versions" flowing through dependency graphs
2. **Step modifiers are essential**: `ensure`/`on_failure`/`try`/`in_parallel` must be first-class in any pipeline format
3. **PostgreSQL as sole coordinator**: No NATS/Kafka for scheduling; event store handles everything
4. **Narrow skill interface**: check/in/out pattern for composable agent capabilities
5. **Streaming is not optional**: SSE with typed events from day one

## 5. Solution Space

### Option A: Concourse-Clone with YAML Pipelines
**Core Idea**: Port Concourse's pipeline YAML format and scheduling algorithm directly, replacing containers with LangGraph agents.

**Approach Overview**:
- Implement a YAML pipeline parser compatible with Concourse's schema
- Port the version-resolution algorithm (individual/group/pinned resolvers)
- Replace Garden containers with LangGraph graph invocations

**Key Trade-offs**:
✅ Pros:
- Proven scheduling semantics, well-documented
- Familiar to CI/CD engineers
- Direct access to Concourse's ecosystem knowledge

❌ Cons:
- YAML cannot express LLM-driven conditional routing [WEB-09 LG]
- No native state management across steps — must bolt on
- Impedance mismatch: AI workflows are non-deterministic; YAML assumes determinism
- Duplicates LangGraph's graph model with a less expressive format

**Complexity**: L
**Best When**: Team is CI/CD-experienced and wants maximum Concourse compatibility

---

### Option B: LangGraph-Native Scheduler with Concourse-Inspired Primitives (Recommended)
**Core Idea**: Keep LangGraph as the pipeline runtime. Adopt Concourse's scheduling patterns (trigger-on-new-version, step modifiers, PostgreSQL coordination) as a scheduling layer that dispatches to LangGraph graphs.

**Approach Overview**:
- Build a `PipelineScheduler` service that watches for trigger events (Slack, webhook, schedule) and dispatches `StartWorkflow` commands
- Use PostgreSQL advisory locks for "one scheduler per tick" coordination
- Compile stored visual graph definitions into `StateGraph` at runtime
- Add step modifier support (`ensure`/`on_failure`/`try`/`in_parallel`) to the graph compiler
- Stream execution via SSE with typed events mapped from LangGraph streaming

**Key Trade-offs**:
✅ Pros:
- Leverages existing LangGraph infrastructure (checkpointing, HITL, streaming) [REPO-04]
- LLM-driven conditional routing is native [WEB-09 LG]
- State management with reducers handles parallel branches [WEB-02 LG]
- Visual editor already saves compatible graph definitions [REPO-13]
- PostgreSQL coordination matches Concourse's proven pattern [WEB-13]

❌ Cons:
- More design work to map Concourse scheduling concepts to LangGraph primitives
- No existing YAML ecosystem compatibility
- Must build trigger scheduler from scratch (Concourse's is battle-tested)

**Complexity**: M-L
**Best When**: Building for AI-first workflows where LLM-driven routing and persistent state are essential

---

### Option C: Minimal Event-Driven Scheduler (Single-Node First)
**Core Idea**: Skip the Concourse scheduling algorithm entirely. Build a simple event-driven scheduler: when a trigger event arrives, dispatch to the appropriate LangGraph graph. Add sophistication later.

**Approach Overview**:
- Wire existing `StartWorkflow` command to `graph.ainvoke()`
- Add a `TriggerHandler` that maps Slack events, webhooks, and cron to `StartWorkflow`
- SSE endpoint tails the event store for live streaming
- No version-resolution, no `passed` constraints, no resource checking

**Key Trade-offs**:
✅ Pros:
- Fastest to implement — wires existing stubs [REPO-14]
- Single-node simplicity; no distributed coordination needed yet
- Unblocks all downstream work (UI streaming, metrics, approval flows)

❌ Cons:
- No pipeline dependency graph (jobs can't depend on upstream job outputs)
- No version-flow model — loses Concourse's most powerful abstraction
- Will need significant rework to add scheduling sophistication later
- No `passed` constraints for multi-stage AI pipelines

**Complexity**: S-M
**Best When**: Need to ship quickly and iterate; single-workflow-at-a-time is acceptable

---

### Option D: Hybrid — Start with Option C, Evolve to Option B
**Core Idea**: Ship the minimal event-driven scheduler (Option C) immediately to unblock streaming and UI work, then incrementally add Concourse-inspired primitives (Option B) as the scheduling needs grow.

**Approach Overview**:
- Phase 1: Wire command bus → LangGraph executor; add SSE streaming; add basic trigger handler
- Phase 2: Add step modifiers to graph compiler; add per-step timing metrics
- Phase 3: Add version-flow model and `passed` constraints for multi-stage pipelines
- Phase 4: Add PostgreSQL advisory lock coordination for eventual multi-node

**Key Trade-offs**:
✅ Pros:
- Unblocks UI/streaming work immediately [REPO-14, REPO-15]
- Each phase delivers standalone value
- Defers complex scheduling until patterns are understood from real usage
- Avoids over-engineering before knowing actual pipeline topology needs

❌ Cons:
- Phase boundaries may blur; risk of accumulating tech debt between phases
- Early users get limited scheduling capabilities
- Architecture may need refactoring as sophistication grows

**Complexity**: S → L (incremental)
**Best When**: Want to ship iteratively with working software at each phase

## 6. Recommendation

**Recommended Approach**: Option D — Hybrid (Start minimal, evolve to Concourse-inspired)

**Why This Option Wins**:
- Unblocks the most critical gaps immediately: wired command dispatch, SSE streaming, and basic trigger handling [REPO-14, REPO-15]
- Each phase is independently valuable and shippable
- Avoids premature complexity — Concourse's scheduling algorithm is powerful but may be over-engineered for Lintel's initial single-node, single-team use case
- Converges on Option B's architecture over time, informed by real usage patterns

**Trade-offs Accepted**:
- Early versions lack pipeline dependency graphs and version-flow
- Multi-stage AI pipelines won't work until Phase 3
- Architecture will evolve, requiring some rework

**Key Risks**:
- Phase 1 stub wiring may be harder than expected if command dispatch patterns aren't clean — Mitigation: existing Protocol interfaces provide clean boundaries [REPO-03]
- SSE streaming may have latency issues with event store polling — Mitigation: NATS JetStream is already a declared dependency for pub/sub [REPO-18]
- `ThreadRef` Slack coupling may block non-Slack triggers — Mitigation: introduce `RunRef` as an alternative identifier in Phase 2

See appendices for detailed risk analysis.

**Confidence**: High
- Strong codebase-Concourse alignment reduces design risk
- LangGraph's production maturity (70+ parallel nodes documented) reduces runtime risk
- PostgreSQL-only coordination is battle-tested by Concourse at scale

## 7. Next Steps

**Decision Required**:
Review the solution options above and select the approach. Option D (Hybrid) is recommended for iterative delivery with working software at each phase.

**Questions to Consider**:
- Is single-workflow-at-a-time acceptable for the first release?
- How soon do multi-stage pipeline dependencies need to work?
- Is the visual editor the primary pipeline authoring experience, or will there also be a code/config path?

**Once Direction is Chosen**:
Proceed to `/plan` for detailed implementation planning. All work should be done in the `concourse-ci-investigation` worktree at `../lintel-concourse-investigation`.

The plan phase will provide:
- Phased implementation steps with complexity ratings
- SSE event type schema definition
- Prometheus metric definitions
- LangGraph graph compiler design
- UI streaming component architecture

---

## APPENDICES

### Appendix A: Codebase Survey — API Layer
**Purpose**: Complete codebase context for plan agent

**Summary**: Lintel has a rich domain model (50+ events, 13 commands, 9 protocols) with a visual workflow editor, but routes are stubs and the single workflow graph is hardcoded.

**Key Findings**:
- Architecture: Event-sourced CQRS with PostgreSQL, Protocol-based infrastructure abstraction
- Patterns: Frozen dataclasses, LangGraph StateGraph with approval gates, in-memory projections
- Gaps: Routes don't dispatch, no SSE streaming, no trigger scheduler, single hardcoded workflow
- Integration: Wire command bus, add SSE endpoint, compile stored visual graphs, add trigger handler

**Contents** ([full details](./research/codebase-survey-api.md)):
- Directory structure and key files
- 5 established patterns with code samples
- 5 integration points
- 7 identified gaps with severity ratings

---

### Appendix B: Concourse CI Architecture
**Purpose**: Complete Concourse scheduling and architecture context

**Summary**: Concourse is a three-primitive system (resources, jobs, tasks) with PostgreSQL-only coordination, a version-resolution scheduling algorithm, and a clean check/in/out resource interface.

**Key Findings**:
- ATC has 4 sub-components; PostgreSQL is the only coordination layer
- Scheduler uses version-matching, not cron; triggers on new resource versions
- check/in/out resource interface: JSON over stdin/stdout, any language
- Single-node deployment fully supported; scales by adding workers

**Contents** ([full details](./research/web-research-concourse-architecture.md)):
- Core architecture (ATC, TSA, workers)
- Pipeline model and step types
- Scheduling algorithm with 3 resolvers
- Resource interface protocol
- Single vs multi-node analysis

---

### Appendix C: Concourse CI UI/UX
**Purpose**: Build visualization and streaming patterns for Lintel's UI

**Summary**: Concourse streams build logs via SSE with richly typed events. Per-step execution duration metrics are an identified gap that Lintel should fill.

**Key Findings**:
- SSE (not WebSockets) for build streaming; typed lifecycle events per step
- Elm SPA + D3 SVG for pipeline DAG visualization
- Prometheus histograms for build duration but NO per-step metrics
- Hybrid: polling for dashboards, SSE for active builds

**Contents** ([full details](./research/web-research-concourse-ui.md)):
- Event stream API with 11 event types
- Build step visualization patterns
- Pipeline graph rendering approach
- Metrics gap analysis
- 5 recommendations for Lintel

---

### Appendix D: LangGraph Pipeline Model
**Purpose**: LangGraph capabilities that replace Concourse's YAML pipelines

**Summary**: LangGraph's StateGraph provides code-first workflow definition with typed state, checkpointing, HITL interrupts, 5 streaming modes, dynamic parallel execution, and integrated observability — all features Concourse YAML cannot express.

**Key Findings**:
- StateGraph with conditional edges enables LLM-driven dynamic routing
- AsyncPostgresSaver shares Lintel's existing Postgres infrastructure
- `interrupt()` + `Command(resume=...)` maps perfectly to Slack approval flows
- 5 streaming modes; `messages` for token streaming, `updates` for progress
- `Send` API for dynamic fan-out; 70+ parallel nodes documented in production

**Contents** ([full details](./research/web-research-langgraph-pipelines.md)):
- StateGraph model and state management
- Checkpointing and time travel
- Human-in-the-loop patterns
- Streaming modes comparison
- Parallel execution and error handling
- LangGraph vs YAML comparison table
