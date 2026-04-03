# Lintel

**AI-human engineering platform where agents and humans collaborate as teammates.**

Lintel orchestrates multi-agent workflows for software delivery using event sourcing and CQRS patterns. It measures **and** executes — acting as both the measurement system and the execution engine for your engineering organisation.

## What Lintel does

- **Multi-agent workflows** — LangGraph-powered pipelines that take a feature request from idea to pull request
- **Event-sourced architecture** — every state change is an immutable event; metrics, projections, and guardrails are derived from the event stream
- **Human-in-the-loop approvals** — configurable approval gates pause workflows for human review
- **Sandboxed execution** — agents run code in isolated Docker containers with `--cap-drop ALL`, seccomp profiles, and no network access
- **PII protection** — automatic detection and anonymisation before data reaches any LLM
- **DORA and agent metrics** — deployment frequency, lead time, agent accuracy, rework rates, and cost efficiency computed from events

## The software delivery flywheel

```
  DESIRE  -->  DEVELOP  -->  REVIEW  -->  DEPLOY  -->  OBSERVE  -->  LEARN
    ^                                                                  |
    +------------------ learnings inform next desire ------------------+
```

Each phase transition is an event. Each event feeds metrics. Metrics trigger guardrails. Guardrails emit commands. The flywheel turns.

## Quick links

- [Getting Started](getting-started.md) — clone, install, and trigger your first workflow
- [Architecture](architecture.md) — package layers, event flow, and key abstractions
- [Package Catalogue](packages.md) — all workspace packages with descriptions and dependencies
- [Workflow Authoring](workflow-authoring.md) — how the feature-to-PR pipeline works and how to extend it
