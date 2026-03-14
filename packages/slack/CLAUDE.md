# lintel-slack

Slack integration — channel adapter, Block Kit builder, and event-to-command translation.

## Key exports

- `SlackChannelAdapter` — implements `ChannelAdapter` protocol; wraps `AsyncWebClient` to send/update/delete messages and upload files
- `translate_message_event` (in `event_translator.py`) — translates raw Slack event dicts to `ProcessIncomingMessage`, `GrantApproval`, or `RejectApproval` commands
- `build_stage_blocks` / `build_approval_blocks` (in `block_kit.py`) — constructs Slack Block Kit payloads for pipeline stages and approval prompts

## Dependencies

- `lintel-contracts` — `ThreadRef`, `ProcessIncomingMessage`, `GrantApproval`, `RejectApproval`
- `slack-bolt>=1.21`, `slack-sdk>=3.33`, `structlog>=24.4`

## Tests

```bash
make test-slack
# or: uv run pytest packages/slack/tests/ -v
```

## Usage

```python
from lintel.slack.adapter import SlackChannelAdapter
from lintel.slack.event_translator import translate_message_event

adapter = SlackChannelAdapter(client=async_web_client)
await adapter.send_message(channel_id, thread_ts, "Hello!", blocks=None)

command = translate_message_event(slack_event_dict)  # returns None if bot/subtype
```
