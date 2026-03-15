"""Slack command schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from lintel.contracts.types import ThreadRef


@dataclass(frozen=True)
class ProcessIncomingMessage:
    thread_ref: ThreadRef
    raw_text: str
    sender_id: str
    sender_name: str
    idempotency_key: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class GrantApproval:
    thread_ref: ThreadRef
    gate_type: str
    approver_id: str
    approver_name: str
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RejectApproval:
    thread_ref: ThreadRef
    gate_type: str
    rejector_id: str
    reason: str
    correlation_id: UUID = field(default_factory=uuid4)
