# Agent Sandbox Abstraction — Research

**EXECUTIVE SUMMARY**

Lintel already has the foundations for a sandbox abstraction — `SandboxConfig`, `SandboxJob`, `SandboxResult` types, a `SandboxManager` Protocol, and a `DockerSandboxManager` implementation — but these are misaligned and incomplete. The Protocol in `contracts/protocols.py` and the implementation in `docker_backend.py` have **incompatible method signatures** (different names and parameter types). A duplicate Protocol exists in `domain/sandbox/protocols.py`. The sandbox API routes are disconnected from the actual infrastructure. Every production AI coding tool in 2025-2026 converges on the same pattern: an abstract runtime interface with a single `execute(command)` primitive, file I/O operations, lifecycle management via async context managers, and swappable backends.

- **Recommended Approach**: Option B — Consolidate & Extend with Named Operations
- **Why**: Reconciles existing code with industry patterns; adds file I/O and lifecycle methods; keeps the single-primitive `execute` core while adding typed file operations that cloud backends can implement natively
- **Trade-offs**: More methods to implement per backend (8 vs 4), but file I/O via shell commands is fragile and encoding-sensitive
- **Confidence**: High — validated by 15+ production systems (E2B, SWE-agent, OpenHands, LangChain DeepAgents, Cursor, Codex CLI)
- **Next Step**: User decision required — review options below

---

## 1. Problem Statement

- **Original Task**: Define an abstract sandbox interface that allows pointing to a repo and spinning up an isolated environment (devcontainer, cloud dev env, etc.) for agents to write code, run tests, and execute commands
- **Success Criteria**: A `SandboxManager` Protocol in `contracts/` that multiple backends (Docker, E2B, Modal, devcontainers) can implement; proper lifecycle management; integration with LangGraph workflow nodes
- **Key Questions**: What operations should the Protocol expose? How should sandbox lifecycle integrate with LangGraph state? What isolation technology is appropriate?
- **Assumptions to Validate**: The existing `SandboxConfig`/`SandboxJob`/`SandboxResult` types are adequate; Docker containers provide sufficient isolation; the Protocol can abstract over both local and cloud backends

## 2. Investigation Summary

- **Codebase survey**: Analyzed ~35 files across contracts, infrastructure, workflows, agents, and API layers. Found duplicate `SandboxManager` Protocols with incompatible signatures, disconnected API routes, and placeholder workflow nodes.
- **Framework documentation**: Reviewed Python typing/Protocol, asyncio patterns, FastAPI DI, Docker SDK, devcontainer spec, E2B SDK, LangGraph state/tool patterns.
- **Production examples**: Researched SWE-agent/SWE-ReX, OpenHands, E2B, Codex CLI, Cursor, Devin, LangChain DeepAgents, Alibaba OpenSandbox, Kubernetes agent-sandbox CRD, Vercel Sandbox, Modal, Daytona.
- **Clean code analysis**: Identified 12+ violations across Protocol mismatch, missing error handling, silent stderr loss, no timeouts, incomplete types, broken conformance tests.

**Evidence collected**: 12 repo files, 6 framework doc topics, 20 web sources, 14 clean code findings.

## 3. Key Findings

### Finding 1: Two Incompatible SandboxManager Protocols Exist
- **Discovery**: `contracts/protocols.py:137-164` defines `create_sandbox(job_id, repo_url, base_sha, ...)` with primitive params. `domain/sandbox/protocols.py:11-30` defines `create(config: SandboxConfig, thread_ref: ThreadRef)` with typed value objects. Only the domain version is implemented by `DockerSandboxManager`.
- **Evidence**: [REPO-01, REPO-04, CLEAN-01]
- **Implication**: The contracts-layer Protocol is authoritative by convention but is dead code. Must consolidate to one Protocol using the richer typed signatures.

### Finding 2: DockerSandboxManager Does Not Satisfy Its Own Protocol
- **Discovery**: 3 of 4 method names differ (`create` vs `create_sandbox`, `execute` vs `execute_command`, `destroy` vs `destroy_sandbox`). Return types also differ (`SandboxResult` vs `CommandResult`). mypy strict mode would reject this.
- **Evidence**: [REPO-05, CLEAN-02, CLEAN-03]
- **Implication**: Any code attempting to use `DockerSandboxManager` through the `SandboxManager` Protocol type will fail at runtime with `AttributeError`.

