# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lintel is an open-source AI collaboration infrastructure platform. It orchestrates multi-agent workflows triggered from Slack threads, using event sourcing and CQRS patterns. Built with Python 3.12+, FastAPI, LangGraph, and PostgreSQL.

## Workspace Structure

This is a **uv workspace monorepo** with 16 packages under `packages/`:

**Core packages:**

| Package | Name | Dependencies | Description |
|---------|------|-------------|-------------|
| `packages/contracts/` | `lintel-contracts` | (none) | Pure domain contracts: types, commands, events, Protocol interfaces |
| `packages/agents/` | `lintel-agents` | contracts | AI agent runtime (roles: planner, coder, reviewer, pm, designer, summarizer) |
| `packages/workflows/` | `lintel-workflows` | contracts, agents | LangGraph workflow orchestration and graph nodes |
| `packages/app/` | `lintel` | all below | FastAPI API routes, middleware, composition root, domain logic |

**Reusable library packages (each independently installable):**

| Package | Name | Dependencies | Description |
|---------|------|-------------|-------------|
| `packages/event-store/` | `lintel-event-store` | contracts | Append-only event persistence (Postgres + in-memory) |
| `packages/event-bus/` | `lintel-event-bus` | contracts | In-memory pub/sub event bus |
| `packages/projections/` | `lintel-projections` | contracts, event-bus | Read-model projection engine and concrete projections |
| `packages/persistence/` | `lintel-persistence` | contracts | Generic CRUD/dict stores, vault |
| `packages/sandbox/` | `lintel-sandbox` | contracts | Docker-based code execution sandboxes |
| `packages/pii/` | `lintel-pii` | contracts | PII detection/anonymization (presidio) |
| `packages/observability/` | `lintel-observability` | contracts | OpenTelemetry tracing/metrics/logging |
| `packages/models/` | `lintel-models` | contracts | LLM provider routing (litellm) |
| `packages/slack/` | `lintel-slack` | contracts | Slack channel adapter |
| `packages/repos/` | `lintel-repos` | contracts | GitHub repository provider |
| `packages/coordination/` | `lintel-coordination` | (asyncpg only) | Database advisory locks |
| `packages/infrastructure/` | `lintel-infrastructure` | (residual) | MCP tool client only — will be dissolved |

Each package has `src/lintel/<pkg>/` source and colocated `tests/` directory. The `lintel` namespace is shared across packages via implicit namespace packages (no `__init__.py` in `src/lintel/`).

Cross-package integration and e2e tests live at the root `tests/` directory.

## Commands

Uses Make with `uv` for Python dependency management. Run `make help` to list all targets.

```bash
make install            # Install all deps (uv sync --all-extras --all-packages)
make test               # Run all tests (pass ARGS= for extra pytest flags)
make test-affected      # Run tests only for packages changed since BASE_REF
make test-contracts     # Run contracts package tests
make test-agents        # Run agents package tests
make test-workflows     # Run workflows package tests
make test-app           # Run app package tests
make test-event-store   # Run event-store package tests
make test-event-bus     # Run event-bus package tests
make test-persistence   # Run persistence package tests
make test-sandbox       # Run sandbox package tests
make test-pii           # Run PII package tests
make test-observability # Run observability package tests
make test-models        # Run models package tests
make test-slack         # Run slack package tests
make test-repos         # Run repos package tests
make test-coordination  # Run coordination package tests
make test-projections   # Run projections package tests
make test-unit          # Run all package tests (parallelised)
make test-integration   # Run integration tests only
make test-e2e           # Run e2e tests only
make lint               # Ruff check + format check
make typecheck          # mypy strict mode
make format             # Auto-fix formatting and lint
make serve              # Dev server on :8000
make migrate            # Run event store migrations
make all                # lint + typecheck + test + integration + UI build
```

Run a single test: `uv run pytest packages/contracts/tests/test_types.py -v`

Run affected tests only: `make test-affected BASE_REF=origin/main`

**CI rule:** The CI workflow (`.github/workflows/ci.yml`) must always use `make` targets — never run raw `uv run`, `pytest`, `ruff`, or `mypy` commands directly. This keeps CI and local dev in sync via a single source of truth in the Makefile.

## Architecture

**Event-sourced CQRS** with clean architecture boundaries enforced by workspace package dependencies:

