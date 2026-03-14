"""Tests that all existing projections implement the extended Projection protocol."""

from __future__ import annotations

from unittest.mock import AsyncMock

from lintel.infrastructure.projections.audit import AuditProjection
from lintel.infrastructure.projections.quality_metrics import QualityMetricsProjection
from lintel.infrastructure.projections.task_backlog import TaskBacklogProjection
from lintel.infrastructure.projections.thread_status import ThreadStatusProjection


class TestTaskBacklogProjectionProtocol:
    def test_has_name(self) -> None:
        p = TaskBacklogProjection()
        assert p.name == "task_backlog"

    def test_get_state_returns_dict(self) -> None:
        p = TaskBacklogProjection()
        assert p.get_state() == {}

    def test_restore_state_replaces_internal(self) -> None:
        p = TaskBacklogProjection()
        p.restore_state({"abc": {"status": "pending"}})
        assert p.get_state() == {"abc": {"status": "pending"}}
        assert p.get_backlog() == [{"status": "pending"}]

    def test_get_state_roundtrips(self) -> None:
        p = TaskBacklogProjection()
        p.restore_state({"x": {"status": "done"}})
        state = p.get_state()
        p2 = TaskBacklogProjection()
        p2.restore_state(state)
        assert p2.get_state() == state


class TestThreadStatusProjectionProtocol:
    def test_has_name(self) -> None:
        p = ThreadStatusProjection()
        assert p.name == "thread_status"

    def test_get_state_roundtrips(self) -> None:
        p = ThreadStatusProjection()
        p.restore_state({"t1": {"status": "active"}})
        state = p.get_state()
        p2 = ThreadStatusProjection()
        p2.restore_state(state)
        assert p2.get_all() == [{"status": "active"}]


class TestAuditProjectionProtocol:
    def test_has_name(self) -> None:
        p = AuditProjection(audit_store=AsyncMock())
        assert p.name == "audit"

    def test_get_state_returns_empty(self) -> None:
        p = AuditProjection(audit_store=AsyncMock())
        assert p.get_state() == {}

    def test_restore_state_is_noop(self) -> None:
        p = AuditProjection(audit_store=AsyncMock())
        p.restore_state({"anything": True})
        assert p.get_state() == {}


class TestQualityMetricsProjectionProtocol:
    def test_has_name(self) -> None:
        p = QualityMetricsProjection()
        assert p.name == "quality_metrics"

    def test_get_state_returns_dict(self) -> None:
        p = QualityMetricsProjection()
        state = p.get_state()
        assert "coverage_records" in state
        assert "defect_records" in state
        assert "commit_records" in state
        assert "merge_records" in state

    def test_restore_state_roundtrips(self) -> None:
        p = QualityMetricsProjection()
        state = p.get_state()
        p2 = QualityMetricsProjection()
        p2.restore_state(state)
        assert p2.get_state() == state
