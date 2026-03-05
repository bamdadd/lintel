# Risks & Troubleshooting

## Consolidated Risk Analysis for Lintel

---

## High-Impact Risks

### Risk 1: Event Store Schema Lock-In
**Description**: The event envelope schema (event_id, thread_ref, correlation_id, payload structure) and NATS subject hierarchy are extremely difficult to change after production data accumulates.
**Likelihood**: High (design decisions are permanent)
**Impact**: High (requires data migration or parallel stores)
**Mitigation**:
1. Invest heavily in schema design before writing application code
2. Use event versioning with upcasters from day one [CLEAN-PY-11]
3. Include `schema_version` on every event type
4. Design NATS subjects with tenant and aggregate granularity before stream creation [DOCS-INFRA-14]
**Evidence**: [REPO-PY-01, CLEAN-INFRA-20, DOCS-INFRA-14]

### Risk 2: LangGraph Ecosystem Coupling
**Description**: Deep dependency on LangGraph for workflow orchestration. LangGraph Platform (production deployment) ties to LangSmith (proprietary).
**Likelihood**: Medium
**Impact**: High (vendor lock-in for core orchestration)
**Mitigation**:
1. Use LangGraph as an internal implementation detail behind Lintel's own workflow abstractions
2. Build Lintel's own HTTP API layer on top of the open-source graph engine
3. Ensure workflow definitions are portable via clean graph builder interfaces
4. Monitor LangGraph's open-source vs commercial feature split
**Evidence**: [REPO-OSS-67, DOCS-OSS-11, DOCS-OSS-12]

### Risk 3: Sandbox Security Escape
**Description**: AI-generated code executing in Docker containers could exploit container escape vulnerabilities.
**Likelihood**: Low (with proper hardening)
**Impact**: Critical (host compromise)
**Mitigation**:
1. Defense-in-depth: cap-drop ALL + seccomp + read-only rootfs + non-root user [CLEAN-INFRA-14]
2. NetworkPolicy default-deny [CLEAN-INFRA-11]
3. Consider gVisor (runsc) for hardened isolation [REPO-INFRA-16]
4. Firecracker microVMs for managed service tier
5. Regular security scanning of sandbox images [CLEAN-INFRA-08]
**Evidence**: [REPO-INFRA-19, CLEAN-INFRA-11-14, WEB-INFRA-09-11]

### Risk 4: PII Leakage
**Description**: Presidio fails to detect all PII, allowing sensitive data to reach LLM providers.
**Likelihood**: Medium (Presidio has known false-negative patterns)
**Impact**: High (compliance violation, data breach)
**Mitigation**:
1. Fail-closed: block messages with residual PII risk above threshold [CLEAN-OSS-24]
2. Custom Presidio recognizers for domain-specific PII patterns
3. Never log original PII text [DOCS-PY-13]
4. Separate encrypted vault for PII mapping, human-only reveal [architecture spec 4.2]
5. Regular PII detection accuracy audits
**Evidence**: [REPO-PY-08, DOCS-PY-13-16, CLEAN-OSS-24]

---

## Medium-Impact Risks

### Risk 5: Async Complexity
**Description**: Full async-first architecture increases debugging difficulty and introduces subtle concurrency bugs.
**Likelihood**: Medium
**Impact**: Medium
**Mitigation**:
1. Ban synchronous blocking in async code (lint enforcement) [CLEAN-PY-19]
2. Wrap sync libraries (Presidio) with `asyncio.to_thread()` [DOCS-PY-16]
3. Use structured logging with correlation IDs [CLEAN-PY-16]
4. Comprehensive async test fixtures [CLEAN-PY-09]
**Evidence**: [CLEAN-PY-06, CLEAN-PY-19, DOCS-PY-12]

### Risk 6: Multi-Agent Coordination Overhead
**Description**: Coordinating multiple AI agents introduces communication overhead that may exceed the productivity gains.
**Likelihood**: Medium
**Impact**: Medium
**Mitigation**:
1. Start with single-agent workflows for v0.1 [REPO-OSS-49]
2. Add multi-agent only when single-agent is insufficient
3. Use explicit graph orchestration (LangGraph), not freeform agent chat [CLEAN-OSS-27]
4. Bounded iteration caps on all agent loops [DOCS-OSS-18]
**Evidence**: [REPO-OSS-49, CLEAN-OSS-27, WEB-OSS-10]

