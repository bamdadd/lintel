# Framework Documentation - Slack Integration

## Documentation Sources

Official Slack Bolt for Python, Events API, Block Kit, and interactive components documentation.

---

## 1. Slack Bolt for Python (DOCS-SLACK-01 to DOCS-SLACK-10)

### DOCS-SLACK-01: AsyncApp Setup

```python
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])

@app.event("message")
async def handle_message(event, say, client):
    thread_ts = event.get("thread_ts", event["ts"])
    await say(text="Processing...", thread_ts=thread_ts)

handler = AsyncSocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
await handler.start_async()
```

### DOCS-SLACK-02: Socket Mode vs HTTP

| Mode | Pros | Cons |
|------|------|------|
| Socket Mode | No public URL, firewall-friendly, dev-friendly | Single process, no load balancing |
| HTTP (Events API) | Load-balanceable, standard infra | Requires public URL, 3s ack timeout |

For v0.1: Socket Mode for simplicity. For production scale: HTTP with immediate `ack()`.

### DOCS-SLACK-03: Event Listeners with Middleware

```python
from slack_bolt.async_app import AsyncApp

@app.middleware
async def correlation_middleware(body, next, logger):
    correlation_id = str(uuid4())
    body["correlation_id"] = correlation_id
    logger.info("request", correlation_id=correlation_id)
    await next()

@app.event("message")
async def handle_message(event, say, body):
    correlation_id = body.get("correlation_id")
    # ... process with correlation context
```

### DOCS-SLACK-04: 3-Second Acknowledgment Rule

For HTTP mode, Slack requires acknowledgment within 3 seconds:

```python
@app.event("message")
async def handle_message(event, say, ack):
    await ack()  # Acknowledge immediately
    # Process asynchronously after ack
    await process_message_async(event)
```

For Socket Mode, ack is handled automatically but processing should still be fast.

### DOCS-SLACK-05: Interactive Components (Buttons)

```python
@app.action("approve_spec")
async def handle_approval(ack, body, client):
    await ack()
    user_id = body["user"]["id"]
    action_value = body["actions"][0]["value"]

    # Update the original message
    await client.chat_update(
        channel=body["channel"]["id"],
        ts=body["message"]["ts"],
        blocks=updated_blocks_with_status(user_id),
    )
```

### DOCS-SLACK-06: Slash Commands

```python
@app.command("/lintel")
async def handle_lintel_command(ack, body, respond):
    await ack()
    subcommand = body["text"].split()[0] if body["text"] else "help"
    if subcommand == "status":
        await respond(text=get_thread_status(body["channel_id"]))
```

### DOCS-SLACK-07: Message Threading

```python
# Always reply in thread
await client.chat_postMessage(
    channel=channel_id,
    thread_ts=thread_ts,  # Reply in thread
    text="Agent update: planning complete",
    blocks=format_status_blocks(status),
)
```

Key: `thread_ts` is the canonical identifier. First message `ts` becomes the `thread_ts` for all replies.

### DOCS-SLACK-08: File Upload

```python
result = await client.files_upload_v2(
    channel=channel_id,
    thread_ts=thread_ts,
    file=diff_content.encode(),
    filename="changes.diff",
    title="Proposed Changes",
)
```

### DOCS-SLACK-09: Conversations API

```python
# Get thread messages
result = await client.conversations_replies(
    channel=channel_id,
    ts=thread_ts,
    limit=100,
)
messages = result["messages"]
```

### DOCS-SLACK-10: Multi-Workspace (OAuth V2)

```python
from slack_bolt.oauth.async_oauth_settings import AsyncOAuthSettings

app = AsyncApp(
    oauth_settings=AsyncOAuthSettings(
        client_id=os.environ["SLACK_CLIENT_ID"],
        client_secret=os.environ["SLACK_CLIENT_SECRET"],
        scopes=["channels:history", "chat:write", "commands"],
        installation_store=PostgresInstallationStore(),
    )
)
```

Store installations per workspace. Look up bot token by `team_id` on each request.

---

## 2. Block Kit (DOCS-SLACK-11 to DOCS-SLACK-18)

