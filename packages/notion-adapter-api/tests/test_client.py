"""Tests for NotionClient with recorded response fixtures."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from lintel.notion_adapter_api.client import NotionAPIError, NotionClient

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# Recorded response fixtures — mirrors real Notion API shape
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
    "results": [{"object": "page", "id": "page-001"}],
    "has_more": True,
    "next_cursor": "cursor-abc",
}

QUERY_DB_PAGE2: dict[str, Any] = {
    "object": "list",
    "results": [{"object": "page", "id": "page-002"}],
    "has_more": False,
    "next_cursor": None,
}

GET_DB_RESPONSE: dict[str, Any] = {
    "object": "database",
    "id": "db-123",
    "title": [{"text": {"content": "Sprint Board"}}],
    "properties": {
        "Name": {"id": "title", "type": "title"},
        "Status": {"id": "status", "type": "select"},
    },
}

CREATE_PAGE_RESPONSE: dict[str, Any] = {
    "object": "page",
    "id": "page-new",
    "properties": {
        "Name": {"title": [{"text": {"content": "New task"}}]},
    },
}

GET_PAGE_RESPONSE: dict[str, Any] = {
    "object": "page",
    "id": "page-001",
    "archived": False,
    "properties": {
        "Name": {"title": [{"text": {"content": "Fix login bug"}}]},
    },
}

UPDATE_PAGE_RESPONSE: dict[str, Any] = {
    "object": "page",
    "id": "page-001",
    "properties": {
        "Status": {"select": {"name": "Done"}},
    },
}

ARCHIVE_PAGE_RESPONSE: dict[str, Any] = {
    "object": "page",
    "id": "page-001",
    "archived": True,
}

SEARCH_RESPONSE: dict[str, Any] = {
    "object": "list",
    "results": [
        {"object": "database", "id": "db-123"},
    ],
    "has_more": False,
    "next_cursor": None,
}

ERROR_404_RESPONSE: dict[str, Any] = {
    "object": "error",
    "status": 404,
    "code": "object_not_found",
    "message": "Could not find page with ID: page-missing.",
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
    """Build a synthetic httpx.Response from a dict."""
    return httpx.Response(
        status_code=status,
        json=data,
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "https://api.notion.com/v1/test"),
    )


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> NotionClient:
    """Create a NotionClient with a mock transport."""
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
# Tests
# ---------------------------------------------------------------------------


class TestNotionClientLifecycle:
    async def test_async_context_manager(self) -> None:
        async with NotionClient(api_key="ntn_test") as client:
            assert client._http is not None
        assert client._http.is_closed

    async def test_aclose(self) -> None:
        client = NotionClient(api_key="ntn_test")
        assert not client._http.is_closed
        await client.aclose()
        assert client._http.is_closed


class TestQueryDatabase:
    async def test_query_database(self) -> None:
        client = _make_client(lambda _req: _json_response(QUERY_DB_RESPONSE))
        result = await client.query_database("db-123")
        assert len(result["results"]) == 2
        assert result["has_more"] is False
        await client.aclose()

    async def test_query_database_with_filter(self) -> None:
        requests_seen: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            requests_seen.append(req)
            return _json_response(QUERY_DB_RESPONSE)

        client = _make_client(handler)
        filter_obj = {"property": "Status", "select": {"equals": "Open"}}
        await client.query_database("db-123", filter_obj=filter_obj, page_size=50)

        body = json.loads(requests_seen[0].content)
        assert body["filter"] == filter_obj
        assert body["page_size"] == 50
        await client.aclose()

    async def test_query_database_all_paginates(self) -> None:
        call_count = 0

        def handler(_req: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _json_response(QUERY_DB_PAGE1)
            return _json_response(QUERY_DB_PAGE2)

        client = _make_client(handler)
        pages = await client.query_database_all("db-123")
        assert len(pages) == 2
        assert pages[0]["id"] == "page-001"
        assert pages[1]["id"] == "page-002"
        assert call_count == 2
        await client.aclose()


class TestGetDatabase:
    async def test_get_database(self) -> None:
        client = _make_client(lambda _req: _json_response(GET_DB_RESPONSE))
        result = await client.get_database("db-123")
        assert result["object"] == "database"
        assert result["id"] == "db-123"
        await client.aclose()


class TestPages:
    async def test_create_page(self) -> None:
        requests_seen: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            requests_seen.append(req)
            return _json_response(CREATE_PAGE_RESPONSE)

        client = _make_client(handler)
        props = {"Name": {"title": [{"text": {"content": "New task"}}]}}
        result = await client.create_page("db-123", props)
        assert result["id"] == "page-new"

        body = json.loads(requests_seen[0].content)
        assert body["parent"]["database_id"] == "db-123"
        assert body["properties"] == props
        await client.aclose()

    async def test_get_page(self) -> None:
        client = _make_client(lambda _req: _json_response(GET_PAGE_RESPONSE))
        result = await client.get_page("page-001")
        assert result["id"] == "page-001"
        assert result["archived"] is False
        await client.aclose()

    async def test_update_page(self) -> None:
        client = _make_client(lambda _req: _json_response(UPDATE_PAGE_RESPONSE))
        result = await client.update_page(
            "page-001",
            {"Status": {"select": {"name": "Done"}}},
        )
        assert result["properties"]["Status"]["select"]["name"] == "Done"
        await client.aclose()

    async def test_archive_page(self) -> None:
        requests_seen: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            requests_seen.append(req)
            return _json_response(ARCHIVE_PAGE_RESPONSE)

        client = _make_client(handler)
        result = await client.archive_page("page-001")
        assert result["archived"] is True

        body = json.loads(requests_seen[0].content)
        assert body["archived"] is True
        await client.aclose()


class TestSearch:
    async def test_search(self) -> None:
        client = _make_client(lambda _req: _json_response(SEARCH_RESPONSE))
        result = await client.search("Sprint", filter_type="database")
        assert len(result["results"]) == 1
        assert result["results"][0]["object"] == "database"
        await client.aclose()

    async def test_search_sends_filter(self) -> None:
        requests_seen: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            requests_seen.append(req)
            return _json_response(SEARCH_RESPONSE)

        client = _make_client(handler)
        await client.search("Board", filter_type="database", page_size=10)

        body = json.loads(requests_seen[0].content)
        assert body["query"] == "Board"
        assert body["filter"] == {"value": "database", "property": "object"}
        assert body["page_size"] == 10
        await client.aclose()


class TestErrorHandling:
    async def test_404_raises_notion_api_error(self) -> None:
        client = _make_client(
            lambda _req: _json_response(ERROR_404_RESPONSE, status=404),
        )
        with pytest.raises(NotionAPIError) as exc_info:
            await client.get_page("page-missing")
        assert exc_info.value.status_code == 404
        assert exc_info.value.code == "object_not_found"
        assert "page-missing" in str(exc_info.value)
        await client.aclose()

    async def test_401_raises_notion_api_error(self) -> None:
        client = _make_client(
            lambda _req: _json_response(ERROR_401_RESPONSE, status=401),
        )
        with pytest.raises(NotionAPIError) as exc_info:
            await client.query_database("db-123")
        assert exc_info.value.status_code == 401
        assert exc_info.value.code == "unauthorized"
        await client.aclose()

    async def test_non_json_error(self) -> None:
        client = _make_client(
            lambda _req: httpx.Response(
                status_code=500,
                text="Internal Server Error",
                headers={"content-type": "text/plain"},
                request=httpx.Request("GET", "https://api.notion.com/v1/test"),
            ),
        )
        with pytest.raises(NotionAPIError) as exc_info:
            await client.get_page("page-001")
        assert exc_info.value.status_code == 500
        assert exc_info.value.code == "unknown"
        await client.aclose()


class TestAuthHeaders:
    async def test_headers_sent_with_request(self) -> None:
        requests_seen: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            requests_seen.append(req)
            return _json_response(GET_PAGE_RESPONSE)

        client = _make_client(handler)
        await client.get_page("page-001")
        assert requests_seen[0].headers["authorization"] == "Bearer ntn_test"
        assert requests_seen[0].headers["notion-version"] == "2022-06-28"
        await client.aclose()
