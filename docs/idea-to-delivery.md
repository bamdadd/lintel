# Lintel: From Idea to Delivery

A step-by-step guide to taking an idea from concept to deployed code using Lintel's AI collaboration platform.

All API calls use `http://localhost:8000/api/v1` as the base URL.

---

## Overview

The full lifecycle:

1. **Setup** — Configure AI provider, credentials, and workspace
2. **Create project** — Register repositories, create a project, set up a board
3. **Describe your idea** — Use chat to decompose an idea into work items
4. **Implement** — AI agents pick up work items and produce PRs
5. **Review & land** — Review PRs, iterate, merge to main
6. **Monitor** — Track pipeline progress and delivery metrics

---

## Step 1: Configure an AI Provider

Lintel needs at least one AI provider to power agent work. Supported types: `anthropic`, `openai`, `ollama`, `azure_openai`, `google`, `bedrock`, `claude_code`, `custom`.

```bash
curl -X POST http://localhost:8000/api/v1/ai-providers \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Anthropic",
    "provider_type": "anthropic",
    "api_key": "sk-ant-...",
    "is_default": true
  }'
```

Response includes a `provider_id` — save it for later.

For local development with Ollama:

```bash
curl -X POST http://localhost:8000/api/v1/ai-providers \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Local Ollama",
    "provider_type": "ollama",
    "api_base": "http://localhost:11434",
    "is_default": true
  }'
```

Verify:

```bash
curl http://localhost:8000/api/v1/ai-providers
```

---

## Step 2: Store Credentials

Store a GitHub token so Lintel can clone repos, create branches, and open PRs.

```bash
curl -X POST http://localhost:8000/api/v1/credentials \
  -H 'Content-Type: application/json' \
  -d '{
    "credential_type": "github_token",
    "name": "My GitHub Token",
    "secret": "ghp_..."
  }'
```

Save the returned `credential_id`.

---

## Step 3: Register a Repository

### Option A: Register an existing repo

```bash
curl -X POST http://localhost:8000/api/v1/repositories \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "my-app",
    "url": "https://github.com/myorg/my-app",
    "default_branch": "main",
    "owner": "myorg",
    "provider": "github"
  }'
```

### Option B: Create a new repo from a template

Available templates: `react-vite`, `python-fastapi`, `monorepo`.

```bash
# List templates
curl http://localhost:8000/api/v1/repositories/templates

# Create from template
curl -X POST http://localhost:8000/api/v1/repositories/create \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "my-new-app",
    "owner": "myorg",
    "template": "react-vite",
    "private": true,
    "description": "My new React app"
  }'
```

Templates scaffold a full project structure (package.json, vite config, src/App.tsx, etc. for `react-vite`; pyproject.toml, Dockerfile, main.py, etc. for `python-fastapi`).

Save the returned `repo_id`.

---

## Step 4: Create a Project

A project ties together repos, credentials, AI config, and workflow settings.

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "My App",
    "description": "AI-powered task management app",
    "repo_ids": ["<repo_id>"],
    "credential_ids": ["<credential_id>"],
    "default_branch": "main",
    "workflow_execution_enabled": true
  }'
```

Save the returned `project_id`.

### Link AI provider and workflow to the project

```bash
curl -X PATCH http://localhost:8000/api/v1/projects/<project_id> \
  -H 'Content-Type: application/json' \
  -d '{
    "ai_provider_id": "<provider_id>",
    "workflow_definition_id": "feature_to_pr"
  }'
```

The built-in `feature_to_pr` workflow is auto-seeded and handles the full cycle: ingest → route → research → plan → implement → review → close.

---

## Step 5: Create a Board

The board is where work items live. Columns map to work item statuses.

```bash
curl -X POST http://localhost:8000/api/v1/boards \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "<project_id>",
    "name": "My App Board",
    "columns": [
      {"name": "Backlog", "position": 0, "work_item_statuses": ["backlog"]},
      {"name": "Open", "position": 1, "work_item_statuses": ["open"]},
      {"name": "In Progress", "position": 2, "work_item_statuses": ["in_progress"]},
      {"name": "In Review", "position": 3, "work_item_statuses": ["in_review"]},
      {"name": "Done", "position": 4, "work_item_statuses": ["merged", "closed"]}
    ]
  }'
