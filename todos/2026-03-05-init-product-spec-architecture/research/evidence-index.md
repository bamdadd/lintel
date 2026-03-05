# Evidence Index

## Consolidated Evidence from All Research Agents

---

## Repository / Architecture Evidence (REPO-XX)

### Python Backend (REPO-PY-01 to REPO-PY-22)
| ID | Finding | Confidence |
|----|---------|------------|
| REPO-PY-01 | Postgres event store schema with stream_id/version uniqueness | 0.95 |
| REPO-PY-02 | Python ES libraries: eventsourcing, esdbclient, custom | 0.90 |
| REPO-PY-03 | Projection pattern: async consumer -> materialized views | 0.90 |
| REPO-PY-04 | LangGraph StateGraph with TypedDict state | 0.95 |
| REPO-PY-05 | LangGraph Send API for parallel agent spawning | 0.90 |
| REPO-PY-06 | langgraph-checkpoint-postgres for durable state | 0.95 |
| REPO-PY-07 | FastAPI command/query/webhook/WebSocket patterns | 0.90 |
| REPO-PY-08 | Presidio analyzer + anonymizer pipeline with stable placeholders | 0.90 |
| REPO-PY-09 | Model routing via ModelPolicy + strategy pattern | 0.85 |
| REPO-PY-10 | Hexagonal architecture project layout | 0.90 |
| REPO-PY-11 | Module boundary rationale (contracts, domain, infrastructure) | 0.90 |
| REPO-PY-12 | Async-throughout recommendation | 0.95 |
| REPO-PY-13 | FastAPI Depends() + service container for DI | 0.90 |
| REPO-PY-14 | pydantic-settings for configuration | 0.90 |
| REPO-PY-15 | Domain vs infrastructure exception hierarchies | 0.85 |
| REPO-PY-16 | structlog + OpenTelemetry + correlation ID propagation | 0.90 |
| REPO-PY-17 | Reference: eventsourcing, Marten, Message DB | 0.85 |
| REPO-PY-18 | Reference: langgraph examples, opengpts | 0.85 |
| REPO-PY-19 | Reference: autogen, crewai, opengpts | 0.85 |
| REPO-PY-20 | Presidio FastAPI service samples | 0.85 |
| REPO-PY-21 | Recommended dependency stack (21 libraries) | 0.90 |
| REPO-PY-22 | Critical path build order (9 steps) | 0.85 |

### Infrastructure (REPO-INFRA-01 to REPO-INFRA-22)
| ID | Finding | Confidence |
|----|---------|------------|
| REPO-INFRA-01 | Devcontainer lifecycle pattern | 0.90 |
| REPO-INFRA-02 | Image caching by config hash | 0.85 |
| REPO-INFRA-03 | K8s node type mapping (4 types) | 0.90 |
| REPO-INFRA-04 | Docker-in-Docker options (Sysbox, Kaniko, privileged) | 0.85 |
| REPO-INFRA-05 | Postgres event store schema with full envelope | 0.95 |
| REPO-INFRA-06 | Three-tier retention strategy | 0.85 |
| REPO-INFRA-07 | NATS JetStream vs Kafka comparison | 0.90 |
| REPO-INFRA-08 | Subject hierarchy design | 0.90 |
| REPO-INFRA-09 | Capability-based worker scheduling | 0.85 |
| REPO-INFRA-10 | Docker Compose local dev layout | 0.90 |
| REPO-INFRA-11 | Helm chart structure | 0.85 |
| REPO-INFRA-12 | CI/CD pipeline stages | 0.85 |
| REPO-INFRA-13 | IaC directory layout | 0.85 |
| REPO-INFRA-14 | Container orchestration: Kubernetes | 0.95 |
| REPO-INFRA-15 | Messaging: NATS JetStream for v0.1 | 0.90 |
| REPO-INFRA-16 | Sandbox: Docker+devcontainers primary | 0.90 |
| REPO-INFRA-17 | Event store: Postgres | 0.95 |
| REPO-INFRA-18 | Networking: default-deny NetworkPolicy | 0.90 |
| REPO-INFRA-19 | Defense-in-depth sandbox isolation | 0.90 |
| REPO-INFRA-20 | Secret management patterns | 0.85 |
| REPO-INFRA-21 | Container security hardening | 0.85 |
| REPO-INFRA-22 | Multi-level resource quotas | 0.85 |

