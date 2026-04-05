"""Browser extension domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class ModificationStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PREVIEW_READY = "preview_ready"
    APPLIED = "applied"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True)
class ComponentModification:
    """A request to modify a React component via the browser extension."""

    id: str
    project_id: str
    component_path: str
    instructions: str
    screenshot_url: str = ""
    selector: str = ""
    page_url: str = ""
    preview_url: str = ""
    diff: str = ""
    status: ModificationStatus = ModificationStatus.PENDING
    error_message: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
