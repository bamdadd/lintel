"""Tests for the chat retry endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestRetryEndpoint:
    """Tests for POST /chat/conversations/{id}/retry."""

    def test_retry_unknown_conversation_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/v1/chat/conversations/nonexistent/retry")
        assert resp.status_code == 404

    def test_retry_conversation_without_workflow_returns_409(
        self,
        client: TestClient,
    ) -> None:
        # Create a plain conversation with no workflow
        resp = client.post(
            "/api/v1/chat/conversations",
            json={"user_id": "user1"},
        )
        assert resp.status_code == 201
        conv_id = resp.json()["conversation_id"]

        resp = client.post(f"/api/v1/chat/conversations/{conv_id}/retry")
        assert resp.status_code == 409
        assert "No workflow" in resp.json()["detail"]

    def test_retry_dispatches_workflow(self, client: TestClient) -> None:
        """Retry on a conversation with a pending workflow should re-dispatch."""
        client.post(
            "/api/v1/projects",
            json={"name": "RetryProj", "project_id": "proj-retry"},
        )

        # Create conversation that triggers a workflow
        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user1",
                "project_id": "proj-retry",
                "message": "implement a new login page with OAuth support please",
            },
        )
        assert resp.status_code == 201
        conv_id = resp.json()["conversation_id"]

        # Verify conversation has a run_id (workflow was dispatched)
        resp = client.get(f"/api/v1/chat/conversations/{conv_id}/status")
        assert resp.status_code == 200
        assert resp.json()["run_id"] is not None
        run_id = resp.json()["run_id"]

        # Mark the pipeline as failed so retry is allowed.
        # Use a fresh asyncpg pool to avoid connection conflicts with TestClient.
        import dataclasses
        import os

        from lintel.workflows.types import PipelineStatus

        pipeline_store = client.app.state.pipeline_store  # type: ignore[union-attr]
        dsn = os.environ.get("LINTEL_DB_DSN")

        if dsn:
            # Postgres backend — use a fresh pool in a new event loop
            import asyncio
            import concurrent.futures

            import asyncpg

            async def _fail_run_pg() -> None:
                pool = await asyncpg.create_pool(dsn)
                assert pool is not None
                store = type(pipeline_store)(pool)  # type: ignore[call-arg]
                run = await store.get(run_id)
                if run is not None:
                    failed = dataclasses.replace(run, status=PipelineStatus.FAILED)
                    await store.update(failed)
                await pool.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(asyncio.run, _fail_run_pg()).result()
        else:
            # In-memory backend — direct mutation is fine
            import asyncio

            async def _fail_run() -> None:
                run = await pipeline_store.get(run_id)
                if run is not None:
                    failed = dataclasses.replace(run, status=PipelineStatus.FAILED)
                    await pipeline_store.update(failed)

            asyncio.get_event_loop().run_until_complete(_fail_run())

        # Retry
        resp = client.post(f"/api/v1/chat/conversations/{conv_id}/retry")
        assert resp.status_code == 200
        data = resp.json()
        # Should have a "Retrying workflow..." message
        agent_msgs = [m for m in data["messages"] if m["role"] == "agent"]
        retry_msgs = [m for m in agent_msgs if "Retrying" in m["content"]]
        assert len(retry_msgs) >= 1
