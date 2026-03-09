# REQ-022: Pipeline Visualisation — Triggers, Artifacts & Data Flow

**Status:** Draft
**Priority:** High
**Created:** 2026-03-09
**Related:** REQ-020 (Generalised Workflow Stages), REQ-021 (Per-Step Model Assignment)

---

## Problem

The current pipeline DAG view (`PipelineDAG.tsx`) shows stages as nodes with status colours and animated edges for running stages. But it doesn't answer three critical questions users have when looking at a pipeline:

1. **What started this?** — Trigger type (chat message, git push, webhook, schedule, manual) is shown as text in the list page but not in the pipeline graph itself.
2. **What flowed between steps?** — Artifacts (diffs, research reports, plans, test results, images) are buried in stage detail panels. There's no visual indication of _what data_ moved from one step to the next.
3. **What did each step produce?** — Stage outputs are raw JSON. Rich outputs (markdown reports, structured plans, code diffs, images) deserve inline preview, not a code block.

## Goal

Redesign the pipeline visualisation to make triggers, artifacts, and data flow first-class visual elements — inspired by Concourse CI's resource-centric graph, Dagster's inline artifact metadata, and n8n's trigger nodes and edge data previews.

---

## Design Inspiration

### Concourse CI (primary inspiration)
- **Resources as first-class nodes** between jobs — data artifacts are visible in the graph, not hidden in panels
- **Solid line = auto-trigger** (e.g. git push triggers build), **dotted line = consumed but not triggered** — answers "why did this run?" at a glance
- **Left-to-right flow** — trigger resources on the far left, terminal outputs on the far right

### Dagster Asset Graph
- **Inline metadata on nodes** — clicking a node shows rendered markdown, images, row counts, file sizes
- **Freshness/status colours** — immediately shows what's stale, what's current
- **Collapsible groups** for scale — essential above ~30 visible nodes

### n8n
- **Explicit trigger nodes** — visually distinct (different colour, lightning bolt icon), always leftmost
- **Item count badges on edges** — "3 items flowed here" without opening a panel
- **Output pins** — multiple outputs from one node (success/error branches) as separate connectors

---

## Architecture

### Node Types in the Graph

```
┌─────────┐     ┌──────────────┐     ┌────────────────┐     ┌──────────────┐     ┌──────────┐
│ TRIGGER  │────▶│  STAGE NODE  │────▶│ ARTIFACT NODE  │────▶│  STAGE NODE  │────▶│  OUTPUT  │
│ (chat)   │     │  (research)  │     │ (report.md)    │     │  (implement) │     │ (PR url) │
└─────────┘     └──────────────┘     └────────────────┘     └──────────────┘     └──────────┘
```

| Node Type | Shape | Colour | Icon | Description |
|-----------|-------|--------|------|-------------|
| **Trigger** | Rounded pill, left edge | Amber/orange | Per type: 💬 chat, 🔀 git push, 🌐 webhook, ⏰ schedule, 👤 manual | What started this pipeline |
| **Stage** | Rectangle with status fill | Green/red/blue/grey/yellow per status | Per stage type from registry | Processing step |
| **Artifact** | Smaller rectangle, dashed border | Purple tint | Per artifact type: 📄 document, 📊 diff, 🧪 test results, 🖼 image, 📋 plan | Data produced by a stage, consumed by the next |
| **Output** | Rounded pill, right edge | Teal | Per output type: 🔗 PR url, ✅ verdict, 📦 package | Terminal pipeline outputs |

### Edge Types

| Edge Type | Line Style | Meaning |
|-----------|-----------|---------|
| **Triggered** | Solid, animated when running | This connection triggered the downstream node (auto-trigger) |
| **Data flow** | Dotted/dashed | Data passes through but doesn't trigger execution |
| **Error branch** | Red dashed | Error/failure path |

### Edge Badges

Small pills on edges showing what flowed through:
- `"3 files"` on a diff artifact edge
- `"2.1k tokens"` on a research output edge
- `"14 tests passed"` on a test result edge

---

## Requirements

### R1 — Trigger Nodes

- **R1.1** Pipeline graph starts with a trigger node on the far left. The trigger node shows: trigger type icon, trigger label (e.g. "Slack: #engineering"), and timestamp.
- **R1.2** Trigger type is derived from `PipelineRun.trigger_type` and `trigger_id`. Mapping:
  | `trigger_type` | Icon | Label source |
  |----------------|------|-------------|
  | `chat:{conversation_id}` | 💬 | Conversation title or "Chat" |
  | `slack_message` | 💬 | Channel name |
  | `webhook` | 🌐 | Webhook name |
  | `schedule` | ⏰ | Schedule expression |
  | `pr_event` | 🔀 | PR title or branch name |
  | `manual` | 👤 | Actor name |
