Lintel Architecture Specification

Version: 0.1
Status: Draft
Scope: Open source, enterprise-grade, self-hosted or managed deployment

1. Architecture goals

Lintel is a distributed system that enables multi-human, multi-agent collaboration through channels like Slack, with agent work executed in isolated sandboxes and governed by event sourcing, auditability, and policy gates.

Key goals:
	•	Channel-first collaboration: threads and channels are the user interface and system control plane
	•	Multi-agent parallelism: many agents can run concurrently on the same thread without sharing a local directory
	•	Replaceable components: channels, models, PII pipeline, sandboxes, repo providers, workflow engines
	•	Event sourcing by default: all state is derived from immutable events with strong audit logs
	•	Enterprise controls: RBAC, SSO, policy enforcement, data residency, observability, retention
	•	Hybrid execution: locally hosted models and managed models can coexist per agent role

Non-goals for v0.1:
	•	Fully autonomous merging and deployment without human approvals
	•	Perfect exactly-once processing across all distributed components (use at-least-once with idempotency)

⸻

2. High-level system view

Lintel is composed of a control plane plus distributed worker nodes. Slack or other channels connect to the control plane. Work is scheduled to workers that run agent steps and sandbox jobs. All actions emit events into an append-only event store. Read models power UI, status, and compliance views.

Logical flow
	1.	Channel message arrives (Slack thread)
	2.	Ingestion normalises and de-identifies content (Presidio)
	3.	Event is appended to event store
	4.	Workflow engine advances the thread state and schedules work
	5.	Agents run (planning, review, summarisation) and may schedule sandbox jobs
	6.	Sandbox jobs run in isolated devcontainers, produce artifacts (patch, PR, logs)
	7.	Humans approve gates (spec gate, merge gate, deploy gate)
	8.	Events capture everything and projections update status

⸻

3. Core concepts and abstractions

3.1 Thread as workflow instance

A thread (Slack thread_ts plus channel_id) is the canonical identifier for a workflow instance.

ThreadRef:
	•	channel_id
	•	thread_ts
	•	workspace_id (Slack workspace or organisation id)

Every action in Lintel is correlated to a ThreadRef and a correlation_id.

3.2 Agent

An agent is a role-bound execution unit with:
	•	model policy (provider, model name, constraints)
	•	tool allow-list
	•	skill access scope
	•	memory scope (thread-only, project-level, global)
	•	sandbox requirement (none, optional, required)

Agents do not access raw PII. They only see sanitised context.

3.3 Skill

A skill is a callable capability exposed to agents and optionally to humans. Skills are dynamically registered and versioned.

A skill consists of:
	•	input schema, output schema
	•	required permissions
	•	required tools
	•	execution mode (inline, async job, sandbox job)
	•	allowed channels and presentation template
	•	policy hooks (pre-check, post-check)

Skills can be added and removed at runtime via the Skill Registry.

3.4 Channel adapter

A channel adapter is a pluggable module that maps a collaboration surface to the Lintel event protocol:
	•	Slack
	•	Teams
	•	GitHub PR comments
	•	Web UI
	•	CLI

Adapters translate events in and responses out, preserving thread context.

3.5 Sandbox job

A sandbox job is a bounded unit of code execution. It runs in a disposable devcontainer with isolated filesystem, resource limits, and controlled network.

Sandbox jobs produce artifacts:
	•	logs
	•	diffs
	•	test results
	•	commit SHAs
	•	PR links

⸻

4. Service boundaries and modules

Lintel should be organised into replaceable services with stable contracts. A single deployment can run these as separate services or a modular monolith initially.

4.1 Channel Gateway

Responsibilities:
	•	receive inbound events from Slack or other channels
	•	verify signatures and identity
	•	translate to canonical events
	•	send outbound messages, task cards, approvals

Interfaces:
	•	inbound: webhook, events API
	•	outbound: post message, update message, interactive components

Replaceable with: other channel adapters

4.2 Ingestion and PII Firewall

Responsibilities:
	•	normalise message text and attachments metadata
	•	detect PII with Microsoft Presidio
	•	anonymise to stable placeholders within a thread
	•	verification pass, fail closed if residual PII risk is above threshold
	•	emit events for detection, anonymisation, and policy outcomes

