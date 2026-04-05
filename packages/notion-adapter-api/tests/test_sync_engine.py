"""Tests for the sync engine."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx

from lintel.notion_adapter_api.client import NotionClient
from lintel.notion_adapter_api.sync_engine import (
    SyncResult,
    _notion_page_to_work_item,
    _work_item_to_notion_properties,
    pull_work_items,
    push_work_items,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# Recorded response fixtures
# ---------------------------------------------------------------------------

QUERY_DB_RESPONSE: dict[str, Any] = {
    "object": "list",
    "results": [
        {
            "object": "page",
            "id": "page-001",
            "properties": {
                "Name": {"title": [{"text": {"content": "Fix login bug"}}]},
                "Status": {"select": {"name": "In Progress"}},
                "Description": {"rich_text": [{"text": {"content": "Login is broken"}}]},
                "Lintel ID": {"rich_text": [{"text": {"content": "wi-100"}}]},
            },
        },
        {
            "object": "page",
            "id": "page-002",
            "properties": {
                "Name": {"title": [{"text": {"content": "Add dark mode"}}]},
                "Status": {"select": {"name": "Open"}},
            },
        },
    ],
    "has_more": False,
    "next_cursor": None,
}

QUERY_DB_PAGE1: dict[str, Any] = {
    "object": "list",
    "results": [
        {
            "object": "page",
            "id": "page-001",
            "properties": {
                "Name": {"title": [{"text": {"content": "Item 1"}}]},
                "Status": {"select": {"name": "Open"}},
            },
        },
    ],
    "has_more": True,
    "next_cursor": "cursor-abc",
}

QUERY_DB_PAGE2: dict[str, Any] = {
    "object": "list",
    "results": [
        {
            "object": "page",
            "id": "page-002",
            "properties": {
                "Name": {"title": [{"text": {"content": "Item 2"}}]},
                "Status": {"select": {"name": "Done"}},
            },
        },
    ],
    "has_more": False,
    "next_cursor": None,
}

CREATE_PAGE_RESPONSE: dict[str, Any] = {
    "object": "page",
    "id": "page-new",
    "properties": {
        "Name": {"title": [{"text": {"content": "New task"}}]},
    },
}

UPDATE_PAGE_RESPONSE: dict[str, Any] = {
    "object": "page",
    "id": "page-001",
    "properties": {
        "Status": {"select": {"name": "Done"}},
    },
}

ERROR_401_RESPONSE: dict[str, Any] = {
    "object": "error",
    "status": 401,
    "code": "unauthorized",
    "message": "API token is invalid.",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_response(data: dict[str, Any], status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=data,
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "https://api.notion.com/v1/test"),
    )


def _make_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> NotionClient:
    transport = httpx.MockTransport(handler)
    client = NotionClient(api_key="ntn_test")
    client._http = httpx.AsyncClient(
        base_url="https://api.notion.com/v1",
        transport=transport,
        headers={
            "Authorization": "Bearer ntn_test",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
    )
    return client


# ---------------------------------------------------------------------------
# Property conversion tests
# ---------------------------------------------------------------------------


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

    def test_description_truncated_to_2000(self) -> None:
        item = {"title": "T", "description": "x" * 3000}
        props = _work_item_to_notion_properties(item)
        content = props["Description"]["rich_text"][0]["text"]["content"]
        assert len(content) == 2000


# ---------------------------------------------------------------------------
# Push tests
# ---------------------------------------------------------------------------


class TestPushWorkItems:
    async def test_push_creates_new_pages(self) -> None:
        requests_seen: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            requests_seen.append(req)
            return _json_response(CREATE_PAGE_RESPONSE)

        client = _make_client(handler)
        items = [{"title": "New task", "status": "open"}]
        result = await push_work_items(client, "db-123", items)
        assert result.pushed == 1
        assert not result.errors

        body = json.loads(requests_seen[0].content)
        assert body["parent"]["database_id"] == "db-123"
        await client.aclose()

    async def test_push_updates_existing_pages(self) -> None:
        requests_seen: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            requests_seen.append(req)
            return _json_response(UPDATE_PAGE_RESPONSE)

        client = _make_client(handler)
        items = [{"title": "Updated", "status": "done", "notion_page_id": "page-001"}]
        result = await push_work_items(client, "db-123", items)
        assert result.pushed == 1
        assert "page-001" in str(requests_seen[0].url)
        await client.aclose()

    async def test_push_handles_errors_gracefully(self) -> None:
        client = _make_client(
            lambda _req: _json_response(ERROR_401_RESPONSE, status=401),
        )
        items = [{"title": "Will fail", "work_item_id": "wi-fail"}]
        result = await push_work_items(client, "db-123", items)
        assert result.pushed == 0
        assert len(result.errors) == 1
        assert "wi-fail" in result.errors[0]
        await client.aclose()

    async def test_push_mixed_create_and_update(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if "pages/" in str(req.url) and req.method == "PATCH":
                return _json_response(UPDATE_PAGE_RESPONSE)
            return _json_response(CREATE_PAGE_RESPONSE)

        client = _make_client(handler)
        items = [
            {"title": "New", "status": "open"},
            {"title": "Existing", "status": "done", "notion_page_id": "page-001"},
        ]
        result = await push_work_items(client, "db-123", items)
        assert result.pushed == 2
        await client.aclose()


# ---------------------------------------------------------------------------
# Pull tests
# ---------------------------------------------------------------------------


class TestPullWorkItems:
    async def test_pull_returns_parsed_items(self) -> None:
        client = _make_client(lambda _req: _json_response(QUERY_DB_RESPONSE))
        result = await pull_work_items(client, "db-123")
        assert result.pulled == 2
        assert len(result.items) == 2
        assert result.items[0]["notion_page_id"] == "page-001"
        assert result.items[0]["title"] == "Fix login bug"
        assert result.items[0]["description"] == "Login is broken"
        assert result.items[0]["lintel_id"] == "wi-100"
        assert result.items[1]["title"] == "Add dark mode"
        await client.aclose()

    async def test_pull_paginates(self) -> None:
        call_count = 0

        def handler(_req: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _json_response(QUERY_DB_PAGE1)
            return _json_response(QUERY_DB_PAGE2)

        client = _make_client(handler)
        result = await pull_work_items(client, "db-123")
        assert result.pulled == 2
        assert call_count == 2
        assert result.items[0]["title"] == "Item 1"
        assert result.items[1]["title"] == "Item 2"
        await client.aclose()

    async def test_pull_incremental_sends_filter(self) -> None:
        requests_seen: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            requests_seen.append(req)
            return _json_response(QUERY_DB_RESPONSE)

        client = _make_client(handler)
        await pull_work_items(client, "db-123", last_synced="2025-01-01T00:00:00+00:00")
        body = json.loads(requests_seen[0].content)
        assert body["filter"]["timestamp"] == "last_edited_time"
        assert body["filter"]["last_edited_time"]["after"] == "2025-01-01T00:00:00+00:00"
        await client.aclose()

    async def test_pull_handles_api_error(self) -> None:
        client = _make_client(
            lambda _req: _json_response(ERROR_401_RESPONSE, status=401),
        )
        result = await pull_work_items(client, "db-123")
        assert result.pulled == 0
        assert len(result.errors) == 1
        assert "Pull failed" in result.errors[0]
        await client.aclose()

    async def test_pull_empty_database(self) -> None:
        empty = {"object": "list", "results": [], "has_more": False, "next_cursor": None}
        client = _make_client(lambda _req: _json_response(empty))
        result = await pull_work_items(client, "db-123")
        assert result.pulled == 0
        assert result.items == []
        assert not result.errors
        await client.aclose()


# ---------------------------------------------------------------------------
# SyncResult tests
# ---------------------------------------------------------------------------


class TestSyncResult:
    def test_defaults(self) -> None:
        r = SyncResult()
        assert r.pushed == 0
        assert r.pulled == 0
        assert r.items == []
        assert r.errors == []
