"""Tests for PipelineScheduler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from lintel.api.domain.pipeline_scheduler import PipelineScheduler
from lintel.domain.types import JobInput, ResourceVersion


async def test_tick_schedules_job_with_new_version() -> None:
    event_store = AsyncMock()
    resolver = AsyncMock()
    dispatcher = AsyncMock()
    dispatcher.dispatch.return_value = "run-123"

    resolver.resolve.return_value = {
        "git-repo": ResourceVersion(resource_name="git-repo", version={"ref": "abc"}),
    }

    pipeline = MagicMock()
    pipeline.definition_id = "pipeline-1"
    pipeline.name = "build-and-test"
    pipeline.jobs = [
        MagicMock(
            name="build",
            inputs=[JobInput(resource_name="git-repo")],
        ),
    ]

    scheduler = PipelineScheduler(
        event_store=event_store,
        version_resolver=resolver,
        dispatcher=dispatcher,
        pipelines=[pipeline],
    )

    runs = await scheduler.tick()

    assert len(runs) == 1
    assert runs[0] == "run-123"
    dispatcher.dispatch.assert_called_once()


async def test_tick_skips_when_no_new_versions() -> None:
    event_store = AsyncMock()
    resolver = AsyncMock()
    dispatcher = AsyncMock()

    resolver.resolve.return_value = None

    pipeline = MagicMock()
    pipeline.definition_id = "pipeline-1"
    pipeline.jobs = [
        MagicMock(
            name="build",
            inputs=[JobInput(resource_name="git-repo")],
        ),
    ]

    scheduler = PipelineScheduler(
        event_store=event_store,
        version_resolver=resolver,
        dispatcher=dispatcher,
        pipelines=[pipeline],
    )

    runs = await scheduler.tick()

    assert len(runs) == 0
    dispatcher.dispatch.assert_not_called()
