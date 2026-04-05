"""Sandbox domain types. Immutable, no I/O dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class SandboxBackend(StrEnum):
    DOCKER = "docker"
    OPENSHELL = "openshell"


class SandboxStatus(StrEnum):
    PENDING = "pending"
    CREATING = "creating"
    RUNNING = "running"
    COLLECTING = "collecting"
    COMPLETED = "completed"
    FAILED = "failed"
    DESTROYED = "destroyed"


class SessionState(StrEnum):
    """Lifecycle state of a sandbox session."""

    RUNNING = "running"
    HIBERNATED = "hibernated"
    RESUMED = "resumed"
    TERMINATED = "terminated"


class PreviewStatus(StrEnum):
    """Status of a sandbox preview server."""

    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True)
class StorageLimits:
    """Configurable storage limits and cleanup thresholds for sandboxes.

    ``max_storage_gb`` is the hard cap passed to Docker via ``--storage-opt``.
    ``cleanup_threshold_pct`` triggers automatic workspace cleanup when usage
    exceeds this percentage of ``max_storage_gb``.
    """

    max_storage_gb: int = 4
    max_allowed_gb: int = 10
    cleanup_threshold_pct: int = 80

    def __post_init__(self) -> None:
        if self.max_storage_gb > self.max_allowed_gb:
            object.__setattr__(self, "max_storage_gb", self.max_allowed_gb)


@dataclass(frozen=True)
class StorageUsage:
    """Current storage usage of a sandbox workspace."""

    used_bytes: int
    limit_bytes: int

    @property
    def used_mb(self) -> int:
        return self.used_bytes // (1024 * 1024)

    @property
    def used_pct(self) -> float:
        if self.limit_bytes == 0:
            return 0.0
        return (self.used_bytes / self.limit_bytes) * 100.0

    @property
    def exceeds_threshold(self) -> bool:
        """True when usage >= 80% of limit (default threshold)."""
        return self.used_pct >= 80.0


@dataclass(frozen=True)
class ResourceLimits:
    """Configurable resource limits for sandbox containers."""

    max_disk_mb: int = 1024
    max_processes: int = 64
    seccomp_profile: str = "default"


@dataclass(frozen=True)
class NetworkEgressPolicy:
    """Network egress control policy for sandbox containers.

    When ``allowed_domains`` is non-empty, iptables rules restrict outbound
    traffic to resolved IPs of those domains only (plus DNS).  An empty tuple
    means *all* egress is permitted when the network is enabled.
    """

    allowed_domains: tuple[str, ...] = ()


@dataclass(frozen=True)
class NetworkEndpoint:
    """An authorized network endpoint for sandbox egress whitelisting.

    When ``port`` is ``None`` all ports are allowed for the given host.
    """

    host: str
    port: int | None = None
    protocol: str = "tcp"


@dataclass(frozen=True)
class NetworkPolicy:
    """Per-sandbox network isolation policy.

    ``allowed_endpoints`` restricts egress to specific host/port pairs.
    ``isolate`` creates a dedicated Docker network per sandbox so containers
    cannot communicate with each other via the shared bridge network.
    """

    allowed_endpoints: tuple[NetworkEndpoint, ...] = ()
    isolate: bool = True


@dataclass(frozen=True)
class ToolCallLimits:
    """Per-step limits on agent tool usage inside a sandbox session."""

    max_tool_calls_per_step: int = 50
    max_file_writes_per_session: int = 100


@dataclass(frozen=True)
class DatabaseReplica:
    """Configuration for a read-only database replica accessible from a sandbox.

    ``credential_ref`` is an opaque key that resolves to actual credentials
    at sandbox creation time (e.g. a sandbox-credentials-api credential id).
    """

    name: str
    host: str
    port: int = 5432
    database: str = "postgres"
    read_only: bool = True
    credential_ref: str = ""


@dataclass(frozen=True)
class SandboxConfig:
    """Configuration for creating a sandbox container."""

    image: str = "lintel-sandbox:latest"
    memory_limit: str = "4g"
    cpu_quota: int = 200000
    network_enabled: bool = False
    timeout_seconds: int = 3600
    environment: frozenset[tuple[str, str]] = frozenset()
    mounts: tuple[tuple[str, str, str], ...] = ()  # (source, target, type) triples
    backend: SandboxBackend = SandboxBackend.DOCKER
    resource_limits: ResourceLimits = ResourceLimits()
    network_egress: NetworkEgressPolicy = NetworkEgressPolicy()
    tool_limits: ToolCallLimits = ToolCallLimits()
    storage_limits: StorageLimits = StorageLimits()
    network_policy: NetworkPolicy | None = None
    replica_connections: tuple[DatabaseReplica, ...] = ()


@dataclass(frozen=True)
class SandboxJob:
    """A command to execute in a sandbox."""

    command: str
    workdir: str | None = None
    timeout_seconds: int = 300


@dataclass(frozen=True)
class SandboxResult:
    """Result of a sandbox command execution."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class TimeoutConfig:
    """Idle-timeout configuration for sandbox sessions.

    ``idle_timeout_seconds`` triggers auto-hibernate after inactivity.
    ``max_lifetime_seconds`` is the hard cap before forced termination.
    """

    idle_timeout_seconds: int = 1800
    max_lifetime_seconds: int = 14400


@dataclass(frozen=True)
class SessionCost:
    """Accumulated cost tracking for a sandbox session lifecycle."""

    cpu_seconds: float = 0.0
    memory_mb_seconds: float = 0.0
    storage_mb_seconds: float = 0.0

    @property
    def total_cost_units(self) -> float:
        """Weighted cost in abstract units."""
        return (
            self.cpu_seconds
            + (self.memory_mb_seconds / 1024) * 0.5
            + (self.storage_mb_seconds / 1024) * 0.1
        )


@dataclass(frozen=True)
class SessionLifecycle:
    """Tracks the full lifecycle of a sandbox session including state transitions and cost."""

    sandbox_id: str
    state: SessionState = SessionState.RUNNING
    snapshot_id: str = ""
    timeout_config: TimeoutConfig = field(default_factory=TimeoutConfig)
    cost: SessionCost = field(default_factory=SessionCost)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    hibernated_at: datetime | None = None
    resumed_at: datetime | None = None
    terminated_at: datetime | None = None


@dataclass(frozen=True)
class PreviewDetection:
    """Result of detecting a runnable app inside a sandbox."""

    detected: bool = False
    command: str = ""
    port: int = 0
    framework: str = ""


@dataclass(frozen=True)
class PreviewInfo:
    """Describes an active preview server running inside a sandbox."""

    sandbox_id: str = ""
    status: PreviewStatus = PreviewStatus.STOPPED
    preview_url: str = ""
    container_port: int = 0
    host_port: int = 0
    framework: str = ""
    started_at: datetime | None = None
