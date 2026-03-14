# REQ-036: Pipeline Stage Retry (Re-execution)

## Problem

The `POST /pipelines/{run_id}/stages/{stage_id}/retry` endpoint resets a stuck/failed stage status to `running` but does **not** re-invoke the workflow executor. After a server restart, all in-flight stages are marked `running` but no background task is processing them. Calling retry only updates the database — nothing actually executes.

The comment at `packages/app/src/lintel/api/routes/pipelines.py:436` says:

> TODO: Re-invoke the workflow node via the executor (Phase 2 integration).

## Requirements

### 1. Retry must re-execute the stage node

When retry is called on a `running` or `failed` stage:

1. Reset stage status to `running` (already done)
2. Look up the pipeline's `workflow_definition_id` to determine the graph
3. Re-invoke the corresponding node function via `asyncio.create_task` using the same pattern as `debug.py:_run_node_background`
4. Pass existing pipeline state (sandbox_id, workspace_path, prior stage outputs) as node inputs
5. On completion, update stage status and advance the pipeline to the next stage

### 2. Bulk retry for stuck pipelines

Add `POST /pipelines/retry-stuck` endpoint that:

1. Finds all pipelines with status `running` where a stage has been `running` for longer than a configurable timeout (default: 10 minutes)
2. Retries each stuck stage (up to `max_retries=3`)
3. Returns a summary of what was retried

### 3. Server restart recovery

On server startup (`app.py` lifespan):

1. Query for pipelines in `running` status
2. For each, check if any stage has been `running` for > 5 minutes (stale from prior process)
3. Automatically retry those stages (respecting max retry count)
4. Log recovery actions

## Architecture Notes

- **Package:** Retry logic in `packages/app/src/lintel/api/routes/pipelines.py`. Recovery in `packages/app/src/lintel/api/app.py` lifespan.
- **Key pattern:** Reuse `NODE_REGISTRY` from `debug.py` to look up node functions. Reuse `_run_node_background` pattern for background execution.
- **State reconstruction:** Build node input state from pipeline run's prior stage outputs + sandbox_id + workspace_path stored on the run.
- **Pipeline advancement:** After stage completes, must trigger the next stage in sequence (same as `WorkflowExecutor` does).

## Out of Scope

- Distributed task queue (Celery/Dramatiq) — that's a separate infrastructure decision
- Partial graph re-execution from checkpoints — requires LangGraph checkpointing (future)

## Priority

P1 — operational reliability. Without this, any server restart loses all in-flight work.
