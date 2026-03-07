# Feature Request Flow — Requirements

## Summary

When a user opens a chat conversation and describes a feature request, the system should:

1. Ask which **project** they're working on
2. Resolve the project's linked **repositories** and credentials
3. **Clone** the repo into an isolated sandbox
4. **Execute the workflow** (plan → implement → test → review → PR) inside that sandbox
5. **Collect artifacts**, create a PR, and report back

---

## Domain Types Involved

This flow touches these core types (all in `contracts/types.py`):

| Type | Role in this flow |
|------|-------------------|
| `ChatSession` | Links the chat to a `project_id` and available MCP servers |
| `Project` | Groups `repo_ids`, `credential_ids`, and `default_branch` |
| `Repository` | Git URL, provider, default branch |
| `Credential` | GitHub token or SSH key for repo access |
| `WorkItem` | Tracks the feature request through to PR |
| `PipelineRun` | The workflow execution instance, linked to a `WorkflowDefinitionRecord` |
| `Stage` | Each step in the pipeline (ingest, plan, implement, test, review) |
| `AgentSession` | Agent execution within a stage (messages, tool calls, token usage) |
| `SandboxConfig` / `SandboxJob` / `SandboxResult` | Sandbox lifecycle |
| `CodeArtifact` | Stores diffs/files produced by agents |
| `TestResult` | Structured test output |
| `ApprovalRequest` | Human-in-the-loop gates |
| `Trigger` | What started this pipeline (manual from chat) |
| `Environment` / `Variable` | Runtime context and secrets for the sandbox |
| `NotificationRule` | Progress updates back to chat/Slack |
| `AuditEntry` | Immutable record of every action |

---

## Detailed Flow

### Step 1: Chat Session & Project Selection

When the ChatRouter classifies a message as a workflow trigger (e.g. `feature_to_pr`), and the `ChatSession` has **no `project_id` set**, the system must:

- Prompt the user: _"Which project is this for?"_
- Present available projects (from ProjectStore) as selectable options
- Once the user selects, create/update the `ChatSession` with that `project_id`
- Create an `AuditEntry` recording the project selection

If the `ChatSession` already has a `project_id`, skip to Step 2.

### Step 2: Repository & Credential Resolution

Using the selected project's `repo_ids` and `credential_ids`:

- Look up all `Repository` records (URLs, default branches, providers)
- For multi-repo projects, determine the **primary repo** (first in `repo_ids`, or let the user pick)
- Resolve `Credential` records for authenticated git access
- Validate that at least one credential covers the target repo (`credential.repo_ids` empty = all repos, or matching `repo_id`)
- Fail gracefully with a chat message if repos or credentials are missing

### Step 3: Work Item & Pipeline Creation

Before starting the sandbox:

- Create a `WorkItem` (type=FEATURE, status=OPEN, linked to `project_id`)
- Create a `PipelineRun` linked to the `WorkItem`, `WorkflowDefinitionRecord`, and `Environment`
- Create a `Trigger` record (type=MANUAL, from chat session)
- Initialize `Stage` records for each step in the workflow definition
- Emit an `AuditEntry` for pipeline creation

### Step 4: Sandbox Provisioning & Repo Clone

- Resolve the target `Environment` and its `Variable` records (inject as env vars into sandbox)
- Create a Docker sandbox via `SandboxManager.create()` with:
  - `network_enabled=True` (needed for git clone)
  - `environment` populated from `Variable` records (excluding secrets passed separately)
  - Credential injected via git config or env var inside the container
- Clone the repository into the sandbox workspace:
  - Use `RepoProvider.clone_repo(url, branch, target_dir)` or execute `git clone` inside the sandbox
  - Clone the project's `default_branch`
  - Create a feature branch (e.g. `lintel/feat/<work_item_id>`)
- Disable network after clone (principle of least privilege)
- Update `Stage` status for the setup step

### Step 5: Workflow Execution

Run the workflow defined by the `WorkflowDefinitionRecord` (resolved via `PipelineRun.workflow_definition_id`):

- Each `WorkflowStepConfig` in the definition binds a node to an agent, model, and provider
- For each step:
  - Create an `AgentSession` tracking messages, tool calls, and token usage
  - The agent operates on code inside the sandbox via tool calls
  - Update the corresponding `Stage` status and duration
  - If `WorkflowStepConfig.requires_approval` is true, create an `ApprovalRequest` and pause
  - Fire `NotificationRule` events for progress updates back to chat
- Apply `Policy` rules at approval gates (auto-approve, require approval, block)

### Step 6: Testing

- Execute tests inside the sandbox via `SandboxManager.execute()`
- Parse output into a `TestResult` (verdict, pass/fail counts, failures)
- Store result on the test `Stage`
- If tests fail, notify user in chat and optionally allow retry

### Step 7: Artifacts & PR

