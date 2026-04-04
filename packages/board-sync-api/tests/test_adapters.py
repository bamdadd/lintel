"""Tests for sync adapters and status mapping."""

from __future__ import annotations

import pytest

from lintel.board_sync_api.adapters import (
    JiraAdapter,
    NotionAdapter,
    get_adapter,
)


class TestJiraAdapter:
    def test_map_status_inbound(self) -> None:
        adapter = JiraAdapter()
        assert adapter.map_status_inbound("To Do") == "open"
        assert adapter.map_status_inbound("In Progress") == "in_progress"
        assert adapter.map_status_inbound("Done") == "done"
        assert adapter.map_status_inbound("Unknown") == "open"

    def test_map_status_outbound(self) -> None:
        adapter = JiraAdapter()
        assert adapter.map_status_outbound("open") == "To Do"
        assert adapter.map_status_outbound("in_progress") == "In Progress"
        assert adapter.map_status_outbound("done") == "Done"
        assert adapter.map_status_outbound("unknown") == "To Do"

    async def test_pull_items_returns_empty(self) -> None:
        adapter = JiraAdapter()
        result = await adapter.pull_items({"board_id": "b1"})
        assert result == []

    async def test_push_item_returns_external_id(self) -> None:
        adapter = JiraAdapter()
        result = await adapter.push_item({}, {"external_id": "PROJ-1"})
        assert result == "PROJ-1"


class TestNotionAdapter:
    def test_map_status_inbound(self) -> None:
        adapter = NotionAdapter()
        assert adapter.map_status_inbound("Not started") == "open"
        assert adapter.map_status_inbound("In progress") == "in_progress"
        assert adapter.map_status_inbound("Done") == "done"

    def test_map_status_outbound(self) -> None:
        adapter = NotionAdapter()
        assert adapter.map_status_outbound("open") == "Not started"
        assert adapter.map_status_outbound("in_progress") == "In progress"


class TestAdapterRegistry:
    def test_get_jira_adapter(self) -> None:
        adapter = get_adapter("jira")
        assert isinstance(adapter, JiraAdapter)

    def test_get_notion_adapter(self) -> None:
        adapter = get_adapter("notion")
        assert isinstance(adapter, NotionAdapter)

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown sync provider"):
            get_adapter("trello")
