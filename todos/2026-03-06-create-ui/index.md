# Todo: Create a UI

## Description

Build the Lintel web dashboard -- a React SPA that serves as the control plane for managing agents, workflows, connections, repositories, and observability.

## Tech Stack

| Choice | Rationale |
|---|---|
| **React 18 + TypeScript** | Standard, large ecosystem |
| **Mantine v7** | Rich component library with excellent form controls, notifications, stepper, code highlights, charts (via `@mantine/charts` / Recharts), and dark mode. Lighter than Ant Design, more complete than Radix. |
| **React Router v7** | Client-side routing with nested layouts |
| **TanStack Query v5** | Server state, caching, polling for real-time event streams |
| **React Flow** | Visual workflow editor (drag-and-drop node graph for LangGraph workflows) |
| **Recharts** (via Mantine Charts) | Charting for metrics dashboards |
| **Vite** | Fast dev server and builds |

The UI lives in `ui/` at the repo root. FastAPI serves the built static files in production.

## Pages and Features

### 1. Setup Wizard (first-run onboarding)

When no connections are configured, the app shows a guided setup flow using Mantine's `Stepper` component. Each step validates before allowing the user to proceed.

**Steps:**
1. **Database** -- Postgres connection string. Test Connection button with inline success/error feedback.
2. **Messaging** -- NATS server URL. Test Connection button.
3. **Slack** -- Bot token + signing secret. Links to Slack app creation docs. Test button sends a verification message.
4. **LLM Provider** -- Provider dropdown (OpenAI, Anthropic, Azure, Ollama, custom). API key input. Model selection per agent role with sensible defaults. Test button runs a ping completion.
5. **Repository** -- Connect first repo (GitHub URL, access token). Validates repo access.
6. **Review** -- Summary of all connections with status indicators. Finish button.

After setup, these values are persisted via the API and the wizard is not shown again (but all settings remain editable from the Settings page).

The wizard uses `Alert` components with contextual help at each step:
- What each connection is for
- Where to find credentials
- Links to external docs (Slack API, provider dashboards)

### 2. Dashboard (`/`)

The landing page after setup. Overview of system health at a glance.

- **Status cards** -- Active workflows count, pending approvals, running sandboxes, agent activity (last 24h)
- **Recent threads** -- Table of the last 20 threads with status badge (`WorkflowPhase`), timestamp, channel
- **Event stream** -- Live-updating feed of recent events with type badges and expandable payloads (uses TanStack Query polling)
- **Quick actions** -- Buttons to start a workflow, register a repo, open settings

### 3. Threads (`/threads`)

List and detail views for workflow threads.

**List view:**
- Filterable table (by phase, channel, date range)
- Status badge per thread showing `WorkflowPhase` (colour-coded)
- Search by thread ID or channel

**Detail view (`/threads/:streamId`):**
- **Timeline** -- Vertical timeline of all events for this thread, grouped by phase. Each event is expandable to show full payload.
- **Current phase** -- Highlighted phase indicator using a `Stepper` showing: Ingesting > Planning > Awaiting Approval > Implementing > Reviewing > Merging > Closed
- **Agent activity** -- Which agents have acted, what steps completed, model calls made
- **Approval gates** -- If the thread is awaiting approval, show an actionable approve/reject card
- **PII summary** -- Count of PII entities detected/anonymised, risk score. No raw PII shown in the UI.
- **Sandbox output** -- If sandboxes ran, show command outputs (stdout/stderr) in a code block
- **PR link** -- If a PR was created, direct link to GitHub

### 4. Workflow Editor (`/workflows`)

Visual graph editor for defining and editing LangGraph workflows.

- **React Flow canvas** -- Nodes represent agent steps (planner, coder, reviewer, etc.), edges represent transitions
- **Node palette** -- Sidebar with draggable node types: agent step, approval gate, sandbox execution, conditional branch
- **Node config panel** -- Click a node to configure: agent role, model policy (provider, model, temperature, max tokens), step name, context parameters
- **Edge conditions** -- Click an edge to set transition conditions (e.g., approval granted, review passed)
- **Templates** -- Pre-built workflow templates (default SDLC workflow, simple Q&A, code review only)
- **Save/Load** -- Workflows saved as JSON, versioned
- **Validation** -- Warns on disconnected nodes, missing required config, unreachable states

### 5. Repositories (`/repositories`)

CRUD for registered git repositories.

- **List view** -- Table with name, URL, provider, branch, status badge (`active`/`archived`/`error`)
- **Register form** -- Modal form: repo URL, name, provider (GitHub/GitLab/Bitbucket), default branch, owner. Inline validation.
- **Detail view** -- Edit settings, view recent branches and commits (via `RepoProvider`), archive/remove with confirmation dialog