- Collect `CodeArtifact` records via `SandboxManager.collect_artifacts()` (git diff)
- Push the feature branch and create a PR via `RepoProvider.create_pr()`
- Update `WorkItem` with `branch_name` and `pr_url`
- Update `PipelineRun` status to SUCCEEDED (or FAILED)
- Post the PR link back to the chat conversation via `NotificationRule`
- Create `AuditEntry` for PR creation
- Destroy the sandbox

---

## What's Missing / Open Questions

### Must Address

| # | Gap | Current State | Needed |
|---|-----|--------------|--------|
| 1 | **ChatSession creation in chat flow** | `ChatSession` type exists but chat routes use ad-hoc conversation dicts | Wire `ChatSession` into chat route lifecycle; use it to track project binding |
| 2 | **Project selection prompt in ChatRouter** | ChatRouter classifies intent but doesn't check for project context | Add a "needs project" state that prompts the user before dispatching workflow |
| 3 | **Credential resolution & injection** | `Credential` type exists, `credential_ids` on Project, but nothing wires tokens into sandbox | Resolve credentials, match to repo via `repo_ids`, inject into sandbox env/git config |
| 4 | **WorkItem + PipelineRun creation** | Types exist but no creation logic in the workflow trigger path | Create WorkItem, PipelineRun, Trigger, and Stage records when workflow starts |
| 5 | **Clone step in workflow** | `implement` node creates a sandbox but doesn't clone a repo | Add a `setup_workspace` node that clones repo and creates feature branch |
| 6 | **Agent tool loop** | `implement.py` has `# TODO: Wire agent tool loop here` | Agents need sandbox tools (read/write/execute) exposed via `AgentSession` |
| 7 | **Network lifecycle in sandbox** | Sandbox is created with network on or off, no toggle | Add ability to enable network for clone, then restrict for execution |
| 8 | **Test node → TestResult** | Test node is a stub returning hardcoded pass | Wire to `sandbox.execute()`, parse output into `TestResult` |
| 9 | **Review node → AgentSession** | Review node returns hardcoded "LGTM" | Wire to reviewer agent with sandbox file access, track in `AgentSession` |
| 10 | **Stage status tracking** | `Stage` type exists but nodes don't update stage status | Each workflow node should update its corresponding `Stage` record |

### Should Address

| # | Gap | Notes |
|---|-----|-------|
| 11 | **Environment & Variable wiring** | `Environment` and `Variable` types exist but aren't passed to sandbox creation | Resolve env for the pipeline run, inject variables as sandbox env vars |
| 12 | **NotificationRule integration** | Type exists but no notification dispatch in workflow nodes | Fire notifications at phase transitions (plan ready, tests passed, PR created) |
| 13 | **Policy enforcement at gates** | `Policy` type exists but approval gates don't check policies | Apply policy rules to decide auto-approve vs require-human at each gate |
| 14 | **AuditEntry emission** | Type exists but no audit trail in workflow path | Emit entries for key actions (pipeline start, approval, PR creation) |
| 15 | **Branch naming strategy** | Need convention for feature branches (e.g. `lintel/feat/<short-desc>`) |
| 16 | **Conflict handling** | What if `default_branch` has moved since clone? Rebase strategy? |
| 17 | **Progress reporting to chat** | User should see status updates as each workflow phase completes |
| 18 | **Failure recovery** | If a node fails mid-workflow, can the user retry? (LangGraph checkpointing supports this) |
| 19 | **Multi-repo clone strategy** | Project now supports `repo_ids` (plural) — which repo(s) to clone into sandbox? |

### Nice to Have

| # | Gap | Notes |
|---|-----|-------|
| 20 | **Caching clones** | Shallow clone every time is slow for large repos. Consider volume-mounted cached clones |
| 21 | **Monorepo support** | Scope sandbox working directory to a subdirectory |
| 22 | **Custom test/build commands** | Store per-project test/lint/build commands (could use `Environment.config` or `Variable`) |
| 23 | **PR template from plan** | Generate PR description from plan `Stage` outputs + `CodeArtifact` summary |
| 24 | **Token budget tracking** | Use `AgentSession.token_usage` to enforce per-pipeline token limits |

---

## Affected Components

- `src/lintel/domain/chat_router.py` — Add project selection flow, ChatSession integration
- `src/lintel/api/routes/chat.py` — Wire ChatSession lifecycle, handle "awaiting project" state
- `src/lintel/contracts/types.py` — No changes needed (types already exist)
- `src/lintel/workflows/nodes/` — New `setup_workspace` node; wire `implement`, `test`, `review` to sandbox + AgentSession
- `src/lintel/workflows/feature_to_pr.py` — Insert `setup_workspace` node, add Stage tracking
- `src/lintel/infrastructure/sandbox/docker_backend.py` — Credential injection, network toggling, Variable injection
- `src/lintel/infrastructure/repos/github_provider.py` — Clone-inside-sandbox support
- `src/lintel/domain/` — WorkItem/PipelineRun/Stage creation logic
- `src/lintel/projections/` — Read-side projections for pipeline status, work item status
