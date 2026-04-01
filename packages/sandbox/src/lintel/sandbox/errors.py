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


class NoSandboxAvailableError(SandboxError):
    """Raised when no sandbox is available in the pool."""

    def __init__(self) -> None:
        super().__init__(
            "No sandbox available in pool. "
            "Pre-provision sandboxes via the API or wait for one to be released."
        )


class SandboxCapacityExceededError(SandboxError):
    """Raised when the sandbox pool has reached its maximum capacity."""

    def __init__(self, active: int, capacity: int) -> None:
        super().__init__(
            f"Sandbox capacity exceeded: {active}/{capacity} active. "
            "Wait for a sandbox to be destroyed before creating a new one."
        )
        self.active = active
        self.capacity = capacity


class ToolCallLimitExceededError(SandboxError):
    """Raised when tool call limit per step is exceeded."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"Tool call limit exceeded: max {limit} calls per step")
        self.limit = limit


class FileWriteLimitExceededError(SandboxError):
    """Raised when file write limit per session is exceeded."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"File write limit exceeded: max {limit} writes per session")
        self.limit = limit


class InsufficientStorageError(SandboxError):
    """Raised when host storage is below minimum threshold for sandbox operations."""

    def __init__(self, available_bytes: int, required_bytes: int) -> None:
        super().__init__(
            f"Insufficient storage: {available_bytes} bytes available, "
            f"minimum {required_bytes} bytes required"
        )
        self.available_bytes = available_bytes
        self.required_bytes = required_bytes