- `packages/contracts/` — **Slim kernel only** (EventEnvelope, ThreadRef, ActorType, core protocols). NEVER add new types, events, or commands here — put them in the relevant domain package instead.
- `packages/domain/` — Domain types and events (projects, work items, boards, users, teams, compliance, etc.)
- `packages/agents/` — AI agent definitions and runtime, agent types/protocols/events
- `packages/workflows/` — LangGraph workflow orchestration, workflow/pipeline types/events/commands
- `packages/event-store/` — Append-only event persistence (Postgres + in-memory)
- `packages/event-bus/` — In-memory pub/sub event bus with subscriptions
- `packages/projections/` — Read-model projection engine and concrete projections
- `packages/persistence/` — Generic CRUD/dict stores, vault
- `packages/sandbox/` — Docker-based isolated code execution
- `packages/pii/` — PII detection/anonymization (presidio)
- `packages/observability/` — OpenTelemetry tracing/metrics/logging
- `packages/models/` — LLM provider routing (litellm)
- `packages/slack/` — Slack channel adapter (slack-bolt)
- `packages/repos/` — GitHub repository provider
- `packages/coordination/` — Database advisory locks
- `packages/app/` — FastAPI routes, middleware, dependency injection (composition root)

**Key patterns:**
- `ThreadRef` (workspace_id, channel_id, thread_ts) is the canonical workflow instance identifier
- Commands are frozen dataclasses expressing intent; events record facts
- `EventEnvelope` wraps all events with metadata (correlation_id, causation, timestamps)
- Library packages implement Protocol interfaces from contracts — never import app from library packages
- pytest uses `--import-mode=importlib` — do NOT add `__init__.py` to test directories

**Import rules — where things live:**
- `lintel.contracts.types` — ONLY ThreadRef, ActorType, CorrelationId, EventId
- `lintel.contracts.events` — ONLY EventEnvelope, register_events, deserialize_event, EVENT_TYPE_MAP
- `lintel.contracts.protocols` — ONLY EventHandler, EventBus, CommandDispatcher, EventStore
- `lintel.domain.types` — All domain types (Project, WorkItem, Board, User, Team, Policy, etc.)
- `lintel.domain.events` — All domain events (ProjectCreated, WorkItemUpdated, etc.)
- `lintel.workflows.types` — Workflow types (PipelineRun, Stage, StageStatus, etc.)
- `lintel.workflows.events` — Workflow events (PipelineRunStarted, WorkflowStarted, etc.)
- `lintel.workflows.commands` — Workflow commands (StartWorkflow)
- `lintel.<pkg>.types/events/protocols` — Package-specific contracts (sandbox, models, pii, repos, agents, etc.)
- **NEVER add new types or events to `lintel-contracts`** — it is a frozen kernel. New domain items go in `lintel-domain`, workflow items in `lintel-workflows`, or the relevant infrastructure package.

## Dependency Injection

Uses `dependency-injector` (v4.x) with a `DeclarativeContainer` for the FastAPI app.

**Container:** `packages/app/src/lintel/api/container.py` — `AppContainer` declares all stores, services, and projections as `providers.Object` holders. The lifespan in `app.py` constructs instances and overrides providers via `wire_container()`.

**Route handler pattern** — all route handlers use `@inject` + `Depends(Provide[...])`:
```python
from dependency_injector.wiring import Provide, inject
from lintel.api.container import AppContainer

@router.get("/items")
@inject
async def list_items(
    store: ItemStore = Depends(Provide[AppContainer.item_store]),  # noqa: B008
) -> list[dict[str, Any]]:
    ...
```
- `@inject` must be the decorator directly above the function (after `@router.X()`)
- Use `= Depends(Provide[AppContainer.X])` default-value syntax with `# noqa: B008`
- Old `get_X_store(request)` getter functions are kept for backward compatibility

**Testing with DI:** Override providers in tests:
```python
container.some_store.override(providers.Object(fake_store))
```

## Key Service Classes

Domain logic is encapsulated in typed classes, not standalone functions:

| Class | Location | Purpose |
|-------|----------|---------|
| `StageTracker` | `workflows/nodes/_stage_tracking.py` | Pipeline stage lifecycle (mark_running, append_log, mark_completed) |
| `ChatService` | `app/routes/chat.py` | Chat routing, project resolution, workflow dispatch |
| `SandboxToolDispatcher` | `agents/sandbox_tools.py` | Routes tool calls to SandboxManager methods |
| `BranchNaming` | `workflows/nodes/_branch_naming.py` | Branch name generation conventions |
| `GitOperations` | `workflows/nodes/_git_helpers.py` | Sandbox git operations (rebase) |
| `WorkflowErrorHandler` | `workflows/nodes/_error_handling.py` | Standardised node error handling |
| `AuditEmitter` | `workflows/nodes/_event_helpers.py` | Audit entry recording |
| `NotificationService` | `workflows/nodes/_notifications.py` | Phase change notifications |
| `ReportVersionService` | `app/routes/pipelines.py` | Pipeline report versioning |

