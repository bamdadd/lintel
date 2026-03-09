# REQ-023: Claude Code Subscription in Sandbox

**Status:** Draft
**Priority:** Medium
**Created:** 2026-03-09
**Related:** REQ-020 (Generalised Workflow Stages), Agents architecture, Sandbox infrastructure

---

## Problem

Lintel currently routes all LLM calls through litellm, using API keys managed server-side. Users who have a **Claude Code subscription** (Claude Max / Team / Enterprise) cannot leverage their existing subscription for agent work. This means:

1. **Cost duplication** — users pay for a Claude subscription _and_ the project pays for API tokens.
2. **Missing Claude Code capabilities** — Claude Code's agentic loop (tool use, file editing, bash execution, MCP integration) is superior to raw API calls for coding tasks. Lintel's coder/reviewer/architect agents would benefit from delegating to Claude Code rather than reimplementing its tool loop.
3. **No interactive auth flow** — Claude Code requires a one-time interactive login (`claude login`). There is no mechanism today for a user to authenticate inside a sandbox during a workflow.

## Goal

Allow users to authenticate their Claude Code subscription once, then let Lintel's sandbox-based agents use `claude` CLI as their execution backend — replacing or augmenting the current litellm-based model calls for supported agent roles.

---

## Design

### 1. Interactive Input During Workflow (prerequisite)

The approval gate already uses LangGraph's `interrupt_before` to pause workflows and wait for user decisions. This same mechanism can be generalised to support **arbitrary user input** during a workflow stage — not just approve/reject, but text input, credential entry, and interactive terminal sessions.

#### 1.1 New Stage Type: `AWAITING_USER_INPUT`

Add to `StageStatus`:

```python
AWAITING_USER_INPUT = "awaiting_user_input"
```

This status signals the UI to render an input widget (text field, terminal emulator, or OAuth redirect) instead of a simple approve/reject button.

#### 1.2 Input Request Contract

```python
@dataclass(frozen=True)
class UserInputRequest:
    """Emitted when a workflow stage needs user interaction."""
    input_type: Literal["text", "terminal", "oauth"]
    prompt: str                    # What to show the user
    stage_id: str
    sandbox_id: str | None = None  # For terminal type — connects to sandbox TTY
    timeout_seconds: int = 300
    sensitive: bool = False        # If True, UI masks input and does not persist
```

#### 1.3 UI Components

| Input type | UI rendering | Use case |
|---|---|---|
| `text` | Single text field + submit | Simple prompts, confirmation codes |
| `terminal` | Embedded xterm.js terminal connected to sandbox PTY via WebSocket | `claude login`, interactive CLI sessions |
| `oauth` | Redirect button + callback listener | Future: GitHub App install, Jira OAuth |

The `terminal` type is the critical one for Claude Code login. It requires:
- WebSocket endpoint: `GET /api/v1/sandboxes/{sandbox_id}/terminal`
- PTY allocation in the Docker container (`docker exec -it`)
- xterm.js in the frontend with fit addon for responsive sizing

### 2. Claude Code Authentication Flow

#### 2.1 First-Time Setup

1. User navigates to **Settings → AI Providers → Claude Code**
2. Clicks "Connect Claude Code Subscription"
3. Lintel creates a persistent sandbox container with Claude Code installed
4. UI renders an embedded terminal (xterm.js) connected to the sandbox
5. User runs `claude login` in the terminal, completes OAuth in browser
6. Lintel detects successful auth (polls `claude --version` or checks `~/.claude/` config)
7. Auth credentials are encrypted and stored in the Vault (`credential_type: "claude_code"`)
8. Sandbox is snapshotted (Docker commit) as the user's Claude Code base image

#### 2.2 Credential Storage

```python
class CredentialType(StrEnum):
    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"
    CLAUDE_CODE = "claude_code"     # NEW — Claude Code session credentials
```

Stored artefacts:
- `~/.claude/` config directory (contains session tokens)
- Encrypted at rest via Vault
- Mounted read-only into agent sandboxes at runtime

### 3. Agent Execution via Claude Code

#### 3.1 Claude Code as Model Backend

New model provider in `infrastructure/models/`:

