"""Tests for the RetroEngine (DL-4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lintel.domain.retrospectives import (
    ActionItemStatus,
    Observation,
    RetroEngine,
    RetroStatus,
)


def _period() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    return (now - timedelta(days=7), now)


class TestRetroEngineLifecycle:
    def test_create_retro(self) -> None:
        engine = RetroEngine()
        retro = engine.create_retro("proj-1", _period())
        assert retro.project_id == "proj-1"
        assert retro.status == RetroStatus.PENDING

    def test_add_observation(self) -> None:
        engine = RetroEngine()
        retro = engine.create_retro("proj-1", _period())
        obs = Observation(category="performance", description="Slow tests", source_run_id="run-1")
        updated = engine.add_observation(retro.retro_id, obs)
        assert len(updated.observations) == 1
        assert updated.observations[0].category == "performance"

    def test_generate_action_items(self) -> None:
        engine = RetroEngine()
        retro = engine.create_retro("proj-1", _period())
        engine.add_observation(
            retro.retro_id,
            Observation(description="Flaky test", source_run_id="run-1"),
        )
        engine.add_observation(
            retro.retro_id,
            Observation(description="Long build time", source_run_id="run-2"),
        )
        items = engine.generate_action_items(retro.retro_id)
        assert len(items) == 2
        updated = engine.get(retro.retro_id)
        assert updated is not None
        assert updated.status == RetroStatus.IN_PROGRESS

    def test_complete(self) -> None:
        engine = RetroEngine()
        retro = engine.create_retro("proj-1", _period())
        completed = engine.complete(retro.retro_id, "All good")
        assert completed.status == RetroStatus.COMPLETED
        assert completed.summary == "All good"

    def test_get_returns_none_for_missing(self) -> None:
        engine = RetroEngine()
        assert engine.get("nonexistent") is None


class TestActionTracking:
    def test_list_open_actions(self) -> None:
        engine = RetroEngine()
        retro = engine.create_retro("proj-1", _period())
        engine.add_observation(
            retro.retro_id, Observation(description="Issue A", source_run_id="r1")
        )
        engine.generate_action_items(retro.retro_id)
        open_actions = engine.list_open_actions("proj-1")
        assert len(open_actions) == 1
        assert open_actions[0].status == ActionItemStatus.OPEN

    def test_track_action_updates_status(self) -> None:
        engine = RetroEngine()
        retro = engine.create_retro("proj-1", _period())
        engine.add_observation(
            retro.retro_id, Observation(description="Fix it", source_run_id="r1")
        )
        items = engine.generate_action_items(retro.retro_id)
        result = engine.track_action(items[0].action_id, ActionItemStatus.DONE)
        assert result is not None
        assert result.status == ActionItemStatus.DONE
        assert engine.list_open_actions("proj-1") == []

    def test_track_action_returns_none_for_missing(self) -> None:
        engine = RetroEngine()
        assert engine.track_action("nope", ActionItemStatus.DONE) is None