Data separation:
	•	sanitised content stored in normal state store
	•	raw content stored encrypted with strict access, never passed to LLMs
	•	mapping vault stores placeholder to raw values, reveal is human-only

Replaceable with: Azure PII container, custom detectors, other DLP tools

4.3 Event Store

Responsibilities:
	•	append-only persistence of all domain events
	•	idempotency enforcement
	•	stream reads for projections
	•	optional tamper-evidence via hash chaining per stream

Implementation choices:
	•	Postgres append-only table to start
	•	Optional event backbone: NATS JetStream or Kafka for fanout, still persist to Postgres for compliance

4.4 Workflow Engine

Default: LangGraph based runner

Responsibilities:
	•	maintain thread workflow state via event-sourced projections
	•	route intents to workflows and skills
	•	schedule agent steps and sandbox jobs
	•	manage parallelism and joins
	•	enforce human approval gates

Replaceable with: Temporal, Prefect, Dagster, Argo

4.5 Agent Runtime

Responsibilities:
	•	execute agent steps with a given model policy and tool set
	•	call skills and tools via controlled interfaces
	•	produce structured outputs (plans, task breakdowns, reviews)
	•	emit events for every step and tool call (sanitised)

Implementation:
	•	Python is natural for LangGraph, LangChain, Presidio integration
	•	Agent runtime can be separated from control plane and run on worker nodes

4.6 Model Router and Provider Layer

Responsibilities:
	•	choose model per agent role, workload type, or sensitivity policy
	•	support multiple providers: local inference, Bedrock, other hosted models
	•	enforce constraints: token limits, temperature policy, safety policies
	•	record model selection decisions as events

Replaceable components:
	•	provider implementations
	•	routing policy engine

4.7 Skill Registry

Responsibilities:
	•	dynamic registration and deregistration of skills
	•	versioning and rollout policies
	•	permission mapping and policy requirements
	•	discovery for agents and UI listing

Skill execution patterns:
	•	in-process skill (fast)
	•	remote skill service over HTTP or gRPC (replaceable, language-agnostic)
	•	sandbox skill (requires devcontainer)

4.8 Sandbox Manager

Responsibilities:
	•	allocate isolated sandboxes per job
	•	schedule across distributed sandbox runners
	•	enforce resource quotas and timeouts
	•	collect logs and artifacts
	•	tear down and garbage collect sandboxes

Backends:
	•	Docker host with devcontainers CLI
	•	Kubernetes Jobs
	•	Firecracker microVMs

4.9 Repo Provider

Responsibilities:
	•	Git operations: clone, branch, commit, push
	•	PR operations: create PR, comment, fetch diffs, statuses
	•	link artifacts back to thread

Providers:
	•	GitHub, GitLab, Bitbucket

4.10 Policy and Identity Service

Responsibilities:
	•	authentication: SSO via OIDC, SAML via enterprise identity
	•	RBAC: who can invoke which agents and skills
	•	approval gates: required approvers and quorum rules
	•	sensitive operations: reveal, merge, deploy
	•	audit exports and retention policies

4.11 Projections and Read Models

Responsibilities:
	•	maintain queryable views derived from events:
	•	thread status view
	•	task backlog view
	•	artifact view
	•	compliance and audit view
	•	billing and usage view

Storage:
	•	Postgres materialised tables
	•	optional search and vector retrieval over sanitised text (pgvector)

4.12 Observability

Responsibilities:
	•	structured logs with correlation_id
	•	distributed tracing (OpenTelemetry)
	•	metrics (Prometheus compatible)
	•	event replay tooling for debugging and compliance

⸻

5. Event sourcing model

5.1 Event envelope

Every event is an immutable record with a shared envelope:
	•	event_id (UUID)
	•	event_type
	•	occurred_at (UTC)
	•	actor_type (human, agent, system)
	•	actor_id
	•	thread_ref (workspace_id, channel_id, thread_ts)
	•	correlation_id
	•	causation_id (the event that led to this one)
	•	payload (JSON)
	•	payload_hash (optional)
	•	prev_hash (optional per stream)

