"""In-memory store for cross-repo test runs."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from enum import StrEnum


class RunStatus(StrEnum):
    pending = "pending"
    running = "running"
    passed = "passed"
    failed = "failed"
    cancelled = "cancelled"


class RepoTestStatus(StrEnum):
    pending = "pending"
    running = "running"
    passed = "passed"
    failed = "failed"
    skipped = "skipped"


@dataclasses.dataclass
class TestResult:
    repository_id: str = ""
    status: str = "pending"
    test_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    error_message: str = ""
    duration_ms: int = 0


@dataclasses.dataclass
class TestRun:
    run_id: str = dataclasses.field(default_factory=lambda: __import__("uuid").uuid4().hex)
    repositories: list[str] = dataclasses.field(default_factory=list)
    results: list[dict[str, object]] = dataclasses.field(default_factory=list)
    status: str = "pending"
    project_id: str = ""
    triggered_by: str = ""
    created_at: str = dataclasses.field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    started_at: str | None = None
    completed_at: str | None = None


class InMemoryTestRunStore:
    """Simple in-memory store for cross-repo test runs."""

    def __init__(self) -> None:
        self._runs: dict[str, TestRun] = {}

    async def add(self, run: TestRun) -> None:
        if run.run_id in self._runs:
            msg = f"Test run {run.run_id} already exists"
            raise ValueError(msg)
        self._runs[run.run_id] = run

    async def get(self, run_id: str) -> TestRun | None:
        return self._runs.get(run_id)

    async def list_all(self, status: str | None = None) -> list[TestRun]:
        items = list(self._runs.values())
        if status is not None:
            items = [r for r in items if r.status == status]
        return items

    async def update(self, run_id: str, fields: dict[str, object]) -> TestRun | None:
        run = self._runs.get(run_id)
        if run is None:
            return None
        for key, value in fields.items():
            if hasattr(run, key):
                object.__setattr__(run, key, value)
        return run

    async def remove(self, run_id: str) -> None:
        if run_id not in self._runs:
            msg = f"Test run {run_id} not found"
            raise KeyError(msg)
        del self._runs[run_id]
