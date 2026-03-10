# REQ-027: Automated Tech Stack Discovery & Maintenance

## Summary

Lintel should automatically discover, store, and maintain a project's tech stack profile. This enables context-aware agent behaviour — better code generation, review, and workflow orchestration tailored to each project's actual tooling.

## Motivation

Today, tech stack manifests (like `docs/tech-stack/api.yaml`) are hand-crafted. For Lintel to work effectively on external projects, it needs to understand their tech stack without manual setup. A project's tech stack also drifts over time — dependencies get added/removed, versions change, patterns evolve. Keeping the profile current is as important as initial discovery.

## Key Decisions & Trade-offs

### Storage: Codebase file vs Database

| Approach | Pros | Cons |
|----------|------|------|
| **Codebase file** (e.g. `.lintel/tech-stack.yaml` committed to repo) | Versioned with code; visible to developers; portable; works offline; reviewable in PRs | Requires write access to repo; merge conflicts; stale if not updated |
| **Database** (stored in Lintel's Postgres) | No repo write access needed; central query/compare across projects; richer metadata | Invisible to developers; can drift from reality; extra infra dependency |
| **Hybrid** (DB as source of truth, optional export to repo) | Best of both; DB for agents, file for humans | More complexity; sync logic needed |

**Recommendation:** Hybrid. Store in the database as the canonical source (linked to `project_id`). Optionally export to `.lintel/tech-stack.yaml` in the repo if the project opts in. The DB record is what agents query at runtime; the file is a convenience for human review.

### Discovery: When and how

| Trigger | Mechanism |
|---------|-----------|
| **On project creation** | Automatic — run discovery as part of project onboarding |
| **On git push/PR** (REQ-026) | Diff-aware — only re-scan if dependency files changed (`package.json`, `pyproject.toml`, `Cargo.toml`, etc.) |
| **Manual** | Chat command: "refresh tech stack" or workflow trigger |
| **Scheduled** | Periodic (e.g. weekly) re-scan for drift detection |

### Scope of discovery

What to detect:
- **Languages** — from file extensions, shebang lines, config files
- **Package managers** — npm/yarn/pnpm/bun, pip/uv/poetry, cargo, go mod, etc.
- **Frameworks** — from dependency declarations + import analysis
- **Dev tooling** — linters, formatters, test runners, type checkers (from config files)
- **CI/CD** — GitHub Actions, GitLab CI, CircleCI, etc. (from workflow files)
- **Infrastructure** — Docker, Terraform, Pulumi, K8s manifests
- **Patterns** — monorepo detection, workspace structure, architecture hints

What NOT to detect (too speculative):
- Runtime performance characteristics
- Business domain classification
- Code quality scores (that's the reviewer's job)

---

## Requirements

### REQ-027.1: Tech Stack Discovery Agent

Create a discovery workflow/agent that analyses a repository and produces a tech stack profile.

**Inputs:**
- Repository reference (local path or clone URL)
- Optional: existing profile to update (for incremental mode)

**Discovery strategy (ordered by reliability):**
1. **Dependency files** — `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `Gemfile`, `pom.xml`, `build.gradle`, `pubspec.yaml`, `composer.json`
2. **Lock files** — for precise version resolution (`uv.lock`, `package-lock.json`, `Cargo.lock`, `go.sum`)
3. **Config files** — `tsconfig.json`, `ruff.toml`, `.eslintrc`, `mypy.ini`, `jest.config.*`, `vite.config.*`, `next.config.*`, `.prettierrc`
4. **CI/CD files** — `.github/workflows/*.yml`, `.gitlab-ci.yml`, `.circleci/config.yml`, `Jenkinsfile`
5. **Infra files** — `Dockerfile`, `docker-compose.yml`, `*.tf`, `Pulumi.yaml`, `k8s/`
6. **Build files** — `Makefile`, `Taskfile.yml`, `justfile`, `Rakefile`
7. **Monorepo signals** — `workspaces` in package.json, `pnpm-workspace.yaml`, `Cargo.toml` with `[workspace]`, `lerna.json`

**Output:** A `TechStackProfile` matching the existing manifest schema (see `docs/tech-stack/*.yaml`), extended with:
- `discovered_at: datetime` — when the scan ran
- `source_commit: str` — git SHA at time of discovery
- `confidence: float` — per-framework confidence score (0-1)
- `tech_areas: list` — multiple areas if monorepo (e.g. `api`, `web`, `mobile`)

### REQ-027.2: Tech Stack Storage

**Domain types:**
```python
@dataclass(frozen=True)
class TechStackProfile:
    project_id: str
    tech_area: str              # "api", "web", "mobile", "infra", etc.
    display_name: str
    description: str
    frameworks: tuple[FrameworkEntry, ...]
    dev_tooling: DevTooling
    deployment: DeploymentInfo | None
    pattern_categories: tuple[str, ...]
    discovered_at: datetime
    source_commit: str
    version: int                # Incremented on each update

@dataclass(frozen=True)
class FrameworkEntry:
    name: str
    version: str
    context7_library_id: str    # Auto-resolved via Context7
    confidence: float           # How confident the detection is
    detected_from: str          # e.g. "pyproject.toml", "import analysis"
```

**Storage protocol:**
```python
class TechStackStore(Protocol):
    async def save(self, profile: TechStackProfile) -> None: ...
    async def get(self, project_id: str, tech_area: str) -> TechStackProfile | None: ...
    async def list_areas(self, project_id: str) -> list[TechStackProfile]: ...
    async def delete(self, project_id: str, tech_area: str) -> None: ...
```

Implementations: `InMemoryTechStackStore`, `PostgresTechStackStore`.

### REQ-027.3: Incremental Updates

When dependency files change (detected via git diff or file watcher):
1. Load the existing profile from the store
2. Re-scan only the changed files
3. Merge: add new frameworks, update versions, remove frameworks no longer present
4. Bump `version`, update `discovered_at` and `source_commit`
5. Emit `TechStackUpdated` event with a diff summary

### REQ-027.4: Context7 Auto-Resolution

After discovery, attempt to resolve `context7_library_id` for each detected framework:
- Call `resolve-library-id` with the framework name
- Store the result (or empty string if resolution fails)
- This enables downstream agents to fetch up-to-date docs automatically

### REQ-027.5: Export to Repository (Optional)

If a project opts in (`project.settings.export_tech_stack = True`):
- Write the profile as `.lintel/tech-stack/<area>.yaml` in the manifest format
- Create a PR or commit to a branch (never force-push to main)
- Include a summary of what changed

### REQ-027.6: Agent Integration

Agents should be able to query the tech stack at runtime:
- `get_tech_stack(project_id)` — returns all areas
- Used by: code generation (pick right idioms), review (check for anti-patterns), planning (understand architecture)
- Exposed as MCP resource: `lintel://projects/{project_id}/tech-stack`

---

## Events

| Event | Payload | When |
|-------|---------|------|
| `TechStackDiscovered` | `project_id`, `tech_areas`, `framework_count` | First scan completes |
| `TechStackUpdated` | `project_id`, `tech_area`, `added`, `removed`, `updated` | Incremental update |
| `TechStackResolutionFailed` | `project_id`, `reason` | Discovery couldn't parse the repo |

---

## Non-Goals (for now)

- **Cross-project analytics** ("which projects use React 18?") — useful but Phase 2
- **Migration recommendations** ("you should upgrade to Pydantic v2") — separate feature
- **Security vulnerability scanning** — defer to dedicated tools (Dependabot, Snyk)
- **LLM-based detection** — start with deterministic parsing; add LLM fallback later if needed for exotic setups

## Dependencies

- `Project` entity (existing)
- REQ-026 (git event listeners) for push-triggered updates
- Context7 MCP server for library ID resolution
- Existing tech stack manifest schema (`docs/tech-stack/*.yaml`)

## Implementation Notes

- The discovery logic should be a standalone module (`src/lintel/skills/tech_stack_discovery.py`) that can run in or out of a workflow
- Monorepo detection should produce multiple `TechStackProfile` entries (one per area)
- For the deterministic parser, consider using existing ecosystem tools where possible (e.g. `importlib.metadata`, `tomllib`, `json`) rather than regex
