# Lintel Architecture Research

**EXECUTIVE SUMMARY**

Lintel is a greenfield open-source platform for multi-agent AI collaboration with event sourcing, PII protection, and sandbox isolation. This research surveyed reference architectures, framework documentation, OSS competitors, and clean code standards across four tech areas: Python backend, infrastructure, Slack integration, and similar OSS projects.

- **Recommended Approach**: Option B — Event-Sourced Modular Monolith with LangGraph orchestration
- **Why**: Combines the cleanest orchestration API (LangGraph) with enterprise-grade audit (event sourcing), addresses gaps no OSS platform fills (PII + channels + audit), and starts as a deployable monolith that can extract services later
- **Trade-offs**: Higher initial complexity than a minimal prototype, but avoids costly architectural migration later
- **Confidence**: High — strong alignment between architecture spec, framework capabilities, and clean code analysis
- **Next Step**: User decision required — review options below

---

## 1. Problem Statement

- **Original Task**: Initialize Lintel project with production-ready architecture based on the product spec and architecture documents
- **Success Criteria**: Architecture that supports multi-agent workflows, event sourcing, PII protection, sandbox execution, and Slack integration — deployable as modular monolith for v0.1
- **Key Questions**:
  1. What is the right orchestration layer for multi-agent workflows?
  2. How should event sourcing be implemented in Python with Postgres?
  3. What sandbox isolation model balances security with developer experience?
  4. How should Slack integration be structured for replaceability?
  5. What can we learn from existing OSS agent platforms?
- **Assumptions to Validate**:
  - LangGraph is mature enough for production orchestration
  - Postgres can serve as both event store and projection store at v0.1 scale
  - Presidio provides acceptable PII detection accuracy
  - Devcontainers are a viable sandbox mechanism

## 2. Investigation Summary

- **Codebase survey**: Greenfield project — surveyed reference implementations across 4 areas, documenting patterns for event stores, LangGraph workflows, Presidio pipelines, Slack adapters, and sandbox managers
- **Framework documentation**: Reviewed LangGraph (StateGraph, checkpointing, Send API, interrupt), FastAPI (DI, lifespan, WebSocket), Presidio, asyncpg, NATS JetStream, Kubernetes Jobs, Slack Bolt, and 6 OSS agent platforms
- **Clean code analysis**: Established 98 standards across Python (20), infrastructure (25), Slack (23), and OSS lessons (30)
- **Web research**: Synthesized current best practices from authoritative sources covering all four areas

**Evidence collected**: ~200+ items across REPO, DOCS, CLEAN, and WEB categories (see [evidence index](./research/evidence-index.md))

## 3. Key Findings

### Finding 1: No OSS Platform Combines Lintel's Enterprise Requirements
**Discovery**: No existing open-source agent platform provides the combination of: multi-agent orchestration + event sourcing + PII protection + channel-first UX + sandbox isolation + multi-tenancy.
**Evidence**: [WEB-OSS-01, WEB-OSS-11, WEB-OSS-12, WEB-OSS-13, WEB-OSS-14]
**Implication**: Lintel fills a genuine gap. The architecture must be built from composable building blocks rather than extending an existing platform.

### Finding 2: LangGraph Has the Cleanest Orchestration API
**Discovery**: Among OSS agent frameworks, LangGraph provides the most suitable orchestration model: typed state, conditional edges, `interrupt_before` for human-in-the-loop, `Send` for parallelism, and durable checkpointing with Postgres.
**Evidence**: [REPO-PY-04, REPO-PY-05, DOCS-PY-01 to DOCS-PY-06, CLEAN-OSS-07, WEB-OSS-05]
**Implication**: LangGraph maps directly to Lintel's workflow requirements. Use it as an implementation detail behind Lintel's own abstractions to avoid vendor lock-in.

### Finding 3: Postgres Event Store Is Viable for v0.1
**Discovery**: Postgres can sustain 10-50M events/day on a single writer with proper indexing and monthly partitioning. Custom thin layer over asyncpg is recommended over heavyweight ES libraries.
**Evidence**: [REPO-PY-01, REPO-INFRA-05, WEB-PY-01, WEB-PY-06, CLEAN-INFRA-16 to CLEAN-INFRA-20]
**Implication**: No need for EventStoreDB or Kafka for v0.1. Postgres simplifies operations while providing compliance-grade persistence.