5.2 Key event types

Channel and ingestion:
	•	ThreadMessageReceived
	•	MessageNormalised
	•	PIIDetected
	•	PIIAnonymised
	•	PIIResidualRiskBlocked
	•	AttachmentReferenced

Workflow and skills:
	•	IntentRouted
	•	WorkflowStarted
	•	WorkflowAdvanced
	•	SkillRegistered
	•	SkillDeregistered
	•	SkillInvoked
	•	SkillSucceeded
	•	SkillFailed

Agents and models:
	•	AgentStepScheduled
	•	AgentStepStarted
	•	ModelSelected
	•	ModelCallStarted
	•	ModelCallCompleted
	•	ToolCallRequested
	•	ToolCallCompleted

Sandbox:
	•	SandboxJobScheduled
	•	SandboxCreated
	•	SandboxCommandExecuted
	•	SandboxArtifactsCollected
	•	SandboxDestroyed

Repo and review:
	•	BranchCreated
	•	CommitCreated
	•	PRCreated
	•	PRCommentPosted
	•	ReviewSuggested
	•	HumanApprovalGranted
	•	HumanApprovalRejected
	•	PRMerged

Security and admin:
	•	PolicyDecisionRecorded
	•	VaultRevealRequested
	•	VaultRevealGranted
	•	VaultRevealDenied

5.3 Idempotency

Processing is at-least-once. Every command that can be retried must include:
	•	idempotency_key
	•	expected_state_version (optimistic concurrency where needed)

Projections must be replayable and resilient to duplicates.

⸻

6. Workflow orchestration with LangGraph

6.1 Thread graph pattern

Each thread has a workflow graph with parallel branches:

Nodes:
	•	ingest_event
	•	update_thread_summary
	•	route_intent
	•	plan_work_items
	•	spawn_parallel_agents (PM, design, eng plan)
	•	join_plans
	•	approval_gate_spec
	•	spawn_sandbox_jobs (parallel coders)
	•	collect_artifacts
	•	review_agent
	•	approval_gate_merge
	•	close_thread

6.2 Parallelism

Parallelism occurs at two levels:
	•	reasoning parallelism: multiple agents produce plans or reviews concurrently
	•	execution parallelism: multiple sandbox jobs run concurrently in devcontainers

A join node reconciles outputs into:
	•	combined plan
	•	task allocation
	•	file ownership suggestion
	•	conflict resolution prompts for humans

6.3 Human approval gates

Gates are modelled as workflow states that require a channel action:
	•	emoji reaction
	•	button click
	•	slash command

Approvals emit events and unlock subsequent nodes.

⸻

7. Sandbox architecture with devcontainers

7.1 Per-agent sandbox isolation

Each coding or test agent runs in its own sandbox, never in a shared local directory.

Sandbox characteristics:
	•	separate filesystem via Docker volume per sandbox
	•	repo cloned at a specific base SHA
	•	dedicated branch per job, e.g. agent//
	•	resource limits: CPU, memory, disk quota
	•	network policy: default deny, allow-list registries if needed
	•	secrets: injected via runner, never included in model context

7.2 Devcontainer lifecycle
	1.	Allocate sandbox on a runner node
	2.	Create volume and clone repo
	3.	Build or pull devcontainer image based on repository devcontainer config
	4.	Run commands (lint, tests, generation scripts)
	5.	Apply patches and commit changes
	6.	Push branch and open PR
	7.	Collect artifacts and logs
	8.	Destroy container, keep volume only if configured, otherwise garbage collect

7.3 Speed optimisations
	•	prebuild devcontainer images keyed by hash of devcontainer config
	•	cache package managers in controlled cache volumes
	•	keep runners warm with base images pulled

⸻

8. Multi-model, per-agent routing

Model routing is policy-driven and evented.

Inputs to routing:
	•	agent role
	•	workload type (planning, coding, review, summarise)
	•	cost profile and SLA
	•	sensitivity policy (even sanitised content may have stricter requirements)
	•	organisation configuration

Output:
	•	provider_id
	•	model_name
	•	parameters

Record ModelSelected events for auditability and cost attribution.

⸻