### Risk 7: Devcontainer Cold Start Latency
**Description**: Devcontainer startup (2-5 min without prebuild) is too slow for interactive use.
**Likelihood**: High
**Impact**: Medium (poor UX, not a blocker)
**Mitigation**:
1. Prebuild images in CI, push to registry [REPO-INFRA-02]
2. Warm container pools [WEB-INFRA-14]
3. Target <30s cold start, <5s warm start
**Evidence**: [REPO-INFRA-01-02, WEB-INFRA-14-15]

### Risk 8: Postgres Event Store at Scale
**Description**: Postgres may not sustain event throughput beyond ~50M events/day on a single writer.
**Likelihood**: Low (for initial scale)
**Impact**: Medium (requires architecture change at scale)
**Mitigation**:
1. Monthly partitioning from day one [CLEAN-INFRA-18]
2. Three-tier retention strategy [REPO-INFRA-06]
3. NATS JetStream as primary bus, Postgres as compliance store
4. Migration path to EventStoreDB if needed
**Evidence**: [REPO-INFRA-05-06, REPO-INFRA-17, WEB-INFRA-05]

---

## Low-Impact Risks

### Risk 9: Dependency Version Conflicts
**Description**: LangChain package split creates frequent dependency conflicts with Pydantic v1/v2.
**Likelihood**: Medium
**Impact**: Low (manageable with pinning)
**Mitigation**: Pin versions tightly, audit dependency tree, use `uv` for fast resolution.
**Evidence**: [DOCS-PY-21, DOCS-PY-31]

### Risk 10: Slack API Rate Limits
**Description**: Fan-out of agent messages could hit Slack's per-workspace rate limits.
**Likelihood**: Medium
**Impact**: Low (messages queued, not lost)
**Mitigation**: Token-bucket rate limiter with priority lanes [REPO-SLACK-10].
**Evidence**: [REPO-SLACK-10, DOCS-SLACK-10]

---

## Common Issues & Solutions

### Issue: Presidio Blocks Event Loop
**Symptom**: API latency spikes during PII analysis
**Cause**: `AnalyzerEngine.analyze()` is synchronous
**Solution**: `await asyncio.to_thread(analyzer.analyze, ...)` [DOCS-PY-16]

### Issue: LangGraph State Not Persisting
**Symptom**: Workflow state lost on restart
**Cause**: Missing `thread_id` in config or checkpointer not initialized
**Solution**: Always pass `{"configurable": {"thread_id": "..."}}` and call `checkpointer.setup()` at startup [DOCS-PY-03]

### Issue: LISTEN/NOTIFY Drops Notifications
**Symptom**: Event bridge misses events after reconnect
**Cause**: Using pooled connection (PgBouncer) for LISTEN
**Solution**: Dedicated non-pooled asyncpg connection + polling fallback [DOCS-INFRA-21]

### Issue: Sandbox Network Escape
**Symptom**: Sandbox container reaches external services
**Cause**: Missing or incomplete NetworkPolicy
**Solution**: Default-deny NetworkPolicy with explicit NATS egress only [DOCS-INFRA-09]

### Issue: Event Schema Evolution Breaks Projections
**Symptom**: Projection errors on old events
**Cause**: Missing upcaster for schema version
**Solution**: Maintain upcaster chain for all event versions [CLEAN-PY-11]

---

## Testing Considerations

### What Needs Testing
- Event store: append, read, optimistic concurrency, projection rebuild
- PII pipeline: detection accuracy, anonymization consistency, fail-closed behavior
- Sandbox: network isolation, resource limits, lifecycle cleanup
- Approval gates: button flow, timeout behavior, message updates
- Model routing: policy selection, fallback behavior, cost tracking

### Testing Strategy
- Domain tests: pure, synchronous, no I/O
- Infrastructure tests: testcontainers with real Postgres/NATS/Docker
- Integration tests: full workflow with mock Slack
- Security tests: sandbox escape attempts, PII bypass attempts
- Load tests: concurrent agent sessions, event store throughput

### Edge Cases
- Concurrent event appends to same stream (optimistic concurrency)
- Slack 3-second acknowledgment timeout under load
- Agent loop exceeding max iterations
- Sandbox timeout during active file writes
- PII detected in code comments and variable names