### Finding 4: Defense-in-Depth Sandbox Security Is Well-Understood
**Discovery**: Container security with cap-drop ALL + seccomp + read-only rootfs + NetworkPolicy default-deny provides strong isolation. Devcontainers add project-specific configuration. Prebuilt images reduce cold start to <30s.
**Evidence**: [REPO-INFRA-19, CLEAN-INFRA-11 to CLEAN-INFRA-14, WEB-INFRA-01 to WEB-INFRA-06]
**Implication**: Docker-based sandboxes with defense-in-depth are sufficient for v0.1. Firecracker upgrade path exists for managed service tier.

### Finding 5: Channel Adapter Pattern Enables Replaceability
**Discovery**: A `ChannelAdapter` protocol with Slack as the first implementation allows the domain to remain channel-agnostic. Slack Bolt provides async support, middleware chain, and interactive components needed for approval gates.
**Evidence**: [REPO-SLACK-01 to REPO-SLACK-07, DOCS-SLACK-01 to DOCS-SLACK-10, CLEAN-SLACK-01 to CLEAN-SLACK-04]
**Implication**: Design the channel gateway as a protocol boundary. Slack types never leak into domain. Thread-as-workflow maps naturally to Slack threads.

### Finding 6: PII Protection Is a Hard Enterprise Requirement
**Discovery**: No existing OSS agent platform includes PII protection. Presidio provides a solid foundation but has known false-negative patterns requiring custom recognizers and fail-closed behavior.
**Evidence**: [REPO-PY-08, WEB-PY-13 to WEB-PY-17, WEB-OSS-12, CLEAN-OSS-24]
**Implication**: PII firewall is a critical differentiator. Must be fail-closed with stable per-thread placeholders and encrypted vault for mappings.

### Finding 7: Start Simple, Extract Later
**Discovery**: OSS platforms that over-abstract early (CrewAI's 15+ param constructors, AutoGen's GroupChatManager) create unnecessary complexity. Successful platforms start with focused abstractions and extract when needed.
**Evidence**: [CLEAN-OSS-09 to CLEAN-OSS-13, CLEAN-OSS-27, WEB-OSS-10]
**Implication**: Start as modular monolith. Skills as plain functions. Single-agent workflows first. Extract services only when scaling demands.

## 4. Analysis & Synthesis

### Current State

Lintel is a greenfield project with detailed product spec (440 lines) and architecture spec (575 lines) defining 12 service boundaries, 30+ event types, and a LangGraph-based workflow engine. The architecture spec already prescribes many of the patterns validated by this research.

The key architectural decisions in the spec are well-supported by evidence:
- Thread-as-workflow maps to LangGraph's checkpointed StateGraph [DOCS-PY-01, DOCS-PY-03]
- Event envelope with hash chaining has clear Postgres implementation patterns [REPO-PY-01, CLEAN-INFRA-16]
- PII firewall with Presidio is the only viable open-source option for Python [REPO-PY-08, WEB-PY-13]
- Devcontainer-based sandboxes balance configurability with isolation [DOCS-INFRA-01 to DOCS-INFRA-05]

### Constraints & Opportunities

**Constraints**:
- Event store schema is extremely hard to change post-production — must be designed carefully upfront [Risk 1]
- LangGraph dependency creates vendor coupling — mitigate by wrapping behind Lintel's own abstractions [Risk 2]
- Presidio has known false negatives — mitigate with fail-closed behavior and custom recognizers [Risk 4]
- Full async architecture increases debugging complexity [Risk 5]

**Opportunities**:
- No competitor fills Lintel's specific niche (enterprise AI collaboration infrastructure)
- LangGraph's interrupt + checkpointing maps perfectly to approval gates
- NATS JetStream as event bus simplifies operations vs Kafka
- Python ecosystem has mature async libraries (asyncpg, httpx, structlog)

### Design Principles

Based on cross-area synthesis, the following principles should guide implementation:

1. **Hexagonal architecture**: Domain logic pure, infrastructure behind protocols [CLEAN-PY-01, CLEAN-PY-03]
2. **Events as source of truth**: Append-only, immutable, versioned [CLEAN-PY-10, CLEAN-PY-11]
3. **Fail-closed PII**: Block rather than leak [CLEAN-OSS-24]
4. **Composition over inheritance**: Skills as functions, agents as configuration [CLEAN-OSS-19]
5. **Interface-first boundaries**: `Protocol` types define every service boundary [CLEAN-PY-03]
6. **Correlation everywhere**: Every log line, span, and event carries `correlation_id` [CLEAN-PY-16, CLEAN-INFRA-25]