**Workflow node pattern** — nodes instantiate `StageTracker` at the top:
```python
async def research_codebase(state, config):
    from lintel.workflows.nodes._stage_tracking import StageTracker
    tracker = StageTracker(config, state)
    await tracker.mark_running("research")
    await tracker.append_log("research", "Researching...")
    # ... do work ...
    await tracker.mark_completed("research", outputs={...})
```

## Development Environment (tmux)

The dev environment runs via `make dev` (or `scripts/dev-tmux.sh`), which creates a tmux session `lintel` with 3 windows:

- **prompts** — 3 horizontal panes, each running a `claude` instance
- **services** — 3 panes: `make serve-db` (API + DB), `make ui-dev` (Vite), `make ollama-serve`
- **editor** — nvim + 2 terminal panes (horizontal split below nvim, split vertically)

**Debugging with dev services:** When debugging runtime issues, check the services window panes for logs/errors. The API server, UI dev server, and Ollama are already running — use `tmux capture-pane` to read their output rather than starting new processes.

**Running commands in tmux:** When the user asks to run a command in a tmux pane, use `tmux send-keys -t lintel:<window>.<pane> '<command>' Enter` to send it, then `tmux capture-pane -t lintel:<window>.<pane> -p | tail -N` to read output. This gives the user visibility in their terminal. Prefer this over running commands directly when the user requests it.

**Running tests:** Run tests directly using the Bash tool when asked. Use `make test-unit`, `make test-affected`, `make all`, or targeted `uv run pytest` commands as needed.

## Live Testing with Dev Services

When doing development work, use the running dev services for integration testing rather than relying solely on unit tests:

- **Make HTTP requests** to the API at `http://localhost:8000/api/v1/` using `rtk proxy curl` (bypasses token filtering for raw JSON)
- **Monitor server logs** via `tmux capture-pane -t lintel:1.0 -p | tail -N`
- **Check pipeline status** at `/api/v1/pipelines/{run_id}` after triggering workflows
- **Start a chat** by POSTing to `/api/v1/chat/conversations` with a `message`, `project_id`, and `model_id`
- **Follow conversation** at `/api/v1/chat/conversations/{conversation_id}`
- **MCP server** is available at `/mcp` for tool/resource interaction

This gives visibility into the full request lifecycle: HTTP status, chat routing, workflow dispatch, stage progression, and server-side errors.

## Code Style

- Ruff with strict rule set (E, F, W, I, N, UP, ANN, B, A, SIM, TCH, RUF), line length 100
- mypy strict mode with pydantic plugin
- pytest-asyncio with `asyncio_mode = "auto"` — no need for `@pytest.mark.asyncio`
- pytest-testmon available for local dev change detection (`uv run pytest --testmon`)
- Integration tests use testcontainers (postgres, nats)

## Tech Stack & Documentation

- Tech stack manifests live in `docs/tech-stack/*.yaml` — see `.claude/docs/tech-stack-schema.md` for the schema
- Context7 MCP server is configured in `.mcp.json` for fetching framework documentation
- Use `mcp__context7__resolve-library-id` to find a library's Context7 ID
- Use `mcp__context7__get-library-docs` to fetch docs by topic
- **Types reference:** `docs/types-reference.md` — all dataclasses, enums, protocols, request/response models with file paths and line numbers. Run `/update-types` to refresh after adding/moving types.
- **Entities:** `docs/requirements/entities.md` — all domain entities, enums, and planned modifications with line numbers. When the user says "entities" or "update entities", this is the file.
- **Agents:** `docs/requirements/agents.md` — agent roles, categories, runtime architecture, sandbox tools, and workflow integration.
- Related docs: `docs/architecture.md`, `docs/events.md`, `docs/local-dev.md`

## Feature Implementation Rules

- **MCP backend required:** Every UI feature must have a corresponding MCP server tool/resource implemented in the backend (`packages/infrastructure/src/lintel/infrastructure/mcp/`). Do not ship frontend-only features — the MCP layer is the integration surface and must be kept in sync.
- **Tests required:** Every feature must include tests colocated with the package:
  - Unit tests for new domain logic in `packages/<pkg>/tests/`
  - Integration tests when the feature touches infrastructure in `tests/integration/`
- **Test the package you changed, not everything:** During development, run per-package tests for fast feedback:
  - `make test-contracts`, `make test-agents`, `make test-workflows`, `make test-app`, `make test-event-store`, `make test-event-bus`, `make test-persistence`, `make test-pii`, `make test-models`, etc.
  - Or use `make test-affected BASE_REF=main` to auto-detect affected packages
  - Only run `make test-unit` or `make all` as a final check before committing
- **Do NOT add `__init__.py` to test directories** — pytest uses `--import-mode=importlib` and `__init__.py` in tests causes namespace collisions across packages.
