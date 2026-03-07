# Concourse CI Investigation for Lintel Scheduling

**Created:** 2026-03-07
**Status:** researched

## Artifacts

- `task.md` — Task definition
- `research.md` — Research findings with synthesis, options, and recommendation
- `research/` — Detailed appendices (4 files):
  - `codebase-survey-api.md` — Lintel codebase survey
  - `web-research-concourse-architecture.md` — Concourse internals
  - `web-research-concourse-ui.md` — Concourse UI/streaming/metrics
  - `web-research-langgraph-pipelines.md` — LangGraph pipeline model
- `plan.md` — Implementation plan (Option D: Hybrid)
- `implementation_checklist.md` — Progress tracking

## Objective

Investigate Concourse CI's architecture and scheduling model to inform Lintel's pipeline/scheduling design. Lintel aims to be "Concourse for AI" — with different channels and a different pipeline format. Start with single-node, unlike Concourse's distributed multi-node default.

## Key Areas to Investigate

- [ ] Concourse CI architecture overview (workers, web, ATC, TSA)
- [ ] Pipeline definition format (YAML resources, jobs, tasks, plans)
- [ ] Scheduling model (how jobs are triggered, resource checking, time triggers)
- [ ] Resource abstraction (inputs/outputs, resource types, custom resources)
- [ ] Task execution model (containers, volumes, caching)
- [ ] Web UI and API design
- [ ] What's missing or doesn't translate well to AI agent orchestration
- [ ] Design single-node equivalent architecture for Lintel

## UI Requirements

- Concourse-style task execution UI where you can click into a job and see each step — we want the same but showing the prompt/input for each tool executed (docker, bash, etc.)
- Live streaming of task output in the UI — minimal latency, output should appear as fast as possible
- Capture and display timing for every task run (start, end, duration per step)
- Expose task timing as metrics for optimization (identify slow steps, track regressions)

## Worktree

Branch: `concourse-ci-investigation`
Path: `../lintel-concourse-investigation`

All work for this task should be done in the worktree above, not on main.

## Reference

- https://concourse-ci.org/
- https://concourse-ci.org/docs.html
- https://concourse-ci.org/examples/
- https://ci.concourse-ci.org/teams/main/pipelines/concourse (live pipeline dogfooding their own CI)

## Notes

- Concourse is distributed multi-node by default; Lintel starts single-node
- Different channels (Slack-based) vs Concourse's resource-based triggers
- Prefer LangGraph pipeline model over Concourse's YAML-based pipeline format
- Focus on scheduling primitives that can be adapted for agent orchestration
