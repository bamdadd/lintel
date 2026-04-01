"""Sandbox domain types. Immutable, no I/O dependencies."""

from __future__ import annotations

from dataclasses import dataclass
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
class ToolCallLimits:
    """Per-step limits on agent tool usage inside a sandbox session."""

    max_tool_calls_per_step: int = 50
    max_file_writes_per_session: int = 100


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
