# Evidence Index

## E.1 Repository Evidence

| ID | File/Location | Finding | Confidence |
|----|---------------|---------|------------|
| REPO-01 | contracts/protocols.py:137-164 | SandboxManager Protocol with primitive params | 0.95 |
| REPO-02 | contracts/types.py:160-183 | SandboxConfig, SandboxJob, SandboxResult types | 0.95 |
| REPO-03 | contracts/types.py:111-118 | SandboxStatus enum with full lifecycle | 0.95 |
| REPO-04 | domain/sandbox/protocols.py:11-30 | Duplicate SandboxManager Protocol with typed params | 0.95 |
| REPO-05 | infrastructure/sandbox/docker_backend.py:13-86 | DockerSandboxManager implementation | 0.95 |
| REPO-06 | workflows/state.py:20 | sandbox_results in state, no sandbox_id | 0.95 |
| REPO-07 | workflows/nodes/implement.py:11 | Placeholder returning hardcoded data | 0.95 |
| REPO-08 | api/routes/sandboxes.py:34 | Routes using in-memory dict | 0.95 |
| REPO-09 | api/app.py:40-59 | Lifespan without SandboxManager | 0.95 |
| REPO-10 | contracts/events.py | Sandbox events defined | 0.90 |
| REPO-11 | contracts/commands.py | ScheduleSandboxJob command | 0.90 |
| REPO-12 | tests/unit/contracts/test_protocols.py | Broken conformance test | 0.90 |
| REPO-13 | ops/docker-compose.yaml | Docker socket mounted | 0.95 |

## E.2 Framework Documentation

| ID | Source | Topic | Key Claim | Confidence |
|----|--------|-------|-----------|------------|
| DOCS-01 | Python docs | typing.Protocol | Structural subtyping without inheritance | 0.95 |
| DOCS-02 | Python docs | asynccontextmanager | Guaranteed cleanup for resource lifecycle | 0.95 |
| DOCS-03 | Docker SDK | exec_run(demux=True) | Separate stdout/stderr streams | 0.95 |
| DOCS-04 | Docker SDK | put_archive/get_archive | File transfer via tar archives | 0.90 |
| DOCS-05 | LangGraph docs | InjectedRuntime | DI for tools via runtime context | 0.90 |
| DOCS-06 | E2B SDK docs | AsyncSandbox API | Native file I/O + command execution | 0.90 |

## E.3 Clean Code Analysis

| ID | Issue Type | Location | Severity | Confidence |
|----|-----------|----------|----------|------------|
| CLEAN-01 | Duplicate Protocol | contracts/ vs domain/ | Critical | 0.95 |
| CLEAN-02 | Method name mismatch | protocols vs docker_backend | Critical | 0.95 |
| CLEAN-03 | Redundant type | CommandResult vs SandboxResult | Medium | 0.90 |
| CLEAN-04 | Missing demux=True | docker_backend.py:63 | High | 0.95 |
| CLEAN-05 | No timeout | docker_backend.py:55 | High | 0.90 |
| CLEAN-06 | In-memory state | docker_backend.py:17 | High | 0.90 |
| CLEAN-07 | Bare KeyError | docker_backend.py:62 | Medium | 0.90 |
| CLEAN-08 | Client per-call | docker_backend.py:19 | Low | 0.85 |
| CLEAN-09 | Disconnected routes | api/routes/sandboxes.py | High | 0.95 |
| CLEAN-10 | Placeholder node | workflows/nodes/implement.py | High | 0.95 |
| CLEAN-11 | Broken test | test_protocols.py | Medium | 0.90 |
| CLEAN-12 | Sparse config | types.py:160-165 | Medium | 0.85 |
| CLEAN-13 | Docker socket | docker-compose.yaml | Critical | 0.95 |
| CLEAN-14 | Missing wiring | api/app.py | High | 0.90 |

## E.4 Web Research

| ID | Source Type | Title/Topic | Key Claim | Confidence |
|----|------------|-------------|-----------|------------|
| WEB-01 | Anthropic blog | Building Effective Agents | Sandbox-as-tool pattern recommended | 0.90 |
| WEB-02 | Real Python | Protocols and Structural Subtyping | Protocol preferred over ABC | 0.85 |
| WEB-03 | Trail of Bits | Container Security for AI | gVisor/Firecracker for untrusted code | 0.90 |
| WEB-04 | LangGraph docs | Runtime context | InjectedRuntime for DI | 0.90 |
| WEB-05 | LangChain blog | Agent Sandbox Patterns | Pattern B (sandbox-as-tool) | 0.85 |
| WEB-06 | OWASP | AI Agent Security | Sandbox isolation requirements | 0.90 |
| WEB-07 | Docker blog | AI Workload Security | Hardening checklist | 0.85 |
| WEB-08 | LangChain | DeepAgents BaseSandbox | Single-primitive pattern | 0.90 |
| WEB-09 | LangChain | Modal/Daytona/Runloop | Multiple backend implementations | 0.85 |
| WEB-10 | Analysis | Cursor/Codex architecture | Sandbox-as-tool in production | 0.80 |
| E2B-01 | E2B docs | Sandbox lifecycle | Firecracker microVMs, async API | 0.95 |
| E2B-02 | E2B docs | Context manager | Guaranteed cleanup | 0.95 |
| E2B-03 | E2B docs | File API | Native read/write/list | 0.95 |
| SWE-01 | SWE-agent paper | Runtime abstraction | Single execute() primitive | 0.90 |
| OH-01 | OpenHands repo | Action/Observation | Typed operation system | 0.90 |
| CODEX-01 | OpenAI blog | Codex CLI | OS-level sandboxing | 0.85 |
| ALI-01 | Alibaba | OpenSandbox | Plugin system for capabilities | 0.80 |
| K8S-01 | K8s SIG Apps | Agent-sandbox CRD | Kubernetes-native sandbox spec | 0.75 |
| DOCKER-01 | Docker docs | Security best practices | Cap drop, read-only, no-new-priv | 0.95 |
| DOCKER-03 | Docker docs | put_archive API | Tar-based file transfer | 0.90 |
