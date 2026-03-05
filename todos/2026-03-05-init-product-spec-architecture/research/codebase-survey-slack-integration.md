# Codebase Survey - Slack Integration

## Survey Context

Lintel is a greenfield project. This survey documents reference patterns for the Slack integration / channel gateway.

---

## 1. Reference Architecture Patterns

### REPO-SLACK-01: Channel Adapter / Gateway Pattern

Ports-and-adapters architecture where Slack is one adapter behind a `ChannelPort` interface:

```python
class ChannelPort(Protocol):
    async def send_message(channel_id, thread_id, content) -> MessageResult
    async def send_interactive(channel_id, thread_id, blocks, callbacks) -> MessageResult
    async def update_message(channel_id, message_ts, content) -> MessageResult
    async def add_reaction(channel_id, message_ts, emoji) -> Result
    async def open_modal(trigger_id, view) -> Result
```

### REPO-SLACK-02: Thread-Based Workflow Management
Each workflow is bound to a single Slack thread. `thread_ts` becomes the `workflow_instance_id`. `ThreadContext` tracks state and is persisted for restart recovery.

### REPO-SLACK-03: Interactive Approval Gates
Button-based (recommended) with `action_id` encoding workflow step ID. On click, ack immediately, update message with outcome, resume workflow. Timeout with reminders.

### REPO-SLACK-04: Rich Message Formatting with Block Kit
Layered composition: header (agent name), section blocks (results), context (metadata), divider, actions (next steps), overflow (secondary actions). Domain `RichContent` model maps to Block Kit JSON.

### REPO-SLACK-05: Multi-Workspace Support
OAuth V2 flow with per-workspace token storage. Route by `team_id` from event envelope.

---

## 2. Recommended Module Structure

### REPO-SLACK-06: Module Layout

```
src/lintel/channels/
├── port.py                    # ChannelPort abstract interface
├── models.py                  # RichContent, ActionButton, MessageResult
└── slack/
    ├── adapter.py             # SlackChannelAdapter
    ├── block_kit.py           # RichContent -> Block Kit JSON
    ├── event_translator.py    # Slack events -> domain events
    ├── interaction_handler.py # Button clicks -> domain commands
    ├── socket_mode.py         # Connection manager
    └── rate_limiter.py        # Token-bucket rate limiter
```

### REPO-SLACK-07: Event Translation Layer

| Slack Event | Domain Event |
|---|---|
| `message` | `UserMessageReceived` |
| `app_mention` | `AgentInvoked` |
| `reaction_added` | `ReactionSignal` |
| `block_actions` | `ApprovalResponse` |
| `view_submission` | `ModalSubmitted` |

### REPO-SLACK-08: Outbound Message Formatting
Auto-split long output (50 block limit, 3000 char per section). Mrkdwn conversion. Text fallback for accessibility.

---

## 3. Key Design Decisions

### REPO-SLACK-09: Socket Mode vs HTTP Mode
Start with Socket Mode for dev/single-deployment. Abstract connection layer for HTTP swap.

### REPO-SLACK-10: Rate Limiting
Token-bucket per `(team_id, method)`. Respect `Retry-After`. Priority lanes for approval gates.

### REPO-SLACK-11: Thread Context Management
Create on workflow start, append per step, pass `thread_ts` as correlation ID, rehydrate on restart, timeout stale threads.

### REPO-SLACK-12: Approval Gate UX
Post summary + buttons -> ack immediately -> update message on decision -> resume/abort workflow -> timeout reminder.

### REPO-SLACK-13: Error Handling
Transient: retry with backoff. Rate limit: retry after header. Auth: don't retry, alert. Invalid payload: don't retry, log.

---

## 4. Reference Projects

### REPO-SLACK-14: Reference Implementations
- **slack-bolt-python**: Official SDK, supports both modes
- **Netflix/dispatch**: Excellent Slack-as-workflow-UI reference
- **Kubiya**: Approval gates via buttons, rich Block Kit
- **Linen.dev**: Thread context management patterns

### REPO-SLACK-15: Recommended Library Stack
- `slack-bolt>=1.18`
- `slack-sdk>=3.27`
- `httpx` for async API calls
- `slack_sdk.models.blocks` for typed Block Kit construction
