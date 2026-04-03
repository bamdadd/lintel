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


class StorageLimitExceededError(SandboxError):
    """Raised when sandbox storage exceeds the configured limit."""

    def __init__(self, used_mb: int, limit_mb: int) -> None:
        super().__init__(
            f"Storage limit exceeded: {used_mb}MB used of {limit_mb}MB limit. "
            "Run cleanup or increase storage_limits.max_storage_gb."
        )
        self.used_mb = used_mb
        self.limit_mb = limit_mb


class SandboxHibernatedError(SandboxError):
    """Raised when an operation is attempted on a hibernated sandbox."""

    def __init__(self, sandbox_id: str) -> None:
        super().__init__(
            f"Sandbox {sandbox_id} is hibernated. Resume it before performing operations."
        )
        self.sandbox_id = sandbox_id


class SessionAlreadyInStateError(SandboxError):
    """Raised when a session transition is invalid."""

    def __init__(self, sandbox_id: str, current_state: str, requested_state: str) -> None:
        super().__init__(
            f"Sandbox {sandbox_id} is already {current_state}, "
            f"cannot transition to {requested_state}."
        )
        self.sandbox_id = sandbox_id
        self.current_state = current_state
        self.requested_state = requested_state
