# Getting Started

This guide walks you through cloning Lintel, starting the development server, creating a project, and triggering your first workflow.

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager
- **Docker** — for sandbox execution and Postgres (via testcontainers)
- **PostgreSQL 16** — for event store and persistence (or use the Docker-based dev setup)

## Clone and install

```bash
git clone https://github.com/lintel-ai/lintel.git
cd lintel
make install
```

`make install` runs `uv sync --all-extras --all-packages`, which installs all workspace packages and development dependencies in a single virtual environment.

## Start the development server

```bash
make serve
```

This starts the FastAPI server on `http://localhost:8000`. The API is available at `/api/v1/`.

!!! tip "Full dev environment"
    For the full development setup with tmux (API + UI + database), run `make dev` instead.
    This creates a tmux session with multiple panes for the API server, Vite UI dev server, and terminals.

## Verify the server is running

```bash
curl http://localhost:8000/api/v1/health
```

You should get a `200 OK` response.

## Create a project

Projects represent ongoing products. Create one via the API:

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-first-project",
    "description": "A test project for getting started",
    "repo_url": "https://github.com/your-org/your-repo"
  }'
```

Note the `id` in the response — you'll need it to trigger a workflow.

## Create a work item

Work items drive the delivery lifecycle. Create one on your project's board:

```bash
curl -X POST http://localhost:8000/api/v1/work-items \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Add user greeting endpoint",
    "description": "Create a GET /hello endpoint that returns a greeting",
    "project_id": "<PROJECT_ID>",
    "kind": "feature"
  }'
```

## Trigger a workflow

Workflows are triggered from the board. Move a work item to the "in progress" state, or use the pipeline API directly:

```bash
curl -X POST http://localhost:8000/api/v1/pipelines \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "<PROJECT_ID>",
    "work_item_id": "<WORK_ITEM_ID>",
    "workflow_type": "feature_to_pr"
  }'
```

This starts the feature-to-PR workflow, which progresses through these stages:

1. **Ingest** — parse the work item description
2. **Route** — classify intent (feature, bug, refactor)
3. **Setup workspace** — provision a sandbox and clone the repo
4. **Research** — analyse the codebase for relevant context
5. **Plan** — generate an implementation plan
6. **Implement** — write code in the sandbox
7. **Review** — automated code review with revision loop
8. **Close** — finalise the pipeline run

## Monitor pipeline progress

Watch the pipeline via SSE (server-sent events):

```bash
curl -N http://localhost:8000/api/v1/pipelines/<RUN_ID>/events
```

Or poll the pipeline status:

```bash
curl http://localhost:8000/api/v1/pipelines/<RUN_ID>
```

## Next steps

- Read the [Architecture](architecture.md) overview to understand the package layers
- Explore the [Package Catalogue](packages.md) to see all workspace packages
- Learn about [Workflow Authoring](workflow-authoring.md) to understand and extend pipelines
