# Clean Code Analysis - Slack Integration

## Standards for Lintel's Channel Gateway

---

## 1. Adapter Pattern (CLEAN-SLACK-01 to 04)
- Abstract `ChannelAdapter` protocol; Slack implements it
- Clean separation: Slack types never leak into domain
- Event translation: Slack events -> domain events (and back)
- True replaceability via DI; domain never imports `slack_sdk`

## 2. Slack-Specific Clean Code (CLEAN-SLACK-05 to 09)
- Bolt middleware for cross-cutting concerns (auth, correlation ID, PII firewall)
- Error handling: retry with backoff, emit `ChannelDeliveryFailed` events
- Token-bucket rate limiter per workspace per API method
- `ThreadRef` as canonical identifier; always reply in-thread
- Organize handlers by domain concern (approval, status, skill), not Slack component type

## 3. Message Formatting (CLEAN-SLACK-10 to 14)
- `SlackBlockBuilder` composes from domain content types
- Consistent agent output template: header, body, footer, actions
- Error messages: plain language + correlation_id + suggested action
- Approval gates: summary + metadata + buttons + mutable status line
- Progress: `chat.update` a pinned status message, not new messages

## 4. Testing (CLEAN-SLACK-15 to 18)
- `FakeSlackClient` for unit tests (no HTTP mocking)
- Integration tests with dedicated test workspace
- Full-cycle interactive component tests
- Contract test fixtures: raw payload -> expected domain event

## 5. Anti-Patterns (CLEAN-SLACK-19 to 23)
- No business logic in Slack event handlers
- No direct Slack API calls from domain layer
- No missing error handling for Slack API failures
- No unstructured message formatting (always use `SlackBlockBuilder`)
- No Slack-specific fields in domain events
