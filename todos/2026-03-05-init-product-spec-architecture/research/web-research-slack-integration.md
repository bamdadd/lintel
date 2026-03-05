# Web Research - Slack Integration

## Current Best Practices (2024-2025) for AI Agent Slack Integration

---

## 1. Slack Bot Architecture (WEB-SLACK-01 to WEB-SLACK-06)

### WEB-SLACK-01: Production Slack Bot Patterns

Patterns from production AI-powered Slack bots:
- **Thread-per-task**: Each workflow is a Slack thread. All agent messages reply in-thread.
- **Status message pattern**: One pinned/updating message per workflow showing current state.
- **Lazy processing**: Acknowledge immediately, process asynchronously.
- **Rate-aware fan-out**: Queue outbound messages to respect Slack's rate limits.

Reference implementations: Netflix Dispatch, Kubiya, Airplane.

**Confidence**: 0.85

### WEB-SLACK-02: Socket Mode vs Events API (Production)

Production deployment recommendations:
- **Socket Mode**: Best for development and single-instance deployments. No public URL needed.
- **Events API (HTTP)**: Required for multi-instance, load-balanced production. Needs 3-second ack.
- **Hybrid**: Socket Mode for dev, Events API for production. Same handler code with different transport.

Slack's guidance: use Events API for production applications serving >1000 workspaces.

**Confidence**: 0.85

### WEB-SLACK-03: Multi-Workspace Management

Production multi-workspace patterns:
- OAuth V2 flow for workspace installation
- Store `bot_token` per `team_id` in encrypted database
- Look up token on every request
- Handle `tokens_revoked` event for cleanup
- Separate rate limit tracking per workspace

**Confidence**: 0.85

### WEB-SLACK-04: Slack Rate Limits

Key rate limits (2025):
- `chat.postMessage`: ~1 msg/sec per channel
- `chat.update`: ~50 req/min per channel
- `reactions.add`: ~50 req/min
- `files.upload`: ~20 req/min
- Web API tier limits: varies by method (Tier 1-4)

Mitigation: Token-bucket rate limiter with per-workspace, per-method tracking.

**Confidence**: 0.90

### WEB-SLACK-05: Slack App Distribution

Distribution models for Lintel:
- **Single-workspace**: Simple, custom app per org
- **Multi-workspace (distributed)**: OAuth flow, app directory listing
- **Enterprise Grid**: Organization-level deployment, org-scoped tokens

For v0.1: single-workspace. For managed service: multi-workspace with OAuth.

**Confidence**: 0.80

### WEB-SLACK-06: Slack Thread Context Limits

Thread context management:
- Slack threads can contain thousands of messages
- `conversations.replies` returns max 1000 messages per call (paginated)
- For AI context: summarize older messages, keep recent N messages full
- Thread metadata: use `metadata` field (requires `metadata.message` scope)
- Thread bookmarks: can't bookmark individual thread replies

**Confidence**: 0.85

---

## 2. AI Agent UX in Slack (WEB-SLACK-07 to WEB-SLACK-12)

### WEB-SLACK-07: Agent Message Formatting

Best practices for AI agent messages in Slack:
- Use Block Kit for structured output (not plain text)
- Consistent template: header (agent name + status), body, footer (metadata)
- Code blocks for diffs and code snippets
- Collapsible sections for verbose output (use `context` blocks)
- Progress indicators using emoji (`:white_check_mark:`, `:hourglass:`)

**Confidence**: 0.85

### WEB-SLACK-08: Approval Gate UX

Effective approval gate design:
- Summary section: what's being approved, key changes
- Metadata: author, timestamp, related PR/issue
- Action buttons: Approve (primary), Reject (danger), View Details
- Confirmation dialog for destructive actions (merge, deploy)
- Post-action: update original message with decision + approver

**Confidence**: 0.85

### WEB-SLACK-09: Progress Updates

Pattern for long-running workflows:
1. Post initial status message with workflow overview
2. `chat.update` the same message as phases complete
3. Use emoji checkmarks for completed phases
4. Final update: summary of results + links to artifacts
5. Avoid flooding thread with per-step messages