## 5. Solution Space

### Option A: Minimal MVP — Single-Agent REST API

**Core Idea**: Build the simplest possible system: FastAPI REST API with a single coding agent, no event sourcing, direct Slack integration, Docker sandbox.

**Approach Overview**:
- FastAPI with simple request/response cycle
- Single LangGraph agent with coding tools
- Postgres for state (traditional CRUD, not event sourced)
- Direct Slack Bolt integration in the same process
- Docker containers for sandboxes (no devcontainers)

**Key Trade-offs**:
- Pros: Ships fastest, lowest complexity, easy to understand [WEB-OSS-10]
- Pros: Validates core UX quickly
- Pros: Minimal infrastructure requirements
- Cons: No audit trail — must rebuild for enterprise [WEB-OSS-11]
- Cons: No PII protection — blocks enterprise adoption [WEB-OSS-12]
- Cons: No event sourcing — loses replaceability and compliance [CLEAN-PY-04]
- Cons: Architecture must be rewritten to add multi-agent, multi-tenant

**Complexity**: S
**Best When**: Rapid prototype to validate market fit, willing to rewrite for production

---

### Option B: Event-Sourced Modular Monolith (Recommended)

**Core Idea**: Build the full architecture as a modular monolith from day one: event sourcing, PII firewall, channel adapter, LangGraph workflows — but deployed as a single service.

**Approach Overview**:
- Hexagonal architecture with clear module boundaries
- Postgres event store with NATS JetStream for event distribution
- LangGraph for workflow orchestration with Postgres checkpointing
- Presidio PII pipeline with fail-closed behavior
- Slack adapter behind `ChannelAdapter` protocol
- Docker+devcontainer sandboxes with defense-in-depth
- Single deployment unit (modular monolith) for v0.1

**Key Trade-offs**:
- Pros: Enterprise-ready from day one (audit, PII, compliance) [WEB-OSS-11, WEB-OSS-12]
- Pros: Architecture matches product spec — no rewrite needed [architecture.md]
- Pros: Event sourcing enables projections, replay, and debugging [CLEAN-PY-04, CLEAN-PY-12]
- Pros: Modular monolith is deployable as single service but extractable later [CLEAN-OSS-27]
- Pros: Fills genuine market gap — no OSS competitor offers this [WEB-OSS-01]
- Cons: Higher initial complexity than Option A
- Cons: Event schema design requires significant upfront investment [Risk 1]
- Cons: Full async codebase increases debugging difficulty [Risk 5]

**Complexity**: L
**Best When**: Building for production enterprise use, willing to invest in architecture upfront

---

### Option C: Microservices from Day One

**Core Idea**: Deploy each of the 12 service boundaries from the architecture spec as independent services from the start.

**Approach Overview**:
- Separate services: Channel Gateway, PII Firewall, Event Store, Workflow Engine, Agent Runtime, etc.
- gRPC or HTTP contracts between services
- NATS JetStream for all inter-service communication
- Kubernetes with separate deployments per service
- Distributed tracing for cross-service debugging

**Key Trade-offs**:
- Pros: Clean service boundaries from the start
- Pros: Independent scaling per service
- Pros: Team can work on services independently
- Cons: Massive operational overhead for a new project [CLEAN-OSS-27]
- Cons: Distributed debugging is hard without existing observability [CLEAN-INFRA-25]
- Cons: Network latency between services adds complexity
- Cons: 12 services to deploy, monitor, and maintain from day one

**Complexity**: XL
**Best When**: Large team (10+), proven need for independent scaling, mature DevOps

---

### Option D: LangGraph Platform + Extensions

**Core Idea**: Use LangGraph Platform (managed service) as the core, extend with custom tools for event sourcing, PII, and sandboxes.

**Approach Overview**:
- LangGraph Platform for workflow orchestration and state management
- Custom tools for Presidio PII pipeline
- Custom tools for sandbox management
- LangSmith for monitoring and tracing
- Bolt on event store as a side-effect logger

