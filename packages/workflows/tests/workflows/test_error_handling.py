"""Tests for workflow node error handling helper."""

from __future__ import annotations

from lintel.workflows.nodes._error_handling import handle_node_error
import pytest


class TestHandleNodeError:
    """Tests for the standard node error handler."""

    @pytest.mark.asyncio
    async def test_sets_error_field(self) -> None:
        result = await handle_node_error({}, "implement", ValueError("boom"))
        assert result["error"] == "implement failed: boom"

    @pytest.mark.asyncio
    async def test_sets_phase_to_node_failed(self) -> None:
        result = await handle_node_error({}, "test", RuntimeError("oops"))
        assert result["current_phase"] == "test_failed"

    @pytest.mark.asyncio
    async def test_includes_node_name_in_error(self) -> None:
        result = await handle_node_error({}, "review", Exception("timeout"))
        assert result["error"].startswith("review failed:")

    @pytest.mark.asyncio
    async def test_agent_outputs_contain_error(self) -> None:
        result = await handle_node_error({}, "plan", Exception("bad"))
        outputs = result["agent_outputs"]
        assert len(outputs) == 1
        assert outputs[0]["node"] == "plan"
        assert outputs[0]["error"] == "bad"

    @pytest.mark.asyncio
    async def test_does_not_set_closed_phase(self) -> None:
        """Phase should not be 'closed' so retries are possible."""
        result = await handle_node_error({}, "setup", Exception("fail"))
        assert result["current_phase"] != "closed"
