# Clean Code Analysis - Similar OSS Projects

## Lessons from OSS AI Agent Platforms for Lintel

---

## 1. Code Quality Lessons

### CrewAI (CLEAN-OSS-01, 02)
- **Good**: Declarative role/goal/backstory agent definition
- **Poor**: Agent class conflates identity, execution, and model binding; stringly-typed tools; minimal error handling

### AutoGen (CLEAN-OSS-03, 04)
- **Good**: Layered architecture (Core, AgentChat, Extensions)
- **Poor**: ConversableAgent base carries too many responsibilities; GroupChatManager over-optimizes for flexibility

### OpenHands (CLEAN-OSS-05, 06)
- **Good**: EventStream pattern; Runtime/Controller separation
- **Poor**: Permissive network by default; no multi-tenancy

### LangGraph (CLEAN-OSS-07, 08)
- **Good**: Cleanest orchestration API; typed state + checkpointing
- **Poor**: Complex graphs hard to visualize; state schema design pitfalls

## 2. Common Issues (CLEAN-OSS-09 to 13)
- Over-abstraction in agent definitions (15+ param constructors)
- Poor error handling in tool execution (broad `except Exception`)
- Missing observability/logging (print-level debugging)
- Inconsistent state management (ad-hoc dicts)
- Tight coupling between orchestration and execution

## 3. Enterprise Requirements (CLEAN-OSS-14 to 18)
- Audit trail completeness (SOC 2 / ISO 27001)
- Hierarchical configuration with runtime changes
- Multi-tenancy isolation at code level
- Security boundary enforcement at infrastructure level
- API versioning and event schema evolution

## 4. Recommended Standards (CLEAN-OSS-19 to 30)

### Adopt
- Typed event schemas from day one (Pydantic + JSON Schema)
- Composition over inheritance for agent definitions
- Structured error types with event emission
- Mandatory correlation context propagation (`contextvars`)
- Interface-first service boundaries (Python `Protocol`)

### More Rigorous Than OSS
- Fail-closed PII detection
- Enforced tool allow-lists at runtime level
- Zero tolerance for state outside event store
- Every service boundary crossing emits a span

### Simpler Than OSS
- Thread-as-workflow with explicit graph nodes (no freeform agent chat)
- Thin model router (retries/caching in middleware, not model abstraction)
- Skills as plain decorated functions, not BaseTool subclasses
- Start as modular monolith, extract services when scaling demands
