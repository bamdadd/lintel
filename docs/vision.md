# Lintel — Platform Vision

## Mission

Lintel is the AI-human engineering platform where agents and humans collaborate as teammates within a unified, event-sourced, measurable software delivery lifecycle.

DX, LinearB, and Minware measure engineering performance. Lintel measures **and** executes — it is both the measurement system and the execution engine. When Lintel detects a quality regression through its metrics projections, it can trigger a remediation workflow automatically.

## Core Principles

### Event-First

Every state change is an immutable event. Events are past-tense facts — they are never rejected or modified. Commands express intent and may fail. The event store is the single source of truth. All read models (projections), metrics, integrations, and guardrails are derived from the event stream.

Events describe what happened. Guardrails emit commands (never events directly). This prevents circular dependencies.

```
Command → Handler → (State Change + Event) → EventBus → Subscribers
                                                 ├── Projections
                                                 ├── Guardrail Engine → (New Command)
                                                 ├── Metrics Engine
                                                 └── Integration Sync
```

### Measurable

Every action by every actor (human, agent, system) produces observable data. DORA metrics, agent accuracy, rework rates, cycle times, and cost efficiency are all computed from the event stream without manual instrumentation.

You cannot measure what doesn't exist. The platform follows a strict bottom-up dependency chain:

```
Layer 6: Continuous Improvement    (learn → feed back → rearchitect)
Layer 5: Measurement & Analytics   (DORA, agent accuracy, team velocity)
Layer 4: Deployment & Observability (deployments, incidents, feature flags)
Layer 3: Guardrails & Safety       (cost limits, escalation, sandbox hardening)
Layer 2: Collaboration & Routing   (teams, channels, integrations, ticketing)
Layer 1: Event Infrastructure      (event bus, subscriptions, projections)
Layer 0: Foundation                (what exists today)
```

### Collaborative

Teams are composed of both humans and AI agents. Agents are first-class team members with the same roles, permissions, and performance records as humans. A team lead can be an AI agent. An agent can approve work items if granted that permission.

Users and agents interact through channels (Slack, Discord, Teams, Web) bound to teams. Projects are ongoing products maintained by teams — they have no end date.

### Safe

Guardrails are not blockers — they are enablers. Threshold-based auto-escalation replaces rigid approval chains:

- **Tier 0 (Warn):** Notification only — agent rework rate > 20%
- **Tier 1 (Approve):** Pause and request human approval — rework rate > 30%
- **Tier 2 (Block):** Block and escalate to team lead — rework rate > 50%
- **Tier 3 (Stop):** Emergency stop — cost exceeds budget by 200%

Agents operate in sandboxed containers with `--cap-drop ALL`, seccomp profiles, read-only root filesystems, and no network access (except during controlled clone phase). Cost controls prevent runaway LLM spending. PII is detected and replaced before reaching any LLM.

## Differentiation

| Dimension | DX | LinearB | Minware | Lintel |
|---|---|---|---|---|
| What it does | Measures developer experience | Measures engineering metrics | Measures time allocation | **Measures AND executes** |
| AI agents | Not tracked | Not tracked | Not tracked | First-class team members with performance records |
| Event architecture | ETL from Git/CI | ETL from Git/CI | ETL from Git/meetings | Native event sourcing — every metric derived from immutable events |
| Software delivery | Measurement only | Measurement only | Measurement only | Full lifecycle: desire → develop → review → deploy → observe → learn |
| Guardrails | None | None | None | Threshold-based auto-escalation with cooldowns |
| Experimentation | None | None | None | Feature flags + A/B testing for agent configurations |
| Workflow execution | None | None | None | LangGraph multi-agent workflows in sandboxed environments |
| Self-improving | No | No | No | Metrics trigger automated remediation workflows |

DX/LinearB/Minware are **mirrors** — they show you what happened. Lintel is a **flywheel** — it measures, acts, and improves automatically.

## Products, Not Projects

Projects in Lintel represent ongoing products. They have no start date, no end date. A product is maintained forever. Work items flow through the product's delivery loop — each work item has a lifecycle, but the product itself is perpetual.

Portfolios group products for cross-product analytics and organizational reporting.

## The Software Delivery Flywheel

```
  +---------+     +---------+     +--------+     +--------+     +---------+     +-------+
  | DESIRE  | --> | DEVELOP | --> | REVIEW | --> | DEPLOY | --> | OBSERVE | --> | LEARN |
  +---------+     +---------+     +--------+     +--------+     +---------+     +-------+
       ^                                                                           |
       +------------- learnings inform next desire --------------------------------+
```

The delivery loop is fully configurable. Teams define their own phase sequences per product. The default sequence is Desire → Develop → Review → Deploy → Observe → Learn, but phases can be skipped, reordered, or custom phases can be added.

Each phase transition is an event. Each event feeds metrics. Metrics trigger guardrails. Guardrails emit commands. Commands produce new events. The flywheel turns.
