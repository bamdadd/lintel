# REQ-024: Telegram & WhatsApp Channel Adapters

**Status:** Draft
**Priority:** High
**Created:** 2026-03-09
**Related:** `ChannelAdapter` protocol (`contracts/protocols.py:136`), Slack adapter (`infrastructure/channels/slack/`), REQ-023 (Interactive Input)

---

## Problem

Lintel currently only supports Slack as a messaging channel. The agent can join Slack channels and respond in threads. But many teams communicate via **Telegram groups** or **WhatsApp groups** — especially in open-source communities, smaller teams, and regions where Slack adoption is low.

Users want to add a Lintel agent to a **Telegram group** or **WhatsApp group** the same way they add it to a Slack channel: mention it, and it kicks off a workflow in that thread.

## Goal

Implement Telegram and WhatsApp as first-class channel adapters, following the same `ChannelAdapter` protocol that Slack uses. The agent should be invocable in group conversations on all three platforms with a consistent experience.

---

## Research: OpenClaw's Channel Architecture

OpenClaw (214k+ GitHub stars) is the leading open-source multi-channel AI gateway. Key patterns we should adopt:

### Adapter Architecture
- **Normalised message envelope** — all inbound messages from any channel are translated into a unified format (sender, body, attachments, channel metadata) before reaching the agent core
- **Per-channel adapters** — each channel is a translation layer with zero business logic; adapters only convert between platform-native formats and the normalised envelope
- **Session keys** — conversations are keyed by `channelType:entityId:threadId`, enabling per-group and per-topic isolation
- **Deterministic routing** — inbound channel always replies on that same channel (no cross-channel replies)

### Trigger Modes
- **`@mention` trigger** — agent only responds when explicitly mentioned (default for groups)
- **`always` trigger** — agent responds to every message (useful for DMs or dedicated bot channels)
- **Per-group override** — users can toggle trigger mode per group via slash commands

### Lintel Already Has This Foundation
- `ChannelAdapter` protocol (`protocols.py:136`) defines `send_message`, `update_message`, `send_approval_request`
- `ThreadRef(workspace_id, channel_id, thread_ts)` is the canonical workflow identifier
- `EventTranslator` converts Slack events → `ProcessIncomingMessage` commands
- The entire domain layer is channel-agnostic — it only sees `ThreadRef` and commands

**What's missing:** `ThreadRef` field names are Slack-flavoured (`workspace_id`, `thread_ts`). The protocol methods use Slack concepts (`blocks`). We need a thin generalisation layer.

---

## Design

### 1. Generalise ThreadRef

`ThreadRef` currently uses Slack terminology. Reinterpret the fields as channel-agnostic:

| Field | Slack meaning | Telegram meaning | WhatsApp meaning |
|---|---|---|---|
| `workspace_id` | Team ID (`T11111`) | Bot token hash (identifies bot instance) | WhatsApp Business Account ID |
| `channel_id` | Channel ID (`C99999`) | Chat ID (`-1001234567890`) | Group JID (`120363...@g.us`) |
| `thread_ts` | Message timestamp | `message_thread_id` (forum topic) or message ID | Message ID for reply context |

No structural change needed — the fields are already strings. Add a `channel_type` field:

```python
@dataclass(frozen=True)
class ThreadRef:
    workspace_id: str
    channel_id: str
    thread_ts: str
    channel_type: ChannelType = ChannelType.SLACK  # NEW — backwards compatible

class ChannelType(StrEnum):
    SLACK = "slack"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
```

The `stream_id` property becomes: `thread:{channel_type}:{workspace_id}:{channel_id}:{thread_ts}`

### 2. Channel Adapter Registry

```python
class ChannelRegistry:
    """Routes outbound messages to the correct channel adapter."""

    _adapters: dict[ChannelType, ChannelAdapter]

    def adapter_for(self, thread_ref: ThreadRef) -> ChannelAdapter:
        return self._adapters[thread_ref.channel_type]

    async def send_message(self, thread_ref: ThreadRef, text: str, **kwargs) -> dict:
        adapter = self.adapter_for(thread_ref)
        return await adapter.send_message(
            channel_id=thread_ref.channel_id,
            thread_ts=thread_ref.thread_ts,
            text=text,
            **kwargs,
        )
```

All existing code that calls `channel_adapter.send_message(...)` switches to `channel_registry.send_message(thread_ref, ...)` — the registry picks the right adapter based on `thread_ref.channel_type`.

### 3. Telegram Adapter

#### 3.1 Bot Setup
- Create bot via BotFather → get token
- **Disable privacy mode** (`/setprivacy` → Disabled) so the bot receives all group messages, not just `/commands` and `@mentions`
- Alternatively, grant bot **admin status** in the group (also bypasses privacy mode)
- Store bot token as a `Credential` in Vault

#### 3.2 Message Reception

