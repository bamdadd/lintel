# lintel-domain

Domain types, events, and business logic shared across packages.

## Structure

- `src/lintel/domain/types.py` — Core domain dataclasses (Project, WorkItem, Board, etc.)
- `src/lintel/domain/events.py` — Domain event definitions
- `src/lintel/domain/seed.py` — Seed data re-exports (agents, skills, workflows)
- `src/lintel/domain/artifacts/` — Artifact parsing, coverage, and quality gate models
- `src/lintel/domain/guardrails/` — Guardrail rules, evaluation engine, condition language, approval bridge, cost rules, escalation
- `src/lintel/domain/metrics/` — Metrics engine + collectors (agent, DORA, human, team)
- `src/lintel/domain/hooks/` — Workflow hook engine and glob-style pattern matching
- `src/lintel/domain/notifications/` — NotificationDispatcher for multi-channel delivery
- `src/lintel/domain/reviews/` — ReviewEngine for automated codebase reviews
- `src/lintel/domain/auth/` — JWT token utilities, password hashing
- `src/lintel/domain/git_events.py` — GitEventListener for git webhook events
- `src/lintel/domain/skills/` — Skill protocols and registry
- `src/lintel/domain/repo/` — Repository provider protocol
- `src/lintel/domain/parallel/` — Parallel execution utilities

## Guardrails Sub-package

- `guardrails/models.py` — `GuardrailRule` dataclass and `GuardrailAction` enum
- `guardrails/default_rules.py` — 7 default rules (warn, block, require_approval)
- `guardrails/engine.py` — `GuardrailEngine` evaluates rules against EventBus events
- `guardrails/evaluator.py` — `GuardrailEvaluator` for condition language evaluation (GRD-3)
- `guardrails/condition_lang.py` — DSL parser for guardrail condition expressions
- `guardrails/approval_bridge.py` — `ApprovalBridge` connects guardrail violations to approvals (GRD-6)
- `guardrails/cost_rules.py` — Cost-based guardrail rules
- `guardrails/repository.py` — `RuleRepository` protocol for rule storage
- `guardrails/escalation.py` — `EscalationTier`, `EscalationPolicy`, `EscalationEngine` (GRD-2)
- `guardrails/seeds.py` — `seed_default_guardrails()` idempotent seed function

## Metrics Sub-package

- `metrics/engine.py` — `MetricsEngine` unified query interface (MET-6)
- `metrics/agent_metrics.py` — Agent performance metrics (MET-1)
- `metrics/dora_metrics.py` — DORA metrics collector (MET-2)
- `metrics/human_metrics.py` — Human interaction metrics (MET-3)
- `metrics/team_metrics.py` — Team-level metrics (MET-4)

## Testing

```bash
make test-domain
# or
uv run pytest packages/domain/tests/ -v
```
