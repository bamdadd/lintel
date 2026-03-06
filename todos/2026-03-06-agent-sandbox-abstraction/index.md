# Todo: Agent Sandbox Abstraction

## Description

Define an abstract sandbox interface that allows pointing to a repo and spinning up an isolated environment (devcontainer, cloud dev environment, etc.) for agents to write code, run tests, and execute commands. Start with abstract Protocol definitions so multiple sandbox backends can be plugged in.

### Goals

- Define a `Sandbox` Protocol in `src/lintel/contracts/` with operations: clone repo, run command, read/write files, run tests
- Create a base abstraction that different sandbox providers can implement (devcontainers, cloud dev environments, local Docker, etc.)
- Integrate with the existing agent workflow so agents can be given a sandbox to operate in
- Ensure sandboxes are ephemeral and isolated per workflow run

## Work Artifacts

| Agent        | File                  | Purpose                              |
| ------------ | --------------------- | ------------------------------------ |
| task-manager | index.md              | Task index and tracking              |
| research     | research.md           | Research synthesis and recommendation |
| research     | research/             | Detailed appendices (19 files)       |
| plan         | plan.md               | Implementation plan (Option B)       |
| plan         | implementation_checklist.md | Progress tracking              |

## Notes

- Research complete. Recommends **Option B: Consolidate & Extend with Named Operations**.
- Plan created: 5 phases, 12 files changed, Phases 3+4 parallelizable.
- Next step: `/code` to implement Phase 1.