### 6. Agents & Models (`/agents`)

Configure agent roles and their model policies.

- **Agent role cards** -- One card per `AgentRole` (planner, coder, reviewer, PM, designer, summarizer) showing current model assignment
- **Model policy form** -- Per role: provider dropdown, model name, max tokens slider, temperature slider
- **Test panel** -- Send a test prompt to any agent role and see the response + latency + token usage

### 7. Skills (`/skills`)

Registry of pluggable agent capabilities.

- **List view** -- Table of registered skills with name, version, execution mode badge (`inline`/`async_job`/`sandbox`), allowed agent roles
- **Detail view** -- Input/output schemas rendered as formatted JSON, invocation history
- **Register form** -- For adding custom skills: name, version, schemas (JSON editor), execution mode, role permissions

### 8. Sandboxes (`/sandboxes`)

Monitor and manage isolated execution environments.

- **Active sandboxes** -- Table with status badge (`pending`/`creating`/`running`/`completed`/`failed`/`destroyed`), associated thread, repo, duration
- **Sandbox detail** -- Command outputs, artifacts collected, resource usage
- **Manual controls** -- Destroy button with confirmation for stuck sandboxes

### 9. Events (`/events`)

Full event store explorer.

- **Event stream** -- Paginated table of all events, newest first
- **Filters** -- By event type (dropdown with all 28 types), actor type, date range, correlation ID
- **Event detail** -- Expandable row showing full `EventEnvelope` fields: event_id, schema_version, occurred_at, actor, correlation/causation chain, payload
- **Correlation view** -- Enter a correlation ID to see the full causal chain of events as a linked timeline

### 10. PII & Security (`/security`)

Visibility into PII handling and security events.

- **PII dashboard** -- Charts: PII detections over time, entity types breakdown (pie chart), anonymisation rate, blocked messages
- **Vault activity** -- Recent reveal requests with requester, reason, and grant/deny status
- **Policy log** -- `PolicyDecisionRecorded` events in a table

### 11. Settings (`/settings`)

All connection and configuration management post-setup.

- **Connections tab** -- Same forms as the setup wizard but editable independently. Each connection shows a status indicator (connected/disconnected/error) and a Test button.
  - Database (Postgres DSN)
  - Messaging (NATS URL)
  - Slack (bot token, signing secret)
  - LLM providers (multiple providers, API keys, default model per role)
  - Repository providers (GitHub tokens)
- **General tab** -- App name, base URL, log level
- **Danger zone** -- Reset event store, clear projections (with double-confirmation)

## UX Patterns

| Pattern | Implementation |
|---|---|
| **Guided onboarding** | Setup wizard on first run; empty states on each page link back to relevant setup step |
| **Empty states** | Every list/table shows a helpful empty state with an action button (e.g., "No repositories yet. Register your first repo.") |
| **Connection status** | Global header shows connection health indicators (green/amber/red dots for DB, NATS, Slack, LLM) |
| **Contextual help** | `?` icons next to complex fields open a tooltip or popover explaining what it does and where to find the value |
| **Inline validation** | Forms validate on blur with clear error messages |
| **Test buttons** | Every connection form has a Test button that gives immediate pass/fail feedback |
| **Notifications** | Mantine `notifications` system for async feedback (save success, connection test results, errors) |
| **Dark mode** | Toggle in header, respects system preference by default |
| **Breadcrumbs** | On all nested pages for orientation |
| **Keyboard shortcuts** | `Cmd+K` command palette for quick navigation |

## Layout

```
+------------------------------------------------------------------+
| [Lintel logo]   Dashboard  Threads  Workflows  ...   [?] [dark] |
+----------+-------------------------------------------------------+
|          |                                                        |
| Sidebar  |  Main content area                                    |
| nav      |                                                        |
|          |                                                        |
| Dashboard|                                                        |
| Threads  |                                                        |
| Workflows|                                                        |
| Repos    |                                                        |
| Agents   |                                                        |
| Skills   |                                                        |
| Sandboxes|                                                        |
| Events   |                                                        |
| Security |                                                        |
| Settings |                                                        |
|          |                                                        |
+----------+-------------------------------------------------------+
```

Collapsible sidebar on smaller screens. Mantine `AppShell` component handles the responsive layout.

## API Dependencies

All 52 endpoints required by the UI exist. All use in-memory stores; some return stub data pending real infrastructure.

### Health

| Endpoint | Used by |
|---|---|
| `GET /healthz` | Header status, setup wizard |

### Threads

| Endpoint | Used by |
|---|---|
| `GET /api/v1/threads` | Threads list, dashboard |