### Finding 3: Industry Converges on Single-Primitive `execute()` + File I/O
- **Discovery**: LangChain DeepAgents, SWE-agent/SWE-ReX, OpenHands, cased/sandboxes, and Alibaba OpenSandbox all define one abstract `execute(command)` method. File operations are either derived from shell commands (LangChain) or exposed as separate typed methods (E2B, OpenHands, Daytona).
- **Evidence**: [WEB-08, WEB-01 (industry), SWE-01, OH-01, E2B-03]
- **Implication**: The current Protocol's 4-method shape (create/execute/collect/destroy) is correct but needs file I/O operations added to be portable across cloud backends.

### Finding 4: Sandbox-as-Tool is the Recommended Architecture
- **Discovery**: LangChain, Anthropic, Vercel, and browser-use all recommend Pattern B: agent runs outside the sandbox, calls it as a tool via API. Secrets stay on the control plane; sandbox has "nothing worth stealing."
- **Evidence**: [WEB-01 (agent-workflows), WEB-05 (agent-workflows), WEB-10 (industry)]
- **Implication**: Lintel's existing architecture (FastAPI service calling sandbox via Protocol) already follows Pattern B. This is validated.

### Finding 5: MicroVMs (Firecracker/gVisor) Required for Multi-Tenant Production
- **Discovery**: Standard Docker containers share the host kernel and are insufficient for untrusted AI-generated code. Production systems use Firecracker (E2B, Vercel) or gVisor (Modal, OpenAI). OS primitives (Seatbelt, Landlock) are viable only for single-user local tools.
- **Evidence**: [WEB-03 (container), WEB-06 (industry)]
- **Implication**: Lintel's Docker backend is appropriate for dev/test. Production deployment needs E2B, Modal, or a gVisor-wrapped container backend.

### Finding 6: LangGraph `InjectedRuntime` is the Correct DI Mechanism
- **Discovery**: LangGraph's `Runtime` context with `InjectedRuntime` injects sandbox instances into tool functions. Sandbox instances must NOT be stored in graph State (not serializable). Only `sandbox_id: str` belongs in state.
- **Evidence**: [DOCS-1 (agent-workflows), WEB-04 (agent-workflows)]
- **Implication**: Add `sandbox_id: str | None` to `ThreadWorkflowState`. Wire `SandboxManager` via LangGraph `Runtime` context, not module globals.

### Finding 7: Async Context Managers are Required for Lifecycle Safety
- **Discovery**: Every production implementation (E2B, SWE-ReX, OpenHands) uses `async with` for sandbox lifecycle. Without guaranteed cleanup, container leaks are inevitable. The current `DockerSandboxManager` has no lifecycle management — `_containers` dict is lost on restart.
- **Evidence**: [DOCS-02 (python), WEB-03 (python), E2B-02]
- **Implication**: Add `sandbox_session()` async context manager. Add `recover()` or label-based discovery for crash recovery.

## 4. Analysis & Synthesis

### Current State
The codebase has the right architectural intent: Protocols in `contracts/`, implementations in `infrastructure/`, frozen dataclass types, event sourcing. The sandbox subsystem is the least mature area — it was built as a v0.1 placeholder. The `implement` workflow node returns hardcoded data, the API routes use an in-memory dict, and the Protocol/implementation are misaligned.

### Constraints & Opportunities
- **Constraint**: Lintel uses mypy strict mode — the Protocol/implementation mismatch is a blocking type error once wired together
- **Constraint**: LangGraph state must be JSON-serializable — no live objects in `ThreadWorkflowState`
- **Opportunity**: `SandboxConfig`, `SandboxJob`, `SandboxResult`, `SandboxStatus` types already exist and are well-designed
- **Opportunity**: Sandbox events (`SandboxJobScheduled`, `SandboxCreated`, `SandboxArtifactsCollected`, `SandboxDestroyed`) are already defined
- **Opportunity**: The `PresidioFirewall` in `infrastructure/pii/` is a gold-standard reference for how infrastructure should implement Protocols

### Design Principles
- Protocol-based structural subtyping (no ABC, no inheritance)
- Frozen dataclasses for all value objects
- `asyncio.to_thread` for synchronous SDK wrapping
- `async with` for resource lifecycle
- Event sourcing for all state transitions
- Sandbox-as-Tool architecture (Pattern B)

