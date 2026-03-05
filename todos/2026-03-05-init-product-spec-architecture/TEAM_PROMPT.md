# Lintel Implementation — Team Execution Guide

## How to Run

Execute phases sequentially, parallelizing where indicated. Each phase uses:

```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase N: <phase name>
```

## Execution Waves

### Wave 1 — Foundation (sequential, 1 agent)

```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 1: Project Skeleton & Tooling
```

Wait for completion, then:

```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 2: Contracts & Domain Types
```

### Wave 2 — Core Infrastructure (parallel, 3 agents)

Run these three simultaneously in separate terminals/sessions:

**Agent A:**
```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 3: Event Store. Depends on Phase 2 contracts being complete.
```

**Agent B:**
```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 4: PII Firewall & Vault. Depends on Phase 2 contracts being complete.
```

**Agent C:**
```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 5: Configuration & Observability. Depends on Phase 2 contracts being complete.
```

Wait for ALL three to complete before proceeding.

### Wave 3 — Channel & Projections (parallel, 2 agents)

**Agent A:**
```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 6: Slack Channel Adapter. Depends on Phase 3 (event store) and Phase 4 (PII firewall) being complete.
```

**Agent B:**
```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 12: Projections & Read Models. Depends on Phase 3 (event store) being complete.
```

Wait for BOTH to complete.

### Wave 4 — Workflow & Agent (sequential, 1 agent)

```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 7: Workflow Engine (LangGraph). Depends on Phase 3 (event store) and Phase 6 (Slack adapter) being complete.
```

Then:

```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 8: Agent Runtime & Model Router. Depends on Phase 7 (workflow engine) being complete.
```

### Wave 5 — Extensions (parallel, 2 agents + 1 follow-up)

**Agent A:**
```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 9: Skill Registry. Depends on Phase 8 (agent runtime) being complete.
```

**Agent B:**
```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 10: Sandbox Manager. Depends on Phase 8 (agent runtime) being complete.
```

Wait for Phase 10 to complete, then:

```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 11: Repo Provider (GitHub). Depends on Phase 10 (sandbox manager) being complete.
```

### Wave 6 — Assembly (sequential, 1 agent each)

```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 13: API Layer & FastAPI App. Depends on all component phases (6-12) being complete.
```

```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 14: Docker Compose & Local Dev. Depends on Phase 13.
```

```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 15: Integration Tests & E2E. Depends on Phase 14.
```

```
/ebury:code @todos/2026-03-05-init-product-spec-architecture/ Implement Phase 16: Documentation & CI/CD. Depends on Phase 15.
```

## Summary

| Wave | Phases | Agents | Blocking? |
|------|--------|--------|-----------|
| 1 | 1, 2 | 1 (sequential) | Blocks everything |
| 2 | 3, 4, 5 | 3 (parallel) | Blocks waves 3-6 |
| 3 | 6, 12 | 2 (parallel) | 6 blocks wave 4 |
| 4 | 7, 8 | 1 (sequential) | Blocks wave 5 |
| 5 | 9, 10, 11 | 2+1 (parallel then sequential) | Blocks wave 6 |
| 6 | 13, 14, 15, 16 | 1 (sequential) | Final assembly |

**Total: 16 phases across 6 waves. Max parallelism: 3 agents.**

## Notes

- Each agent should work in a separate git worktree to avoid conflicts
- After each parallel wave, merge worktrees and resolve any conflicts before the next wave
- Check `implementation_checklist.md` after each phase to track progress
