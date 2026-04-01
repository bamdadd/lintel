"""Multi-agent collaboration primitives (REQ-004).

Provides delegation routing and shared context so that agents within a
pipeline run can hand off subtasks and exchange intermediate results.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
import logging
from typing import Any
from uuid import uuid4

from lintel.agents.types import AgentRole

logger = logging.getLogger(__name__)


class DelegationStatus(StrEnum):
    """Lifecycle status of a delegation request."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class DelegationRequest:
    """One agent asks another to handle a subtask.

    The *from_role* creates the request, targeting *to_role*.  The
    ``CollaborationManager`` routes the request and tracks its status.
    """

    request_id: str = field(default_factory=lambda: uuid4().hex)
    from_role: AgentRole = AgentRole.PLANNER
    to_role: AgentRole = AgentRole.CODER
    task_description: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    status: DelegationStatus = DelegationStatus.PENDING


@dataclass
class DelegationResult:
    """The outcome returned by the delegate agent."""

    request_id: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class SharedContext:
    """Shared mutable state between collaborating agents in one pipeline run.

    Each entry is keyed by an arbitrary namespace string (typically the
    producing agent's role) so consumers can read cross-agent artefacts
    without tight coupling.
    """

    run_id: str = ""
    _entries: dict[str, dict[str, Any]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Read / write
    # ------------------------------------------------------------------

    def set(self, namespace: str, key: str, value: Any) -> None:  # noqa: ANN401
        """Store *value* under *namespace*/*key*."""
        self._entries.setdefault(namespace, {})[key] = value

    def get(self, namespace: str, key: str, default: Any = None) -> Any:  # noqa: ANN401
        """Retrieve a value, returning *default* if absent."""
        return self._entries.get(namespace, {}).get(key, default)

    def get_namespace(self, namespace: str) -> dict[str, Any]:
        """Return a shallow copy of all entries in *namespace*."""
        return dict(self._entries.get(namespace, {}))

    def namespaces(self) -> list[str]:
        """Return the list of populated namespace keys."""
        return list(self._entries)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Return a deep-ish copy suitable for serialisation."""
        return {ns: dict(entries) for ns, entries in self._entries.items()}

    def merge(self, other: SharedContext) -> None:
        """Merge *other*'s entries into this context (last-write wins)."""
        for ns, entries in other._entries.items():
            self._entries.setdefault(ns, {}).update(entries)

    def clear_namespace(self, namespace: str) -> None:
        """Remove all entries in *namespace*."""
        self._entries.pop(namespace, None)


class CollaborationManager:
    """Routes delegation requests and manages shared context for a run.

    One ``CollaborationManager`` instance is created per pipeline run.
    Agents call :meth:`delegate` to request work from a peer and
    :meth:`complete_delegation` to deliver the result.
    """

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.shared_context = SharedContext(run_id=run_id)
        self._requests: dict[str, DelegationRequest] = {}
        self._results: dict[str, DelegationResult] = {}
        self._waiters: dict[str, asyncio.Event] = {}

    # ------------------------------------------------------------------
    # Delegation lifecycle
    # ------------------------------------------------------------------

    def delegate(self, request: DelegationRequest) -> DelegationRequest:
        """Register a new delegation request.

        Returns the request (useful when the caller lets request_id be
        auto-generated).
        """
        if request.request_id in self._requests:
            msg = f"Duplicate delegation request: {request.request_id}"
            raise ValueError(msg)
        self._requests[request.request_id] = request
        self._waiters[request.request_id] = asyncio.Event()
        logger.info(
            "Delegation %s: %s -> %s (%s)",
            request.request_id,
            request.from_role,
            request.to_role,
            request.task_description[:80],
        )
        return request

    def accept(self, request_id: str) -> None:
        """Mark a delegation as accepted by the target agent."""
        req = self._get_request(request_id)
        self._requests[request_id] = DelegationRequest(
            request_id=req.request_id,
            from_role=req.from_role,
            to_role=req.to_role,
            task_description=req.task_description,
            payload=req.payload,
            priority=req.priority,
            status=DelegationStatus.ACCEPTED,
        )

    def complete_delegation(self, result: DelegationResult) -> None:
        """Record the result of a completed delegation."""
        req = self._get_request(result.request_id)
        status = DelegationStatus.COMPLETED if result.success else DelegationStatus.REJECTED
        self._requests[result.request_id] = DelegationRequest(
            request_id=req.request_id,
            from_role=req.from_role,
            to_role=req.to_role,
            task_description=req.task_description,
            payload=req.payload,
            priority=req.priority,
            status=status,
        )
        self._results[result.request_id] = result
        waiter = self._waiters.get(result.request_id)
        if waiter:
            waiter.set()

    async def wait_for_result(
        self,
        request_id: str,
        timeout: float | None = None,
    ) -> DelegationResult | None:
        """Block until the delegation completes or *timeout* elapses.

        Returns ``None`` on timeout.
        """
        waiter = self._waiters.get(request_id)
        if waiter is None:
            msg = f"Unknown delegation request: {request_id}"
            raise KeyError(msg)
        try:
            await asyncio.wait_for(waiter.wait(), timeout=timeout)
        except TimeoutError:
            req = self._requests[request_id]
            self._requests[request_id] = DelegationRequest(
                request_id=req.request_id,
                from_role=req.from_role,
                to_role=req.to_role,
                task_description=req.task_description,
                payload=req.payload,
                priority=req.priority,
                status=DelegationStatus.TIMED_OUT,
            )
            return None
        return self._results.get(request_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_request(self, request_id: str) -> DelegationRequest:
        """Return a delegation request by id."""
        return self._get_request(request_id)

    def pending_for(self, role: AgentRole) -> list[DelegationRequest]:
        """Return pending delegations targeted at *role*."""
        return [
            r
            for r in self._requests.values()
            if r.to_role == role and r.status == DelegationStatus.PENDING
        ]

    def all_requests(self) -> list[DelegationRequest]:
        """Return all tracked delegation requests."""
        return list(self._requests.values())

    def get_result(self, request_id: str) -> DelegationResult | None:
        """Return the result for a completed delegation, or ``None``."""
        return self._results.get(request_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_request(self, request_id: str) -> DelegationRequest:
        try:
            return self._requests[request_id]
        except KeyError:
            msg = f"Unknown delegation request: {request_id}"
            raise KeyError(msg) from None
