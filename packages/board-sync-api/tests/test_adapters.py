"""Tests for sync adapters and status mapping."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

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


# ---------------------------------------------------------------------------
# Notion adapter — uses mocked NotionClient
# ---------------------------------------------------------------------------

NOTION_CONFIG: dict[str, Any] = {
    "api_key": "ntn_test",
    "external_database_id": "db-abc",
    "board_id": "b1",
    "last_synced": "",
}

NOTION_PAGES: list[dict[str, Any]] = [
    {
        "id": "page-001",
        "properties": {
            "Name": {"title": [{"text": {"content": "Fix login bug"}}]},
            "Status": {"select": {"name": "In progress"}},
            "Description": {"rich_text": [{"text": {"content": "Bug desc"}}]},
        },
    },
    {
        "id": "page-002",
        "properties": {
            "Name": {"title": [{"text": {"content": "Add dark mode"}}]},
            "Status": {"select": {"name": "Not started"}},
        },
    },
]


def _mock_notion_client() -> AsyncMock:
    """Build a mock NotionClient that returns NOTION_PAGES."""
    client = AsyncMock()
    client.query_database_all = AsyncMock(return_value=NOTION_PAGES)
    client.create_page = AsyncMock(return_value={"id": "page-new"})
    client.update_page = AsyncMock(return_value={"id": "page-001"})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


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

    async def test_pull_items_queries_notion(self) -> None:
        adapter = NotionAdapter()
        mock_client = _mock_notion_client()
        with patch.object(adapter, "_get_client", return_value=mock_client):
            items = await adapter.pull_items(NOTION_CONFIG)

        assert len(items) == 2
        assert items[0]["external_id"] == "page-001"
        assert items[0]["title"] == "Fix login bug"
        assert items[0]["status"] == "in_progress"  # mapped from "In progress"
        assert items[1]["status"] == "open"  # mapped from "Not started"
        mock_client.query_database_all.assert_called_once_with(
            "db-abc",
            filter_obj=None,
        )

    async def test_pull_items_incremental_filter(self) -> None:
        adapter = NotionAdapter()
        mock_client = _mock_notion_client()
        config = {**NOTION_CONFIG, "last_synced": "2025-01-01T00:00:00+00:00"}
        with patch.object(adapter, "_get_client", return_value=mock_client):
            await adapter.pull_items(config)

        mock_client.query_database_all.assert_called_once_with(
            "db-abc",
            filter_obj={
                "timestamp": "last_edited_time",
                "last_edited_time": {"after": "2025-01-01T00:00:00+00:00"},
            },
        )

    async def test_pull_items_missing_api_key_raises(self) -> None:
        adapter = NotionAdapter()
        with pytest.raises(ValueError, match="missing 'api_key'"):
            await adapter.pull_items({"external_database_id": "db-1"})

    async def test_pull_items_missing_database_id_raises(self) -> None:
        adapter = NotionAdapter()
        with pytest.raises(ValueError, match="missing 'external_database_id'"):
            await adapter.pull_items({"api_key": "ntn_test"})

    async def test_push_item_creates_new_page(self) -> None:
        adapter = NotionAdapter()
        mock_client = _mock_notion_client()
        with patch.object(adapter, "_get_client", return_value=mock_client):
            ext_id = await adapter.push_item(
                NOTION_CONFIG,
                {"title": "New task", "status": "Not started", "work_item_id": "wi-1"},
            )

        assert ext_id == "page-new"
        mock_client.create_page.assert_called_once()

    async def test_push_item_updates_existing_page(self) -> None:
        adapter = NotionAdapter()
        mock_client = _mock_notion_client()
        with patch.object(adapter, "_get_client", return_value=mock_client):
            ext_id = await adapter.push_item(
                NOTION_CONFIG,
                {"title": "Updated", "external_id": "page-001", "work_item_id": "wi-1"},
            )

        assert ext_id == "page-001"
        mock_client.update_page.assert_called_once()
        mock_client.create_page.assert_not_called()

    async def test_push_item_missing_database_id_raises(self) -> None:
        adapter = NotionAdapter()
        with pytest.raises(ValueError, match="missing 'external_database_id'"):
            await adapter.push_item({"api_key": "ntn_test"}, {"title": "x"})


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