## 5. Solution Space

### Option A: Minimal Fix — Reconcile Protocol Names Only
**Core Idea**: Rename `DockerSandboxManager` methods to match the contracts Protocol (or vice versa). Change nothing else.

**Approach Overview**:
- Rename 3 methods on `DockerSandboxManager` to match `contracts/protocols.py`
- Delete `domain/sandbox/protocols.py` (duplicate)
- Fix conformance test
- Wire into `app.state` and implement node

**Key Trade-offs**:
- ✅ Smallest change, lowest risk
- ✅ Unblocks actual sandbox execution in workflows
- ✅ Fixes the type safety violation
- ❌ Protocol still uses primitive params (`repo_url: str`) not typed value objects
- ❌ No file I/O operations — agents must construct shell commands
- ❌ No lifecycle management (async context manager)
- ❌ Cloud backends (E2B, Modal) would need awkward parameter mapping

**Complexity**: XS
**Best When**: You need to ship something immediately and will iterate later

### Option B: Consolidate & Extend with Named Operations (Recommended)
**Core Idea**: Consolidate to one Protocol using typed value objects. Add file I/O and lifecycle methods. Keep `execute()` as the core primitive.

**Approach Overview**:
- Replace contracts-layer Protocol with the domain-layer signature (using `SandboxConfig`, `SandboxJob`, `SandboxResult`)
- Add `read_file()`, `write_file()`, `list_files()` to Protocol
- Add `get_status()` and async context manager support
- Extend `SandboxConfig` with `network_enabled`, `timeout_seconds`, `environment`
- Extend `SandboxJob` with `timeout_seconds`
- Add `SandboxNotFoundError` exception hierarchy
- Fix `demux=True` for stderr capture
- Wire into workflow nodes and app lifespan

**Key Trade-offs**:
- ✅ Typed value objects align Protocol with existing types [REPO-02]
- ✅ File I/O operations enable cloud backend portability [E2B-03, OH-01]
- ✅ Lifecycle management prevents container leaks [DOCS-02]
- ✅ Matches industry standard (E2B, OpenHands, DeepAgents) [WEB-08]
- ✅ `SandboxNotFoundError` replaces opaque `KeyError` crashes
- ❌ More methods to implement per backend (8 vs 4)
- ❌ File I/O in Docker requires tar archive manipulation [DOCKER-3]
- ❌ Larger change surface than Option A

**Complexity**: M
**Best When**: You want a production-ready abstraction that supports multiple backends

### Option C: Single-Primitive Pattern (LangChain Style)
**Core Idea**: Define only `execute(command: str) -> ExecutionResult` as the abstract method. All file operations are derived from shell commands in a base implementation class.

**Approach Overview**:
- Protocol has just: `create()`, `execute()`, `destroy()`, `get_status()`
- A `BaseSandboxOperations` mixin in `domain/` provides `read_file()`, `write_file()`, `list_files()` by calling `execute()` with shell commands
- Each backend implements only the minimal Protocol
- File I/O is shell-based: `cat`, `echo > file`, `ls -la`

**Key Trade-offs**:
- ✅ Smallest interface for backend implementors [WEB-08]
- ✅ Proven at scale by LangChain DeepAgents (Modal, Daytona, Runloop) [WEB-09]
- ✅ Any backend that can run a shell command gets file I/O for free
- ❌ Shell-based file I/O is fragile (encoding, escaping, binary files) [OH-01]
- ❌ Cloud backends (E2B) have native file APIs that are faster and more reliable than shell commands
- ❌ Mixin introduces a second abstraction layer alongside the Protocol

**Complexity**: S
**Best When**: You expect many backends and want the easiest path for new provider implementations

### Option D: Full Runtime Abstraction (OpenHands Style)
**Core Idea**: Define an Action/Observation type system. The Protocol accepts typed `Action` objects and returns typed `Observation` objects. Each operation has its own action and result type.

**Approach Overview**:
- Define `CmdRunAction`, `FileReadAction`, `FileWriteAction` as frozen dataclasses
- Define corresponding `CmdOutputObservation`, `FileReadObservation`, `FileWriteObservation`
- Protocol has a single `async def run(action: SandboxAction) -> SandboxObservation` method
- Pattern-match on action type in the implementation
- Plugin system for extensible capabilities

