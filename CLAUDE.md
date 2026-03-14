# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lintel is an open-source AI collaboration infrastructure platform. It orchestrates multi-agent workflows triggered from Slack threads, using event sourcing and CQRS patterns. Built with Python 3.12+, FastAPI, LangGraph, and PostgreSQL.

## Workspace Structure

This is a **uv workspace monorepo** with 6 packages under `packages/`:

| Package | Name | Dependencies | Description |
|---------|------|-------------|-------------|
| `packages/contracts/` | `lintel-contracts` | (none) | Pure domain contracts: types, commands, events, Protocol interfaces |
| `packages/domain/` | `lintel-domain` | contracts | Domain logic, skills, chat routing, pipeline scheduling |
| `packages/agents/` | `lintel-agents` | contracts | AI agent runtime (roles: planner, coder, reviewer, pm, designer, summarizer) |
| `packages/infrastructure/` | `lintel-infrastructure` | contracts, domain | Concrete Protocol implementations (postgres, slack, presidio, sandbox, vault) |
| `packages/workflows/` | `lintel-workflows` | contracts, agents | LangGraph workflow orchestration and graph nodes |
| `packages/app/` | `lintel` | all above | FastAPI API routes, middleware, composition root |

Each package has `src/lintel/<pkg>/` source and colocated `tests/` directory. The `lintel` namespace is shared across packages via implicit namespace packages (no `__init__.py` in `src/lintel/`).

Cross-package integration and e2e tests live at the root `tests/` directory.

## Commands

Uses Make with `uv` for Python dependency management. Run `make help` to list all targets.

```bash
make install            # Install all deps (uv sync --all-extras --all-packages)
make test               # Run all tests (pass ARGS= for extra pytest flags)
make test-affected      # Run tests only for packages changed since BASE_REF
make test-contracts     # Run contracts package tests
make test-domain        # Run domain package tests
make test-agents        # Run agents package tests
make test-infrastructure # Run infrastructure package tests
make test-workflows     # Run workflows package tests
make test-app           # Run app package tests
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

- `packages/contracts/` — Pure domain contracts (no I/O). Types, commands, events, and Protocol interfaces that define service boundaries. Domain code depends only on these abstractions.
- `packages/domain/` — Domain logic, chat routing, pipeline scheduling, skills
- `packages/agents/` — AI agent definitions and runtime
- `packages/workflows/` — LangGraph workflow orchestration with `workflows/nodes/` for graph nodes
- `packages/infrastructure/` — Concrete implementations of Protocol interfaces:
  - `channels/slack/` — Slack integration (slack-bolt)
  - `event_store/` — PostgreSQL event store (asyncpg/SQLAlchemy async)
  - `models/` — LLM provider abstraction (litellm)
  - `pii/` — PII detection/anonymization (presidio)
  - `sandbox/` — Isolated code execution environments
  - `vault/` — Secret management (cryptography)
  - `repos/` — Repository access
  - `observability/` — OpenTelemetry tracing
- `packages/app/` — FastAPI routes, middleware, dependency injection (composition root)

**Key patterns:**
- `ThreadRef` (workspace_id, channel_id, thread_ts) is the canonical workflow instance identifier
- Commands are frozen dataclasses expressing intent; events record facts
- `EventEnvelope` wraps all events with metadata (correlation_id, causation, timestamps)
- Infrastructure implements Protocol interfaces — never import infrastructure from domain/contracts
- pytest uses `--import-mode=importlib` — do NOT add `__init__.py` to test directories

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
  - `make test-contracts`, `make test-domain`, `make test-agents`, `make test-infrastructure`, `make test-workflows`, `make test-app`
  - Or use `make test-affected BASE_REF=main` to auto-detect affected packages
  - Only run `make test-unit` or `make all` as a final check before committing
- **Do NOT add `__init__.py` to test directories** — pytest uses `--import-mode=importlib` and `__init__.py` in tests causes namespace collisions across packages.
