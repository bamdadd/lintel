"""Cloud environment domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class CloudProvider(StrEnum):
    """Supported cloud providers."""

    AWS_EC2 = "aws_ec2"
    GCP_CE = "gcp_ce"


class CloudEnvStatus(StrEnum):
    """Cloud environment lifecycle status."""

    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"
    ERROR = "error"


@dataclass(frozen=True)
class CloudEnvironment:
    """A cloud VM environment record."""

    cloud_environment_id: str
    name: str
    provider: CloudProvider
    instance_type: str = "t3.micro"
    region: str = "us-east-1"
    status: CloudEnvStatus = CloudEnvStatus.PENDING
    config: dict[str, object] | None = None
    error_message: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
