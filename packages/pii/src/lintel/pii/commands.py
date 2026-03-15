"""PII-related commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from lintel.contracts.types import ThreadRef


@dataclass(frozen=True)
class RevealPII:
    thread_ref: ThreadRef
    placeholder: str
    requester_id: str
    reason: str
    correlation_id: UUID = field(default_factory=uuid4)
