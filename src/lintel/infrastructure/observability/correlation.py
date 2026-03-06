"""Correlation ID propagation via contextvars."""

from __future__ import annotations

import contextvars
from uuid import UUID, uuid4

correlation_id_var: contextvars.ContextVar[UUID] = contextvars.ContextVar(
    "correlation_id", default=uuid4()
)


def get_correlation_id() -> UUID:
    return correlation_id_var.get()


def set_correlation_id(cid: UUID) -> contextvars.Token[UUID]:
    return correlation_id_var.set(cid)
