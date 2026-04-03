"""Tests for sub-session tool schemas and dispatcher."""

from __future__ import annotations

import json

import pytest

from lintel.agents.sub_session_tools import (
    SubSessionToolDispatcher,
    is_sub_session_tool,
    sub_session_tool_schemas,
)
from lintel.agents.sub_sessions import SubSessionManager


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
        assert is_sub_session_tool("sub_session_spawn")
        assert is_sub_session_tool("sub_session_check_status")
        assert not is_sub_session_tool("sandbox_read_file")
        assert not is_sub_session_tool("random_tool")


class TestSubSessionToolDispatcher:
    @pytest.fixture()
    def manager(self) -> SubSessionManager:
        return SubSessionManager(max_sub_sessions=3)

    @pytest.fixture()
    def dispatcher(self, manager: SubSessionManager) -> SubSessionToolDispatcher:
        return SubSessionToolDispatcher(manager, parent_session_id="parent-1")

    async def test_spawn(self, dispatcher: SubSessionToolDispatcher) -> None:
        result = await dispatcher.dispatch(
            "sub_session_spawn", {"repo": "org/repo", "prompt": "find auth patterns"}
        )
        data = json.loads(result)
        assert "session_id" in data
        assert data["status"] == "pending"

    async def test_spawn_missing_fields(self, dispatcher: SubSessionToolDispatcher) -> None:
        result = await dispatcher.dispatch("sub_session_spawn", {"repo": "org/repo"})
        data = json.loads(result)
        assert "error" in data

    async def test_spawn_exceeds_max(self, manager: SubSessionManager) -> None:
        dispatcher = SubSessionToolDispatcher(manager, parent_session_id="parent-1")
        # Use max_sub_sessions=3
        for i in range(3):
            await dispatcher.dispatch("sub_session_spawn", {"repo": f"org/r{i}", "prompt": "p"})
        result = await dispatcher.dispatch(
            "sub_session_spawn", {"repo": "org/overflow", "prompt": "p"}
        )
        data = json.loads(result)
        assert "error" in data
        assert "Max sub-sessions" in data["error"]

    async def test_check_status(
        self, dispatcher: SubSessionToolDispatcher, manager: SubSessionManager
    ) -> None:
        spawn_result = json.loads(
            await dispatcher.dispatch("sub_session_spawn", {"repo": "org/repo", "prompt": "p"})
        )
        sid = spawn_result["session_id"]
        result = await dispatcher.dispatch("sub_session_check_status", {"session_id": sid})
        data = json.loads(result)
        assert data["status"] == "pending"

    async def test_check_status_not_found(self, dispatcher: SubSessionToolDispatcher) -> None:
        result = await dispatcher.dispatch(
            "sub_session_check_status", {"session_id": "nonexistent"}
        )
        data = json.loads(result)
        assert "error" in data

    async def test_get_result_completed(
        self, dispatcher: SubSessionToolDispatcher, manager: SubSessionManager
    ) -> None:
        spawn_result = json.loads(
            await dispatcher.dispatch("sub_session_spawn", {"repo": "org/repo", "prompt": "p"})
        )
        sid = spawn_result["session_id"]
        manager.mark_running(sid)
        manager.mark_completed(sid, "JWT auth uses RS256 keys")
        result = await dispatcher.dispatch("sub_session_get_result", {"session_id": sid})
        data = json.loads(result)
        assert data["result"] == "JWT auth uses RS256 keys"

    async def test_get_result_failed(
        self, dispatcher: SubSessionToolDispatcher, manager: SubSessionManager
    ) -> None:
        spawn_result = json.loads(
            await dispatcher.dispatch("sub_session_spawn", {"repo": "org/repo", "prompt": "p"})
        )
        sid = spawn_result["session_id"]
        manager.mark_running(sid)
        manager.mark_failed(sid, "sandbox timeout")
        result = await dispatcher.dispatch("sub_session_get_result", {"session_id": sid})
        data = json.loads(result)
        assert data["error"] == "sandbox timeout"

    async def test_get_result_not_complete(self, dispatcher: SubSessionToolDispatcher) -> None:
        spawn_result = json.loads(
            await dispatcher.dispatch("sub_session_spawn", {"repo": "org/repo", "prompt": "p"})
        )
        sid = spawn_result["session_id"]
        result = await dispatcher.dispatch("sub_session_get_result", {"session_id": sid})
        data = json.loads(result)
        assert data["status"] == "pending"
        assert "not yet completed" in data["message"]

    async def test_unknown_tool(self, dispatcher: SubSessionToolDispatcher) -> None:
        result = await dispatcher.dispatch("sub_session_unknown", {})
        data = json.loads(result)
        assert "error" in data
