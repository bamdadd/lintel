"""Model-related domain exceptions."""


class ClaudeCodeCredentialError(Exception):
    """Raised when Claude Code credentials are expired or invalid."""

    def __init__(self, status: str, user_id: str = "") -> None:
        from lintel.models.types import TokenStatus

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
