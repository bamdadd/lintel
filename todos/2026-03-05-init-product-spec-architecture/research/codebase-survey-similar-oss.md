# Codebase Survey - Similar OSS Projects

## Survey Context

Survey of existing open-source AI agent platforms to identify patterns and lessons for Lintel.

---

## 1. Platform Comparison Matrix

| Dimension | CrewAI | AutoGen v0.4 | OpenHands | SWE-agent | LangGraph | Haystack |
|---|---|---|---|---|---|---|
| **Agent Model** | Role-based | Conversable actors | Controller loop | Single agent + ACI | Graph nodes | Pipeline components |
| **Orchestration** | Sequential/hierarchical | Group chat/swarm | Event-driven loop | ReAct loop | Directed graph | DAG pipelines |
| **Sandbox** | None | Docker (optional) | Docker (required) | Docker | None | None |
| **Human-in-Loop** | Callback | UserProxyAgent | UI-based | Minimal | interrupt_before/after | Not built-in |
| **Event Logging** | Callbacks | Conversation history | Event stream | Trajectory files | Checkpointing | Pipeline tracing |
| **Extensibility** | Custom tools/agents | Custom agents/skills | Plugin system | Custom commands | Any Python function | Component protocol |
| **Deployment** | pip install | Library + Studio | Docker Compose/K8s | CLI + Docker | Library + Platform | Library + Hayhooks |

---

## 2. Architecture Lessons

### What Works Well

- **REPO-OSS-43**: Graph-based orchestration (LangGraph) — predictable, debuggable workflows with checkpoint replay
- **REPO-OSS-44**: Sandbox isolation (OpenHands) — disposable Docker sandboxes with pre-built images
- **REPO-OSS-45**: Conversation-as-interface (AutoGen) — message passing is intuitive and debuggable
- **REPO-OSS-46**: Component contracts (Haystack) — strict I/O schema enforcement prevents integration errors
- **REPO-OSS-47**: Specialized agent interfaces (SWE-agent) — constraining agent capabilities improves reliability

### Common Pitfalls

- **REPO-OSS-48**: No isolation by default blocks enterprise adoption
- **REPO-OSS-49**: Monolithic agent loops get stuck; need explicit state machines with bounded retries
- **REPO-OSS-50**: Opaque decision-making; Lintel's evented routing addresses this
- **REPO-OSS-51**: Configuration complexity (AutoGen v0.2→v0.4 rewrite)
- **REPO-OSS-52**: Tight coupling to single LLM providers

---

## 3. Differentiation Analysis

### Lintel's Unique Capabilities

| Capability | Lintel | Nearest Competitor | Gap |
|---|---|---|---|
| Event sourcing with audit | Core architecture | LangGraph checkpoints | LG lacks append-only, compliance views, hash chaining |
| PII anonymization | Built-in (Presidio) | None | Complete gap |
| Channel-first (Slack/Teams) | Primary interface | AutoGen (chat-based) | AutoGen chat is inter-agent only |
| Multi-agent + sandbox per agent | Both integrated | OpenHands (sandbox) or CrewAI (multi-agent) | No platform combines both |
| Policy-driven model routing | Per agent/workload | None built-in | All platforms use single model config |
| Dynamic skill registry | Runtime hot-reload | Haystack components | Haystack requires pipeline rebuild |

### Where to Follow Established Patterns
- **REPO-OSS-63**: LangGraph's graph orchestration
- **REPO-OSS-64**: OpenHands' sandbox model
- **REPO-OSS-65**: Haystack's component contracts
- **REPO-OSS-66**: AutoGen's conversation history

### Risks of Over-Building
- **REPO-OSS-67**: Don't build custom workflow engine — use LangGraph
- **REPO-OSS-68**: Wrap existing agent runtimes, don't rebuild
- **REPO-OSS-69**: Use devcontainers CLI + Docker, don't build custom container runtime

---

## 4. Adoption Patterns

- **REPO-OSS-70**: Bottom-up single-team pilot
- **REPO-OSS-71**: Security review gate (Lintel addresses blockers directly)
- **REPO-OSS-72**: Gradual autonomy increase via configurable approval gates
- **REPO-OSS-73**: Custom model providers (Lintel's router handles this)
- **REPO-OSS-74**: Custom tools via skill registry
- **REPO-OSS-75**: SSO/OIDC integration (planned)
- **REPO-OSS-76**: Data residency via distributed nodes
- **REPO-OSS-77**: Git-flow integration via branch-per-job
- **REPO-OSS-78**: Existing CI/CD triggering (complement, not replace)
- **REPO-OSS-79**: OpenTelemetry for observability stack integration

---

## Summary

Lintel's three strongest differentiators:
1. **Event sourcing as core architecture** — no competitor has this
2. **Built-in PII protection** — complete gap in market
3. **Channel-first collaboration with enterprise governance** — combines Slack-native UX with RBAC/audit

Recommended strategy: wrap LangGraph + Docker/devcontainers + Presidio, and invest engineering in the event store, PII firewall, channel adapters, policy engine, and skill registry.
