"""Correlation ID propagation via contextvars."""

from __future__ import annotations

import contextvars
from uuid import UUID, uuid4

correlation_id_var: contextvars.ContextVar[UUID] = contextvars.ContextVar("correlation_id")


def get_correlation_id() -> UUID:
    try:
        return correlation_id_var.get()
    except LookupError:
        cid = uuid4()
        correlation_id_var.set(cid)
        return cid


def set_correlation_id(cid: UUID) -> contextvars.Token[UUID]:
    return correlation_id_var.set(cid)
