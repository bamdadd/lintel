# Framework Documentation - Similar OSS Projects

## Documentation from Open Source AI Agent Platforms

---

## 1. LangGraph (DOCS-OSS-01 to DOCS-OSS-06)

### DOCS-OSS-01: Graph Builder API

LangGraph's `StateGraph` provides the cleanest orchestration API among OSS platforms:

```python
from langgraph.graph import StateGraph, END

builder = StateGraph(AgentState)
builder.add_node("planner", planner_node)
builder.add_node("coder", coder_node)
builder.add_node("reviewer", reviewer_node)
builder.set_entry_point("planner")
builder.add_conditional_edges("planner", route_to_workers)
builder.add_edge("coder", "reviewer")
builder.add_edge("reviewer", END)
graph = builder.compile(checkpointer=postgres_saver)
```

### DOCS-OSS-02: LangGraph Platform vs Open Source

| Feature | Open Source | LangGraph Platform |
|---------|------------|-------------------|
| Graph execution | Yes | Yes |
| Checkpointing | Yes (self-hosted DB) | Managed |
| Streaming | Yes | Yes |
| Human-in-the-loop | Yes (interrupt) | Yes + UI |
| Monitoring | DIY | LangSmith integration |
| Deployment | Self-managed | Managed Cloud/BYOC |
| Cost | Free | Per-invocation pricing |

Lintel should use open-source LangGraph only, avoiding LangSmith dependency.

### DOCS-OSS-03: LangGraph Interrupt Patterns

Three interrupt patterns for human-in-the-loop:
1. `interrupt_before=["node"]` — pause before node execution
2. `interrupt_after=["node"]` — pause after node produces output
3. Dynamic interrupt via `NodeInterrupt` exception within a node

Pattern 1 fits Lintel's approval gates (pause before merge, before deploy).

### DOCS-OSS-04: Multi-Agent Architectures in LangGraph

Documented patterns:
- **Supervisor**: One agent delegates to specialists
- **Network**: Agents hand off to each other via conditional edges
- **Hierarchical**: Nested supervisors with subgraphs
- **Map-Reduce**: Fan-out via `Send`, collect via reducer

Lintel's architecture maps to Supervisor + Map-Reduce hybrid.

### DOCS-OSS-05: LangGraph Memory

- **Short-term**: Graph state (TypedDict) — within a single invocation
- **Long-term**: Checkpointer (Postgres) — across invocations for same thread
- **Cross-thread**: Custom store (Postgres/Redis) — project-level memory

### DOCS-OSS-06: Tool Nodes

```python
from langgraph.prebuilt import ToolNode

tools = [search_code, run_tests, create_pr]
tool_node = ToolNode(tools)

builder.add_node("tools", tool_node)
builder.add_conditional_edges("agent", should_use_tool, {
    "tool": "tools",
    "done": END,
})
builder.add_edge("tools", "agent")
```

---

## 2. CrewAI (DOCS-OSS-07 to DOCS-OSS-10)

### DOCS-OSS-07: Agent Definition

```python
from crewai import Agent

planner = Agent(
    role="Technical Planner",
    goal="Break features into implementable tasks",
    backstory="Senior engineer who excels at system design",
    llm="anthropic/claude-sonnet-4-20250514",
    tools=[search_codebase, read_file],
    verbose=True,
)
```

Declarative role/goal/backstory is intuitive but the Agent class conflates too many concerns.

### DOCS-OSS-08: Task and Crew

```python
from crewai import Task, Crew

task = Task(
    description="Plan implementation for {feature}",
    agent=planner,
    expected_output="Ordered task list with file changes",
)

crew = Crew(
    agents=[planner, coder, reviewer],
    tasks=[plan_task, code_task, review_task],
    process=Process.sequential,
)
result = crew.kickoff(inputs={"feature": "user auth"})
```

### DOCS-OSS-09: CrewAI Flows

