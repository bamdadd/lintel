"""Cloud provider domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class CloudProviderType(StrEnum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


@dataclass(frozen=True)
class CloudProvider:
    """A cloud infrastructure provider configuration."""

    id: str
    name: str
    provider_type: CloudProviderType = CloudProviderType.AWS
    config: dict[str, str] = field(default_factory=dict)
    credentials_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
