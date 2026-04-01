"""Unit tests for hook types (HookPreResponse, HookType)."""

from __future__ import annotations

from lintel.domain.hooks import HookPreResponse
from lintel.domain.types import HookType


class TestHookType:
    """Tests for HookType enum."""

    def test_pre_value(self) -> None:
        assert HookType.PRE == "pre"

    def test_post_value(self) -> None:
        assert HookType.POST == "post"

    def test_scheduled_value(self) -> None:
        assert HookType.SCHEDULED == "scheduled"

    def test_from_string(self) -> None:
        assert HookType("pre") == HookType.PRE
        assert HookType("post") == HookType.POST


class TestHookPreResponse:
    """Tests for HookPreResponse."""

    def test_default_allows(self) -> None:
        response = HookPreResponse()
        assert response.allow is True
        assert response.modified_payload is None

    def test_block_response(self) -> None:
        response = HookPreResponse(allow=False)
        assert response.allow is False

    def test_modified_payload(self) -> None:
        payload = {"key": "value"}
        response = HookPreResponse(allow=True, modified_payload=payload)
        assert response.modified_payload == {"key": "value"}

    def test_frozen(self) -> None:
        response = HookPreResponse()
        try:
            response.allow = False  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass

    def test_max_chain_depth_default(self) -> None:
        """Trigger.max_chain_depth defaults to 5."""
        from lintel.domain.types import Trigger, TriggerType

        trigger = Trigger(
            trigger_id="t1",
            project_id="p1",
            trigger_type=TriggerType.WEBHOOK,
            name="test",
        )
        assert trigger.max_chain_depth == 5