- **R1.3** Clicking the trigger node navigates to the source (chat conversation, PR, webhook config).

### R2 — Artifact Nodes

- **R2.1** Artifacts appear as small nodes between the stages that produce and consume them. They are not separate from the graph — they sit on the edges.
- **R2.2** Artifact nodes are derived from stage `outputs` at runtime. The system maps known output keys to artifact types:
  | Output key | Artifact type | Icon | Preview |
  |-----------|--------------|------|---------|
  | `research_context` / `research_report` | Document | 📄 | First 2 lines of markdown |
  | `plan` | Plan | 📋 | Task count + complexity summary |
  | `diff` / `git_diff` | Diff | 📊 | Files changed count |
  | `test_verdict` / `test_results` | Test results | 🧪 | Pass/fail counts |
  | `pr_url` | PR link | 🔗 | PR number |
  | `sandbox_id` | Sandbox | 🖥 | Sandbox status |
  | Image/screenshot paths | Image | 🖼 | Thumbnail |
- **R2.3** Artifact nodes show a compact preview (one line of text or a badge). Clicking opens a popover or side panel with the full content:
  - **Documents:** Rendered markdown
  - **Diffs:** Syntax-highlighted diff viewer
  - **Plans:** PlanView timeline component (already exists)
  - **Test results:** Pass/fail breakdown table
  - **Images:** Full-size image with zoom
- **R2.4** Artifacts that are not consumed by any downstream stage appear as terminal output nodes on the right edge of the graph.

### R3 — Generalised Stage I/O Declaration

- **R3.1** Each `NodeDescriptor` (from REQ-020 registry) declares its `output_keys` with type metadata:
  ```python
  @dataclass(frozen=True)
  class OutputDeclaration:
      key: str                    # state key name
      artifact_type: ArtifactType # document, diff, test_results, plan, image, link, data
      label: str                  # human-readable: "Research Report"
      preview_strategy: str       # "first_lines", "count", "badge", "thumbnail", "none"
  ```
- **R3.2** The graph compiler uses `output_keys` from upstream and `input_keys` from downstream to determine which artifact nodes to place on each edge.
- **R3.3** At runtime, the executor populates artifact nodes with actual data as stages complete. Artifact nodes transition from "pending" (grey) to "available" (purple) when their producing stage succeeds.

### R4 — Output Nodes (Terminal Artifacts)

- **R4.1** Pipeline terminal outputs (PR url, final verdict, merged branch) appear as distinct nodes on the far right of the graph.
- **R4.2** Output nodes are clickable — PR urls open in a new tab, verdicts show summary, artifacts open the detail viewer.
- **R4.3** The pipeline detail page shows a summary bar above the graph: `Trigger: Chat #eng → 5 stages → Output: PR #42 merged` with quick links.

### R5 — Edge Visualisation

- **R5.1** Edges between stages use the Concourse solid/dotted convention:
  - **Solid animated line:** Active data flow (stage is running or was triggered by this connection)
  - **Dotted line:** Data available but not a trigger relationship
  - **Red dashed line:** Error/failure path
- **R5.2** Edge badges show compact metadata about what flowed through: item count, token usage, file count, or a type label.
- **R5.3** Hovering an edge highlights the full path from trigger → output that passes through it (Concourse trace pattern).

### R6 — Real-Time Updates

- **R6.1** Artifact nodes appear in real-time as stages complete, using the existing SSE pipeline (`usePipelineSSE`).
- **R6.2** Stage completion SSE events include `outputs` summary so the UI can render artifact nodes without a separate API call.
- **R6.3** Running stages pulse/animate. Completed artifact nodes fade in with a brief transition.

### R7 — Pipeline Graph Layout

- **R7.1** Left-to-right flow: Trigger → Stages (with artifacts between) → Outputs.
- **R7.2** Approval gates render as diamond-shaped nodes (already exist as `approvalGate` type) with status: waiting (yellow pulse), approved (green), rejected (red).
- **R7.3** Parallel branches (future, from REQ-020 Phase 4) render as vertical forks that rejoin.
- **R7.4** For pipelines with > 15 visible nodes, support collapsing groups of consecutive stages into a summary node showing stage count and overall status.

---

## UI Wireframe

### Pipeline Graph (expanded)

