"""Tests for SessionLifecycleManager."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from lintel.sandbox.errors import (
    SandboxHibernatedError,
    SandboxNotFoundError,
    SessionAlreadyInStateError,
)
from lintel.sandbox.session_lifecycle import SessionLifecycleManager
from lintel.sandbox.types import (
    SessionCost,
    SessionState,
    TimeoutConfig,
)


class TestRegisterAndGet:
    def test_register_creates_running_session(self) -> None:
        mgr = SessionLifecycleManager()
        session = mgr.register("sbx-1")
        assert session.sandbox_id == "sbx-1"
        assert session.state == SessionState.RUNNING
        assert session.cost.cpu_seconds == 0.0

    def test_register_with_custom_timeout(self) -> None:
        mgr = SessionLifecycleManager()
        cfg = TimeoutConfig(idle_timeout_seconds=600, max_lifetime_seconds=3600)
        session = mgr.register("sbx-1", timeout_config=cfg)
        assert session.timeout_config.idle_timeout_seconds == 600
        assert session.timeout_config.max_lifetime_seconds == 3600

    def test_get_existing(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        session = mgr.get("sbx-1")
        assert session.sandbox_id == "sbx-1"

    def test_get_missing_raises(self) -> None:
        mgr = SessionLifecycleManager()
        with pytest.raises(SandboxNotFoundError):
            mgr.get("nonexistent")

    def test_get_or_none_returns_none(self) -> None:
        mgr = SessionLifecycleManager()
        assert mgr.get_or_none("nonexistent") is None

    def test_list_all(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        mgr.register("sbx-2")
        assert len(mgr.list_all()) == 2


class TestRecordActivity:
    def test_updates_last_activity(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        before = mgr.get("sbx-1").last_activity_at
        updated = mgr.record_activity("sbx-1")
        assert updated.last_activity_at >= before

    def test_raises_on_hibernated(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        mgr.hibernate("sbx-1", "snap-1")
        with pytest.raises(SandboxHibernatedError):
            mgr.record_activity("sbx-1")


class TestHibernate:
    def test_hibernate_running(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        session = mgr.hibernate("sbx-1", "snap-1")
        assert session.state == SessionState.HIBERNATED
        assert session.snapshot_id == "snap-1"
        assert session.hibernated_at is not None

    def test_hibernate_already_hibernated_raises(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        mgr.hibernate("sbx-1", "snap-1")
        with pytest.raises(SessionAlreadyInStateError):
            mgr.hibernate("sbx-1", "snap-2")

    def test_hibernate_terminated_raises(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        mgr.terminate("sbx-1")
        with pytest.raises(SessionAlreadyInStateError):
            mgr.hibernate("sbx-1", "snap-1")

    def test_hibernate_accumulates_cost(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        session = mgr.hibernate("sbx-1", "snap-1")
        # Cost should be >= 0 (small elapsed time)
        assert session.cost.cpu_seconds >= 0.0


class TestResume:
    def test_resume_hibernated(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        mgr.hibernate("sbx-1", "snap-1")
        session = mgr.resume("sbx-1")
        assert session.state == SessionState.RESUMED
        assert session.resumed_at is not None

    def test_resume_non_hibernated_raises(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        with pytest.raises(SessionAlreadyInStateError):
            mgr.resume("sbx-1")

    def test_resume_then_record_activity(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        mgr.hibernate("sbx-1", "snap-1")
        mgr.resume("sbx-1")
        # Should succeed after resume
        updated = mgr.record_activity("sbx-1")
        assert updated.state == SessionState.RESUMED


class TestTerminate:
    def test_terminate_running(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        session = mgr.terminate("sbx-1")
        assert session.state == SessionState.TERMINATED
        assert session.terminated_at is not None

    def test_terminate_hibernated(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        mgr.hibernate("sbx-1", "snap-1")
        session = mgr.terminate("sbx-1")
        assert session.state == SessionState.TERMINATED

    def test_terminate_already_terminated_raises(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        mgr.terminate("sbx-1")
        with pytest.raises(SessionAlreadyInStateError):
            mgr.terminate("sbx-1")


class TestRemove:
    def test_remove_existing(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        mgr.remove("sbx-1")
        assert mgr.get_or_none("sbx-1") is None

    def test_remove_nonexistent_noop(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.remove("nonexistent")  # Should not raise


class TestTimeoutConfig:
    def test_update_timeout_config(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1")
        cfg = TimeoutConfig(idle_timeout_seconds=300, max_lifetime_seconds=7200)
        session = mgr.update_timeout_config("sbx-1", cfg)
        assert session.timeout_config.idle_timeout_seconds == 300
        assert session.timeout_config.max_lifetime_seconds == 7200


class TestIdleAndExpiredChecks:
    def test_check_idle_sessions(self) -> None:
        mgr = SessionLifecycleManager()
        session = mgr.register("sbx-1", TimeoutConfig(idle_timeout_seconds=0))
        # Force last_activity_at to the past
        old = replace(session, last_activity_at=datetime.now(UTC) - timedelta(seconds=10))
        mgr._sessions["sbx-1"] = old

        idle = mgr.check_idle_sessions()
        assert "sbx-1" in idle

    def test_check_idle_skips_hibernated(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1", TimeoutConfig(idle_timeout_seconds=0))
        mgr.hibernate("sbx-1", "snap-1")
        idle = mgr.check_idle_sessions()
        assert "sbx-1" not in idle

    def test_check_expired_sessions(self) -> None:
        mgr = SessionLifecycleManager()
        session = mgr.register("sbx-1", TimeoutConfig(max_lifetime_seconds=0))
        old = replace(session, created_at=datetime.now(UTC) - timedelta(seconds=10))
        mgr._sessions["sbx-1"] = old

        expired = mgr.check_expired_sessions()
        assert "sbx-1" in expired

    def test_check_expired_skips_terminated(self) -> None:
        mgr = SessionLifecycleManager()
        mgr.register("sbx-1", TimeoutConfig(max_lifetime_seconds=0))
        mgr.terminate("sbx-1")
        expired = mgr.check_expired_sessions()
        assert "sbx-1" not in expired


class TestSessionCost:
    def test_total_cost_units(self) -> None:
        cost = SessionCost(cpu_seconds=100.0, memory_mb_seconds=4096.0, storage_mb_seconds=1024.0)
        # 100 + (4096/1024)*0.5 + (1024/1024)*0.1 = 100 + 2.0 + 0.1 = 102.1
        assert abs(cost.total_cost_units - 102.1) < 0.001

    def test_default_cost_is_zero(self) -> None:
        cost = SessionCost()
        assert cost.total_cost_units == 0.0
