"""Concourse-style version resolution for pipeline scheduling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lintel.domain.types import ResourceVersion

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventStore
    from lintel.domain.types import JobInput


class VersionResolver:
    """Resolves resource versions respecting passed constraints."""

    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    async def resolve(
        self,
        job_name: str,
        inputs: list[JobInput],
    ) -> dict[str, ResourceVersion] | None:
        """Return resolved version set, or None if no versions available."""
        all_events = await self._event_store.read_all()
        resolved: dict[str, ResourceVersion] = {}

        for inp in inputs:
            if inp.passed_constraints:
                version = self._resolve_with_passed(inp, all_events)
            else:
                version = self._resolve_latest(inp.resource_name, all_events)

            if version is None:
                return None
            resolved[inp.resource_name] = version

        return resolved

    def _resolve_latest(
        self,
        resource_name: str,
        events: list[EventEnvelope],
    ) -> ResourceVersion | None:
        """Return the most recently produced version for a resource."""
        latest = None
        for evt in events:
            if (
                evt.event_type == "ResourceVersionProduced"
                and evt.payload.get("resource_name") == resource_name
            ):
                latest = ResourceVersion(
                    resource_name=resource_name,
                    version=evt.payload.get("version", {}),
                )
        return latest

    def _resolve_with_passed(
        self,
        inp: JobInput,
        events: list[EventEnvelope],
    ) -> ResourceVersion | None:
        """Return latest version that has passed all required jobs."""
        # Collect all produced versions for this resource
        produced: list[dict[str, str]] = []
        for evt in events:
            if (
                evt.event_type == "ResourceVersionProduced"
                and evt.payload.get("resource_name") == inp.resource_name
            ):
                produced.append(evt.payload.get("version", {}))
        # Collect consumed-by-job pairs
        consumed_by: dict[str, set[str]] = {}  # version_key -> set of jobs
        for evt in events:
            if (
                evt.event_type == "ResourceVersionConsumed"
                and evt.payload.get("resource_name") == inp.resource_name
            ):
                ver_key = str(evt.payload.get("version", {}))
                job = str(evt.payload.get("consuming_job", ""))
                consumed_by.setdefault(ver_key, set()).add(job)

        # Find latest version that satisfies all passed constraints
        required_jobs: set[str] = set()
        for constraint in inp.passed_constraints:
            required_jobs.update(constraint.jobs)

        for version in reversed(produced):
            ver_key = str(version)
            passed_jobs = consumed_by.get(ver_key, set())
            if required_jobs.issubset(passed_jobs):
                return ResourceVersion(
                    resource_name=inp.resource_name,
                    version=version,
                )

        return None
