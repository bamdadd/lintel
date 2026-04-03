"""Tests for agent sub-session spawning and lifecycle."""

from __future__ import annotations

import pytest

from lintel.agents.sub_sessions import SubSessionManager
from lintel.agents.types import SubSessionStatus


class TestSubSessionManager:
    def test_spawn_creates_pending_session(self) -> None:
        mgr = SubSessionManager()
        session = mgr.spawn("parent-1", "org/repo", "research auth patterns")
        assert session.status == SubSessionStatus.PENDING
        assert session.repo == "org/repo"
        assert session.prompt == "research auth patterns"
        assert session.parent_session_id == "parent-1"
        assert session.session_id  # non-empty

    def test_get_returns_session(self) -> None:
        mgr = SubSessionManager()
        session = mgr.spawn("parent-1", "org/repo", "prompt")
        found = mgr.get(session.session_id)
        assert found is not None
        assert found.session_id == session.session_id

    def test_get_returns_none_for_unknown(self) -> None:
        mgr = SubSessionManager()
        assert mgr.get("nonexistent") is None

    def test_list_for_parent(self) -> None:
        mgr = SubSessionManager()
        mgr.spawn("parent-1", "org/a", "prompt a")
        mgr.spawn("parent-1", "org/b", "prompt b")
        mgr.spawn("parent-2", "org/c", "prompt c")
        sessions = mgr.list_for_parent("parent-1")
        assert len(sessions) == 2
        assert all(s.parent_session_id == "parent-1" for s in sessions)

    def test_list_all(self) -> None:
        mgr = SubSessionManager()
        mgr.spawn("p1", "org/a", "a")
        mgr.spawn("p2", "org/b", "b")
        assert len(mgr.list_all()) == 2

    def test_mark_running(self) -> None:
        mgr = SubSessionManager()
        session = mgr.spawn("parent-1", "org/repo", "prompt")
        updated = mgr.mark_running(session.session_id)
        assert updated.status == SubSessionStatus.RUNNING
        assert mgr.get(session.session_id) is not None
        assert mgr.get(session.session_id).status == SubSessionStatus.RUNNING  # type: ignore[union-attr]

    def test_mark_completed(self) -> None:
        mgr = SubSessionManager()
        session = mgr.spawn("parent-1", "org/repo", "prompt")
        mgr.mark_running(session.session_id)
        updated = mgr.mark_completed(session.session_id, "Found JWT auth pattern")
        assert updated.status == SubSessionStatus.COMPLETED
        assert updated.result == "Found JWT auth pattern"

    def test_mark_failed(self) -> None:
        mgr = SubSessionManager()
        session = mgr.spawn("parent-1", "org/repo", "prompt")
        mgr.mark_running(session.session_id)
        updated = mgr.mark_failed(session.session_id, "sandbox timeout")
        assert updated.status == SubSessionStatus.FAILED
        assert updated.error == "sandbox timeout"

    def test_max_sub_sessions_enforced(self) -> None:
        mgr = SubSessionManager(max_sub_sessions=2)
        mgr.spawn("parent-1", "org/a", "a")
        mgr.spawn("parent-1", "org/b", "b")
        with pytest.raises(ValueError, match="Max sub-sessions"):
            mgr.spawn("parent-1", "org/c", "c")

    def test_max_sub_sessions_per_parent(self) -> None:
        mgr = SubSessionManager(max_sub_sessions=1)
        mgr.spawn("parent-1", "org/a", "a")
        # Different parent should still be allowed
        session = mgr.spawn("parent-2", "org/b", "b")
        assert session.parent_session_id == "parent-2"