```
 ┌──────────┐    ┌───────────┐   ┄ report ┄   ┌──────────┐   ┄ plan ┄   ◇ approve ◇
 │ 💬 Chat  │───▶│ Research  │───(📄 2.1k)───▶│  Plan    │───(📋 5T)──▶◇  spec   ◇
 │ #eng-ai  │    │  ✅ 12s   │                 │  ✅ 8s   │             │  ✅ auto │
 └──────────┘    └───────────┘                 └──────────┘             └────┬─────┘
                                                                             │
    ┌────────────────────────────────────────────────────────────────────────┘
    │
    ▼
 ┌───────────┐   ┄ diff ┄    ┌──────────┐   ┄ results ┄   ┌──────────┐    ┌──────────┐
 │ Implement │───(📊 3 files)─▶│  Test    │───(🧪 14/14)──▶│  Review  │───▶│ 🔗 PR#42│
 │  ✅ 45s   │                │  ✅ 20s  │                 │  ✅ 15s  │    │  merged  │
 └───────────┘                └──────────┘                 └──────────┘    └──────────┘
```

### Stage Detail Panel (when stage selected)

```
┌─────────────────────────────────────────────────┐
│ Research                              ✅ 12.3s  │
│                                                  │
│ Model: qwen-2.5-72b (Ollama)    Tokens: 2,140   │
│                                                  │
│ ┌─ Outputs ─────────────────────────────────────┐│
│ │ 📄 Research Report                    [View]  ││
│ │   Architecture overview, 3 key files found... ││
│ │                                               ││
│ │ 📊 Codebase Map                       [View]  ││
│ │   src/lintel/ — 42 files, 8.2k LOC           ││
│ └───────────────────────────────────────────────┘│
│                                                  │
│ ┌─ Logs ────────────────────────────────────────┐│
│ │ > Scanning repository structure...            ││
│ │ > Found 3 relevant files for feature X        ││
│ │ > Generating research report...               ││
│ └───────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
```

---

## Phased Delivery

### Phase 1 — Trigger & Output Nodes
- Add trigger node to `PipelineDAG.tsx` (new ReactFlow node type)
- Add output nodes for terminal artifacts (PR url, verdict)
- Summary bar above graph
- Trigger click → navigate to source

### Phase 2 — Artifact Nodes on Edges
- `OutputDeclaration` on `NodeDescriptor` (ties into REQ-020 registry)
- Artifact nodes between stages derived from stage outputs
- Compact preview on artifact nodes
- Click → popover with rendered content (markdown, diff viewer, plan view)

### Phase 3 — Edge Visualisation & Real-Time
- Solid/dotted/red edge styles
- Edge badges (item counts, tokens)
- Hover trace (highlight full path)
- Real-time artifact node appearance via SSE

### Phase 4 — Rich Artifact Viewers
- Inline diff viewer (syntax-highlighted)
- Image preview with zoom
- Test results breakdown table
- Collapsible groups for large pipelines

---

## Backend Changes Required

### New Types
```python
class ArtifactType(str, Enum):
    DOCUMENT = "document"
    DIFF = "diff"
    PLAN = "plan"
    TEST_RESULTS = "test_results"
    IMAGE = "image"
    LINK = "link"
    DATA = "data"

@dataclass(frozen=True)
class OutputDeclaration:
    key: str
    artifact_type: ArtifactType
    label: str
    preview_strategy: str  # first_lines, count, badge, thumbnail, none
```

### API Changes
- `GET /api/v1/pipelines/{run_id}` response enriched with:
  - `trigger_display: { type, icon, label, link }` — resolved trigger metadata
  - Per-stage `artifact_summaries: [{ key, type, label, preview }]` — compact artifact previews
- `GET /api/v1/stage-types` response enriched with `output_declarations` per node type
- SSE `stage_update` events include `artifact_summaries` when stage completes

### Trigger Resolution
- New `TriggerResolver` that maps `(trigger_type, trigger_id)` → display metadata (icon, label, navigation link)
- Injected into the pipelines API route

---

## Out of Scope

- Artifact diffing between pipeline runs (comparing outputs across runs)
- Artifact storage/versioning (artifacts are already stored via `CodeArtifact` — this REQ is about visualisation only)
- Drag-and-drop pipeline editing in this view (that's REQ-020's workflow editor)
- Pipeline-level metrics/analytics dashboard

---

## Success Criteria

1. Opening a pipeline shows the trigger on the left (with type icon and label), stages in the middle, and terminal outputs on the right.
2. Artifacts appear as small nodes between stages, showing a one-line preview. Clicking opens the full content.
3. Users can trace data flow visually: "the research report produced by Research was consumed by Plan".
4. Solid vs dotted edges communicate trigger relationships without needing a legend.
5. All node types update in real-time as the pipeline executes — artifact nodes appear when stages complete.
6. The graph works with any workflow definition (generalised via REQ-020), not just the `feature_to_pr` pipeline.
