# REQ-031: Sandbox Storage Limits & Cleanup

**Status:** Proposed
**Priority:** High
**Category:** Reliability / Infrastructure

## Problem

Sandbox containers use a 4GB tmpfs for `/workspace`. When sandboxes are reused from the pool, previous workspace data is not cleaned up, eventually causing "No space left on device" errors on git clone. There are no storage monitoring, limits, or automatic cleanup policies.

## Proposed Solution

### Requirements

1. **Workspace cleanup on reuse:** Before cloning a repo into a reused sandbox, remove previous workspace data. *(Fixed — `setup_workspace.py` now runs `rm -rf /workspace/*` before clone.)*
2. **Storage monitoring:** Track disk usage per sandbox. Expose via sandbox status API.
3. **Configurable storage limit:** Allow per-sandbox storage limits (default: 4GB tmpfs, configurable up to 10GB).
4. **Automatic cleanup policy:** When a pipeline run completes (success or failure), clean workspace data unless configured to retain for debugging.
5. **Retention period:** Workspace data for failed runs retained for configurable period (default: 24 hours) for post-mortem debugging, then auto-cleaned.
6. **Pre-clone space check:** Before cloning, verify available space. If below threshold (500MB), clean up or fail fast with a clear error.
7. **Dashboard visibility:** Show sandbox storage usage on the pipeline detail view.

### Configuration

```yaml
sandbox:
  storage:
    workspace_size: "4g"       # tmpfs size
    cleanup_on_reuse: true     # rm workspace before new run
    retain_failed_hours: 24    # keep failed workspace for debugging
    min_free_mb: 500           # fail fast if less than this available
```

## Depends On

- REQ-029 (Pipeline Step Timeout — timeout + storage cleanup work together)
