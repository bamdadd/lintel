# REQ-029: Pipeline Step Timeout

**Status:** Proposed
**Priority:** High
**Category:** Reliability / Distributed Execution

## Problem

Pipeline steps (workflow nodes) can run indefinitely. A stuck LLM call, a hung sandbox process, or an infinite review loop will block the entire pipeline run with no automatic recovery. This is a prerequisite for distributed execution — remote executors must not hold resources forever.

## Proposed Solution

Enforce a maximum timeout per pipeline step, defaulting to **2 hours**. When a step exceeds its timeout, it is cancelled and the pipeline run is marked as failed (or retried, if retry policy allows).

### Requirements

1. **Default timeout:** 2 hours (7200 seconds) per step.
2. **Per-step override:** Each workflow node can declare a custom timeout via configuration (e.g., `implement` may need longer than `plan`).
3. **Per-pipeline override:** Pipeline definitions can set a global step timeout that overrides the system default.
4. **Cancellation:** On timeout, the step's sandbox process / LLM call is cancelled, resources are released, and the stage is marked `TIMED_OUT`.
5. **Stage tracking:** The stage tracker records the timeout event with elapsed duration.
6. **Notification:** The chat / Slack thread is notified that the step timed out.
7. **Pipeline-level timeout:** Optional aggregate timeout for the entire pipeline run (e.g., 8 hours). Independent of per-step timeouts.

### Implementation Sketch

```python
# In WorkflowNode base class (REQ-028) or as a wrapper

class StepTimeout(BaseModel):
    default: int = 7200  # seconds
    per_step: dict[str, int] = {}  # node_name -> seconds

# In the graph executor
async def execute_with_timeout(node_fn, state, config, timeout_seconds):
    try:
        async with asyncio.timeout(timeout_seconds):
            return await node_fn(state, config)
    except TimeoutError:
        # Mark stage as TIMED_OUT, notify, clean up
        ...
```

### Stage Status Addition

Add `TIMED_OUT` to the `StageStatus` enum alongside existing `RUNNING`, `COMPLETED`, `FAILED`.

### Configuration

```yaml
# Pipeline definition or system config
timeouts:
  default_step: 7200      # 2 hours
  max_pipeline: 28800     # 8 hours
  per_step:
    implement: 10800      # 3 hours — code gen takes longer
    plan: 3600            # 1 hour
    review: 3600          # 1 hour
```

## Depends On

- REQ-028 (WorkflowNode base class — natural place to declare timeout)

## Future Extensions

- Retry with backoff on timeout (configurable retry count per step)
- Adaptive timeouts based on historical step durations
- Heartbeat-based liveness (step must report progress within N minutes or be killed)
- Ties into distributed executor model: executors enforce timeout locally, coordinator enforces globally
