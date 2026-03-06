# Clean Code Analysis: Industry Patterns

## Protocol Gaps vs Industry Standards

### Missing File I/O Operations
**Lintel**: No file read/write/list in Protocol.
**Industry**: E2B, OpenHands, Vercel all provide typed file I/O methods.
**Impact**: Agents must construct shell commands for file operations, which is fragile (encoding, escaping, binary files).

### Missing Lifecycle Management
**Lintel**: No async context manager, no `get_status()`.
**Industry**: Every production system uses `async with` for sandbox lifecycle.
**Impact**: Container leaks on exceptions, no crash recovery.

### Missing Timeout Support
**Lintel**: No timeout on `execute()` or `create()`.
**Industry**: E2B (per-command + sandbox TTL), SWE-ReX (per-command), OpenHands (per-action).
**Impact**: Hanging commands block indefinitely.

### Missing Environment Variables
**Lintel**: No way to pass env vars to sandbox or commands.
**Industry**: E2B (`envs` param on `run()`), Docker SDK (`environment` on create).
**Impact**: Cannot configure tools (CI=true, PATH, etc.) in sandbox.

## Architecture Alignment

### Sandbox-as-Tool (Pattern B) — Correct
**Lintel**: Agent runs in FastAPI process, calls sandbox via Protocol. Correct.
**Industry**: LangChain, Anthropic, Vercel all recommend this pattern.
**Why**: Secrets stay on control plane; sandbox is disposable; agent can use multiple sandboxes.

### Event Sourcing for Sandbox Lifecycle — Correct
**Lintel**: Sandbox events defined (`SandboxCreated`, `SandboxDestroyed`, etc.).
**Industry**: OpenHands uses event stream. Others use logging/telemetry.
**Why**: Audit trail, replay, debugging.

## Anti-Patterns to Avoid

### Don't Use ABC
**LangChain**: Uses `class BaseSandbox(ABC)` — requires explicit inheritance.
**Lintel Convention**: `typing.Protocol` — structural subtyping. Do not follow LangChain here.

### Don't Over-Abstract
**OpenHands**: Action/Observation type system with pattern matching — powerful but complex.
**Lintel Reality**: 1 backend (Docker), 6 agent roles, single-team. Named methods are simpler and sufficient.

### Don't Store Live Objects in State
**Common Mistake**: Storing sandbox client in workflow state.
**Correct**: Only `sandbox_id: str` in state. Live object in runtime context.
