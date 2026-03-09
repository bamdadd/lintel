# Multi-Agent Teams Research

**Source:** Open-source multi-agent application patterns (community collection, 101k+ stars)
**Date:** 2026-03-08
**Relevance:** REQ-016 through REQ-021 (Agent Team Management), REQ-028 (Workflow Templates)

---

## 1. Self-Evolving Agents

**Project:** `advanced_ai_agents/multi_agent_apps/ai_self_evolving_agent`

Framework for automatically evolving agent workflows through structured feedback. Directly relevant to REQ-021 (Feedback Loop & Self-Improvement).

### Evolution Algorithms
- **TextGrad** — Optimizes prompts via gradient-based feedback signals (HotPotQA: 63.58% → 71.02%)
- **AFlow** — Evolves both prompts AND workflow structures simultaneously (MBPP: 69% → 79%)
- **MIPRO** — Iterative instruction-following refinement (MATH: 66% → 76%)

### Architecture Pattern
```
WorkFlowGenerator → AgentManager → WorkFlow → Optimization Layer
```
1. Generate agent graph from natural language goal
2. Instantiate agents with configs
3. Execute workflow
4. Apply evolution algorithm to improve performance

### Lintel Takeaways
- **Prompt optimization as a first-class concern** — Don't just store prompts (REQ-019), actively optimize them with measurable before/after metrics
- **Workflow structure evolution** — Not just prompt tuning; the graph topology itself should be evolvable (REQ-028 Workflow Templates could support this)
- **Benchmark-driven** — Every evolution step is measured against a benchmark; Lintel needs per-agent benchmarks

---

## 2. Multi-Agent Trust Layer

**Project:** `advanced_ai_agents/multi_agent_apps/multi_agent_trust_layer`

Middleware for secure agent-to-agent communication with behavioral governance. Relevant to REQ-017 (Approval Gates), REQ-020 (Chief of Staff).

### Trust Scoring System
- Dynamic 0–1000 score per agent
- Successful task: +10 points
- Policy violation: up to -100 points
- Score ranges determine autonomy:
  - **900+**: Full access
  - **500–699**: Limited actions, requires logging
  - **300–499**: Requires human approval
  - **0–299**: Suspended

### Governance Components
```
Identity Registry → Trust Scoring → Delegation Manager → Policy Engine
                    ↓
              Audit Logger (observes all operations)
```

- **Scope narrowing**: Parent agents grant narrowed permissions to child agents (allowed actions, token limits, time windows, domain restrictions)
- **Human sponsors**: Every agent has a human sponsor for accountability
- **Cryptographic delegation**: Delegations are cryptographically signed

### Lintel Takeaways
- **Trust scores as the autonomy lever** — Instead of binary human-in-the-loop, use a graduated trust score that determines how much oversight an agent needs. The Chief of Staff (REQ-020) adjusts trust scores based on performance
- **Automatic scope narrowing** — When agents are underperforming, automatically restrict their scope rather than just rewriting prompts
- **Human sponsor model** — Each agent has an accountable human; maps well to Lintel's team-based approach
- **Audit as a projection** — All agent actions logged; trust score is a projection over action events (natural fit for event sourcing)

---

## 3. Agent Governance (Policy-Based Sandboxing)

**Project:** `advanced_ai_agents/single_agent_apps/ai_agent_governance`

Deterministic policy-based control layer for agents. Relevant to REQ-017 (Approval Gates), REQ-018 (Human Worker Nodes).

### Three-State Decision Model
Every agent action gets one of:
- **ALLOW** — Proceed autonomously
- **DENY** — Blocked by policy
- **REQUIRE_APPROVAL** — Routes to human-in-the-loop

### Implementation Pattern
- **Action wrapping**: Tools are decorated with governance checks before execution
- **Declarative policies**: YAML config specifying allowed/denied actions
- **Layered validation**: Defense-in-depth with multiple checkpoint rules
- **Rate limiting**: Configurable per action type (e.g., 60 actions/minute)

### Lintel Takeaways
- **YAML-based policy engine** — Governance rules as config, not code; easy for the Chief of Staff agent to modify
- **Three-state model** — Clean pattern for REQ-017 approval gates; every agent action is ALLOW/DENY/REQUIRE_APPROVAL
- **Action wrapping as middleware** — Implement governance as a LangGraph middleware/interceptor that wraps every tool call

---

## 4. Signal Intelligence Pipeline

**Project:** `advanced_ai_agents/multi_agent_apps/devpulse_ai`

Multi-agent pipeline for collecting and evaluating technical signals. Relevant to REQ-016 (Performance Tracking), REQ-025 (Feedback Ingestion).

### Pipeline Architecture
```
Data Collection → Signal Normalization → Relevance Scoring → Risk Assessment → Synthesis
     (utility)        (utility)            (agent)            (agent)          (agent)
```

### Key Design Principle
> "Agents are used only where reasoning is required."

Deterministic operations (HTTP fetching, normalization, deduplication) are plain utilities, NOT agents. This avoids "misleading architecture that suggests LLM involvement where none exists."

### Per-Agent Model Selection
| Component | Type | Model | Rationale |
|---|---|---|---|
| SignalCollector | Utility | None | Pure deterministic logic |
| RelevanceAgent | Agent | gpt-4.1-mini | Fast classification, high-volume |
| RiskAgent | Agent | gpt-4.1-mini | Structured analysis, cost-effective |
| SynthesisAgent | Agent | gpt-4.1 | Complex reasoning across datasets |

