---
name: lintel-board-prioritise
description: Groom and prioritise board work items — clean up done tasks, break down oversized work, and align priorities with the Lintel vision.
---

# /lintel-board-prioritise — Groom and Prioritise Board Work Items

Review all work items on the board, clean up completed/stale items, break down oversized tasks, and prioritise the backlog aligned with the Lintel vision.

## Context: Lintel Vision

Lintel is the AI-human engineering platform — both measurement system and execution engine. Prioritisation should favour work that advances these pillars (in order):

1. **Event infrastructure** — event store, bus, projections, subscriptions
2. **Collaboration & routing** — teams, channels, integrations
3. **Guardrails & safety** — cost limits, escalation, sandbox hardening
4. **Deployment & observability** — deployments, incidents, feature flags
5. **Measurement & analytics** — DORA metrics, agent accuracy, team velocity
6. **Continuous improvement** — learning loops, automated remediation

## Workflow Capacity Reference

A single `feature_to_pr` workflow run can handle work that fits in roughly one focused feature or bug fix — 11 stages: ingest → route → setup_workspace → research → plan → implement (up to 5 review cycles) → review → close. If a task requires multiple unrelated code changes across different packages, or touches more than ~3 files substantially, it should be broken down.

## Steps

### 1. Fetch current state

Use MCP tools to gather data:
- `mcp__lintel__boards_list_boards` — get all boards (needs a project_id; list projects first if needed)
- `mcp__lintel__work-items_list_work_items` — get all work items

Present a summary table of current work items grouped by status.

### 2. Groom — remove completed work

Identify work items with terminal statuses (`merged`, `closed`) — these are done. Delete them with `mcp__lintel__work-items_remove_work_item`.

Also identify `failed` items — ask the user whether to retry (move back to `open`) or delete.

Report what was cleaned up.

### 3. Assess scope — break down oversized tasks

For each remaining `open` work item, evaluate whether it can be completed in a single `feature_to_pr` run:

**Too big if:**
- Description mentions multiple unrelated changes
- Touches more than 3 packages substantially
- Contains words like "and also", "plus", "as well as" suggesting bundled work
- Would require multiple PRs to review sensibly

**For oversized items:**
- Propose a breakdown into smaller work items (each achievable in one workflow run)
- Ask the user to confirm the breakdown
- On confirmation: create the new smaller work items with `mcp__lintel__work-items_create_work_item`, then delete the original with `mcp__lintel__work-items_remove_work_item`

### 4. Prioritise

Rank all remaining `open` work items by:

1. **Vision alignment** — how directly does this advance the Lintel vision pillars (see above)?
2. **Unblocking value** — does this unblock other work items or capabilities?
3. **Foundation-first** — lower-layer work (event infra, contracts) before higher-layer (UI, analytics)
4. **Risk reduction** — security, data integrity, and correctness issues first
5. **User impact** — features that make the platform usable for real workflows

Present the proposed priority order as a numbered list with brief rationale for each position.

### 5. Apply priority

After user confirms the priority order:
- Update `column_position` on each work item using `mcp__lintel__work-items_update_work_item` to reflect the agreed priority (position 0 = highest priority)

### 6. Summary

Show the final board state: a clean table of prioritised work items with title, type, status, and position.

## Important

- Always ask for user confirmation before deleting items or creating breakdowns
- Never delete `in_progress` or `in_review` items — those have active workflows
- Use the Lintel MCP tools (`mcp__lintel__*`), not HTTP requests
- If no project_id is known, use `mcp__lintel__projects_list_projects` to find it first