### Events

| Endpoint | Used by | Notes |
|---|---|---|
| `GET /api/v1/events` | Events page, dashboard feed | |
| `GET /api/v1/events/types` | Events filter dropdown | Returns all 28 registered event type names |
| `GET /api/v1/events/stream/:stream_id` | Thread detail timeline | Stub -- returns empty list, needs EventStore |
| `GET /api/v1/events/correlation/:correlation_id` | Correlation view | Stub -- returns empty list, needs EventStore |

### Repositories

| Endpoint | Used by |
|---|---|
| `POST /api/v1/repositories` | Repo registration |
| `GET /api/v1/repositories` | Repo list |
| `GET /api/v1/repositories/:id` | Repo detail |
| `PATCH /api/v1/repositories/:id` | Repo edit |
| `DELETE /api/v1/repositories/:id` | Repo removal |

### Credentials

| Endpoint | Used by | Notes |
|---|---|---|
| `POST /api/v1/credentials` | Store SSH key or GitHub token | Secrets masked on read |
| `GET /api/v1/credentials` | List all credentials | |
| `GET /api/v1/credentials/:id` | Get credential detail | |
| `GET /api/v1/credentials/repo/:repo_id` | Credentials for a repo | |
| `DELETE /api/v1/credentials/:id` | Revoke and delete | |

### Workflows

| Endpoint | Used by |
|---|---|
| `POST /api/v1/workflows` | Start workflow |
| `GET /api/v1/workflows` | Workflow list |
| `GET /api/v1/workflows/:stream_id` | Workflow detail |
| `POST /api/v1/workflows/messages` | Process incoming message |

### Workflow Definitions

| Endpoint | Used by | Notes |
|---|---|---|
| `POST /api/v1/workflow-definitions` | Save workflow graph | |
| `GET /api/v1/workflow-definitions` | List all definitions | Ships with "Feature to PR" template |
| `GET /api/v1/workflow-definitions/templates` | List templates only | |
| `GET /api/v1/workflow-definitions/:id` | Get definition | |
| `PUT /api/v1/workflow-definitions/:id` | Update definition | |
| `DELETE /api/v1/workflow-definitions/:id` | Delete definition | |

### Agents

| Endpoint | Used by | Notes |
|---|---|---|
| `GET /api/v1/agents/roles` | Agent role list | Returns all 6 roles |
| `GET /api/v1/agents/policies` | All model policies | Defaults all roles to claude-sonnet-4-20250514 |
| `GET /api/v1/agents/policies/:role` | Single role policy | |
| `PUT /api/v1/agents/policies/:role` | Update model policy | provider, model_name, max_tokens, temperature |
| `POST /api/v1/agents/test-prompt` | Test agent prompt | Stub -- returns dry-run echo, needs ModelRouter |
| `POST /api/v1/agents/steps` | Schedule agent step | |

### Approvals

| Endpoint | Used by |
|---|---|
| `POST /api/v1/approvals/grant` | Grant approval |
| `POST /api/v1/approvals/reject` | Reject approval |

### Sandboxes

| Endpoint | Used by | Notes |
|---|---|---|
| `POST /api/v1/sandboxes` | Schedule sandbox job | Registers in in-memory registry |
| `GET /api/v1/sandboxes` | Sandbox list | |
| `GET /api/v1/sandboxes/:id` | Sandbox detail | |
| `DELETE /api/v1/sandboxes/:id` | Destroy sandbox | Marks status as `destroyed` |

### Skills

| Endpoint | Used by |
|---|---|
| `POST /api/v1/skills` | Skill registration |
| `GET /api/v1/skills` | Skills list |
| `GET /api/v1/skills/:skill_id` | Skill detail |
| `POST /api/v1/skills/:skill_id/invoke` | Skill invocation (echo stub) |

### PII & Vault

| Endpoint | Used by | Notes |
|---|---|---|
| `POST /api/v1/pii/reveal` | PII reveal request | Logs to vault, increments stats |
| `GET /api/v1/pii/vault/log` | Vault activity log | |
| `GET /api/v1/pii/stats` | PII detection stats | Counters only update via reveal |

### Metrics

| Endpoint | Used by | Notes |
|---|---|---|
| `GET /api/v1/metrics/pii` | Security dashboard | Same counters as `/pii/stats` |
| `GET /api/v1/metrics/agents` | Agent activity | Last 100 entries |
| `GET /api/v1/metrics/overview` | Dashboard overview | Combined PII + sandbox + connection counts |

### Settings