```

### Kanban view

```bash
curl http://localhost:8000/api/v1/boards/<board_id>/kanban?project_id=<project_id>
```

---

## Step 6: Create a Team (Optional)

Teams group users and link to projects.

```bash
curl -X POST http://localhost:8000/api/v1/teams \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Backend Team",
    "project_ids": ["<project_id>"]
  }'
```

---

## Step 7: Define Agent Definitions (Optional)

Lintel ships with built-in agent roles (`planner`, `coder`, `reviewer`, `pm`, `designer`, `summarizer`). You can also create custom agent definitions:

```bash
# List built-in roles
curl http://localhost:8000/api/v1/agents/roles

# Create a custom agent
curl -X POST http://localhost:8000/api/v1/agents/definitions \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Security Reviewer",
    "description": "Reviews code for security vulnerabilities",
    "system_prompt": "You are a security-focused code reviewer...",
    "role": "reviewer",
    "max_tokens": 4096,
    "temperature": 0.0,
    "allowed_skills": ["code_review", "security_scan"]
  }'
```

---

## Step 8: Enable Workflows

Verify the `feature_to_pr` workflow is enabled:

```bash
curl http://localhost:8000/api/v1/workflow-definitions
```

If `enabled` is `false`, toggle it:

```bash
curl -X PATCH http://localhost:8000/api/v1/workflow-definitions/feature_to_pr \
  -H 'Content-Type: application/json' \
  -d '{"enabled": true}'
```

---

## Step 9: Describe Your Idea

### Option A: Use chat to decompose an idea into work items

Start a conversation and describe your idea. The chat router detects intent and can automatically decompose it into work items on your board.

```bash
# Create a conversation
curl -X POST http://localhost:8000/api/v1/chat/conversations \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "admin",
    "message": "I want to build a user dashboard with login, profile page, and activity feed",
    "project_id": "<project_id>",
    "model_id": "claude-sonnet-4-20250514"
  }'
```

The `IdeaDecomposer` breaks this into individual work items (3-10 items), each with a title, description, work type, and order. They appear on your board as `open` items.

### Option B: Create work items manually

```bash
curl -X POST http://localhost:8000/api/v1/work-items \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "<project_id>",
    "title": "Add user login with JWT auth",
    "description": "Implement login page with email/password, JWT token generation, and session management",
    "work_type": "feature",
    "status": "open"
  }'
```

Work item types: `feature`, `bug`, `task`, `spike`, `chore`.
Statuses: `backlog`, `open`, `in_progress`, `in_review`, `merged`, `closed`, `failed`.

---

## Step 10: Trigger Implementation

Move a work item to `in_progress` to signal it's ready for an agent:

```bash
curl -X PATCH http://localhost:8000/api/v1/work-items/<work_item_id> \
  -H 'Content-Type: application/json' \
  -d '{"status": "in_progress"}'
```

### Using the AI orchestration flow

If you have the `lintel-ai` tmux session running (`scripts/lintel-ai.sh`), agents automatically pick up `in_progress` work items and run the `feature_to_pr` pipeline:

1. **Ingest** — Parse the work item description
2. **Route** — Identify affected repos and packages
3. **Research** — Analyse the codebase for context
4. **Plan** — Generate an implementation plan
5. **Implement** — Write code in a sandbox, run tests, iterate
6. **Review** — Automated code review (up to 2 review cycles)
7. **Close** — Create PR, update work item to `in_review`

### Monitor pipeline progress

```bash
# List active pipelines
curl http://localhost:8000/api/v1/pipelines

# Get pipeline details
curl http://localhost:8000/api/v1/pipelines/<run_id>

