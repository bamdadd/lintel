# Implementation Log

## Phases 2-5: Extract domain, agents, infrastructure, workflows packages

### Completed Steps

1. **Phase 2: Extract domain (+ merge skills)** — committed as `c512649`
   - Created `packages/domain/` with `lintel-domain` package
   - Moved `lintel.domain` source and tests from `packages/app/`
   - Merged `lintel.skills` into `lintel.domain.skills/`
   - Updated all `lintel.skills.*` imports to `lintel.domain.skills.*` in:
     - `workflows/nodes/implement.py`
     - `workflows/nodes/test_code.py`
     - `tests/workflows/test_artifact_persistence.py`
     - `tests/workflows/test_test_code.py`
     - `tests/skills/test_discover_test_command.py`
   - Added `lintel-domain = { workspace = true }` to `packages/app`

2. **Phase 3: Extract agents** — committed as `379b030`
   - Created `packages/agents/` with `lintel-agents` package
   - Moved `lintel.agents` source and tests from `packages/app/`
   - `lintel.infrastructure.mcp.tool_client` import in `runtime.py` is TYPE_CHECKING-only — no runtime dep on infrastructure
   - Added `lintel-agents = { workspace = true }` to `packages/app`

3. **Phase 4: Extract infrastructure** — committed as `5042731` + `bea6869`
   - Created `packages/infrastructure/` with `lintel-infrastructure` package
   - Moved all heavy deps there: asyncpg, sqlalchemy, presidio, litellm, slack, opentelemetry, cryptography, nats, boto3, fastapi-mcp
   - Moved infrastructure-related test dirs: channels, persistence, projections, repo, sandbox
   - Removed empty `packages/app/src/lintel/projections/` stub
   - Trimmed `packages/app` deps to fastapi, uvicorn, langgraph + workspace members
   - Fixed double-nesting in `packages/infrastructure/tests/infrastructure/` (a `git mv` artifact)

4. **Phase 5: Extract workflows** — committed as `da25dae`
   - Created `packages/workflows/` with `lintel-workflows` package
   - Moved `lintel.workflows` source and tests from `packages/app/`
   - Fixed cross-test import: `tests.workflows.test_implement_node` → `workflows.test_implement_node`
   - Added `lintel-workflows = { workspace = true }` to `packages/app`

5. **Makefile + testpaths** — committed as `d82a41e`
   - Added per-package make targets: `test-domain`, `test-agents`, `test-infrastructure`, `test-workflows`
   - Updated `test-unit` and `test-postgres` to cover all packages
   - Expanded `typecheck` target to include all new packages
   - Updated `pytest.ini_options.testpaths` in root `pyproject.toml`

### Deviations from Plan

- **Double-nesting on `git mv` of directories**: When moving a directory `foo/` to a destination that ends in `foo/`, git creates `destination/foo/foo/`. Fixed by moving contents up one level after each package extraction. This affected domain, infrastructure, and workflows. The agents package (only 3 files) was moved file-by-file and didn't hit this issue.
- **`test-postgres` target**: Updated to run across all package test dirs (not just `packages/app/tests/`).

### Files Created

- `/Users/bamdad/projects/lintel/packages/domain/pyproject.toml` — lintel-domain package definition
- `/Users/bamdad/projects/lintel/packages/agents/pyproject.toml` — lintel-agents package definition
- `/Users/bamdad/projects/lintel/packages/infrastructure/pyproject.toml` — lintel-infrastructure package definition
- `/Users/bamdad/projects/lintel/packages/workflows/pyproject.toml` — lintel-workflows package definition

### Test Results

- 1151 tests passing, 74 skipped
- All packages resolve correctly as namespace packages under `lintel.*`

### Notes for Reviewer

- The `packages/` glob in pytest (e.g. `uv run pytest packages/ -x -q`) will also collect `packages/workflows/src/lintel/workflows/nodes/test_code.py` which is production code named with a `test_` prefix. Always use explicit test directory paths (as the Makefile targets do) to avoid this.
- `lintel.domain.skills` was previously `lintel.skills` — all internal references updated. No public API change since skills was always an internal module.
