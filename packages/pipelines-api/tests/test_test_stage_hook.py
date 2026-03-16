"""Tests for TestStageHook (REQ-010)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lintel.pipelines_api.hooks import TestStageHook

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope


class _FakeEventBus:
    def __init__(self) -> None:
        self.published: list[EventEnvelope] = []

    async def publish(self, event: EventEnvelope) -> None:
        self.published.append(event)


class _FakeStore:
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []

    async def save(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        self.saved.append(kwargs)
        return kwargs


SAMPLE_JUNIT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="suite1" tests="2" failures="0" errors="0">
    <testcase classname="mod.Test" name="test_one" time="0.01"/>
    <testcase classname="mod.Test" name="test_two" time="0.02"/>
  </testsuite>
</testsuites>
"""

SAMPLE_LCOV = """\
SF:src/app.py
DA:1,1
DA:2,1
DA:3,0
LH:2
LF:3
end_of_record
"""


class TestTestStageHook:
    async def test_parses_test_result_artifact(self) -> None:
        bus = _FakeEventBus()
        parsed_store = _FakeStore()
        coverage_store = _FakeStore()
        hook = TestStageHook(
            parsed_result_store=parsed_store,
            coverage_store=coverage_store,
            event_bus=bus,
        )

        await hook.on_stage_complete(
            run_id="run-1",
            project_id="proj-1",
            stage_id="test",
            artifacts=[
                {
                    "content": SAMPLE_JUNIT_XML.encode("utf-8"),
                    "mime_type": "application/xml",
                    "extension": ".xml",
                    "artifact_type": "test_result",
                    "artifact_id": "art-1",
                }
            ],
        )

        assert len(parsed_store.saved) == 1
        assert parsed_store.saved[0]["run_id"] == "run-1"
        # Should publish TestResultsParsed
        test_events = [e for e in bus.published if e.event_type == "TestResultsParsed"]
        assert len(test_events) == 1
        assert test_events[0].payload["total"] == 2
        assert test_events[0].payload["passed"] == 2

    async def test_parses_coverage_artifact(self) -> None:
        bus = _FakeEventBus()
        parsed_store = _FakeStore()
        coverage_store = _FakeStore()
        hook = TestStageHook(
            parsed_result_store=parsed_store,
            coverage_store=coverage_store,
            event_bus=bus,
        )

        await hook.on_stage_complete(
            run_id="run-1",
            project_id="proj-1",
            stage_id="test",
            artifacts=[
                {
                    "content": SAMPLE_LCOV.encode("utf-8"),
                    "extension": ".info",
                    "artifact_type": "coverage",
                    "artifact_id": "cov-1",
                }
            ],
        )

        assert len(coverage_store.saved) == 1
        assert coverage_store.saved[0]["run_id"] == "run-1"
        # Should publish CoverageMeasured
        cov_events = [e for e in bus.published if e.event_type == "CoverageMeasured"]
        assert len(cov_events) == 1
        assert cov_events[0].payload["run_id"] == "run-1"

    async def test_handles_string_content(self) -> None:
        bus = _FakeEventBus()
        parsed_store = _FakeStore()
        coverage_store = _FakeStore()
        hook = TestStageHook(
            parsed_result_store=parsed_store,
            coverage_store=coverage_store,
            event_bus=bus,
        )

        await hook.on_stage_complete(
            run_id="run-1",
            project_id="proj-1",
            stage_id="test",
            artifacts=[
                {
                    "content": SAMPLE_JUNIT_XML,  # str, not bytes
                    "extension": ".xml",
                    "artifact_type": "test_result",
                }
            ],
        )

        assert len(parsed_store.saved) == 1

    async def test_handles_parse_failure_gracefully(self) -> None:
        bus = _FakeEventBus()
        parsed_store = _FakeStore()
        coverage_store = _FakeStore()
        hook = TestStageHook(
            parsed_result_store=parsed_store,
            coverage_store=coverage_store,
            event_bus=bus,
        )

        await hook.on_stage_complete(
            run_id="run-1",
            project_id="proj-1",
            stage_id="test",
            artifacts=[
                {
                    "content": b"not valid xml at all <<<",
                    "extension": ".xml",
                    "artifact_type": "test_result",
                }
            ],
        )

        # Should not crash; may or may not save depending on parser behaviour
        # Key assertion: no unhandled exception
        assert len(bus.published) <= 1

    async def test_no_event_bus_does_not_crash(self) -> None:
        parsed_store = _FakeStore()
        coverage_store = _FakeStore()
        hook = TestStageHook(
            parsed_result_store=parsed_store,
            coverage_store=coverage_store,
            event_bus=None,
        )

        await hook.on_stage_complete(
            run_id="run-1",
            project_id="proj-1",
            stage_id="test",
            artifacts=[
                {
                    "content": SAMPLE_JUNIT_XML.encode("utf-8"),
                    "extension": ".xml",
                    "artifact_type": "test_result",
                }
            ],
        )

        assert len(parsed_store.saved) == 1

    async def test_multiple_artifacts_processed(self) -> None:
        bus = _FakeEventBus()
        parsed_store = _FakeStore()
        coverage_store = _FakeStore()
        hook = TestStageHook(
            parsed_result_store=parsed_store,
            coverage_store=coverage_store,
            event_bus=bus,
        )

        await hook.on_stage_complete(
            run_id="run-1",
            project_id="proj-1",
            stage_id="test",
            artifacts=[
                {
                    "content": SAMPLE_JUNIT_XML.encode("utf-8"),
                    "extension": ".xml",
                    "artifact_type": "test_result",
                },
                {
                    "content": SAMPLE_LCOV.encode("utf-8"),
                    "extension": ".info",
                    "artifact_type": "coverage",
                },
            ],
        )

        assert len(parsed_store.saved) == 1
        assert len(coverage_store.saved) == 1
        assert len(bus.published) == 2