### DOCS-SLACK-11: Block Kit Composition

```python
blocks = [
    {
        "type": "header",
        "text": {"type": "plain_text", "text": "Feature Specification Ready"}
    },
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*Summary*\n" + spec_summary},
    },
    {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Approve"},
                "style": "primary",
                "action_id": "approve_spec",
                "value": json.dumps({"thread_ref": thread_ref}),
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Reject"},
                "style": "danger",
                "action_id": "reject_spec",
                "value": json.dumps({"thread_ref": thread_ref}),
            },
        ],
    },
]
```

### DOCS-SLACK-12: Block Kit Builder

Use Slack's Block Kit Builder (https://app.slack.com/block-kit-builder) for visual design.

Constraints:
- Max 50 blocks per message
- Max 3000 chars per text block
- Max 5 elements per actions block
- Max 10 options per overflow menu

### DOCS-SLACK-13: Message Updates (Progress Pattern)

```python
# Post initial status
result = await client.chat_postMessage(
    channel=channel_id,
    thread_ts=thread_ts,
    blocks=build_progress_blocks(phase="planning", progress=0),
)
status_ts = result["ts"]

# Update as work progresses
await client.chat_update(
    channel=channel_id,
    ts=status_ts,
    blocks=build_progress_blocks(phase="coding", progress=60),
)
```

### DOCS-SLACK-14: Rich Text Formatting

```python
# Markdown in mrkdwn text objects
text = (
    "*Agent: CodeWriter*\n"
    "Status: :white_check_mark: Complete\n"
    "Files changed: `src/api/routes.py`, `src/domain/thread.py`\n"
    "```diff\n+ def new_function():\n+     pass\n```"
)
```

### DOCS-SLACK-15: Confirmation Dialogs

```python
{
    "type": "button",
    "text": {"type": "plain_text", "text": "Merge PR"},
    "style": "danger",
    "action_id": "merge_pr",
    "confirm": {
        "title": {"type": "plain_text", "text": "Confirm Merge"},
        "text": {"type": "mrkdwn", "text": "Merge PR #42 into main?"},
        "confirm": {"type": "plain_text", "text": "Merge"},
        "deny": {"type": "plain_text", "text": "Cancel"},
    },
}
```

### DOCS-SLACK-16: Modal Views

```python
@app.shortcut("lintel_config")
async def handle_shortcut(ack, body, client):
    await ack()
    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": "Lintel Settings"},
            "blocks": config_blocks,
            "submit": {"type": "plain_text", "text": "Save"},
        },
    )
```

### DOCS-SLACK-17: Home Tab

```python
@app.event("app_home_opened")
async def update_home_tab(client, event):
    await client.views_publish(
        user_id=event["user"],
        view={
            "type": "home",
            "blocks": build_dashboard_blocks(event["user"]),
        },
    )
```

### DOCS-SLACK-18: Unfurl Links

```python
@app.event("link_shared")
async def handle_link_shared(event, client):
    unfurls = {}
    for link in event["links"]:
        if "github.com" in link["url"]:
            unfurls[link["url"]] = build_pr_preview_blocks(link["url"])
    await client.chat_unfurl(
        channel=event["channel"],
        ts=event["message_ts"],
        unfurls=unfurls,
    )
```

---

## 3. Slack SDK Utilities (DOCS-SLACK-19 to DOCS-SLACK-24)

### DOCS-SLACK-19: Rate Limiting

Slack SDK handles rate limiting automatically with `AsyncWebClient`. It retries on 429 responses with the `Retry-After` header.

For additional control:
```python
from slack_sdk.web.async_client import AsyncWebClient

client = AsyncWebClient(
    token=bot_token,
    retry_handlers=[RateLimitErrorRetryHandler(max_retry_count=3)],
)
```

### DOCS-SLACK-20: Token Types

| Token | Prefix | Use |
|-------|--------|-----|
| Bot token | `xoxb-` | API calls on behalf of app |
| User token | `xoxp-` | API calls on behalf of user |
| App-level token | `xapp-` | Socket Mode connections |