| Telegram concept | Lintel mapping |
|---|---|
| Update (webhook or long-poll) | Inbound event |
| `chat.id` | `thread_ref.channel_id` |
| `message_thread_id` (forum topics) | `thread_ref.thread_ts` |
| `@botusername` in text | Trigger detection |
| `reply_to_message` | Thread context |

```python
class TelegramEventTranslator:
    def translate(self, update: dict) -> ProcessIncomingMessage | None:
        message = update.get("message")
        if not message:
            return None

        chat_id = str(message["chat"]["id"])
        thread_id = str(message.get("message_thread_id", message["message_id"]))

        # Group trigger: only respond to @mentions or replies to bot
        if message["chat"]["type"] in ("group", "supergroup"):
            if not self._is_triggered(message):
                return None

        return ProcessIncomingMessage(
            thread_ref=ThreadRef(
                workspace_id=self._bot_id,
                channel_id=chat_id,
                thread_ts=thread_id,
                channel_type=ChannelType.TELEGRAM,
            ),
            raw_text=message.get("text", ""),
            sender_id=str(message["from"]["id"]),
            sender_name=message["from"].get("first_name", ""),
        )

    def _is_triggered(self, message: dict) -> bool:
        text = message.get("text", "")
        # @mention trigger
        if f"@{self._bot_username}" in text:
            return True
        # Reply to bot's message
        reply = message.get("reply_to_message")
        if reply and reply.get("from", {}).get("is_bot"):
            return True
        return False
```

#### 3.3 Message Sending

```python
class TelegramChannelAdapter:
    """Implements ChannelAdapter via Telegram Bot API."""

    async def send_message(self, channel_id, thread_ts, text, blocks=None):
        return await self._bot.send_message(
            chat_id=int(channel_id),
            text=text,
            message_thread_id=int(thread_ts) if thread_ts else None,
            parse_mode="Markdown",
        )

    async def send_approval_request(self, channel_id, thread_ts, gate_type, summary, callback_id):
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve:{gate_type}:{callback_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject:{gate_type}:{callback_id}"),
            ]
        ])
        return await self._bot.send_message(
            chat_id=int(channel_id),
            text=summary,
            reply_markup=keyboard,
            message_thread_id=int(thread_ts) if thread_ts else None,
        )
```

#### 3.4 Telegram-Specific Features

| Feature | Implementation |
|---|---|
| **Forum topics** | Map `message_thread_id` to `thread_ts` — each topic is a separate workflow |
| **Inline keyboards** | Approval buttons via `InlineKeyboardMarkup` (callback queries) |
| **File attachments** | `document`, `photo`, `video` in updates → download via `getFile` → attach to command |
| **Reactions** | Use `setMessageReaction` API for status indicators (⏳ processing, ✅ done) |
| **Long messages** | Telegram limit is 4096 chars — split into multiple messages or use `Telegraph` for long reports |

### 4. WhatsApp Adapter

#### 4.1 Platform Constraints (Critical)

**As of January 2026, Meta bans general-purpose AI chatbots from WhatsApp.** Only narrowly-scoped business bots are allowed (customer support, transactional notifications, etc.).

Implications for Lintel:
- WhatsApp adapter is viable for **business-specific workflows** (e.g., a team using WhatsApp for project updates, deployment notifications)
- NOT viable for open-ended AI chat in WhatsApp groups
- Groups API limits: **max 8 participants**, **1 API contact per group**
- Messages outside the 24-hour session window require **pre-approved templates**

#### 4.2 WhatsApp Business Cloud API

| WhatsApp concept | Lintel mapping |
|---|---|
| Business Account ID (WABA) | `thread_ref.workspace_id` |
| Group JID | `thread_ref.channel_id` |
| Message ID | `thread_ref.thread_ts` |
| Webhook notification | Inbound event |

```python
class WhatsAppChannelAdapter:
    """Implements ChannelAdapter via WhatsApp Business Cloud API."""

    async def send_message(self, channel_id, thread_ts, text, blocks=None):
        return await self._client.post(
            f"{self._api_url}/{self._phone_id}/messages",
            json={
                "messaging_product": "whatsapp",
                "to": channel_id,
                "type": "text",
                "text": {"body": text},
                "context": {"message_id": thread_ts} if thread_ts else None,
            },
        )

    async def send_approval_request(self, channel_id, thread_ts, gate_type, summary, callback_id):
        # WhatsApp interactive messages with buttons (max 3 buttons)
        return await self._client.post(
            f"{self._api_url}/{self._phone_id}/messages",
            json={
                "messaging_product": "whatsapp",
                "to": channel_id,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": summary},
                    "action": {
                        "buttons": [
                            {"type": "reply", "reply": {"id": f"approve:{callback_id}", "title": "Approve"}},
                            {"type": "reply", "reply": {"id": f"reject:{callback_id}", "title": "Reject"}},
                        ]
                    },
                },
            },
        )
```

