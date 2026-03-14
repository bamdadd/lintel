"""PipelineScheduler — checks for new resource versions and schedules jobs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lintel.contracts.commands import StartWorkflow
from lintel.contracts.types import ThreadRef

if TYPE_CHECKING:
    from lintel.api.domain.version_resolver import VersionResolver
    from lintel.contracts.protocols import CommandDispatcher, EventStore


class PipelineScheduler:
    """Checks for new resource versions and schedules downstream jobs."""

    def __init__(
        self,
        event_store: EventStore,
        version_resolver: VersionResolver,
        dispatcher: CommandDispatcher,
        pipelines: list[object] | None = None,
    ) -> None:
        self._event_store = event_store
        self._resolver = version_resolver
        self._dispatcher = dispatcher
        self._pipelines = pipelines or []

    async def tick(self) -> list[str]:
        """One scheduling tick — check all pipelines for schedulable jobs."""
        scheduled_runs: list[str] = []

        for pipeline in self._pipelines:
            for job in pipeline.jobs:  # type: ignore[attr-defined]
                versions = await self._resolver.resolve(job.name, job.inputs)
                if versions is not None:
                    run_id = await self._schedule_job(pipeline, job, versions)
                    scheduled_runs.append(str(run_id))

        return scheduled_runs

    async def _schedule_job(
        self,
        pipeline: object,
        job: object,
        versions: dict[str, Any],
    ) -> object:
        """Schedule a single job execution."""
        pipeline_id = getattr(pipeline, "definition_id", "unknown")
        command = StartWorkflow(
            thread_ref=ThreadRef(
                workspace_id="system",
                channel_id=str(pipeline_id),
                thread_ts=f"scheduled:{getattr(job, 'name', 'job')}",
            ),
            workflow_type=str(pipeline_id),
        )
        return await self._dispatcher.dispatch(command)
