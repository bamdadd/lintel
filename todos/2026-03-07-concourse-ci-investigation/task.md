# Concourse CI Investigation for Lintel Scheduling

**Created:** 2026-03-07
**Status:** todo

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

## Reference

- https://concourse-ci.org/
- https://concourse-ci.org/docs.html

## Notes

- Concourse is distributed multi-node by default; Lintel starts single-node
- Different channels (Slack-based) vs Concourse's resource-based triggers
- Different pipeline format needed for AI agent workflows vs CI/CD tasks
- Focus on scheduling primitives that can be adapted for agent orchestration
