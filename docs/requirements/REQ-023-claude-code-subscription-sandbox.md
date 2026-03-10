# REQ-023: Claude Code Subscription in Sandbox

**Status:** Draft
**Priority:** High
**Created:** 2026-03-09
**Updated:** 2026-03-10
**Related:** REQ-020 (Generalised Workflow Stages), REQ-025 (AI Firewall), Agents architecture, Sandbox infrastructure

---

## Problem

Lintel currently routes all LLM calls through litellm, using API keys managed server-side. Users who have a **Claude Code subscription** (Claude Max / Team / Enterprise) cannot leverage their existing subscription for agent work. This means:

1. **Cost duplication** — users pay for a Claude subscription _and_ the project pays for API tokens.
2. **Missing Claude Code capabilities** — Claude Code's agentic loop (tool use, file editing, bash execution, MCP integration) is superior to raw API calls for coding tasks. Lintel's coder/reviewer/architect agents would benefit from delegating to Claude Code rather than reimplementing its tool loop.
3. **No auth flow** — Claude Code requires a one-time interactive login (`claude login`). There is no mechanism today for a user to authenticate and have credentials stored for sandbox use.

## Goal

Allow users to authenticate their Claude Code subscription once (via pre-authenticated session mount), then let Lintel's sandbox-based agents use `claude` CLI as their execution backend. **Workflows must fail fast with a clear error if credentials are expired or invalid** — no silent fallback, no retries.

### Decision Record

| Decision | Choice | Rationale |
|---|---|---|
| Auth method (now) | **Option 2: Pre-authenticated session mount** | User runs `claude login` locally, copies credentials to Lintel |
| Auth method (future) | **Option 3: Lintel-hosted OAuth flow** | Lintel acts as OAuth intermediary — user clicks "Connect", redirected to Anthropic, token returned to Lintel |
| API key approach | **Rejected** | User preference — subscription-based auth preferred over API billing |
| Expired token behavior | **Hard fail** | Workflow stage fails immediately with `CREDENTIAL_EXPIRED` error; no fallback to litellm, no silent retry |

---

## Design

### 1. Authentication: Pre-Authenticated Session Mount (Phase 1)

#### 1.1 How Claude Code Stores Credentials

Research findings (as of 2026-03):

