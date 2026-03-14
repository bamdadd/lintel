# Automations UI Design Spec

**Date:** 2026-03-14
**Status:** Approved

## Overview

Add a frontend UI for the Automations feature, allowing users to create, view, manage, and monitor automation rules and their execution history. The UI consists of a list page (card grid), a detail page (tabbed: Overview, Runs, Settings), and a create/edit modal.

## Tech Stack

- React 19 + TypeScript
- Mantine v8 (component library + forms)
- Tabler Icons
- React Router v7 (lazy-loaded routes)
- React Query v5 via Orval-generated hooks
- Recharts (for timeline visualization)

## Pages & Components

### 1. Sidebar Navigation

New "Scheduling" section in the sidebar (`AppLayout.tsx` `navSections` array), containing a single item: "Automations" at `/automations`.

### 2. AutomationListPage (`/automations`)

Card grid layout showing all automations.

**Card contents:**
- Automation name (dimmed if disabled)
- Project name
- Trigger type badge (cron=purple, event=blue)
- Trigger config preview (cron expression or event type name)
- Last run status + time ago
- Enable/disable toggle (top-right)
- Left border color: green (last run passed), red (failed), gray (disabled/no runs)

**Header:** Title + "Create Automation" button (opens modal).

**Empty state:** Standard `EmptyState` component when no automations exist.

**Card click:** Navigates to `/automations/:automationId`.

### 3. AutomationDetailPage (`/automations/:automationId`)

Tabbed page with breadcrumb navigation.

**Header:** Automation name + enabled badge + trigger type badge + "Trigger Now" button + "Edit" button (opens edit modal).

#### Overview Tab
Two-column layout:
- **Left — Configuration card:** Project, workflow, schedule/event types, timezone, concurrency policy, max chain depth
- **Right — Next 5 Runs card** (cron only): List of upcoming fire times computed client-side via `cronstrue` for human-readable display and `cron-parser` for next dates. For event/manual triggers, show "Triggered on demand" instead.
- **Right — Quick Stats card:** Count of passed, failed, skipped runs
- **Full-width — Run Timeline:** Bar chart (Recharts) showing run results over last 7 days, color-coded green/red/gray

#### Runs Tab
Table with expandable rows:
- Columns: Run ID (monospace), Status (badge), Started (relative time), Duration
- Click row to expand inline, showing pipeline stages as horizontal cards (stage name, status, duration)
- "View full pipeline →" link navigates to existing `/pipelines/:runId` page
- Collapsed/expanded toggle via chevron icon

#### Settings Tab
Edit form (same layout as create modal) pre-filled with current values. Save button PATCHes the automation. Delete button with confirmation.

### 4. Create/Edit Modal

Modal form with dynamic fields based on trigger type:

- **Name** — text input (required)
- **Project** — select dropdown populated from projects API (required)
- **Workflow** — select dropdown populated from workflow-definitions API (required)
- **Trigger Type** — Mantine `SegmentedControl` (Cron / Event / Manual) (required, immutable on edit)
- **Trigger Config** (dynamic section):
  - Cron: schedule input (monospace, with human-readable preview via `cronstrue`) + timezone select
  - Event: multi-select of event types
  - Manual: no extra fields
- **Concurrency Policy** — select with descriptions (queue, allow, skip, cancel)
- **Enabled** — switch toggle

## Data Fetching

Orval-generated hooks from the `/api/v1/automations` endpoints:
- `useAutomationsListAutomations` — list page
- `useAutomationsGetAutomation` — detail page
- `useAutomationsCreateAutomation` — create modal
- `useAutomationsUpdateAutomation` — settings tab / edit modal
- `useAutomationsDeleteAutomation` — settings tab
- `useAutomationsTriggerAutomation` — "Trigger Now" button
- `useAutomationsListAutomationRuns` — runs tab

Query invalidation after mutations on `['/api/v1/automations']`.

Additional hooks for dropdowns:
- `useProjectsListProjects` — project select
- `useWorkflowDefinitionsListWorkflowDefinitions` — workflow select

## Client-Side Dependencies

- `cronstrue` — human-readable cron expression descriptions ("Every day at 2:00 AM")
- `cron-parser` — compute next N fire times for the "Next 5 Runs" card

These are lightweight, client-only packages. No backend changes needed.

## File Layout

```
ui/src/features/automations/
├── pages/
│   ├── AutomationListPage.tsx
│   └── AutomationDetailPage.tsx
└── components/
    ├── AutomationCard.tsx
    ├── AutomationFormModal.tsx
    ├── RunsTable.tsx
    ├── RunTimeline.tsx
    └── NextRunsList.tsx
```

## Routes

Add to `ui/src/app/routes.tsx`:
```
{ path: 'automations', lazy: () => import('@/features/automations/pages/AutomationListPage') }
{ path: 'automations/:automationId', lazy: () => import('@/features/automations/pages/AutomationDetailPage') }
```

## Scope

**In scope:**
- Card grid list page with enable/disable toggle
- Detail page with Overview, Runs, Settings tabs
- Create/edit modal with dynamic trigger config fields
- Cron expression preview (human-readable)
- Next 5 runs list (cron only)
- Run timeline bar chart (7 days)
- Expandable runs table with inline stage view
- Sidebar navigation under new "Scheduling" section

**Out of scope:**
- Real-time SSE updates for run status (future enhancement)
- Drag-and-drop reordering
- Bulk operations
- Input parameters editor (future, when workflows support parameterization UI)