### Lintel Takeaways
- **Not everything needs an agent** — Deterministic steps should be utilities; only use agents where reasoning is required
- **Per-agent model selection** — Different agents can use different models based on their task complexity; Lintel should support this in REQ-019 (agent config)
- **Graceful degradation** — Pipeline works with heuristic scoring when LLM APIs are unavailable; important for reliability
- **Env-var model overrides** — Per-agent model customization without code changes

---

## 5. Agent Team Patterns (from Agent Teams directory)

### Services Agency Pattern
**Hierarchical team with CEO oversight:**
- CEO Agent: Strategic decisions, final review
- CTO Agent: Technical feasibility
- Product Manager: Product direction, cross-functional bridge
- Developer: Implementation
- Client Success: Market strategy

**Pattern:** CEO has veto/override power. PM bridges technical and business. Specialized tools per role (AnalyzeProjectRequirements, CreateTechnicalSpecification).

### Multimodal Coding Agent Team
**Sequential pipeline for code generation:**
1. Vision Agent (Gemini) — Extracts problem from images
2. Coding Agent (o3-mini) — Generates solution
3. Execution Agent — Runs in sandboxed environment

**Pattern:** Each agent's output feeds the next. No collaborative back-and-forth; strictly sequential handoff.

### Multi-Agent Researcher
**Sequential enrichment pipeline:**
1. News Researcher → finds stories
2. Article Reader → extracts content from URLs
3. Web Searcher → adds supplementary context

**Pattern:** Progressive enrichment. Each agent adds to the context rather than operating independently.

### Lintel Takeaways
- **Hierarchical vs flat teams** — The Services Agency pattern (CEO oversight) maps directly to the Chief of Staff model. CEO = CoS agent, other agents = specialized workers
- **Sequential vs parallel** — Most real implementations are sequential pipelines, not parallel collaboration. Lintel's LangGraph already supports this
- **Specialized tools per agent** — Each agent role should have its own tool set, not access to everything
- **Cross-functional bridges** — Some agents (PM) exist specifically to translate between domains; useful pattern for the CoS agent

---

## 6. Agent Skills Library

**Directory:** `awesome_agent_skills/`

Curated collection of reusable agent skill definitions. Relevant to REQ-028 (Workflow Templates), REQ-019 (Agent Prompt Store).

### Relevant Skills
| Skill | Key Patterns |
|---|---|
| **project-planner** | 6-step planning framework, task sizing (2–8 hours), three-point estimation, T-shirt sizing, dependency mapping |
| **sprint-planner** | Modified Fibonacci story points, capacity formula (Team × Days × Hours × Focus Factor), Definition of Done checklist |
| **code-reviewer** | Severity hierarchy (Security > Performance > Correctness > Maintainability), structured output with severity indicators |

### Skill Structure Pattern
Each skill is a markdown file with:
- Metadata (name, version, license, author)
- Trigger conditions (when to activate)
- Core framework/methodology
- Output template (standardized format)
- Examples

### Lintel Takeaways
- **Skills as versioned markdown** — Simple, version-controlled skill definitions; aligns with REQ-019 prompt store
- **Trigger conditions** — Skills activate based on context, not explicit invocation; Lintel agents could auto-select skills
- **Output templates** — Standardized output formats per skill ensure consistency; useful for performance grading (REQ-016)
- **Reusable across agents** — Same skill can be used by different agents; supports Workflow Templates (REQ-028)

---

## Summary: Key Patterns for Lintel

### Must-Have Patterns

1. **Graduated trust/autonomy** (Trust Layer) — Don't use binary human-in-the-loop. Use a trust score (0–1000) that determines how much oversight each agent needs. High performers get autonomy; low performers get restrictions.

2. **Three-state action model** (Governance) — Every agent action is ALLOW/DENY/REQUIRE_APPROVAL. Implement as LangGraph middleware.

3. **Measurable prompt evolution** — When the CoS agent changes a prompt, measure before/after performance with benchmarks. Without measurement, you're flying blind.

4. **Agents only where reasoning is needed** — Don't wrap deterministic operations in agents. Performance tracking aggregation, drift detection scanning, etc. should be utilities, not agents.

### Nice-to-Have Patterns

5. **Hierarchical team structure** (Services Agency) — CoS agent as CEO, specialized agents as department heads. CEO has override power and sets priorities.

6. **Skills as composable units** (Agent Skills) — Reusable, versioned skill definitions that any agent can load. Keeps agent capabilities modular.

7. **Per-agent model selection** — Simple tasks get cheaper/faster models; complex reasoning gets powerful models. Cost optimization built into the agent config.

8. **Scope narrowing as a governance lever** (Trust Layer) — Instead of only rewriting prompts, restrict what tools/actions an underperforming agent can use.

### Anti-Patterns to Avoid

- **Full parallel collaboration** — Real implementations are mostly sequential pipelines. Don't over-engineer collaborative back-and-forth between agents.
- **Agent wrapping for everything** — Only use agents where LLM reasoning adds value. Deterministic operations should be plain functions.
- **Binary oversight** — Don't make human-in-the-loop all-or-nothing. Graduate it based on trust/performance.
