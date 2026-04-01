# lintel-workflows

LangGraph workflow orchestration and graph nodes. Depends on `lintel-contracts` and `lintel-agents`.

## Key modules

- `src/lintel/workflows/base.py` — `WorkflowNode` abstract base class for all graph nodes (REQ-028). Provides standard stage tracking, error handling, and config access.
- `src/lintel/workflows/nodes/` — Concrete node implementations (research, implement, review, etc.)
- `src/lintel/workflows/nodes/approval_gate.py` — `ApprovalGateNode` for human-in-the-loop approval using LangGraph interrupts (REQ-F017)
- `src/lintel/workflows/types.py` — Workflow types (PipelineRun, Stage, StageStatus, etc.)
- `src/lintel/workflows/events.py` — Workflow events (PipelineRunStarted, WorkflowStarted, etc.)
- `src/lintel/workflows/commands.py` — Workflow commands (StartWorkflow)

## Testing

```bash
make test-workflows
```