```python
class ClaudeCodeProvider:
    """Executes agent prompts via `claude` CLI in a sandbox."""

    async def invoke(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        *,
        sandbox_id: str,
        allowed_tools: list[str] | None = None,
    ) -> AgentResponse:
        # 1. Write prompt to file in sandbox
        # 2. Run: claude --print --system-prompt <file> --allowedTools <tools>
        # 3. Stream stdout back as agent response
        # 4. Parse tool calls and results from structured output
        ...
```

#### 3.2 CLI Flags

Key `claude` CLI flags for headless/sandbox use:

| Flag | Purpose |
|---|---|
| `--print` | Non-interactive, output-only mode |
| `--output-format json` | Structured output for parsing |
| `--system-prompt <file>` | Inject Lintel's agent system prompt |
| `--allowedTools` | Restrict to safe tools (e.g. `Edit`, `Read`, `Bash`) |
| `--max-turns N` | Limit agentic loop iterations |
| `--model` | Override model (use user's subscription default) |

#### 3.3 Which Agents Benefit

| Agent Role | Claude Code value | Priority |
|---|---|---|
| `coder` | High — file editing, bash, test running | P0 |
| `reviewer` | High — code reading, grep, analysis | P0 |
| `architect` | Medium — codebase exploration | P1 |
| `researcher` | Medium — web search, doc reading | P1 |
| `qa_engineer` | High — test writing and execution | P1 |
| `planner` | Low — mostly text generation | P2 |

### 4. Model Assignment Integration

REQ-021 (Per-Step Model Assignment) already supports per-stage model configuration. Extend the model selector to include Claude Code as a provider option:

```
Model selector options:
  ├── API providers (litellm): claude-sonnet-4-20250514, gpt-4o, ollama/llama3, ...
  └── Claude Code (subscription): claude-code/opus, claude-code/sonnet
```

When a stage is assigned a `claude-code/*` model, the workflow executor:
1. Creates a sandbox with the user's Claude Code credentials mounted
2. Clones the repo into the sandbox
3. Uses `ClaudeCodeProvider` instead of litellm
4. Streams output back through the existing SSE pipeline

---

## Implementation Phases

### Phase 1: Interactive Terminal in Sandbox (foundation)
- Add `AWAITING_USER_INPUT` stage status
- WebSocket terminal endpoint (`/api/v1/sandboxes/{id}/terminal`)
- xterm.js component in UI
- PTY support in `DockerSandboxManager`
- **Test:** User can open a terminal to a running sandbox from the UI

### Phase 2: Claude Code Auth Flow
- Claude Code installation in sandbox Dockerfile
- Settings page for "Connect Claude Code"
- Auth flow: terminal → `claude login` → detect success → store credentials
- `CredentialType.CLAUDE_CODE` in Vault
- **Test:** User completes login, credentials are encrypted and stored

### Phase 3: Claude Code as Agent Backend
- `ClaudeCodeProvider` in `infrastructure/models/`
- Integration with `AgentRuntime` — route to Claude Code when configured
- Structured output parsing from `claude --print --output-format json`
- Streaming support via SSE
- **Test:** Coder agent executes a task via Claude Code CLI in sandbox

### Phase 4: UI & Model Assignment
- Extend model selector to show Claude Code option (when credentials exist)
- Per-stage model assignment with `claude-code/*` prefix
- Usage tracking (token counts from Claude Code output)
- **Test:** User assigns Claude Code to a coder stage, sees output in pipeline view

---

## Security Considerations

- **Credential isolation:** Claude Code session tokens are mounted read-only; agent code cannot exfiltrate them
- **Sandbox network:** Sandboxes have restricted network access (allowlist for Anthropic API endpoints only)
- **Token scope:** Claude Code tokens inherit the user's subscription limits — no risk of runaway API costs beyond their plan
- **Audit trail:** All Claude Code invocations are logged as events with correlation IDs
- **Multi-tenant:** Each user's Claude Code credentials are isolated; no cross-user access

## Open Questions

1. **Session expiry:** How long do Claude Code session tokens last? Do we need a refresh flow?
2. **Rate limits:** Does Claude Code subscription have different rate limits than API? How do we surface throttling?
3. **Offline/local models:** Claude Code can also use local models — should we support this path for air-gapped deployments?
4. **Shared team credentials:** For Claude Team/Enterprise plans, can a single org-level credential be shared across team members?
5. **Claude Code SDK:** Anthropic may release a programmatic SDK for Claude Code (beyond CLI). Should we wait for that or build on the CLI now and migrate later?
