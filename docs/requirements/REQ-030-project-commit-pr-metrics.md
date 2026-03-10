# REQ-030: Project Commit & PR Metrics Dashboard

**Status:** Proposed
**Priority:** Medium
**Category:** Observability / UI

## Problem

There is no visibility into the output velocity of projects managed by Lintel. Teams cannot see how many PRs are being opened, how many commits are landing, or what proportion of work is AI-generated vs human-authored. This data is essential for understanding ROI and spotting bottlenecks.

## Proposed Solution

Track commits and PRs per project from GitHub (via webhooks or polling), classify each as AI or human authored, and surface metrics on the project dashboard.

### Requirements

1. **Data collection:** Monitor GitHub repos linked to each project for commits (merged to default branch) and pull requests (opened, merged, closed).
2. **AI vs human classification:** Classify each commit/PR as AI-authored, human-authored, or co-authored based on:
   - Commit author/committer (e.g., bot accounts, `Co-Authored-By: Claude` trailers)
   - PR author (bot users, Lintel-created PRs)
   - Presence of AI-generated markers in commit messages
3. **Metrics stored:**
   - Commits merged per day (total, AI, human)
   - PRs opened per day (total, AI, human)
   - PRs merged per day (total, AI, human)
   - PRs closed without merge per day
4. **Dashboard UI:**
   - Per-project metrics page with date range selector
   - Daily bar chart: commits by AI vs human
   - Daily bar chart: PRs opened/merged by AI vs human
   - Summary cards: total PRs, total commits, AI %, human % (for selected period)
   - Trend line: rolling 7-day average
5. **Aggregation:** Global dashboard view across all projects for org-level metrics.
6. **Refresh:** Near real-time via GitHub webhooks (preferred) or polling every 5 minutes.

### Data Model

```python
@dataclass(frozen=True)
class CommitMetric:
    project_id: str
    repo: str
    sha: str
    author: str
    author_type: AuthorType  # AI | HUMAN | CO_AUTHORED
    merged_at: datetime
    branch: str

@dataclass(frozen=True)
class PullRequestMetric:
    project_id: str
    repo: str
    pr_number: int
    author: str
    author_type: AuthorType
    opened_at: datetime
    merged_at: datetime | None
    closed_at: datetime | None
    status: PRStatus  # OPEN | MERGED | CLOSED

class AuthorType(str, Enum):
    AI = "ai"
    HUMAN = "human"
    CO_AUTHORED = "co_authored"
```

### API Endpoints

```
GET /api/v1/projects/{project_id}/metrics/commits?from=&to=&granularity=day
GET /api/v1/projects/{project_id}/metrics/prs?from=&to=&granularity=day
GET /api/v1/metrics/summary?from=&to=  # org-wide
```

### GitHub Integration

- **Webhook events:** `push` (commits on default branch), `pull_request` (opened/closed/merged)
- **Fallback:** Poll `GET /repos/{owner}/{repo}/commits` and `GET /repos/{owner}/{repo}/pulls` on a schedule
- Ties into existing REQ-026 (Git Event Listeners) infrastructure

### AI Author Detection Heuristics

1. Commit `Co-Authored-By` trailer contains known AI identifiers (Claude, Copilot, etc.)
2. Commit author email matches configured bot accounts
3. PR was created by Lintel pipeline (tracked via `pipeline_run_id` in PR body/metadata)
4. Configurable per-project allow-list of bot usernames

## Depends On

- REQ-026 (Git Event Listeners — webhook infrastructure)

## Future Extensions

- Lines changed per day (AI vs human)
- Review turnaround time metrics
- Deployment frequency correlation
- Per-agent metrics (which AI agent produced which commits)
- Export to CSV / analytics integrations
