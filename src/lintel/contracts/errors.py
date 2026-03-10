"""Domain exceptions for sandbox operations."""


class SandboxError(Exception):
    """Base for all sandbox errors."""


class SandboxNotFoundError(SandboxError):
    """Raised when a sandbox ID does not exist."""

    def __init__(self, sandbox_id: str) -> None:
        super().__init__(f"Sandbox not found: {sandbox_id}")
        self.sandbox_id = sandbox_id


class SandboxTimeoutError(SandboxError):
    """Raised when a sandbox operation exceeds its timeout."""


class SandboxExecutionError(SandboxError):
    """Raised when command execution fails unexpectedly."""


class ClaudeCodeCredentialError(SandboxError):
    """Raised when Claude Code credentials are expired or invalid."""

    def __init__(self, status: str, user_id: str = "") -> None:
        from lintel.contracts.types import TokenStatus

        messages: dict[str, str] = {
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
        super().__init__(messages.get(status, f"Claude Code credential error: {status}"))
        self.status = status
        self.user_id = user_id
