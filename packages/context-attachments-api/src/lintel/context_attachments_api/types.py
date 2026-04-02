"""Context attachment domain types (REQ-027)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class AttachmentType(StrEnum):
    """Kind of attached context."""

    DOCUMENT = "document"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    LINK = "link"
    CODE_SNIPPET = "code_snippet"
    OTHER = "other"


class AttachmentTarget(StrEnum):
    """Entity type an attachment can be linked to."""

    THREAD = "thread"
    WORK_ITEM = "work_item"
    CONVERSATION = "conversation"
    PROJECT = "project"


@dataclass(frozen=True)
class Attachment:
    """A context attachment linked to a work item, thread, or conversation (REQ-027)."""

    attachment_id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    target_type: AttachmentTarget = AttachmentTarget.WORK_ITEM
    target_id: str = ""
    attachment_type: AttachmentType = AttachmentType.OTHER
    filename: str = ""
    url: str = ""
    description: str = ""
    mime_type: str = ""
    size_bytes: int = 0
    tags: tuple[str, ...] = ()
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
