# Web Research: Industry Patterns

## Production AI Sandbox Systems Survey (2024-2025)

### E2B (e2b.dev)
- **Users**: Cursor, Vercel, LangChain, hundreds of AI startups
- **Isolation**: Firecracker microVMs
- **Key Innovation**: Custom sandbox templates from Dockerfiles; sub-second starts
- **SDK**: `AsyncSandbox.create()`, `.commands.run()`, `.files.read()/.write()`
- **Evidence**: [E2B-01 through E2B-05]

### SWE-agent / SWE-ReX (Princeton NLP)
- **Users**: Academic research, SWE-bench leaderboard
- **Isolation**: Docker containers
- **Key Innovation**: Minimal runtime abstraction; agent operates entirely through shell
- **SDK**: `SWEEnv` class with `execute()` method
- **Evidence**: [SWE-01 through SWE-03]

### OpenHands (formerly OpenDevin)
- **Users**: Open source community, 40k+ GitHub stars
- **Isolation**: Docker + E2B backends
- **Key Innovation**: Action/Observation type system; event stream architecture
- **SDK**: `Runtime` class with `run_action(action)` dispatcher
- **Evidence**: [OH-01 through OH-03]

### Codex CLI (OpenAI)
- **Users**: Developers using OpenAI API
- **Isolation**: OS-level (Seatbelt/Landlock), no containers
- **Key Innovation**: Zero-overhead sandboxing via OS primitives
- **Limitations**: Single-user, local only, no multi-tenant
- **Evidence**: [CODEX-01, CODEX-02]

### Devin (Cognition)
- **Users**: Enterprise customers
- **Isolation**: Cloud VMs (proprietary)
- **Key Innovation**: Full development environment with browser, terminal, editor
- **Note**: Closed source, limited public information

### Alibaba OpenSandbox
- **Users**: Alibaba Cloud
- **Isolation**: Docker with enhanced security
- **Key Innovation**: Plugin system for extensible capabilities
- **Evidence**: [ALI-01]

### Kubernetes Agent-Sandbox CRD (SIG Apps)
- **Status**: Emerging standard (2025)
- **Key Innovation**: Kubernetes-native sandbox lifecycle management
- **Pattern**: CRD defines sandbox spec, operator manages container/pod lifecycle
- **Evidence**: [K8S-01]

## Convergence Analysis

### Universal Patterns
1. **Single `execute(command)` primitive** — every system has this
2. **Async lifecycle management** — create/destroy with cleanup guarantees
3. **Ephemeral by default** — sandboxes are disposable
4. **Timeout support** — per-command and per-sandbox
5. **String sandbox IDs** — UUID or similar

### Divergence Points
1. **File I/O**: Typed methods (E2B, OpenHands) vs shell-based (SWE-ReX, DeepAgents)
2. **Abstraction level**: Named methods (E2B) vs Action/Observation (OpenHands) vs single-primitive (DeepAgents)
3. **Isolation**: MicroVMs (E2B) vs Docker (SWE-ReX) vs OS (Codex)
4. **Base class**: Protocol (none use it) vs ABC (LangChain) vs concrete class

### Recommendation for Lintel
- Use `typing.Protocol` (unique to Lintel, but correct for the codebase)
- Named methods (Option B level) — not single-primitive, not Action/Observation
- Docker backend for dev/test, E2B/Modal for production
- Typed file I/O methods on Protocol
