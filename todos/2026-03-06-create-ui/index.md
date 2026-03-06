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

The UI consumes these existing and planned API endpoints:

| Endpoint | Exists | Used by |
|---|---|---|
| `GET /healthz` | Yes | Header status, setup wizard |
| `GET /api/v1/threads` | Yes | Threads list, dashboard |
| `GET /api/v1/events` | Yes | Events page, dashboard feed |
| `POST /api/v1/repositories` | Yes | Repo registration |
| `GET /api/v1/repositories` | Yes | Repo list |
| `GET /api/v1/repositories/:id` | Yes | Repo detail |
| `PATCH /api/v1/repositories/:id` | Yes | Repo edit |
| `DELETE /api/v1/repositories/:id` | Yes | Repo removal |
| `GET /api/v1/threads/:streamId/events` | Needed | Thread detail timeline |
| `POST /api/v1/threads/:streamId/approve` | Needed | Approval gates |
| `POST /api/v1/threads/:streamId/reject` | Needed | Approval gates |
| `GET /api/v1/agents` | Needed | Agent config |
| `PUT /api/v1/agents/:role/policy` | Needed | Model policy config |
| `GET /api/v1/skills` | Needed | Skills list |
| `POST /api/v1/skills` | Needed | Skill registration |
| `GET /api/v1/sandboxes` | Needed | Sandbox monitor |
| `DELETE /api/v1/sandboxes/:id` | Needed | Sandbox destroy |
| `GET /api/v1/events/stream` | Needed | Correlation view, advanced filtering |
| `GET /api/v1/settings/connections` | Needed | Settings, setup wizard |
| `PUT /api/v1/settings/connections/:type` | Needed | Settings, setup wizard |
| `POST /api/v1/settings/connections/:type/test` | Needed | Connection testing |
| `GET /api/v1/workflows` | Needed | Workflow editor |
| `POST /api/v1/workflows` | Needed | Save workflow |
| `GET /api/v1/metrics/pii` | Needed | Security dashboard charts |

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

## Work Artifacts

| Agent        | File     | Purpose                 |
| ------------ | -------- | ----------------------- |
| task-manager | index.md | Task index and tracking |

## Notes

- Mantine v7 was chosen over Ant Design (smaller bundle, better DX, native dark mode) and over Shadcn (Mantine has more built-in complex components like Stepper, Transfer, and Charts that we need out of the box)
- React Flow is the de facto standard for node-based graph editors in React and will be used for the workflow editor
- The UI should be buildable as a static SPA and served by FastAPI in production (or separately via a CDN)
- All forms should degrade gracefully when the API is unreachable, showing connection error banners rather than blank screens