```python
from crewai.flow.flow import Flow, start, listen

class FeatureFlow(Flow):
    @start()
    def plan(self):
        return crew.kickoff(inputs=self.state)

    @listen(plan)
    def implement(self, plan_result):
        return coding_crew.kickoff(inputs={"plan": plan_result})
```

Flows add orchestration on top of Crews. Similar to LangGraph but less mature.

### DOCS-OSS-10: CrewAI Limitations for Lintel

- No built-in event sourcing or audit trail
- No sandbox isolation (agents run in-process)
- No human-in-the-loop gates (approval is manual)
- Limited persistence (no durable checkpointing)
- Tight coupling to specific LLM providers

---

## 3. AutoGen (DOCS-OSS-11 to DOCS-OSS-14)

### DOCS-OSS-11: AutoGen 0.4 Architecture

Three layers:
- **Core**: Message passing, agent runtime, CancellationToken
- **AgentChat**: High-level agents (AssistantAgent, UserProxyAgent)
- **Extensions**: Model clients, tool executors, code execution

### DOCS-OSS-12: Team Patterns

```python
from autogen_agentchat.teams import RoundRobinGroupChat, SelectorGroupChat

team = SelectorGroupChat(
    participants=[planner, coder, reviewer],
    model_client=model,
    termination_condition=MaxMessageTermination(20),
)
result = await team.run(task="Implement feature X")
```

### DOCS-OSS-13: Code Execution

```python
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor

executor = DockerCommandLineCodeExecutor(
    image="python:3.12-slim",
    timeout=60,
    work_dir="/workspace",
)
result = await executor.execute_code_blocks([
    CodeBlock(language="python", code="print('hello')"),
])
```

AutoGen's Docker executor is simpler than devcontainers but less configurable.

### DOCS-OSS-14: AutoGen Limitations for Lintel

- GroupChat manager is complex and hard to customize
- No native event sourcing
- Code execution is per-block, not per-repository
- No built-in channel integration (Slack, etc.)

---

## 4. OpenHands (DOCS-OSS-15 to DOCS-OSS-18)

### DOCS-OSS-15: Event Stream Architecture

OpenHands uses an event stream pattern closest to Lintel's vision:

```python
class EventStream:
    async def add_event(self, event: Event, source: EventSource):
        ...
    def get_events(self, start_id=0, end_id=None, filter_type=None):
        ...
    def subscribe(self, subscriber: EventStreamSubscriber):
        ...
```

Events include: `AgentStateChangedObservation`, `CmdRunAction`, `FileEditAction`, `BrowseURLAction`.

### DOCS-OSS-16: Runtime Isolation

```python
class DockerRuntime(Runtime):
    async def run_action(self, action: Action) -> Observation:
        # Execute inside Docker container
        ...
    async def connect(self):
        # Start container with network isolation
        ...
```

OpenHands runs each agent session in a Docker container with:
- Sandboxed filesystem
- Network restrictions
- Resource limits
- Persistent workspace volume

### DOCS-OSS-17: Controller Pattern

```python
class AgentController:
    async def step(self):
        observation = await self.runtime.run_action(action)
        self.event_stream.add_event(observation)
        action = await self.agent.step(self.state)
        self.event_stream.add_event(action)
```

Clean separation: Controller orchestrates, Agent thinks, Runtime executes.

### DOCS-OSS-18: OpenHands Limitations for Lintel

- No multi-agent coordination (single agent per session)
- No channel integration
- No PII protection
- Permissive network by default
- No multi-tenancy

---

## 5. SWE-agent (DOCS-OSS-19 to DOCS-OSS-20)

### DOCS-OSS-19: Command Interface

SWE-agent defines a constrained command set for code editing:
- `open <file>` - Open file in editor
- `edit <start>:<end> <replacement>` - Edit lines
- `search_dir <query>` - Search codebase
- `find_file <name>` - Find file
- `submit` - Create patch

This constrained interface reduces hallucination vs. free-form shell access.

### DOCS-OSS-20: SWE-agent Evaluation

SWE-bench metrics show constrained tool sets outperform unrestricted shell access for code editing tasks. Lintel's skill system should provide structured tools rather than raw shell access.
