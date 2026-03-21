# lintel-domain

Domain types, events, and business logic shared across packages.

## Structure

- `src/lintel/domain/types.py` — Core domain dataclasses (Project, WorkItem, Board, etc.)
- `src/lintel/domain/events.py` — Domain event definitions
- `src/lintel/domain/seed.py` — Seed data re-exports (agents, skills, workflows)
- `src/lintel/domain/artifacts/` — Artifact parsing, coverage, and quality gate models
- `src/lintel/domain/guardrails/` — Guardrail rules, evaluation engine, and default rule definitions (GRD-7)
- `src/lintel/domain/skills/` — Skill protocols and registry
- `src/lintel/domain/repo/` — Repository provider protocol

## Guardrails Sub-package

- `guardrails/models.py` — `GuardrailRule` dataclass and `GuardrailAction` enum
- `guardrails/default_rules.py` — 7 default rules (warn, block, require_approval)
- `guardrails/engine.py` — `GuardrailEngine` evaluates rules against EventBus events
- `guardrails/repository.py` — `RuleRepository` protocol for rule storage
- `guardrails/seeds.py` — `seed_default_guardrails()` idempotent seed function

## Testing

```bash
make test-domain
# or
uv run pytest packages/domain/tests/ -v
```
