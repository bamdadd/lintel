# REQ-021: Per-Step Model Assignment Per Project

**Status:** Draft
**Priority:** High
**Created:** 2026-03-09
**Related:** REQ-020 (Generalised Workflow Stages)

---

## Problem

Projects have a single `model_id` / `ai_provider_id` used for all workflow steps. Different steps have fundamentally different needs — research benefits from large-context models, coding from specialised code models, and planning from reasoning models. Users want to assign a specific model to each workflow step per project, with fallback to the project default.

**Example:**
| | Project: lintel | Project: mobile-app |
|---|---|---|
| research | qwen-2.5-72b (Ollama) | claude-3-5-sonnet |
| plan | llama-3.3-70b (Ollama) | llama-3.3-70b |
| implement | claude-sonnet-4 | qwen-coder-32b |
| review | claude-haiku-4 | claude-haiku-4 |
| test | *(project default)* | *(project default)* |

---

## Existing Infrastructure

The codebase already has the building blocks:

- **`ModelAssignment`** (`contracts/types.py:183`) — binds a model to a context with `context: ModelAssignmentContext` supporting `"workflow_step"` context type and `context_id` for the specific step
- **`GET /model-assignments`** — lists assignments with `context` and `context_id` filters
- **`POST /models/{model_id}/assignments`** — creates assignments
- **Models + Providers API** — full CRUD for models and providers with discovery (Ollama, Bedrock)
- **Project `model_id`** — stored as extra field on `ProjectData`

**What's missing:** A project-scoped layer that ties `(project_id, workflow_step, model_id)` together, a UI for managing it, and executor integration to resolve the right model at runtime.

---

## Requirements

### R1 — Data Model: Project Step Model Override

- **R1.1** New type `ProjectStepModelOverride`:
  ```python
  @dataclass(frozen=True)
  class ProjectStepModelOverride:
      project_id: str
      node_type: str          # e.g. "research", "implement", "review"
      model_id: str           # FK to Model
      created_at: str = ""
      updated_at: str = ""
  ```
- **R1.2** Stored in a dedicated store (in-memory + Postgres) keyed by `(project_id, node_type)`. One override per step per project.
- **R1.3** Deletion of an override reverts that step to the project default — no tombstone, just absence.

### R2 — API