| Item | Detail |
|---|---|
| Config location | `~/.config/claude-code/auth.json` (Linux), macOS Keychain |
| Token format | `sk-ant-oat01-xxxxx...xxxxx` (OAuth bearer token) |
| Token lifetime | ~1 year from generation |
| Headless env var | `CLAUDE_CODE_OAUTH_TOKEN` — accepts the token directly |
| Expiry detection | HTTP 401 with `{"type": "authentication_error"}` — no pre-check command |
| Auto-refresh | **Not implemented** in headless mode (open issues: #12447, #21765, #28827) |

#### 1.2 Credential Capture Flow

1. User navigates to **Settings → AI Providers → Claude Code**
2. Clicks "Connect Claude Code Subscription"
3. **Two options presented:**
   - **Paste token:** User runs `claude setup-token` locally, copies the `sk-ant-oat01-...` token, pastes into Lintel settings (simplest)
   - **Upload config:** User uploads `~/.config/claude-code/auth.json` file (for users who prefer file-based)
4. Lintel encrypts and stores in Vault with `credential_type: "claude_code"`
5. Health check: Lintel immediately validates the token (see §1.4)

#### 1.3 Credential Injection into Sandbox

Credentials are injected via the `CLAUDE_CODE_OAUTH_TOKEN` environment variable:

```python
# In setup_workspace.py or sandbox creation
env_vars = {}
claude_cred = await vault.get_credential(user_id, CredentialType.CLAUDE_CODE)
if claude_cred:
    env_vars["CLAUDE_CODE_OAUTH_TOKEN"] = claude_cred.token
```

**Security:** The env var is set at container creation, not written to filesystem. When AI Firewall (REQ-025) is implemented, this moves to proxy-layer header injection.

#### 1.4 Token Validation & Expiry Detection

Since there is no `claude auth status` command, validation uses a lightweight CLI probe:

```python
async def validate_claude_token(sandbox_id: str) -> TokenStatus:
    """Validate Claude Code credentials before workflow execution."""
    result = await sandbox.execute(
        sandbox_id,
        SandboxJob(command="claude --print --output-format json 'respond with ok'", timeout=15)
    )
    if result.exit_code == 0:
        return TokenStatus.VALID

    if "authentication_error" in result.stderr:
        return TokenStatus.EXPIRED

    return TokenStatus.INVALID
```

```python
class TokenStatus(StrEnum):
    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"
    NOT_CONFIGURED = "not_configured"
```

#### 1.5 Hard Fail on Expired Tokens

**Principle:** Workflows must never silently degrade. If Claude Code is configured for a stage and the token is expired, the stage fails with a clear, actionable error.

```python
class ClaudeCodeCredentialError(LintelError):
    """Raised when Claude Code credentials are expired or invalid."""

    def __init__(self, status: TokenStatus, user_id: str) -> None:
        messages = {
            TokenStatus.EXPIRED: (
                "Claude Code session token has expired. "
                "Please re-authenticate in Settings → AI Providers → Claude Code."
            ),
            TokenStatus.INVALID: (
                "Claude Code credentials are invalid. "
                "Please reconnect in Settings → AI Providers → Claude Code."
            ),
            TokenStatus.NOT_CONFIGURED: (
                "Claude Code is assigned to this stage but no credentials are configured. "
                "Please connect your subscription in Settings → AI Providers → Claude Code."
            ),
        }
        super().__init__(messages[status])
        self.status = status
        self.user_id = user_id
```

**Validation points:**
1. **Pre-flight check** — Before workflow starts, validate all stages that require Claude Code. Fail the entire pipeline before any work begins.
2. **Per-invocation check** — If a token expires mid-workflow (unlikely given 1-year lifetime, but possible), the `ClaudeCodeProvider` catches the 401 and raises `ClaudeCodeCredentialError`.
3. **Settings page health** — Show token status badge (green/red) on the Claude Code settings card. Poll on page load.

#### 1.6 Credential Storage

```python
class CredentialType(StrEnum):
    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"
    CLAUDE_CODE = "claude_code"     # Claude Code session token
```

Stored fields:
- `token` — The `sk-ant-oat01-...` OAuth token (encrypted at rest)
- `captured_at` — Timestamp when credential was stored
- `last_validated_at` — Timestamp of last successful validation
- `status` — Current `TokenStatus`

### 2. Future: Lintel-Hosted OAuth Flow (Phase 2+)

When Anthropic provides OAuth client registration (or if we reverse-engineer the existing flow):

1. User clicks "Connect Claude Code" in Settings
2. Lintel redirects to Anthropic's OAuth authorization endpoint
3. User approves access in browser
4. Callback returns to Lintel with authorization code
5. Lintel exchanges code for access token + refresh token
6. Both stored in Vault; refresh token used to auto-renew before expiry

**Migration path:** The `ClaudeCodeProvider` and `ClaudeCodeCredentialError` remain identical — only the credential capture mechanism changes. The `CLAUDE_CODE_OAUTH_TOKEN` injection is the same regardless of how the token was obtained.

### 3. Sandbox Dockerfile Update

Bake Claude Code CLI into the sandbox image (eliminate runtime `npm install`):

```dockerfile
FROM mcr.microsoft.com/devcontainers/base:ubuntu

# ... existing Python, Node, Go, Rust, Bun installs ...

# Install Claude Code CLI (baked in, not postCreateCommand)
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /workspace
```

This saves ~30s per sandbox start vs the current `postCreateCommand` approach.

### 4. Agent Execution via Claude Code

#### 4.1 Claude Code as Model Backend

New model provider in `infrastructure/models/`:

```python
class ClaudeCodeProvider:
    """Executes agent prompts via `claude` CLI in a sandbox."""

    def __init__(self, sandbox_manager: SandboxManager, vault: VaultService) -> None:
        self._sandbox = sandbox_manager
        self._vault = vault

    async def invoke(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        *,
        sandbox_id: str,
        user_id: str,
        allowed_tools: list[str] | None = None,
        max_turns: int = 20,
    ) -> AgentResponse:
        # 1. Validate token (fail fast)
        status = await validate_claude_token(sandbox_id)
        if status != TokenStatus.VALID:
            raise ClaudeCodeCredentialError(status, user_id)

        # 2. Write system prompt to file in sandbox
        await self._sandbox.write_file(sandbox_id, "/tmp/system-prompt.md", system_prompt)

        # 3. Build command
        cmd = [
            "claude", "--print",
            "--output-format", "json",
            "--system-prompt", "/tmp/system-prompt.md",
            "--max-turns", str(max_turns),
        ]
        if allowed_tools:
            cmd.extend(["--allowedTools", ",".join(allowed_tools)])

        # 4. Append user message
        user_msg = messages[-1]["content"] if messages else ""
        cmd.append(shlex.quote(user_msg))

        # 5. Execute and parse response
        result = await self._sandbox.execute(sandbox_id, SandboxJob(
            command=" ".join(cmd),
            timeout=600,
        ))

        if result.exit_code != 0:
            if "authentication_error" in result.stderr:
                raise ClaudeCodeCredentialError(TokenStatus.EXPIRED, user_id)
            raise SandboxExecutionError(f"Claude Code failed: {result.stderr}")

        return self._parse_response(result.stdout)
```

#### 4.2 CLI Flags

| Flag | Purpose |
|---|---|
| `--print` | Non-interactive, output-only mode |
| `--output-format json` | Structured output for parsing |
| `--system-prompt <file>` | Inject Lintel's agent system prompt |
| `--allowedTools` | Restrict to safe tools (e.g. `Edit`, `Read`, `Bash`) |
| `--max-turns N` | Limit agentic loop iterations |
| `--model` | Override model (use user's subscription default) |

#### 4.3 Which Agents Benefit

| Agent Role | Claude Code value | Priority |
|---|---|---|
| `coder` | High — file editing, bash, test running | P0 |
| `reviewer` | High — code reading, grep, analysis | P0 |
| `architect` | Medium — codebase exploration | P1 |
| `researcher` | Medium — web search, doc reading | P1 |
| `qa_engineer` | High — test writing and execution | P1 |
| `planner` | Low — mostly text generation | P2 |

### 5. Model Assignment Integration

REQ-021 (Per-Step Model Assignment) supports per-stage model configuration. Extend the model selector to include Claude Code as a provider option:

```
Model selector options:
  ├── API providers (litellm): claude-sonnet-4-20250514, gpt-4o, ollama/llama3, ...
  └── Claude Code (subscription): claude-code/opus, claude-code/sonnet
```

When a stage is assigned a `claude-code/*` model, the workflow executor:
1. **Pre-flight validates** Claude Code credentials for the user
2. Creates a sandbox with `CLAUDE_CODE_OAUTH_TOKEN` injected
3. Clones the repo into the sandbox
4. Uses `ClaudeCodeProvider` instead of litellm
5. Streams output back through the existing SSE pipeline

---

## Implementation Phases

### Phase 1: Dockerfile + Credential Storage (foundation)
- Bake `@anthropic-ai/claude-code` into sandbox Dockerfile
- Add `CredentialType.CLAUDE_CODE` to Vault
- Settings UI: "Connect Claude Code" with paste-token flow
- Token validation endpoint: `POST /api/v1/settings/claude-code/validate`
- `TokenStatus` type and `ClaudeCodeCredentialError`
- **Test:** User pastes token, it's encrypted in Vault, validation returns status

### Phase 2: Claude Code as Agent Backend
- `ClaudeCodeProvider` in `infrastructure/models/`
- Pre-flight token validation in workflow executor
- Hard fail with `ClaudeCodeCredentialError` on expired/invalid/missing tokens
- Structured output parsing from `claude --print --output-format json`
- Streaming support via SSE
- **Test:** Coder agent executes via Claude Code CLI; expired token test confirms hard fail

### Phase 3: UI & Model Assignment
- Extend model selector to show Claude Code option (when credentials exist)
- Per-stage model assignment with `claude-code/*` prefix
- Token status badge on settings page (green valid / red expired)
- Usage tracking (token counts from Claude Code output)
- **Test:** User assigns Claude Code to coder stage, sees output in pipeline view

### Phase 4: Lintel-Hosted OAuth Flow (future)
- Implement OAuth client flow when Anthropic supports it
- Auto-refresh via refresh tokens
- Migrate credential capture from paste-token to browser-based OAuth
- Remove manual token management from settings UI
- **Test:** Full OAuth round-trip; auto-refresh before expiry

---

## Security Considerations

- **Credential isolation:** `CLAUDE_CODE_OAUTH_TOKEN` is set as container env var, not written to filesystem; agent code cannot easily exfiltrate it
- **Sandbox network:** Sandboxes have restricted network access (allowlist for Anthropic API endpoints only)
- **Token scope:** Claude Code tokens inherit the user's subscription limits — no risk of runaway API costs beyond their plan
- **Audit trail:** All Claude Code invocations are logged as events with correlation IDs
- **Multi-tenant:** Each user's Claude Code credentials are isolated; no cross-user access
- **No fallback:** Expired tokens cause hard failure — prevents accidental use of wrong billing path

## Resolved Questions

| Question | Answer |
|---|---|
| Session expiry | ~1 year. No auto-refresh in headless mode. Hard fail on expiry. |
| Auth approach | Pre-authenticated session mount (Option 2) now; Lintel OAuth (Option 3) future |
| API key approach | Rejected — subscription-based auth preferred |
| Expired token behavior | Hard fail with `ClaudeCodeCredentialError`, no fallback |

## Open Questions

1. **Rate limits:** Does Claude Code subscription have different rate limits than API? How do we surface throttling?
2. **Offline/local models:** Claude Code can also use local models — should we support this path for air-gapped deployments?
3. **Shared team credentials:** For Claude Team/Enterprise plans, can a single org-level credential be shared across team members?
4. **Claude Code SDK:** Anthropic may release a programmatic SDK for Claude Code (beyond CLI). Should we wait for that or build on the CLI now and migrate later?
5. **Anthropic OAuth client registration:** When does Anthropic plan to support third-party OAuth clients for Claude Code?