#### 4.3 WhatsApp Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| 24-hour session window | Can't send after 24h without template | Use templates for async notifications |
| Max 3 interactive buttons | Approval UI is constrained | Approve/Reject fits; complex flows need fallback |
| No threading | Can't create sub-threads | Use `context.message_id` for reply chains |
| 8-person group limit | Small groups only | Position as team/project channel, not org-wide |
| General AI bot ban | Can't market as AI chatbot | Frame as "workflow automation" not "AI chat" |

### 5. Trigger Configuration

Each channel connection should have configurable trigger behaviour:

```python
@dataclass(frozen=True)
class ChannelConnection:
    """A Lintel agent connected to a specific channel/group."""
    id: str
    project_id: str
    channel_type: ChannelType
    channel_id: str                          # Group/channel ID on the platform
    channel_name: str
    trigger_mode: TriggerMode = TriggerMode.MENTION
    credential_id: str | None = None         # Vault credential for this platform

class TriggerMode(StrEnum):
    MENTION = "mention"      # Only respond to @bot mentions
    ALWAYS = "always"        # Respond to every message (DMs, dedicated channels)
    KEYWORD = "keyword"      # Respond to messages matching keywords
    SLASH = "slash"          # Only respond to /lintel commands
```

### 6. Unified Message Envelope

Following OpenClaw's pattern, normalise all inbound messages before they reach the domain:

```python
@dataclass(frozen=True)
class InboundMessage:
    """Channel-agnostic inbound message. Adapters produce these."""
    thread_ref: ThreadRef
    text: str
    sender_id: str
    sender_name: str
    attachments: list[Attachment] = field(default_factory=list)
    is_reply: bool = False
    reply_to_message_id: str | None = None
    raw_event: dict[str, Any] = field(default_factory=dict)  # Platform-native payload
```

This replaces `ProcessIncomingMessage` as the adapter output, with `ProcessIncomingMessage` becoming an internal command derived from it.

---

## Implementation Phases

### Phase 1: Generalise Channel Abstraction
- Add `ChannelType` enum and `channel_type` field to `ThreadRef`
- Create `ChannelRegistry` that routes to adapters by type
- Refactor existing Slack code to register via the registry
- Introduce `InboundMessage` envelope
- Update `stream_id` format to include channel type
- Event store migration for new stream ID format
- **Test:** Existing Slack flows work unchanged through the registry

### Phase 2: Telegram Adapter
- `infrastructure/channels/telegram/adapter.py` — `TelegramChannelAdapter`
- `infrastructure/channels/telegram/event_translator.py` — webhook/long-poll → `InboundMessage`
- `infrastructure/channels/telegram/markup.py` — inline keyboards for approvals
- Webhook endpoint: `POST /api/v1/channels/telegram/webhook`
- Settings UI: connect Telegram bot (enter token, set trigger mode)
- Forum topic support (maps to `thread_ts`)
- **Test:** Bot in a Telegram group, @mention triggers workflow, approval via inline keyboard

### Phase 3: WhatsApp Adapter
- `infrastructure/channels/whatsapp/adapter.py` — `WhatsAppChannelAdapter`
- `infrastructure/channels/whatsapp/event_translator.py` — webhook → `InboundMessage`
- Webhook verification endpoint (Meta's challenge handshake)
- Template message support for out-of-session notifications
- Settings UI: connect WhatsApp Business Account (API key, phone number ID)
- **Test:** Bot in a WhatsApp group, message triggers workflow, approval via interactive buttons

### Phase 4: Channel Management UI
- **Connections page** — list all connected channels across platforms
- **Per-channel config** — trigger mode, linked project, notification preferences
- **Channel health** — webhook status, last message received, error counts
- **Onboarding wizard** — guided setup for each platform (bot token, webhook URL, permissions)

---

## Security Considerations

- **Credential isolation:** Bot tokens and API keys stored in Vault, never exposed to agents or UI
- **Webhook verification:** Telegram (secret token header), WhatsApp (Meta signature verification), Slack (existing signing secret)
- **Rate limiting:** Per-channel rate limits to avoid platform throttling (Telegram: 30 msg/sec to groups, WhatsApp: tiered by quality rating)
- **PII handling:** Messages from all channels pass through the same PII detection pipeline (`infrastructure/pii/`)
- **Audit trail:** All inbound/outbound messages logged as events with `ThreadRef` and `channel_type`

## Open Questions

1. **Matrix/Discord:** Should we plan the abstraction for these channels too, or add them later?
2. **WhatsApp viability:** Given Meta's AI bot ban, is WhatsApp worth the investment now, or should we defer until policy clarifies?
3. **Cross-channel workflows:** Can a workflow started in Telegram send notifications to Slack? Or should we enforce single-channel per workflow?
4. **Telegram library:** Use `python-telegram-bot` (mature, async) or `aiogram` (lighter, faster)? Or raw Bot API calls?
5. **Self-hosted bridges:** Should we support Matrix bridges (mautrix-telegram, mautrix-whatsapp) as an alternative to direct API integration?
