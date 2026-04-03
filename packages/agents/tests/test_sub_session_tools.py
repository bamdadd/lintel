"""Tests for sub-session agent tools."""

from __future__ import annotations

import json

from lintel.agents.sub_session_tools import (
    SubSessionToolDispatcher,
    is_sub_session_tool,
    sub_session_tool_schemas,
)
from lintel.sandboxes_api.sub_session_store import InMemorySubSessionStore


class TestSubSessionToolSchemas:
    def test_returns_three_tools(self) -> None:
        schemas = sub_session_tool_schemas()
        assert len(schemas) == 3
        names = {s["function"]["name"] for s in schemas}
        assert names == {
            "sub_session_spawn",
            "sub_session_check_status",
            "sub_session_get_result",
        }

    def test_is_sub_session_tool(self) -> None:
        assert is_sub_session_tool("sub_session_spawn") is True
        assert is_sub_session_tool("sub_session_check_status") is True
        assert is_sub_session_tool("sandbox_read_file") is False


class TestSubSessionToolDispatcher:
    async def test_spawn(self) -> None:
        store = InMemorySubSessionStore()
        dispatcher = SubSessionToolDispatcher(store, "run-1")
        result = json.loads(
            await dispatcher.dispatch(
                "sub_session_spawn",
                {"prompt": "research auth", "repo_url": "https://github.com/org/repo"},
            ),
        )
        assert result["status"] == "pending"
        assert result["session_id"]

        # Verify in store
        got = await store.get(result["session_id"])
        assert got is not None
        assert got["prompt"] == "research auth"
        assert got["repo_url"] == "https://github.com/org/repo"
        assert got["parent_pipeline_run_id"] == "run-1"

    async def test_spawn_max_reached(self) -> None:
        store = InMemorySubSessionStore()
        dispatcher = SubSessionToolDispatcher(store, "run-1", max_sub_sessions=2)

        await dispatcher.dispatch("sub_session_spawn", {"prompt": "p1"})
        await dispatcher.dispatch("sub_session_spawn", {"prompt": "p2"})

        result = json.loads(
            await dispatcher.dispatch("sub_session_spawn", {"prompt": "p3"}),
        )
        assert "error" in result
        assert "Maximum" in result["error"]

    async def test_check_status(self) -> None:
        store = InMemorySubSessionStore()
        dispatcher = SubSessionToolDispatcher(store, "run-1")

        spawn_result = json.loads(
            await dispatcher.dispatch("sub_session_spawn", {"prompt": "research"}),
        )
        session_id = spawn_result["session_id"]

        status_result = json.loads(
            await dispatcher.dispatch("sub_session_check_status", {"session_id": session_id}),
        )
        assert status_result["status"] == "pending"
        assert status_result["session_id"] == session_id

    async def test_check_status_not_found(self) -> None:
        store = InMemorySubSessionStore()
        dispatcher = SubSessionToolDispatcher(store, "run-1")

        result = json.loads(
            await dispatcher.dispatch("sub_session_check_status", {"session_id": "missing"}),
        )
        assert "error" in result

    async def test_get_result(self) -> None:
        store = InMemorySubSessionStore()
        dispatcher = SubSessionToolDispatcher(store, "run-1")

        spawn_result = json.loads(
            await dispatcher.dispatch("sub_session_spawn", {"prompt": "research"}),
        )
        session_id = spawn_result["session_id"]

        # Simulate completion
        from lintel.domain.types import SubSessionStatus

        await store.update(
            session_id,
            {"status": SubSessionStatus.COMPLETED, "result": "found JWT auth"},
        )

        result = json.loads(
            await dispatcher.dispatch("sub_session_get_result", {"session_id": session_id}),
        )
        assert result["status"] == "completed"
        assert result["result"] == "found JWT auth"
        assert result["error"] == ""

    async def test_get_result_not_found(self) -> None:
        store = InMemorySubSessionStore()
        dispatcher = SubSessionToolDispatcher(store, "run-1")

        result = json.loads(
            await dispatcher.dispatch("sub_session_get_result", {"session_id": "missing"}),
        )
        assert "error" in result

    async def test_unknown_tool(self) -> None:
        store = InMemorySubSessionStore()
        dispatcher = SubSessionToolDispatcher(store, "run-1")

        result = json.loads(
            await dispatcher.dispatch("sub_session_unknown", {}),
        )
        assert "error" in result
        assert "Unknown" in result["error"]
