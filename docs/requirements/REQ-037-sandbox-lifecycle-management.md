# REQ-037: Sandbox Lifecycle Management

## Problem

Sandboxes are created during `setup_workspace` but never cleaned up. Every pipeline run creates a new sandbox, and completed, failed, or cancelled pipelines leave orphaned sandboxes behind. This leads to unbounded resource consumption — 104 orphaned sandboxes were found after just a few days of operation.

## Requirements

### 1. Max sandbox limit

Enforce a configurable maximum number of concurrent sandboxes (default: 20).

- When `setup_workspace` tries to create a sandbox and the limit is reached:
  1. Evict the oldest sandbox not tied to a `running` pipeline
  2. If all sandboxes are active, reject with a clear error and fail the pipeline stage
- Configurable via existing settings endpoint: `PUT /settings` with `max_sandboxes` field (alongside existing `max_concurrent_workflows`, `sandbox_enabled`, etc.)
- Surface current count and limit in `GET /admin/cache-stats`
- Default: 20. Set to 0 for unlimited (not recommended)

### 2. Automatic cleanup on pipeline completion

When a pipeline reaches a terminal state (`succeeded`, `failed`, `cancelled`):

1. Look up the sandbox_id from the pipeline's `setup_workspace` stage outputs
2. Destroy the sandbox automatically
3. Emit a `SandboxDestroyed` event with correlation to the pipeline run

Implementation: hook into the pipeline status update logic in `WorkflowExecutor` and the `cancel_pipeline` / pipeline completion handlers.

### 3. Automatic cleanup on pipeline cancellation

The `POST /pipelines/{run_id}/cancel` endpoint must also destroy the associated sandbox. Currently it only updates status.

### 4. Stale sandbox reaper

Background task (runs every 10 minutes) that:

1. Lists all sandboxes with status `running`
2. For each, checks if an active pipeline references it
3. If no active pipeline references the sandbox and it's older than 30 minutes, destroy it
4. Log reaper actions for observability

Implementation: `asyncio` background task started in the app lifespan, similar to how health checks work.

### 5. Sandbox status tracking

Add `pipeline_run_id` field to sandbox records so orphan detection is a simple join/lookup rather than scanning all pipeline stage outputs.

## Architecture Notes

- **Package:** Sandbox cleanup in `packages/infrastructure/src/lintel/infrastructure/sandbox/`. Reaper task in `packages/app/src/lintel/api/app.py` lifespan. Pipeline hooks in `packages/app/src/lintel/api/routes/pipelines.py`.
- **Events:** `SandboxDestroyed`, `SandboxEvicted` (new events in contracts)
- **Settings:** `max_sandboxes` added to global settings store
- **Key pattern:** Sandbox lifecycle is tied to pipeline lifecycle. Create on `setup_workspace`, destroy on pipeline terminal state.

## Priority

P1 — resource leak. Without this, sandbox count grows unboundedly and will eventually exhaust disk/container resources.