**Key Trade-offs**:
- Pros: Fastest path to working multi-agent workflows
- Pros: LangSmith provides immediate observability
- Pros: Managed infrastructure for orchestration
- Cons: Vendor lock-in to LangGraph Platform (proprietary) [Risk 2, DOCS-OSS-02]
- Cons: Event sourcing becomes secondary, not the source of truth
- Cons: PII pipeline is a bolt-on, not integral
- Cons: Cannot self-host without LangGraph Platform license
- Cons: Contradicts Lintel's open-source positioning

**Complexity**: M
**Best When**: Willing to accept vendor dependency, want fastest time-to-demo

## 6. Recommendation

**Recommended Approach**: Option B — Event-Sourced Modular Monolith

**Why This Option Wins**:
- Directly implements the architecture spec without deviation — the spec is well-designed and research validates its decisions
- Enterprise differentiators (event sourcing + PII + audit) are built-in from day one, not bolted on later
- Modular monolith avoids the operational overhead of microservices while maintaining clean boundaries for future extraction
- LangGraph is used as an implementation detail behind Lintel's protocols, preserving replaceability

**Trade-offs Accepted**:
- Higher initial complexity vs Option A (but avoids full rewrite)
- Event schema design requires careful upfront work (mitigated by schema versioning + upcasters)
- Full async codebase requires discipline (mitigated by lint enforcement, structured logging)

**Key Risks**:
- Event store schema lock-in — Mitigation: Invest in schema design before application code [Risk 1]
- LangGraph coupling — Mitigation: Wrap behind Lintel's own workflow abstractions [Risk 2]
- Sandbox security escape — Mitigation: Defense-in-depth with cap-drop, seccomp, NetworkPolicy [Risk 3]
- PII leakage — Mitigation: Fail-closed behavior, custom recognizers, encrypted vault [Risk 4]
- Async complexity — Mitigation: Lint enforcement, `asyncio.to_thread()` for sync libs [Risk 5]

See [risks.md](./research/risks.md) for detailed risk analysis.

**Confidence**: High
- Rationale: Architecture spec already prescribes this approach; research validates every major decision with evidence from frameworks, OSS competitors, and production patterns. The only risk is execution complexity, not architectural uncertainty.

## 7. Next Steps

**Decision Required**:
Review the solution options above and select the approach that best fits project constraints and priorities.

**Questions to Consider**:
- Is the team ready to invest in event sourcing from day one, or would a simpler prototype validate assumptions first?
- What is the acceptable cold-start latency for sandboxes? (Determines Docker vs prebuild investment)
- Should v0.1 support multi-workspace Slack, or single-workspace only?

**Once Direction is Chosen**:
Proceed to `/plan` for detailed implementation planning.

The plan phase will provide:
- Sequenced implementation steps with complexity ratings
- Complete code examples for event store, PII pipeline, and workflow engine
- Docker Compose local dev setup
- Testing strategy with testcontainers
- Build order following the critical path [REPO-PY-22]

**If More Research Needed**:
Specific areas that could benefit from deeper investigation:
- Presidio accuracy benchmarks for code-specific PII patterns
- LangGraph checkpoint migration strategies
- NATS JetStream production tuning parameters

---

## APPENDICES

*Detailed context for plan phase and technical deep-dive*

### Codebase Survey (4 files)
**Purpose**: Reference architecture patterns for greenfield implementation

**Summary**: Documented reference implementations for Postgres event store, LangGraph workflows, Presidio PII pipeline, FastAPI patterns, K8s sandbox management, Slack Bolt adapter, and 6 OSS agent platforms.

**Contents**:
- [codebase-survey-python-backend.md](./research/codebase-survey-python-backend.md) — Event store schema, LangGraph patterns, project structure, dependency stack
- [codebase-survey-infrastructure.md](./research/codebase-survey-infrastructure.md) — Devcontainer lifecycle, K8s node types, NATS vs Kafka, Docker Compose layout
- [codebase-survey-slack-integration.md](./research/codebase-survey-slack-integration.md) — ChannelPort adapter, thread management, approval gates, Block Kit
- [codebase-survey-similar-oss.md](./research/codebase-survey-similar-oss.md) — Platform comparison matrix, architecture lessons, differentiation analysis

---

### Framework Documentation (4 files)
**Purpose**: Framework APIs and best practices for implementation

**Summary**: Documented LangGraph (StateGraph, checkpointing, Send, interrupt), FastAPI (DI, lifespan, WebSocket), Presidio, asyncpg, NATS JetStream, Kubernetes (Jobs, NetworkPolicy, KEDA), Slack Bolt (async, middleware, Block Kit), and OSS platform APIs.

