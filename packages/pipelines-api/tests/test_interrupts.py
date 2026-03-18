"""Tests for interrupt resume and query API routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.pipelines_api.interrupts import interrupt_store_provider, router
from lintel.workflows.repositories.interrupt_repository import InMemoryInterruptRepository
from lintel.workflows.types import InterruptRequest, InterruptType

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def interrupt_repo() -> InMemoryInterruptRepository:
    return InMemoryInterruptRepository()


@pytest.fixture()
def client(interrupt_repo: InMemoryInterruptRepository) -> Generator[TestClient]:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    interrupt_store_provider.override(interrupt_repo)
    with TestClient(app) as c:
        yield c


async def _seed_interrupt(
    repo: InMemoryInterruptRepository,
    *,
    run_id: str = "run-1",
    stage: str = "approval_gate_spec",
    deadline: datetime | None = None,
) -> InterruptRequest:
    """Seed an interrupt record into the repo."""
    req = InterruptRequest(
        id=uuid4(),
        run_id=run_id,
        stage=stage,
        interrupt_type=InterruptType.APPROVAL_GATE,
        payload={"node_name": stage},
        timeout_seconds=0,
        deadline=deadline,
    )
    await repo.create_interrupt(req)
    return req


class TestResumeInterrupt:
    async def test_resume_pending_interrupt(
        self,
        client: TestClient,
        interrupt_repo: InMemoryInterruptRepository,
    ) -> None:
        req = await _seed_interrupt(interrupt_repo)
        resp = client.post(
            f"/api/v1/pipelines/{req.run_id}/stages/{req.stage}/resume",
            json={"input": {"approved": True}, "resumed_by": "tester"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resumed"
        assert data["resumed_by"] == "tester"

    def test_resume_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/pipelines/no-run/stages/no-stage/resume",
            json={"input": None},
        )
        assert resp.status_code == 404

    async def test_resume_already_resumed_returns_409(
        self,
        client: TestClient,
        interrupt_repo: InMemoryInterruptRepository,
    ) -> None:
        req = await _seed_interrupt(interrupt_repo)
        await interrupt_repo.mark_resumed(req.id, "first-user")
        resp = client.post(
            f"/api/v1/pipelines/{req.run_id}/stages/{req.stage}/resume",
            json={"input": "second attempt"},
        )
        assert resp.status_code == 409

    async def test_resume_past_deadline_returns_410(
        self,
        client: TestClient,
        interrupt_repo: InMemoryInterruptRepository,
    ) -> None:
        past = datetime.now(tz=UTC) - timedelta(minutes=5)
        req = await _seed_interrupt(interrupt_repo, deadline=past)
        resp = client.post(
            f"/api/v1/pipelines/{req.run_id}/stages/{req.stage}/resume",
            json={"input": "too late"},
        )
        assert resp.status_code == 410


class TestGetInterrupt:
    async def test_get_existing_interrupt(
        self,
        client: TestClient,
        interrupt_repo: InMemoryInterruptRepository,
    ) -> None:
        req = await _seed_interrupt(interrupt_repo)
        resp = client.get(
            f"/api/v1/pipelines/{req.run_id}/stages/{req.stage}/interrupt",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == req.run_id
        assert data["stage"] == req.stage
        assert data["status"] == "pending"

    def test_get_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/pipelines/no-run/stages/no-stage/interrupt",
        )
        assert resp.status_code == 404