- **R2.1** `GET /api/v1/projects/{project_id}/step-models` — Returns all step model overrides for a project, merged with step metadata from the node registry (step label, current model name, whether it's an override or default).
  ```json
  {
    "project_default_model": { "model_id": "m-1", "name": "gpt-4o-mini", "provider": "openai" },
    "steps": [
      { "node_type": "research", "label": "Research", "model_id": "m-3", "model_name": "qwen-2.5-72b", "provider": "ollama", "is_override": true },
      { "node_type": "plan", "label": "Plan", "model_id": null, "model_name": "gpt-4o-mini", "provider": "openai", "is_override": false },
      { "node_type": "implement", "label": "Implement", "model_id": "m-5", "model_name": "claude-sonnet-4", "provider": "anthropic", "is_override": true },
      ...
    ]
  }
  ```
- **R2.2** `PUT /api/v1/projects/{project_id}/step-models/{node_type}` — Set or update the model for a step. Body: `{ "model_id": "m-5" }`.
- **R2.3** `DELETE /api/v1/projects/{project_id}/step-models/{node_type}` — Remove override, revert to project default.
- **R2.4** `PUT /api/v1/projects/{project_id}/step-models` — Bulk update all overrides in one call. Body: `{ "overrides": { "research": "m-3", "implement": "m-5" } }`. Steps not listed are left unchanged.

### R3 — Model Resolution at Execution Time

- **R3.1** Resolution chain: **step override** → **project default model** → **global default model**.
- **R3.2** `ModelResolver` protocol:
  ```python
  class ModelResolver(Protocol):
      async def resolve(self, project_id: str, node_type: str) -> Model: ...
  ```
- **R3.3** The resolver is injected into `WorkflowExecutor` and passed to nodes via `RunnableConfig["configurable"]["model_resolver"]`. Nodes call `resolver.resolve(project_id, node_type)` to get their model.
- **R3.4** If resolution fails at all levels (no override, no project default, no global default), the executor marks the stage as FAILED with a clear error message.

### R4 — UI: Step Model Configuration Table

Based on UX research, the recommended pattern is an **inline table with per-row dropdown** on the project detail page.

#### R4.1 — Layout

A new "Step Models" section/tab on the Project Detail page:

```
┌──────────────────────────────────────────────────────────────┐
│  Step Models                                                  │
│  Configure which AI model to use for each workflow step.      │
│  Steps without an override use the project default.           │
│                                                               │
│  Project default: gpt-4o-mini (OpenAI)  [Change]             │
│                                                               │
│  ┌──────────────┬──────────────────────────────────┬────────┐│
│  │ Step         │ Model                            │        ││
│  ├──────────────┼──────────────────────────────────┼────────┤│
│  │ Research     │ qwen-2.5-72b                [↺]  │        ││
│  │ Plan         │ gpt-4o-mini  (default)           │        ││
│  │ Implement    │ claude-sonnet-4             [↺]  │        ││
│  │ Test         │ gpt-4o-mini  (default)           │        ││
│  │ Review       │ claude-haiku-4              [↺]  │        ││
│  └──────────────┴──────────────────────────────────┴────────┘│
└──────────────────────────────────────────────────────────────┘
```

#### R4.2 — Override vs Default Visual Language

| State | Appearance |
|-------|-----------|
| **Using default** | Model name in muted/dimmed text + `(default)` label. No reset icon. Dropdown shows project default pre-selected. |
| **Custom override** | Model name in full-colour text. Small reset icon `[↺]` to the right — click reverts to default. Subtle highlight on the row (light background tint). |
| **No model available** | Red border on dropdown, inline warning: "No model configured" |

#### R4.3 — Model Selector Dropdown

When the user clicks a model cell, a popover/dropdown opens with:

```
┌─────────────────────────────────────────┐
│ Search models...                        │
├─────────────────────────────────────────┤
│ ── Use project default ──               │
│   gpt-4o-mini (OpenAI)                  │
├─────────────────────────────────────────┤
│ ── Anthropic ──                         │
│   claude-sonnet-4         Code ★        │
│   claude-haiku-4          Fast ⚡        │
│   claude-opus-4           Best ◆        │
├─────────────────────────────────────────┤
│ ── Ollama (Local) ──                    │
│   qwen-2.5-72b            Large ctx     │
│   llama-3.3-70b           Reasoning     │
│   qwen-coder-32b          Code ★        │
├─────────────────────────────────────────┤
│ ── OpenAI ──                            │
│   gpt-4o                  Fast ★        │
│   gpt-4o-mini             Cheap ⚡       │
└─────────────────────────────────────────┘
```

- Grouped by provider
- Search/filter at top (essential once > 8 models)
- "Use project default" as first option, visually separated
- Capability badges from `model.capabilities` tuple (e.g. `coding` → "Code ★")
- Current selection highlighted with checkmark

#### R4.4 — Interactions

- Selecting a model immediately saves (optimistic update via `PUT /step-models/{node_type}`)
- Clicking `[↺]` reset icon calls `DELETE /step-models/{node_type}` and reverts to default
- Steps list is derived from the project's workflow definition — if the workflow has 7 steps, the table shows 7 rows
- If the project has no workflow definition assigned, show an empty state: "Assign a workflow to this project to configure step models"

---

## Phased Delivery

### Phase 1 — Backend + Basic UI
- `ProjectStepModelOverride` data model and store
- API endpoints (R2.1–R2.4)
- `ModelResolver` with 3-level fallback chain
- Wire resolver into executor
- Basic UI table with Mantine `Select` dropdowns (no grouped popover yet)

### Phase 2 — Polished UI
- Grouped model selector popover with search and capability badges
- Override vs default visual language (muted text, reset icons, row highlighting)
- Optimistic updates with error rollback
- "Project default" banner with change link

### Phase 3 — Advanced
- Per-step temperature / max_tokens overrides (expand table or use accordion rows)
- Model usage analytics per step per project (which model was used, token counts)
- Recommendation hints: "This step used 45k tokens — consider a large-context model"

---

## Out of Scope

- Per-step API key overrides (use provider-level keys)
- A/B testing between models on the same step
- Cost budgeting per step

---

## Success Criteria

1. On the project detail page, users see all workflow steps with their assigned model in an inline table.
2. Clicking a model cell opens a grouped, searchable dropdown. Selecting a model saves immediately.
3. Steps without an override show the project default in muted text with `(default)` label.
4. Overridden steps show a reset icon that reverts to default in one click.
5. The workflow executor uses the correct model per step per project at runtime, with 3-level fallback.
6. The feature works with any workflow definition — adding/removing steps from a workflow automatically updates the table.