Lintel uses bot tokens (stored per workspace) and one app-level token for Socket Mode.

### DOCS-SLACK-21: Scopes Required

Minimum scopes for Lintel:
- `channels:history` - Read channel messages
- `channels:read` - List channels
- `chat:write` - Send messages
- `commands` - Slash commands
- `files:write` - Upload files
- `reactions:read` - Read reactions (for approval)
- `users:read` - User info

### DOCS-SLACK-22: Event Subscriptions

Events to subscribe to:
- `message.channels` - Public channel messages
- `message.groups` - Private channel messages
- `message.im` - Direct messages
- `app_mention` - @mentions
- `reaction_added` - Emoji reactions (for approvals)
- `link_shared` - URL previews

### DOCS-SLACK-23: Error Handling

```python
from slack_sdk.errors import SlackApiError

try:
    result = await client.chat_postMessage(channel=cid, text=text)
except SlackApiError as e:
    if e.response["error"] == "channel_not_found":
        # Handle gracefully
        pass
    elif e.response["error"] == "not_in_channel":
        # Bot needs to be invited
        pass
    else:
        raise
```

### DOCS-SLACK-24: Testing with Mock Server

```python
from slack_sdk.web.async_client import AsyncWebClient
from unittest.mock import AsyncMock

mock_client = AsyncMock(spec=AsyncWebClient)
mock_client.chat_postMessage.return_value = {"ok": True, "ts": "123.456"}

# Inject mock into handler
adapter = SlackChannelAdapter(client=mock_client)
await adapter.send_message(thread_ref, "Hello")

mock_client.chat_postMessage.assert_called_once_with(
    channel="C123", thread_ts="123.456", text="Hello", blocks=ANY,
)
```

---

## 4. Webhook Verification (DOCS-SLACK-25 to DOCS-SLACK-29)

### DOCS-SLACK-25: Request Verification

```python
from slack_sdk.signature import SignatureVerifier

verifier = SignatureVerifier(signing_secret=os.environ["SLACK_SIGNING_SECRET"])

@app.post("/slack/events")
async def slack_events(request: Request):
    body = await request.body()
    if not verifier.is_valid(
        body=body.decode(),
        timestamp=request.headers.get("X-Slack-Request-Timestamp"),
        signature=request.headers.get("X-Slack-Signature"),
    ):
        raise HTTPException(status_code=401)
    ...
```

### DOCS-SLACK-26: URL Verification Challenge

```python
@app.post("/slack/events")
async def slack_events(request: Request):
    data = await request.json()
    if data.get("type") == "url_verification":
        return {"challenge": data["challenge"]}
    ...
```

### DOCS-SLACK-27: Bolt Lazy Listeners

```python
@app.event("message", lazy=[process_in_background])
async def acknowledge_only(ack):
    await ack()

async def process_in_background(event, client):
    # Heavy processing happens here, after ack
    await run_pipeline(event)
```

Lazy listeners separate acknowledgment from processing. Critical for HTTP mode's 3-second rule.

### DOCS-SLACK-28: App Manifest

```yaml
display_information:
  name: Lintel
  description: AI Collaboration Infrastructure
  background_color: "#2c3e50"
features:
  bot_user:
    display_name: Lintel
    always_online: true
  slash_commands:
    - command: /lintel
      description: Lintel commands
oauth_config:
  scopes:
    bot:
      - channels:history
      - chat:write
      - commands
settings:
  event_subscriptions:
    bot_events:
      - message.channels
      - app_mention
  interactivity:
    is_enabled: true
  socket_mode_enabled: true
```

### DOCS-SLACK-29: Bolt Middleware Chain

Execution order:
1. Global middleware (auth, logging, correlation)
2. Listener middleware (permission checks)
3. Listener function (business logic)

```python
async def auth_middleware(body, next, logger):
    # Check workspace is registered
    team_id = body.get("team_id") or body.get("team", {}).get("id")
    if not await is_workspace_registered(team_id):
        logger.warning("unregistered_workspace", team_id=team_id)
        return
    await next()

app.use(auth_middleware)
```