**Contents**:
- [framework-docs-python-backend.md](./research/framework-docs-python-backend.md) — LangGraph API (10 topics), FastAPI (7 topics), infrastructure libraries (8 topics)
- [framework-docs-infrastructure.md](./research/framework-docs-infrastructure.md) — Devcontainers (5 topics), Kubernetes (8 topics), NATS (6 topics), Postgres (5 topics)
- [framework-docs-slack-integration.md](./research/framework-docs-slack-integration.md) — Bolt API (10 topics), Block Kit (8 topics), SDK utilities (6 topics), webhooks (5 topics)
- [framework-docs-similar-oss.md](./research/framework-docs-similar-oss.md) — LangGraph (6 topics), CrewAI (4 topics), AutoGen (4 topics), OpenHands (4 topics), SWE-agent (2 topics)

---

### Clean Code Analysis (4 files)
**Purpose**: Code quality standards and anti-patterns

**Summary**: Established 98 standards: Python backend (20 standards covering hexagonal architecture, event sourcing, async patterns), infrastructure (25 standards covering IaC, containers, sandbox security, event store ops), Slack (23 standards covering adapter pattern, formatting, testing), OSS lessons (30 standards covering adoption, enterprise requirements, recommended practices).

**Contents**:
- [clean-code-python-backend.md](./research/clean-code-python-backend.md) — CLEAN-PY-01 to 20
- [clean-code-infrastructure.md](./research/clean-code-infrastructure.md) — CLEAN-INFRA-01 to 25
- [clean-code-slack-integration.md](./research/clean-code-slack-integration.md) — CLEAN-SLACK-01 to 23
- [clean-code-similar-oss.md](./research/clean-code-similar-oss.md) — CLEAN-OSS-01 to 30

---

### Web Research (4 files)
**Purpose**: Current best practices and production patterns (2024-2025)

**Summary**: Synthesized best practices for event sourcing in Python, LangGraph production patterns, PII protection, FastAPI at scale, sandbox isolation, NATS JetStream, Kubernetes for AI workloads, Slack bot architecture, and OSS agent platform landscape.

**Contents**:
- [web-research-python-backend.md](./research/web-research-python-backend.md) — Event sourcing (6 topics), LangGraph production (6 topics), PII (5 topics), FastAPI (5 topics)
- [web-research-infrastructure.md](./research/web-research-infrastructure.md) — Sandbox isolation (6 topics), NATS (4 topics), K8s (6 topics), Docker/CI-CD (5 topics)
- [web-research-slack-integration.md](./research/web-research-slack-integration.md) — Bot architecture (6 topics), Agent UX (6 topics), security (4 topics), integration patterns (4 topics)
- [web-research-similar-oss.md](./research/web-research-similar-oss.md) — Market landscape (5 topics), architecture lessons (5 topics), enterprise gaps (5 topics), trends (5 topics)

---

### Shared Appendices (2 files)
**Purpose**: Cross-cutting evidence and risk analysis

**Contents**:
- [evidence-index.md](./research/evidence-index.md) — Consolidated 200+ evidence items across all categories
- [risks.md](./research/risks.md) — 10 risks with likelihood/impact/mitigation, common issues, testing considerations

---

## Decision Matrix

| Criterion (Weight) | Option A: Minimal MVP | Option B: Modular Monolith | Option C: Microservices | Option D: LangGraph Platform |
|---|---|---|---|---|
| Enterprise Readiness (0.30) | 2/10 (0.6) | 9/10 (2.7) | 9/10 (2.7) | 5/10 (1.5) |
| Architecture Fit (0.25) | 3/10 (0.75) | 10/10 (2.5) | 8/10 (2.0) | 5/10 (1.25) |
| Clean Code (0.20) | 5/10 (1.0) | 9/10 (1.8) | 7/10 (1.4) | 6/10 (1.2) |
| Operational Simplicity (0.15) | 9/10 (1.35) | 7/10 (1.05) | 3/10 (0.45) | 8/10 (1.2) |
| Risk/Complexity (0.10) | 9/10 (0.9) | 6/10 (0.6) | 3/10 (0.3) | 5/10 (0.5) |
| **Total** | **4.6** | **8.65** | **6.85** | **5.65** |

Option B scores highest by a significant margin, balancing enterprise readiness with operational simplicity.
