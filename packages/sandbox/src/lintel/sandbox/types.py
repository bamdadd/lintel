"""Sandbox domain types. Immutable, no I/O dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SandboxStatus(StrEnum):
    PENDING = "pending"
    CREATING = "creating"
    RUNNING = "running"
    COLLECTING = "collecting"
    COMPLETED = "completed"
    FAILED = "failed"
    DESTROYED = "destroyed"


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
