# Decision Context

## C.1 Detailed Comparison Matrix

| Option | Clean Code (0.40) | Industry Alignment (0.30) | Codebase Fit (0.20) | Risk (0.10) | Total |
|--------|-------------------|--------------------------|---------------------|-------------|-------|
| A: Minimal Fix | 5/10 (2.0) | 4/10 (1.2) | 9/10 (1.8) | 9/10 (0.9) | **5.9** |
| B: Consolidate+Extend | 9/10 (3.6) | 9/10 (2.7) | 8/10 (1.6) | 7/10 (0.7) | **8.6** |
| C: Single-Primitive | 7/10 (2.8) | 8/10 (2.4) | 6/10 (1.2) | 8/10 (0.8) | **7.2** |
| D: Full Runtime | 8/10 (3.2) | 7/10 (2.1) | 4/10 (0.8) | 5/10 (0.5) | **6.6** |

### Scoring Rationale

**Option A: Minimal Fix** (5.9)
- Clean Code 5/10: Fixes method names but leaves Protocol with primitive params, keeps redundant `CommandResult`, no lifecycle [CLEAN-01, CLEAN-03]
- Industry 4/10: No file I/O, no lifecycle, no timeout — below every production system [WEB-08, E2B-03]
- Fit 9/10: Smallest change, follows existing patterns
- Risk 9/10: Very low risk, very limited scope

**Option B: Consolidate+Extend** (8.6)
- Clean Code 9/10: Addresses all 14 CLEAN findings, typed params, lifecycle, error hierarchy [CLEAN-01 through CLEAN-14]
- Industry 9/10: Matches E2B/OpenHands feature set, typed file I/O [E2B-03, OH-01]
- Fit 8/10: Uses existing types, follows Protocol convention, extends naturally [REPO-02]
- Risk 7/10: Moderate scope, Docker tar API adds complexity [DOCKER-03]

**Option C: Single-Primitive** (7.2)
- Clean Code 7/10: Clean minimal interface, but file I/O via shell is fragile [WEB-08]
- Industry 8/10: Matches LangChain DeepAgents exactly [WEB-09]
- Fit 6/10: Mixin pattern (BaseSandboxOperations) is foreign to Lintel's Protocol-only approach
- Risk 8/10: Small surface area, proven pattern

**Option D: Full Runtime** (6.6)
- Clean Code 8/10: Most type-safe with per-operation result types [OH-01]
- Industry 7/10: Matches OpenHands but not the broader consensus
- Fit 4/10: Action/Observation pattern very different from Lintel's named-method conventions
- Risk 5/10: Large implementation, complex dispatch, over-engineered for current scale

## C.2 Rejected Options Analysis

### Option A: Minimal Fix
**Why rejected**: While safe and fast, it leaves Lintel below the minimum viable abstraction for multi-backend support. No file I/O means agents must construct fragile shell commands. No lifecycle management means container leaks. Would require immediate follow-up work, making the "minimal" label misleading.

**Would be viable if**: Timeline was extremely tight (< 1 day) and only Docker backend was ever needed.

### Option C: Single-Primitive (LangChain Style)
**Why rejected**: The mixin pattern (`BaseSandboxOperations` providing `read_file`/`write_file` via `execute("cat ...")`) introduces a second abstraction layer alongside the Protocol. Lintel's architecture uses Protocols exclusively — adding a mixin is a pattern break. Shell-based file I/O is also fragile for binary files and encoding edge cases.

**Would be viable if**: Lintel expected 5+ backend implementations and wanted to minimize per-backend effort.

### Option D: Full Runtime (OpenHands Style)
**Why rejected**: The Action/Observation type system with pattern-matching dispatch adds significant complexity (15+ new types) for a system that currently has 1 backend and 6 agent roles. The extensibility benefits don't justify the cost at Lintel's current scale.

**Would be viable if**: Lintel was a general-purpose agent platform with plugin authors implementing custom actions.

## C.3 Trade-off Deep Dive

### Typed File I/O vs Shell-Based File I/O
Option B adds `read_file`, `write_file`, `list_files` as Protocol methods. Option C derives these from `execute("cat ...")`.

**Why typed wins**:
- Cloud backends (E2B, Modal) have native file APIs that are faster and more reliable [E2B-03]
- Shell-based file I/O fails on binary files, files with special characters, very large files
- Explicit Protocol methods are self-documenting and type-checkable
- Docker backend can use `put_archive`/`get_archive` (more robust than shell) [DOCKER-03]

**Cost**: Each backend must implement 3 extra methods. For Docker, this means tar archive handling (~30 lines).

### More Methods vs Fewer Methods
Option B has ~8 methods. Option C has ~4. Option A has ~4.

**Why more is acceptable**:
- Lintel currently has 1 backend. Adding 4 methods to 1 implementation is trivial.
- When adding E2B backend, all 8 methods map directly to E2B SDK calls.
- The alternative (fewer methods + mixin) adds a second abstraction layer.