| Endpoint | Used by | Notes |
|---|---|---|
| `POST /api/v1/settings/connections` | Create connection | Types: slack, github, llm_provider, postgres, nats |
| `GET /api/v1/settings/connections` | List connections | |
| `GET /api/v1/settings/connections/:id` | Get connection | |
| `PATCH /api/v1/settings/connections/:id` | Update connection | |
| `DELETE /api/v1/settings/connections/:id` | Remove connection | |
| `POST /api/v1/settings/connections/:id/test` | Test connection | Stub -- always returns `ok` |
| `GET /api/v1/settings` | General settings | workspace_name, default_model_provider, pii_detection_enabled, sandbox_enabled, max_concurrent_workflows |
| `PATCH /api/v1/settings` | Update general settings | |

### Admin

| Endpoint | Used by |
|---|---|
| `POST /api/v1/admin/reset-projections` | Settings danger zone |

### Stubs Needing Real Infrastructure

| Stub | What's needed |
|---|---|
| Event stream/correlation queries | PostgreSQL EventStore wired to read_stream / read_by_correlation |
| Agent test-prompt | ModelRouter integration to actually call an LLM |
| Connection test | Real connectivity checks per type (pg_isready, NATS ping, Slack auth.test, LLM completion) |
| Sandbox lifecycle | Real SandboxManager (container runtime) instead of in-memory status tracking |
| PII stats | Deidentifier pipeline feeding counters from actual message processing |
| All in-memory stores | Persistent storage (Postgres) for workflow definitions, settings, policies, credentials, sandbox registry, skills -- all reset on restart currently |

## File Structure

```
ui/
  index.html
  vite.config.ts
  tsconfig.json
  package.json
  src/
    main.tsx
    App.tsx
    api/                  # TanStack Query hooks and API client
      client.ts
      hooks/
        useThreads.ts
        useEvents.ts
        useRepositories.ts
        useAgents.ts
        useSkills.ts
        useSandboxes.ts
        useSettings.ts
        useWorkflows.ts
    components/
      layout/
        AppShell.tsx      # Mantine AppShell with sidebar
        Header.tsx
        Sidebar.tsx
        ConnectionStatus.tsx
      shared/
        EmptyState.tsx
        StatusBadge.tsx
        TestConnectionButton.tsx
        ContextHelp.tsx
        CommandPalette.tsx
    pages/
      Dashboard.tsx
      setup/
        SetupWizard.tsx
      threads/
        ThreadList.tsx
        ThreadDetail.tsx
        ThreadTimeline.tsx
        ApprovalCard.tsx
      workflows/
        WorkflowEditor.tsx
        NodePalette.tsx
        NodeConfigPanel.tsx
      repositories/
        RepoList.tsx
        RepoDetail.tsx
        RegisterRepoModal.tsx
      agents/
        AgentList.tsx
        ModelPolicyForm.tsx
        TestAgentPanel.tsx
      skills/
        SkillList.tsx
        SkillDetail.tsx
        RegisterSkillForm.tsx
      sandboxes/
        SandboxList.tsx
        SandboxDetail.tsx
      events/
        EventExplorer.tsx
        CorrelationView.tsx
      security/
        PIIDashboard.tsx
        VaultActivity.tsx
        PolicyLog.tsx
      settings/
        Settings.tsx
        ConnectionForm.tsx
    theme/
      index.ts              # Mantine theme customisation
    types/
      index.ts              # TypeScript types mirroring backend contracts
```

## Artifacts

- `index.md` - Task definition
- `research.md` - Research findings with synthesis and appendix summaries
- `research/` - Detailed appendices (10 files)
  - `codebase-survey-python-api.md` - Backend API surface survey
  - `codebase-survey-react-ui.md` - Frontend infrastructure survey
  - `framework-docs-python-api.md` - FastAPI/Pydantic documentation
  - `framework-docs-react-ui.md` - Mantine/TanStack/React Flow/Vite documentation
  - `web-research-python-api.md` - FastAPI+React integration best practices
  - `web-research-react-ui.md` - React dashboard best practices
  - `clean-code-python-api.md` - Backend code quality analysis
  - `clean-code-react-ui.md` - Frontend patterns to establish
  - `evidence-index.md` - Consolidated evidence citations
  - `risks.md` - Risk analysis and troubleshooting

## Notes

- Mantine v7 was chosen over Ant Design (smaller bundle, better DX, native dark mode) and over Shadcn (Mantine has more built-in complex components like Stepper, Transfer, and Charts that we need out of the box)
- React Flow is the de facto standard for node-based graph editors in React and will be used for the workflow editor
- The UI should be buildable as a static SPA and served by FastAPI in production (or separately via a CDN)
- All forms should degrade gracefully when the API is unreachable, showing connection error banners rather than blank screens
