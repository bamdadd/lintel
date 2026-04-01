"""Unit tests for ReportVersionProjection."""

from __future__ import annotations

from datetime import UTC, datetime

from lintel.contracts.events import EventEnvelope
from lintel.projections.report_versions import ReportVersionProjection


def _make_event(
    event_type: str,
    run_id: str = "run-1",
    stage_id: str = "stage-1",
    actor_id: str = "user-1",
    occurred_at: datetime | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        actor_id=actor_id,
        occurred_at=occurred_at or datetime.now(UTC),
        payload={"run_id": run_id, "stage_id": stage_id},
    )


async def test_initial_state_is_empty() -> None:
    proj = ReportVersionProjection()
    assert proj.get_state() == {}
    assert proj.get_latest("run-1", "stage-1") == 0
    assert proj.get_history("run-1", "stage-1") == []
    assert proj.get_edit_count("run-1", "stage-1") == 0


async def test_project_stage_report_edited_creates_version() -> None:
    proj = ReportVersionProjection()
    event = _make_event("StageReportEdited")
    await proj.project(event)

    assert proj.get_latest("run-1", "stage-1") == 1
    assert proj.get_edit_count("run-1", "stage-1") == 1

    history = proj.get_history("run-1", "stage-1")
    assert len(history) == 1
    assert history[0]["version"] == 1
    assert history[0]["editor"] == "user-1"
    assert history[0]["event_type"] == "StageReportEdited"


async def test_multiple_events_increment_version_and_edit_count() -> None:
    proj = ReportVersionProjection()
    await proj.project(_make_event("StageReportEdited", actor_id="user-1"))
    await proj.project(_make_event("StageReportEdited", actor_id="user-2"))
    await proj.project(_make_event("StageReportEdited", actor_id="user-3"))

    assert proj.get_latest("run-1", "stage-1") == 3
    assert proj.get_edit_count("run-1", "stage-1") == 3

    history = proj.get_history("run-1", "stage-1")
    assert len(history) == 3
    assert [h["version"] for h in history] == [1, 2, 3]
    assert [h["editor"] for h in history] == ["user-1", "user-2", "user-3"]


async def test_get_latest_returns_correct_version() -> None:
    proj = ReportVersionProjection()
    await proj.project(_make_event("StageReportEdited"))
    await proj.project(_make_event("StageReportEdited"))

    assert proj.get_latest("run-1", "stage-1") == 2
    assert proj.get_latest("run-1", "nonexistent") == 0


async def test_get_history_returns_summaries_in_order() -> None:
    proj = ReportVersionProjection()
    t1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
    t3 = datetime(2026, 1, 3, 0, 0, 0, tzinfo=UTC)

    await proj.project(_make_event("StageReportEdited", actor_id="a", occurred_at=t1))
    await proj.project(_make_event("StageReportRegenerated", actor_id="b", occurred_at=t2))
    await proj.project(_make_event("StageReportEdited", actor_id="c", occurred_at=t3))

    history = proj.get_history("run-1", "stage-1")
    assert len(history) == 3
    assert history[0]["edited_at"] == t1.isoformat()
    assert history[1]["edited_at"] == t2.isoformat()
    assert history[2]["edited_at"] == t3.isoformat()
    assert history[0]["version"] < history[1]["version"] < history[2]["version"]


async def test_get_edit_count_returns_correct_count() -> None:
    proj = ReportVersionProjection()
    assert proj.get_edit_count("run-1", "stage-1") == 0

    await proj.project(_make_event("StageReportEdited"))
    assert proj.get_edit_count("run-1", "stage-1") == 1

    await proj.project(_make_event("StageReportRegenerated"))
    assert proj.get_edit_count("run-1", "stage-1") == 2


async def test_stage_report_regenerated_increments_version() -> None:
    proj = ReportVersionProjection()
    await proj.project(_make_event("StageReportRegenerated"))

    assert proj.get_latest("run-1", "stage-1") == 1
    assert proj.get_edit_count("run-1", "stage-1") == 1

    history = proj.get_history("run-1", "stage-1")
    assert len(history) == 1
    assert history[0]["event_type"] == "StageReportRegenerated"


async def test_rebuild_clears_state_and_replays() -> None:
    proj = ReportVersionProjection()

    # Project some events manually first
    await proj.project(_make_event("StageReportEdited"))
    await proj.project(_make_event("StageReportEdited"))
    assert proj.get_latest("run-1", "stage-1") == 2

    # Rebuild with a different set of events
    rebuild_events = [
        _make_event("StageReportEdited", run_id="run-2", stage_id="s2"),
        _make_event("StageReportRegenerated", run_id="run-2", stage_id="s2"),
        _make_event("StageReportEdited", run_id="run-2", stage_id="s2"),
    ]
    await proj.rebuild(rebuild_events)

    # Old state should be cleared
    assert proj.get_latest("run-1", "stage-1") == 0
    # New state from rebuild
    assert proj.get_latest("run-2", "s2") == 3
    assert proj.get_edit_count("run-2", "s2") == 3


async def test_rebuild_ignores_unhandled_event_types() -> None:
    proj = ReportVersionProjection()
    events = [
        _make_event("StageReportEdited"),
        _make_event("WorkflowStarted"),  # not handled
        _make_event("StageReportRegenerated"),
    ]
    await proj.rebuild(events)

    assert proj.get_latest("run-1", "stage-1") == 2


async def test_get_state_and_restore_state_roundtrip() -> None:
    proj = ReportVersionProjection()
    await proj.project(_make_event("StageReportEdited", actor_id="user-a"))
    await proj.project(_make_event("StageReportRegenerated", actor_id="user-b"))

    state = proj.get_state()

    # Create a new projection and restore
    proj2 = ReportVersionProjection()
    assert proj2.get_latest("run-1", "stage-1") == 0

    proj2.restore_state(state)
    assert proj2.get_latest("run-1", "stage-1") == 2
    assert proj2.get_edit_count("run-1", "stage-1") == 2

    history = proj2.get_history("run-1", "stage-1")
    assert len(history) == 2
    assert history[0]["editor"] == "user-a"
    assert history[1]["editor"] == "user-b"


async def test_handled_event_types_property() -> None:
    proj = ReportVersionProjection()
    handled = proj.handled_event_types
    assert handled == {"StageReportEdited", "StageReportRegenerated"}


async def test_name_property() -> None:
    proj = ReportVersionProjection()
    assert proj.name == "report_versions"
