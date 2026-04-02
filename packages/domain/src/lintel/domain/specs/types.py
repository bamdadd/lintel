"""Domain types for collaborative spec editing (REQ-F022)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class SpecStatus(StrEnum):
    """Lifecycle status of a specification document."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class SpecSection:
    """A single section within a specification."""

    section_id: str
    title: str
    content: str
    author: str
    version: int = 1


@dataclass(frozen=True)
class Spec:
    """A collaborative specification document."""

    spec_id: str
    title: str
    sections: tuple[SpecSection, ...] = ()
    status: SpecStatus = SpecStatus.DRAFT
    created_by: str = ""
    reviewers: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    version: int = 1


@dataclass(frozen=True)
class SpecComment:
    """A comment on a spec or spec section."""

    comment_id: str
    spec_id: str
    section_id: str
    author: str
    content: str
    resolved: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