# Stream real-time stage events (SSE)
curl http://localhost:8000/api/v1/pipelines/<run_id>/events
```

---

## Step 11: Review and Land PRs

Once a pipeline completes, the work item moves to `in_review` with a `pr_url`.

```bash
# Check work item for PR URL
curl http://localhost:8000/api/v1/work-items/<work_item_id>

# List PRs for a repo
curl http://localhost:8000/api/v1/repositories/<repo_id>/pull-requests
```

Review the PR on GitHub. When satisfied, merge it and update the work item:

```bash
curl -X PATCH http://localhost:8000/api/v1/work-items/<work_item_id> \
  -H 'Content-Type: application/json' \
  -d '{"status": "merged"}'
```

---

## Step 12: Preview (Optional)

If your work item produces a web application, use sandbox preview to see it running:

```bash
# Start preview (auto-detects framework)
curl -X POST http://localhost:8000/api/v1/sandboxes/<sandbox_id>/preview \
  -H 'Content-Type: application/json' \
  -d '{}'

# Check preview status and URL
curl http://localhost:8000/api/v1/sandboxes/<sandbox_id>/preview

# Stop preview
curl -X DELETE http://localhost:8000/api/v1/sandboxes/<sandbox_id>/preview
```

The preview endpoint auto-detects the framework (React, Next.js, FastAPI, etc.) and starts the appropriate dev server, returning a `preview_url` you can open in a browser.

---

## Step 13: Connect Channels (Optional)

### Slack

```bash
# Install Slack app (OAuth flow)
# Navigate to: http://localhost:8000/api/v1/channels/slack/install

# Check status
curl http://localhost:8000/api/v1/channels/slack/status
```

### Telegram

```bash
curl -X POST http://localhost:8000/api/v1/channels/telegram/connect \
  -H 'Content-Type: application/json' \
  -d '{"bot_token": "123456:ABC..."}'
```

Once connected, you can trigger workflows directly from Slack threads or Telegram messages.

---

## Quick Start Checklist

For the minimal path from idea to PR:

- [ ] Configure an AI provider (`POST /ai-providers`)
- [ ] Store a GitHub credential (`POST /credentials`)
- [ ] Register your repo (`POST /repositories`)
- [ ] Create a project linking repo + credential (`POST /projects`)
- [ ] Create a board with columns (`POST /boards`)
- [ ] Enable `feature_to_pr` workflow (`PATCH /workflow-definitions/feature_to_pr`)
- [ ] Describe your idea via chat (`POST /chat/conversations`) or create work items manually (`POST /work-items`)
- [ ] Move work items to `in_progress` to trigger agents
- [ ] Monitor pipeline stages (`GET /pipelines/<run_id>`)
- [ ] Review and merge the PR

---

## Using the UI

The Lintel UI at `http://localhost:5173` provides a visual interface for all of the above:

- **Dashboard** — Overview of projects, pipelines, and metrics
- **Chat** — Conversational interface for describing ideas and checking status
- **Projects** — Create and manage projects with linked repos
- **Boards** — Kanban view of work items across columns
- **Settings > AI Providers** — Configure LLM providers
- **Settings > Bots** — Manage Slack and Telegram bots
- **Settings > Channels** — Connect messaging channels
- **Settings > Board Sync** — Sync boards with external tools (Jira, Notion)

---

## Architecture Reference

```
Idea → Chat → IdeaDecomposer → Work Items → Board
                                    ↓
                          Agent picks up (in_progress)
                                    ↓
                          feature_to_pr pipeline
                          ┌─────────────────────┐
                          │ ingest → route →     │
                          │ research → plan →    │
                          │ implement → review → │
                          │ close                │
                          └─────────────────────┘
                                    ↓
                              PR on GitHub
                                    ↓
                          Review → Merge → Done
```

Each pipeline stage emits events that update the board, notify channels, and track metrics. The event-sourced architecture means every action is recorded and replayable.