**Confidence**: 0.85

### WEB-SLACK-10: Error Communication

Error handling UX:
- Plain language error description (not stack traces)
- Suggested actions (retry, contact admin, check config)
- Correlation ID for debugging
- Link to detailed logs (if available)
- Offer retry button where appropriate

**Confidence**: 0.85

### WEB-SLACK-11: Agent Presence and Availability

Making agents feel responsive:
- Typing indicator while processing (limited to 3 seconds)
- Immediate acknowledgment message
- Status emoji on bot profile
- Home tab dashboard showing active workflows
- Reaction to received messages (`:eyes:`) for acknowledgment

**Confidence**: 0.80

### WEB-SLACK-12: Thread Summarization

For long threads:
- Summarize thread state on demand (`/lintel status`)
- Auto-summarize at phase transitions
- Pin key decisions and outcomes
- Link to external dashboard for full detail
- Keep summary under 3000 chars (Block Kit limit per section)

**Confidence**: 0.80

---

## 3. Security and Compliance (WEB-SLACK-13 to WEB-SLACK-16)

### WEB-SLACK-13: Slack Security Best Practices

- Verify all incoming requests (signing secret)
- Rotate bot tokens periodically
- Minimum required scopes
- Don't store message content beyond processing needs
- PII firewall before any LLM processing
- Audit log all Slack API calls

**Confidence**: 0.85

### WEB-SLACK-14: Enterprise Slack Compliance

Enterprise considerations:
- Slack Enterprise Grid: org-level app deployment
- eDiscovery: event store serves as compliance record
- DLP integration: PII firewall satisfies DLP requirements
- Retention policies: align event store retention with Slack workspace retention
- SOC 2: audit trail completeness via event sourcing

**Confidence**: 0.80

### WEB-SLACK-15: Token Security

Token management:
- Store tokens encrypted at rest
- Use External Secrets Operator in K8s
- Separate token per workspace (multi-workspace)
- Handle `tokens_revoked` events
- Never log tokens (structlog processors to filter)

**Confidence**: 0.85

### WEB-SLACK-16: Channel Permissions

Permission management:
- Bot must be invited to channels
- Respect channel-level permissions
- Admin can restrict which channels Lintel operates in
- Private channel access requires explicit invitation
- Direct messages: opt-in per user

**Confidence**: 0.85

---

## 4. Integration Patterns (WEB-SLACK-17 to WEB-SLACK-20)

### WEB-SLACK-17: Reference Implementations

Notable Slack + AI integrations:
- **Netflix Dispatch**: Incident management with Slack integration
- **Kubiya**: AI DevOps assistant with Slack as primary interface
- **Airplane**: Internal tool builder with Slack notifications
- **Linear**: Project management with Slack thread integration
- **PagerDuty**: On-call with Slack approval workflows

**Confidence**: 0.80

### WEB-SLACK-18: Slack + GitHub Integration

Patterns for Slack-GitHub bridging:
- Link shared events for PR preview cards
- Thread-to-PR association stored in event metadata
- PR status updates posted to originating thread
- Review requests via Slack with approve/reject buttons
- Merge gate as interactive Slack component

**Confidence**: 0.85

### WEB-SLACK-19: Webhook Reliability

Handling Slack webhook delivery:
- Slack retries 3 times with exponential backoff on failure
- Must return 200 within 3 seconds
- Idempotency: deduplicate by `event_id` from Slack
- Dead letter queue for failed processing
- Monitor webhook delivery rate in observability

**Confidence**: 0.85

### WEB-SLACK-20: Testing Slack Integrations

Testing strategies:
- **Unit**: Mock `WebClient`, test handler logic
- **Integration**: Dedicated test workspace, real Slack API
- **Contract**: Capture real Slack payloads, replay in tests
- **E2E**: Bot sends message, verify thread state
- Tools: `slack_sdk.web.async_client.AsyncWebClient` with mock

**Confidence**: 0.85