### Slack Integration (REPO-SLACK-01 to REPO-SLACK-15)
| ID | Finding | Confidence |
|----|---------|------------|
| REPO-SLACK-01 | ChannelPort adapter pattern | 0.90 |
| REPO-SLACK-02 | Thread-based workflow management | 0.90 |
| REPO-SLACK-03 | Button-based approval gates | 0.90 |
| REPO-SLACK-04 | Block Kit rich message formatting | 0.85 |
| REPO-SLACK-05 | Multi-workspace OAuth V2 support | 0.85 |
| REPO-SLACK-06 | Module layout for channel adapters | 0.85 |
| REPO-SLACK-07 | Event translation layer mapping | 0.90 |
| REPO-SLACK-08 | Outbound message truncation/conversion | 0.85 |
| REPO-SLACK-09 | Socket Mode vs HTTP Mode analysis | 0.90 |
| REPO-SLACK-10 | Rate limiting strategy | 0.85 |
| REPO-SLACK-11 | Thread context management | 0.85 |
| REPO-SLACK-12 | Approval gate UX flow | 0.90 |
| REPO-SLACK-13 | Error handling strategy | 0.85 |
| REPO-SLACK-14 | Reference implementations (Netflix Dispatch, Kubiya) | 0.80 |
| REPO-SLACK-15 | Library stack (slack-bolt, slack-sdk) | 0.90 |

### Similar OSS (REPO-OSS-43 to REPO-OSS-79)
See `codebase-survey-similar-oss.md` for full table (37 evidence items).

---

## Framework Documentation (DOCS-XX)

### Python Backend (DOCS-PY-01 to DOCS-PY-31)
Key findings: LangGraph StateGraph + checkpointing, FastAPI DI, Presidio async wrapping, Pydantic discriminated unions, SQLAlchemy async patterns, LangChain structured output.

### Infrastructure (DOCS-INFRA-01 to DOCS-INFRA-24)
Key findings: devcontainer CLI + features, K8s Jobs/RBAC/NetworkPolicy, NATS JetStream streams/consumers/KV, Helm charts/hooks, PostgreSQL partitioning/LISTEN-NOTIFY/JSONB.

### Slack Integration (DOCS-SLACK-01 to DOCS-SLACK-29)
Key findings: Bolt event listeners + middleware, AsyncApp/AsyncWebClient, Block Kit composition, Events API threading, interactive components with confirmation dialogs.

### Similar OSS (DOCS-OSS-01 to DOCS-OSS-20)
Key findings: CrewAI role-based agents, AutoGen teams/swarm, LangGraph interrupt/checkpoint, OpenHands event stream/DockerRuntime.

---

## Clean Code Analysis (CLEAN-XX)

### Python Backend: CLEAN-PY-01 to CLEAN-PY-20
### Infrastructure: CLEAN-INFRA-01 to CLEAN-INFRA-25
### Slack Integration: CLEAN-SLACK-01 to CLEAN-SLACK-23
### Similar OSS: CLEAN-OSS-01 to CLEAN-OSS-30

---

## Web Research (WEB-XX)

Web research agents operated from training knowledge (WebSearch/WebFetch were unavailable). Content was synthesized from authoritative sources through August 2025 covering LangGraph, FastAPI, Presidio, NATS JetStream, Kafka, Docker security, Firecracker, devcontainers, Slack Bolt, and 10+ OSS agent platforms.

**Total evidence items: ~200+ across all categories**
