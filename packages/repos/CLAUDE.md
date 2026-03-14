# lintel-repos

Repository access — GitHub provider and in-memory store.

## Key exports

- `GitHubRepoProvider` — implements `RepoProvider` protocol; uses `git` CLI subprocess + GitHub REST API via `httpx`; supports clone, fetch, push, PR creation, and branch operations
- `InMemoryRepositoryStore` — implements `RepositoryStore` protocol; dict-backed store with `get`, `get_by_url`, `add`, `remove`, `list`

## Dependencies

- `lintel-contracts` — `Repository`, `RepoProvider`, `RepositoryStore` protocols
- `httpx>=0.28`, `structlog>=24.4`

## Tests

```bash
make test-repos
# or: uv run pytest packages/repos/tests/ -v
```

## Usage

```python
from lintel.repos.github_provider import GitHubRepoProvider
from lintel.repos.repository_store import InMemoryRepositoryStore

provider = GitHubRepoProvider(token="ghp_...", api_base="https://api.github.com")
pr_url = await provider.create_pull_request(repo_url, branch, title, body)

store = InMemoryRepositoryStore()
await store.add(repository)
repo = await store.get_by_url("https://github.com/org/repo")
```