9. Dynamic skills system

9.1 Skill packaging options

Lintel should support multiple packaging methods:
	•	HTTP skill services (recommended for replaceability)
	•	in-process Python skills (fast iteration)
	•	containerised skills (strong isolation)
	•	optional WASM skills (portable, safer execution)

9.2 Skill registry operations
	•	register skill version
	•	enable skill for an organisation
	•	attach policy requirements and permissions
	•	deprecate and remove skill versions
	•	audit every change as events

9.3 Skill permissions

Permissions should be enforced at invocation time:
	•	who can invoke skill
	•	which agents can use skill
	•	which data scopes skill can access
	•	whether sandbox is required

⸻

10. Distributed nodes

10.1 Node types
	•	Control plane nodes: API, event store, policy, registry
	•	Agent worker nodes: run LangGraph steps and model calls
	•	Sandbox runner nodes: run devcontainers and heavy compute
	•	Projection nodes: build read models, compliance views, exports

10.2 Node registry and scheduling

Workers advertise capabilities:
	•	sandbox support
	•	devcontainer versions
	•	GPU availability for local models
	•	network profiles
	•	region and residency

Scheduler places jobs based on:
	•	capability requirements
	•	data residency
	•	queue depth
	•	cost profile
	•	affinity to repos or caches

10.3 Messaging backbone

Use an event bus for distribution:
	•	NATS JetStream or Kafka recommended
	•	control plane persists to Postgres event store
	•	workers subscribe to relevant event types and command topics

⸻

11. Security model

11.1 Data handling
	•	raw channel text stored encrypted and restricted
	•	sanitised text used for agents and persisted for projections
	•	PII map stored in vault, reveal is human-only and audited
	•	never send raw PII to models

11.2 Tooling safety
	•	strict tool allow-list per agent role
	•	sandbox jobs run with least privilege credentials
	•	no Docker socket access inside sandboxes
	•	default network deny in sandboxes, allow-list as needed

11.3 Approval gates

Enforce gates for:
	•	PR merge
	•	infrastructure changes
	•	deployments
	•	vault reveals

All gate decisions emit policy and approval events.

⸻

12. Deployment modes

12.1 Self-hosted enterprise
	•	Kubernetes recommended
	•	external Postgres for event store and projections
	•	Redis optional for job queues if not using NATS/Kafka
	•	organisation SSO integration
	•	private model inference or approved providers

12.2 Managed service
	•	multi-tenant control plane with tenant isolation
	•	dedicated sandbox runner pools per tenant or per compliance tier
	•	tenant-specific encryption keys
	•	audit export APIs and retention policies

⸻

13. Suggested repository and service layout

Monorepo layout:
	•	/contracts (schemas for events, commands, skills)
	•	/channel-adapters/slack
	•	/security/pii-firewall (Presidio adapter)
	•	/security/vault
	•	/core/event-store
	•	/core/policy
	•	/core/skill-registry
	•	/workflow/langgraph-runner
	•	/agents/runtime
	•	/models/router and providers
	•	/sandbox/manager
	•	/sandbox/runner-devcontainers
	•	/integrations/repo-github, repo-gitlab
	•	/projections/thread-view, compliance-view
	•	/ops/helm-charts, docker-compose

⸻

14. Minimal viable architecture for v0.1

Must-have services:
	•	Slack adapter
	•	PII firewall with Presidio
	•	Postgres event store with projections
	•	LangGraph runner
	•	Model router with at least 2 providers (local and hosted)
	•	Skill registry with hot reload
	•	Sandbox manager with Docker devcontainers backend
	•	GitHub provider
	•	RBAC and audit export endpoints

Must-have workflows:
	•	feature spec workflow with spec approval gate
	•	implement workflow that spawns parallel coding sandboxes
	•	PR review workflow with merge approval gate

⸻

If you want, I can turn this into:
	•	a concrete event schema set (JSON Schema or Pydantic models)
	•	a “service contract” document with interfaces for ChannelAdapter, Deidentifier, Skill, SandboxProvider, RepoProvider
	•	a first LangGraph workflow definition for the feature-to-PR pipeline, including the approval gates and sandbox scheduling logic