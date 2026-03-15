"""Tests for VersionResolver."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

from lintel.domain.events import ResourceVersionConsumed, ResourceVersionProduced
from lintel.domain.types import JobInput, PassedConstraint
from lintel.api.domain.version_resolver import VersionResolver


def _make_produced_event(
    resource: str,
    version: dict[str, str],
    job: str,
) -> ResourceVersionProduced:
    return ResourceVersionProduced(
        payload={
            "resource_name": resource,
            "version": version,
            "producing_job": job,
            "run_id": str(uuid4()),
        },
    )


def _make_consumed_event(
    resource: str,
    version: dict[str, str],
    job: str,
) -> ResourceVersionConsumed:
    return ResourceVersionConsumed(
        payload={
            "resource_name": resource,
            "version": version,
            "consuming_job": job,
            "run_id": str(uuid4()),
        },
    )


async def test_resolve_latest_returns_most_recent_version() -> None:
    event_store = AsyncMock()
    event_store.read_all.return_value = [
        _make_produced_event("git-repo", {"ref": "abc"}, "build"),
        _make_produced_event("git-repo", {"ref": "def"}, "build"),
    ]

    resolver = VersionResolver(event_store=event_store)
    inputs = [JobInput(resource_name="git-repo")]

    result = await resolver.resolve("deploy", inputs)

    assert result is not None
    assert result["git-repo"].version == {"ref": "def"}


async def test_resolve_with_passed_constraint() -> None:
    event_store = AsyncMock()
    event_store.read_all.return_value = [
        _make_produced_event("git-repo", {"ref": "abc"}, "build"),
        _make_consumed_event("git-repo", {"ref": "abc"}, "test"),
        _make_produced_event("git-repo", {"ref": "def"}, "build"),
    ]

    resolver = VersionResolver(event_store=event_store)
    inputs = [
        JobInput(
            resource_name="git-repo",
            passed_constraints=(PassedConstraint(resource_name="git-repo", jobs=("test",)),),
        ),
    ]

    result = await resolver.resolve("deploy", inputs)

    assert result is not None
    # Should return "abc" since it's the only version that passed "test"
    assert result["git-repo"].version == {"ref": "abc"}


async def test_resolve_returns_none_when_no_versions() -> None:
    event_store = AsyncMock()
    event_store.read_all.return_value = []

    resolver = VersionResolver(event_store=event_store)
    inputs = [JobInput(resource_name="git-repo")]

    result = await resolver.resolve("deploy", inputs)

    assert result is None
