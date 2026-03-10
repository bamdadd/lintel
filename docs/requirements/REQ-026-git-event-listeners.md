# REQ-026: Git Event Listeners — Commit & PR Review Workflows

## Summary

Enable Lintel to listen for git events (commits pushed, PRs opened/updated) on project repositories and automatically trigger review workflows that post feedback.

## Motivation

Currently workflows are triggered manually via chat or Slack threads. Projects should be able to configure automatic triggers so that every PR or push to a watched branch runs a code review workflow, with feedback written back as PR comments.

## Dependencies

- **Existing:** `TriggerType.PR_EVENT`, `Repository`, `RepoProvider` protocol, `WorkflowHook`, `Trigger`
- **Planned:** `Integration` entity (ENT-7), `CredentialType.GITLAB_TOKEN` (ENT-M7)
- **Builds on:** INT-1.4 (webhook receivers) from `integrations.md`

---

## Requirements

### REQ-026.1: Webhook Receiver Endpoints

Create two webhook endpoints that receive events from git providers:

**`POST /api/v1/webhooks/github`**
- Verify signature via `X-Hub-Signature-256` header using the integration's webhook secret
- Parse event type from `X-GitHub-Event` header
- Handle events:
  - `push` → extract commits, branch, repo URL
  - `pull_request` (actions: `opened`, `synchronize`, `reopened`) → extract PR metadata, diff URL, head/base refs
  - `pull_request_review` → track external review status
- Return `200 OK` immediately, process asynchronously

**`POST /api/v1/webhooks/gitlab`**
- Verify token via `X-Gitlab-Token` header
- Handle events:
  - `push` → extract commits, branch, repo URL
  - `merge_request` (actions: `open`, `update`, `reopen`) → extract MR metadata
- Return `200 OK` immediately, process asynchronously

### REQ-026.2: Git Event Domain Events

New domain events in `contracts/events.py`:

```python
@dataclass(frozen=True)
class CommitPushed:
    """One or more commits pushed to a branch."""
    repo_url: str
    branch: str
    commits: tuple[dict[str, object], ...]  # [{sha, message, author, timestamp}]
    pusher: str
    provider: str  # "github" | "gitlab"

@dataclass(frozen=True)
class PullRequestOpened:
    """A new PR/MR was opened or updated."""
    repo_url: str
    pr_number: int
    title: str
    description: str
    author: str
    head_branch: str
    base_branch: str
    diff_url: str
    html_url: str
    action: str  # "opened" | "synchronize" | "reopened"
    provider: str
    head_sha: str

@dataclass(frozen=True)
class PRReviewPosted:
    """Lintel posted a review on a PR."""
    repo_url: str
    pr_number: int
    run_id: str
    summary: str
    comments_count: int
```

### REQ-026.3: Git Event Trigger Handler

Extend `TriggerHandler` with:

```python
async def handle_push_event(self, event: CommitPushed) -> str | None:
    """Match push event against project triggers, dispatch workflows."""

async def handle_pr_event(self, event: PullRequestOpened) -> str | None:
    """Match PR event against project triggers, dispatch review workflow."""
```

**Matching logic:**
1. Look up `Repository` by `repo_url` (via `RepositoryStore.get_by_url()`)
2. Find `Project` linked to that repository (via `project.repo_ids`)
3. Find enabled `Trigger` entities for that project where `trigger_type == PR_EVENT`
4. Check trigger `config` for branch filters (e.g., `{"branches": ["main", "develop"], "ignore_drafts": true}`)
5. If matched, dispatch `StartWorkflow` command with `workflow_type="pr_review"`

### REQ-026.4: PR Review Workflow

New workflow type: `pr_review`

**Stages:**
1. **fetch** — Clone repo, checkout PR branch, compute diff
2. **analyse** — Analyze changed files: complexity, test coverage impact, security patterns
3. **review** — AI reviewer agent examines diff with project context, generates review comments
4. **post_feedback** — Write review back to the PR via `RepoProvider.add_review()`

**Inputs (via StartWorkflow command):**
- `repo_url` — which repo
- `pr_number` — PR to review
- `head_sha` — commit to review
- `diff_url` — URL to fetch the diff
- `base_branch` — target branch for context

**Agent roles used:** `reviewer` (primary), optionally `security_auditor` for security-focused review

### REQ-026.5: Review Feedback via RepoProvider

Extend `RepoProvider` protocol with:

```python
async def add_review(
    self,
    repo_url: str,
    pr_number: int,
    body: str,
    comments: list[dict[str, Any]],  # [{path, line, body}]
    event: str = "COMMENT",  # "APPROVE" | "REQUEST_CHANGES" | "COMMENT"
) -> str: ...

async def get_pr_diff(self, repo_url: str, pr_number: int) -> str: ...

async def get_pr_files(self, repo_url: str, pr_number: int) -> list[dict[str, Any]]: ...
```

Implement in `GitHubRepoProvider`:
- `add_review` → `POST /repos/{owner}/{repo}/pulls/{pr_number}/reviews`
- `get_pr_diff` → `GET /repos/{owner}/{repo}/pulls/{pr_number}` with `Accept: application/vnd.github.diff`
- `get_pr_files` → `GET /repos/{owner}/{repo}/pulls/{pr_number}/files`

### REQ-026.6: Trigger Configuration

Users configure git event triggers via the existing trigger CRUD API:

```python
Trigger(
    trigger_id="trg-pr-review-001",
    project_id="proj-001",
    trigger_type=TriggerType.PR_EVENT,
    name="Auto-review PRs to main",
    config={
        "events": ["pull_request"],           # or ["push", "pull_request"]
        "branches": ["main", "develop"],      # target branches to watch
        "ignore_drafts": True,
        "ignore_bots": True,                  # skip dependabot etc.
        "workflow_type": "pr_review",         # which workflow to run
        "review_mode": "comment",             # "comment" | "request_changes" | "approve"
        "agents": ["reviewer"],               # which agent roles to use
    },
    enabled=True,
)
```

For push/commit triggers:

```python
Trigger(
    trigger_id="trg-commit-review-001",
    project_id="proj-001",
    trigger_type=TriggerType.PR_EVENT,  # reuse PR_EVENT or add PUSH_EVENT
    name="Review commits on main",
    config={
        "events": ["push"],
        "branches": ["main"],
        "workflow_type": "commit_review",
        "min_files_changed": 1,               # skip empty commits
    },
    enabled=True,
)
```

### REQ-026.7: Webhook Registration API

Endpoint for users to register/manage webhook configuration:

**`POST /api/v1/projects/{project_id}/webhooks`**
- Generates a webhook secret
- Returns the webhook URL and secret for the user to configure in GitHub/GitLab
- Stores secret in `Integration.config.webhook_secret`

**`GET /api/v1/projects/{project_id}/webhooks`**
- List configured webhooks with status (last received event, error count)

**`DELETE /api/v1/projects/{project_id}/webhooks/{webhook_id}`**
- Disable and remove webhook configuration

### REQ-026.8: Idempotency & Deduplication

- Store `(repo_url, pr_number, head_sha)` as deduplication key
- If a `synchronize` event arrives for the same `head_sha` that's already being reviewed, skip
- If a new `head_sha` arrives while a review is in progress, cancel the in-flight review and start a new one
- Use `EventEnvelope.correlation_id` to link all events in a single PR review lifecycle

### REQ-026.9: TriggerType Enum Extension

Add to `TriggerType`:

```python
class TriggerType(StrEnum):
    SLACK_MESSAGE = "slack_message"
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    PR_EVENT = "pr_event"
    PUSH_EVENT = "push_event"    # NEW
    MANUAL = "manual"
```

This distinguishes push-triggered workflows from PR-triggered ones in trigger config and event routing.

---

## Data Flow

```
GitHub/GitLab
    │
    ▼
POST /api/v1/webhooks/github
    │
    ├── Verify signature
    ├── Parse event type + payload
    ├── Emit CommitPushed or PullRequestOpened event
    │
    ▼
TriggerHandler.handle_pr_event() / handle_push_event()
    │
    ├── Lookup Repository by repo_url
    ├── Find Project by repo_id
    ├── Match enabled Triggers (branch filter, event type)
    │
    ▼
StartWorkflow(workflow_type="pr_review", repo_url=..., pr_number=...)
    │
    ▼
WorkflowExecutor → pr_review graph
    │
    ├── fetch: clone repo, get diff
    ├── analyse: code analysis
    ├── review: AI review with reviewer agent
    └── post_feedback: RepoProvider.add_review()
    │
    ▼
PRReviewPosted event
    │
    ▼
PR comment visible on GitHub/GitLab
```

---

## Non-Functional Requirements

- **Latency:** Webhook response < 500ms (async processing). Full review posted within 2-5 minutes.
- **Retry:** Failed webhook processing retried 3x with exponential backoff.
- **Security:** Webhook signature verification is mandatory. Reject unsigned requests.
- **Rate limiting:** Max 10 concurrent review workflows per project to prevent resource exhaustion.
- **Audit:** All webhook events logged as domain events in the event store for traceability.

---

## Implementation Priority

| Phase | Scope |
|---|---|
| **P0** | GitHub webhook receiver, PR event handling, `pr_review` workflow, feedback via `add_review` |
| **P1** | GitLab webhook receiver, push/commit event handling, `commit_review` workflow |
| **P1** | Webhook management API, deduplication, cancellation of stale reviews |
| **P2** | Configurable review agents (security_auditor, performance), multi-provider webhook auto-setup via API |

---

## Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| `src/lintel/api/routes/webhooks.py` | Create | Webhook receiver endpoints |
| `src/lintel/contracts/events.py` | Modify | Add `CommitPushed`, `PullRequestOpened`, `PRReviewPosted` |
| `src/lintel/contracts/types.py` | Modify | Add `PUSH_EVENT` to `TriggerType` |
| `src/lintel/domain/trigger_handler.py` | Modify | Add `handle_push_event`, `handle_pr_event` |
| `src/lintel/contracts/protocols.py` | Modify | Add `add_review`, `get_pr_diff`, `get_pr_files` to `RepoProvider` |
| `src/lintel/infrastructure/repos/github_provider.py` | Modify | Implement new `RepoProvider` methods |
| `src/lintel/workflows/graphs/pr_review.py` | Create | PR review workflow graph |
| `src/lintel/workflows/nodes/fetch.py` | Create | Fetch/diff node for PR review |
| `src/lintel/workflows/nodes/post_feedback.py` | Create | Post review comments node |
| `src/lintel/api/routes/webhook_management.py` | Create | Webhook registration/management API |
| `tests/unit/api/test_webhooks.py` | Create | Webhook endpoint tests |
| `tests/unit/domain/test_trigger_handler_git.py` | Create | Git event trigger handler tests |
| `tests/integration/test_pr_review_workflow.py` | Create | End-to-end PR review test |
