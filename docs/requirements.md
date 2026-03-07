# Lintel — Requirements & Roadmap

## Phase 1 — Noop Pipeline (Polish)

### REQ-1.1: Approval gates pause workflow and request user approval
- When a workflow reaches an approval stage (e.g. `approve_spec`, `approve_merge`), it must pause execution.
- Post an approval request message to the originating chat conversation with approve/reject options.
- Create an `ApprovalRequest` record in the `approval_request_store`.
- Resume workflow on user approval; abort and mark pipeline as failed on rejection.
- Approval status reflected on pipeline DAG (yellow/pending badge).

### REQ-1.2: Mark work item as failed when workflow fails
- When `WorkflowExecutor` catches an exception, set the linked work item status to `failed`.
- Currently only success path marks work item as `closed`.

### REQ-1.3: Real-time chat message updates
- Chat page should poll or use SSE so that stage update messages (completions, approvals, final status) appear without manual refresh.
- Consider WebSocket or SSE endpoint for push-based updates.

### REQ-1.4: Pipeline list row navigation
- Clicking a row in the pipeline list page must navigate to `/pipelines/:runId` (DAG detail page).
- Verify this works end-to-end with current routing.

### REQ-1.5: RunDetailPage event display
- `PipelineRunStarted` event currently shows a "Running" status badge which is confusing.
- Show event type label (e.g. "Started", "Stage Completed", "Failed") instead of pipeline status.

### REQ-1.6: Stage log streaming and detail view
- Clicking a stage node in the pipeline DAG should expand a panel showing real-time logs from that stage.
- For running stages: stream stdout/stderr from the sandbox container via SSE.
- For completed/failed stages: show stored `agent_outputs` and `sandbox_results` formatted as readable logs.
- Backend: `GET /api/v1/pipelines/{runId}/stages/{stageId}/logs` SSE endpoint.
- Stage outputs (agent text, sandbox stdout, errors) stored on the Stage record for post-mortem viewing.

### REQ-1.7: Retry individual pipeline stages
- When a stage is stuck (running too long) or has failed, allow re-running it from the pipeline detail page.
- Backend: `POST /api/v1/pipelines/{runId}/stages/{stageId}/retry` endpoint.
- Resets the stage status to `running`, re-invokes the corresponding workflow node with existing state.
- Only allowed for stages in `running` or `failed` status.
- Stage retry count tracked to prevent infinite loops.

---

## Phase 2 — Real Graph Execution

### REQ-2.1: Replace noop graph with real LangGraph
- Remove `_noop_astream` and `AsyncMock` from `app.py`.
- Wire `GraphCompiler` or `WorkflowRegistry` to produce the actual compiled graph from workflow definitions.
- Each workflow definition's `graph_nodes` and `stage_names` drive real node execution.

### REQ-2.2: Agent runtime integration
- Connect `AgentRuntime` to actual LLM calls via `ModelRouter` for each workflow node (planner, coder, reviewer, etc.).
- Each node invokes the appropriate agent role with the correct model policy and system prompt.
- Agent output stored in stage outputs and surfaced in pipeline detail.

### REQ-2.3: Sandbox execution for code nodes
- Wire `DockerBackend` (or configured sandbox backend) for isolated code execution in `implement` and `test` nodes.
- Sandbox receives repo context, executes agent-generated code/commands, returns results.
- Sandbox lifecycle managed per workflow run (create on start, destroy on completion).

### REQ-2.4: Repository cloning in setup workspace
- `setup_workspace` node clones the target repository into the sandbox using credentials from `credential_store`.
- Supports branch checkout (`repo_branch` from `StartWorkflow` command).
- Multi-repo support: clone all repos in `repo_urls` when provided.

### REQ-2.5: Code artifact and test result storage
- `implement` node stores generated code as `CodeArtifact` records.
- `test` node stores test results as `TestResult` records.
- Both linked to the pipeline run and work item for traceability.

### REQ-2.6: Review node with PR creation
- `review` node creates a pull request on the target repository.
- PR URL stored on the work item (`pr_url` field).
- Review comments from the reviewer agent attached to the PR.

---

## Phase 3 — Multi-Channel & Production

### REQ-3.1: Slack channel integration
- Workflows triggered from Slack threads using existing `ThreadRef` (workspace_id, channel_id, thread_ts).
- Slack messages classified and dispatched the same way as chat messages.
- Stage updates and approval requests posted back to the originating Slack thread.

### REQ-3.2: Persistent chat store
- All chat conversations and messages persist across server restarts.
- `PostgresChatStore` already exists; ensure it is used when Postgres backend is active.
- Verify message ordering and pagination work with Postgres.

### REQ-3.3: SSE/WebSocket streaming for real-time updates
- Replace polling with push-based updates for pipeline stage changes and chat messages.
- SSE endpoint per conversation or per pipeline run.
- Frontend subscribes on page load, receives stage transitions and chat messages in real time.

### REQ-3.4: MCP tool integration for agents
- Agents use configured MCP servers for codebase context during planning and implementation.
- MCP tools registered per project or globally via `mcp_server_store`.
- Tool calls logged and visible in pipeline stage detail.

### REQ-3.5: Observability and audit trail
- All workflow executions emit OpenTelemetry traces via `observability` infrastructure.
- Audit entries created for key lifecycle events: workflow started, approval granted/rejected, PR created, workflow completed/failed.
- Audit log queryable by project, user, resource type.

### REQ-3.6: Policy enforcement
- Policies from `policy_store` enforced at approval gates (e.g. require N approvals, restrict who can approve).
- Model usage policies enforced by `ModelRouter` (e.g. which models allowed per project/environment).
- Branch protection policies checked before merge.

---

## Done (Completed)

- [x] Chat classifies messages as `chat_reply` or `start_workflow` (keyword + LLM fallback)
- [x] Project context flows through chat → workflow dispatch
- [x] Pipeline stages created with correct names from workflow definition seed data
- [x] Stage status updates (pending → running → succeeded) tracked and persisted
- [x] Stage timing (started_at, finished_at, duration_ms) recorded
- [x] Chat notifications for each stage completion, approval auto-approve, workflow success/failure
- [x] Work items created on dispatch, marked closed on success
- [x] Pipeline DAG detail page with colored nodes, timing bar, event log link
- [x] Trigger links pipeline back to originating chat conversation
- [x] Chat URL syncs with active conversation selection
- [x] Postgres nested dataclass reconstruction (Stage objects in PipelineRun.stages)
