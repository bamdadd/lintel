"""In-memory fleet run store."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class FleetRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class RepoRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class RepoRun:
    repo_id: str
    status: RepoRunStatus = RepoRunStatus.PENDING
    error: str = ""
    started_at: str = ""
    completed_at: str = ""


@dataclass(frozen=True)
class FleetRun:
    run_id: str
    name: str
    repo_ids: tuple[str, ...]
    agent_definition_id: str = ""
    workflow_definition_id: str = ""
    status: FleetRunStatus = FleetRunStatus.PENDING
    repo_runs: tuple[RepoRun, ...] = ()
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    cancelled_at: str = ""


def _fleet_to_dict(run: FleetRun) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "name": run.name,
        "repo_ids": list(run.repo_ids),
        "agent_definition_id": run.agent_definition_id,
        "workflow_definition_id": run.workflow_definition_id,
        "status": run.status.value,
        "repo_runs": [
            {
                "repo_id": rr.repo_id,
                "status": rr.status.value,
                "error": rr.error,
                "started_at": rr.started_at,
                "completed_at": rr.completed_at,
            }
            for rr in run.repo_runs
        ],
        "created_at": run.created_at,
        "cancelled_at": run.cancelled_at,
    }


class InMemoryFleetRunStore:
    """Simple in-memory store for fleet runs."""

    def __init__(self) -> None:
        self._runs: dict[str, FleetRun] = {}

    async def add(self, run: FleetRun) -> None:
        self._runs[run.run_id] = run

    async def get(self, run_id: str) -> FleetRun | None:
        return self._runs.get(run_id)

    async def list_all(self) -> list[FleetRun]:
        return list(self._runs.values())

    async def update(self, run: FleetRun) -> None:
        self._runs[run.run_id] = run

    async def remove(self, run_id: str) -> None:
        self._runs.pop(run_id, None)