**Key Trade-offs**:
- ✅ Most expressive and extensible [OH-01]
- ✅ Each operation has its own typed result
- ✅ Plugin system allows capability composition
- ❌ Highest implementation complexity
- ❌ Over-engineered for Lintel's current needs (4 agent roles, 1 backend)
- ❌ Action dispatch adds indirection without clear benefit at current scale

**Complexity**: L
**Best When**: You're building a general-purpose agent platform with many action types and plugin authors

## 6. Recommendation

**Recommended Approach**: Option B — Consolidate & Extend with Named Operations

**Why This Option Wins**:
- Directly addresses the Protocol/implementation mismatch (the #1 blocker) using existing typed value objects
- Adds file I/O as typed Protocol methods, enabling cloud backends (E2B, Modal) to use their native file APIs instead of shell pass-through
- Includes lifecycle management (`async with`) which every production system requires
- Matches the established codebase patterns (Protocol + frozen dataclasses + event sourcing)
- Evidence-backed by E2B, Daytona, and OpenHands which all expose typed file operations alongside command execution

**Trade-offs Accepted**:
- More methods per backend (8 vs 4 in Option A, vs 3 in Option C)
- Docker file I/O requires tar archive manipulation (acceptable complexity)
- Larger initial change surface than Option A

**Key Risks** (high-level):
- Docker socket mount in `docker-compose.yaml` defeats sandbox isolation — Mitigation: use socket proxy or sidecar
- In-memory `_containers` dict loses state on restart — Mitigation: Docker label-based recovery
- `DockerSandboxManager` uses synchronous SDK — Mitigation: `asyncio.to_thread` (already done) or switch to `aiodocker`

See [research/risks.md](./research/risks.md) for detailed risk analysis.

**Confidence**: High
- Rationale: Validated by 15+ production systems; aligns with Lintel's existing architectural patterns; addresses all identified codebase issues

## 7. Next Steps

**Decision Required**:
Review the solution options above and select the approach that best fits project constraints and priorities.

**Questions to Consider**:
- Is the immediate priority unblocking sandbox execution (Option A) or building a multi-backend-ready abstraction (Option B)?
- Will Lintel support cloud sandbox providers (E2B, Modal) in the near term?
- Is file I/O via shell commands acceptable, or do you need typed file operations?

**Once Direction is Chosen**:
Proceed to planning for detailed implementation steps.

The plan phase will provide:
- Reconciled Protocol definition with exact method signatures
- Sequenced implementation steps with complexity ratings
- Complete code examples for Protocol, Docker backend, and test fixtures
- LangGraph integration pattern with `InjectedRuntime`
- Testing strategy with `DummySandboxManager` for unit tests

**If More Research Needed**:
- Deep dive into E2B SDK integration patterns
- Performance benchmarking of Docker vs E2B cold-start times
- Security audit of Docker socket exposure

---

## APPENDICES

*Detailed context for plan agent and technical deep-dive*

### Appendix: Codebase Survey
**Purpose**: Complete codebase context for plan agent

**Summary**: Surveyed ~35 files across contracts, infrastructure, workflows, agents, and API layers. Found a well-structured Protocol-based architecture with the sandbox subsystem as the primary gap.

**Key Findings**:
- Architecture: Clean separation between contracts (Protocols), infrastructure (implementations), and workflows (LangGraph nodes)
- Patterns: Frozen dataclasses, `TYPE_CHECKING` guards, `asyncio.to_thread`, constructor injection
- Gaps: Duplicate SandboxManager Protocols, disconnected API routes, placeholder workflow nodes
- Integration: `PresidioFirewall` is the gold-standard reference for Protocol-conforming infrastructure

**Contents** (per-area files in `research/`):
- `codebase-survey-python-backend.md` — Contracts, types, protocols, infrastructure patterns
- `codebase-survey-container-sandbox.md` — Docker implementation, security hardening, compose setup
- `codebase-survey-agent-workflows.md` — LangGraph state, workflow nodes, agent runtime

---

### Appendix: Framework & API Documentation
**Purpose**: Framework knowledge without re-fetching

**Summary**: Reviewed Python typing/Protocol, asyncio patterns, FastAPI DI, Docker SDK, devcontainer spec, E2B SDK, and LangGraph state/tool patterns.

**Key Findings**:
- Python: `typing.Protocol` over ABC; `@dataclass(frozen=True, slots=True)`; `asynccontextmanager` for lifecycle
- Docker SDK: `exec_run(demux=True)` for separate stdout/stderr; `put_archive`/`get_archive` for file transfer; labels for orphan recovery
- LangGraph: `InjectedRuntime` for sandbox DI into tools; `Annotated[list, add]` reducers; only serializable data in state
- E2B: `AsyncSandbox.create()` as factory + context manager; `.commands.run()`, `.files.read()/.write()`

**Contents** (per-area files in `research/`):
- `framework-docs-python-backend.md` — Protocol, asyncio, FastAPI patterns
- `framework-docs-container-sandbox.md` — Docker SDK, devcontainer spec, E2B SDK, testcontainers
- `framework-docs-agent-workflows.md` — LangGraph ToolNode, state management, checkpointing
- `framework-docs-industry-patterns.md` — E2B, SWE-agent, OpenHands, Daytona SDK documentation

---

### Appendix: Decision Context
**Purpose**: Explain why Option B wins

**Summary**: Option B scored highest across all weighted criteria. It addresses every identified codebase issue, aligns with industry patterns, and builds on existing types.

**Scoring**:

| Option | Clean Code (0.40) | Industry Alignment (0.30) | Codebase Fit (0.20) | Risk (0.10) | Total |
|--------|-------------------|--------------------------|---------------------|-------------|-------|
| A: Minimal Fix | 5/10 (2.0) | 4/10 (1.2) | 9/10 (1.8) | 9/10 (0.9) | 5.9 |
| B: Consolidate+Extend | 9/10 (3.6) | 9/10 (2.7) | 8/10 (1.6) | 7/10 (0.7) | **8.6** |
| C: Single-Primitive | 7/10 (2.8) | 8/10 (2.4) | 6/10 (1.2) | 8/10 (0.8) | 7.2 |
| D: Full Runtime | 8/10 (3.2) | 7/10 (2.1) | 4/10 (0.8) | 5/10 (0.5) | 6.6 |

**Contents**: See `research/decision-context.md` for detailed rejected options analysis.

---

### Appendix: Implementation Context
**Purpose**: Integration guidance for plan agent

**Summary**: The primary integration points are: (1) consolidate Protocol in `contracts/protocols.py`, (2) wire `DockerSandboxManager` into `app.state` via lifespan, (3) connect sandbox routes to infrastructure, (4) implement `spawn_implementation` workflow node with real sandbox calls.

**Key Integration Points**:
- `contracts/protocols.py:137` — Replace primitive-param Protocol with typed version
- `api/app.py:40-59` — Add `DockerSandboxManager()` to lifespan
- `api/routes/sandboxes.py:34` — Call `app.state.sandbox_manager` instead of in-memory dict
- `workflows/nodes/implement.py:11` — Replace placeholder with real sandbox calls
- `workflows/state.py:20` — Add `sandbox_id: str | None`

**Contents** (per-area files in `research/`):
- `clean-code-python-backend.md` — 12 violations with proposed fixes
- `clean-code-container-sandbox.md` — Docker security, error handling, resource management
- `clean-code-agent-workflows.md` — Workflow integration, state typing, tool abstractions
- `clean-code-industry-patterns.md` — Protocol gaps vs industry tools

---

### Appendix: Evidence Index
**Purpose**: Complete citation trail

**Summary**: 46+ evidence sources across 4 categories.

**Coverage**:
- Repository: 13 REPO-XX citations across contracts, infrastructure, workflows, API, tests
- Clean Code: 14 CLEAN-XX citations for violations and improvements
- Framework Docs: 6 DOCS-XX citations for Python, Docker, LangGraph, E2B patterns
- Web Research: 20 WEB-XX citations across industry patterns, container runtimes, agent workflows

**Contents**: See `research/evidence-index.md` for consolidated evidence table.

---

### Appendix: Risks & Troubleshooting
**Purpose**: Anticipate issues for plan phase

**Summary**: 7 risks identified, ranging from security (Docker socket exposure) to reliability (in-memory state loss) to correctness (Protocol mismatch).

**Risk Profile**:
- High impact: Docker socket privilege escalation; Protocol/implementation mismatch (runtime AttributeError)
- Medium impact: In-memory container dict (state loss on restart); silent stderr loss; no execution timeouts
- Low impact: Docker client created per-call; missing conformance tests

**Contents**: See `research/risks.md` for detailed risk analysis with mitigations.
