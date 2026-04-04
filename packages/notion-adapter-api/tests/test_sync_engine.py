"""Tests for the sync engine."""

from lintel.notion_adapter_api.sync_engine import (
    _notion_page_to_work_item,
    _work_item_to_notion_properties,
)


class TestPropertyConversion:
    def test_work_item_to_notion_properties(self) -> None:
        item = {
            "work_item_id": "wi-1",
            "title": "Fix bug",
            "status": "open",
            "description": "A bug to fix",
        }
        props = _work_item_to_notion_properties(item)
        assert props["Name"]["title"][0]["text"]["content"] == "Fix bug"
        assert props["Status"]["select"]["name"] == "open"
        assert props["Lintel ID"]["rich_text"][0]["text"]["content"] == "wi-1"

    def test_notion_page_to_work_item(self) -> None:
        page = {
            "id": "page-1",
            "properties": {
                "Name": {"title": [{"text": {"content": "Task A"}}]},
                "Status": {"select": {"name": "done"}},
                "Description": {"rich_text": [{"text": {"content": "desc"}}]},
                "Lintel ID": {"rich_text": [{"text": {"content": "wi-99"}}]},
            },
        }
        result = _notion_page_to_work_item(page)
        assert result["notion_page_id"] == "page-1"
        assert result["title"] == "Task A"
        assert result["status"] == "done"
        assert result["lintel_id"] == "wi-99"

    def test_notion_page_to_work_item_empty_properties(self) -> None:
        page = {"id": "page-2", "properties": {}}
        result = _notion_page_to_work_item(page)
        assert result["title"] == ""
        assert result["status"] == ""
