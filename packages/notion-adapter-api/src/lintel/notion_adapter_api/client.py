"""Notion REST API client wrapper."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

_NOTION_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


class NotionAPIError(Exception):
    """Raised when the Notion API returns a non-2xx response."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(f"Notion API error {status_code} ({code}): {message}")


class NotionClient:
    """Thin wrapper around the Notion REST API.

    Uses a shared ``httpx.AsyncClient`` for connection pooling.  Call
    :meth:`aclose` (or use as an async context manager) to release resources.
    """

    def __init__(self, api_key: str, *, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._http = httpx.AsyncClient(
            base_url=_NOTION_API_BASE,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": _NOTION_VERSION,
                "Content-Type": "application/json",
            },
        )

    # -- lifecycle ------------------------------------------------------------

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> NotionClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    # -- helpers --------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resp = await self._http.request(method, path, json=json)
        if resp.status_code >= 400:
            body: dict[str, Any] = {}
            content_type = resp.headers.get("content-type", "")
            if content_type.startswith("application/json"):
                body = resp.json()
            raise NotionAPIError(
                status_code=resp.status_code,
                code=body.get("code", "unknown"),
                message=body.get("message", resp.text),
            )
        return resp.json()  # type: ignore[no-any-return]

    # -- databases ------------------------------------------------------------

    async def get_database(self, database_id: str) -> dict[str, Any]:
        """Retrieve a Notion database schema by ID."""
        return await self._request("GET", f"/databases/{database_id}")

    async def query_database(
        self,
        database_id: str,
        *,
        filter_obj: dict[str, Any] | None = None,
        start_cursor: str | None = None,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """Query a Notion database and return the raw response."""
        body: dict[str, Any] = {"page_size": page_size}
        if filter_obj is not None:
            body["filter"] = filter_obj
        if start_cursor is not None:
            body["start_cursor"] = start_cursor
        return await self._request(
            "POST",
            f"/databases/{database_id}/query",
            json=body,
        )

    async def query_database_all(
        self,
        database_id: str,
        *,
        filter_obj: dict[str, Any] | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Query a Notion database, auto-paginating through all results."""
        pages: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            result = await self.query_database(
                database_id,
                filter_obj=filter_obj,
                start_cursor=cursor,
                page_size=page_size,
            )
            pages.extend(result.get("results", []))
            if not result.get("has_more"):
                break
            cursor = result.get("next_cursor")
        return pages

    # -- pages ----------------------------------------------------------------

    async def create_page(
        self,
        database_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a page (row) in a Notion database."""
        body: dict[str, Any] = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }
        return await self._request("POST", "/pages", json=body)

    async def get_page(self, page_id: str) -> dict[str, Any]:
        """Retrieve a single Notion page by ID."""
        return await self._request("GET", f"/pages/{page_id}")

    async def update_page(
        self,
        page_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Update properties on an existing Notion page."""
        return await self._request(
            "PATCH",
            f"/pages/{page_id}",
            json={"properties": properties},
        )

    async def archive_page(self, page_id: str) -> dict[str, Any]:
        """Archive (soft-delete) a Notion page."""
        return await self._request(
            "PATCH",
            f"/pages/{page_id}",
            json={"archived": True},
        )

    # -- search ---------------------------------------------------------------

    async def search(
        self,
        query: str = "",
        *,
        filter_type: str | None = None,
        start_cursor: str | None = None,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """Search across the workspace for pages or databases."""
        body: dict[str, Any] = {"page_size": page_size}
        if query:
            body["query"] = query
        if filter_type:
            body["filter"] = {"value": filter_type, "property": "object"}
        if start_cursor:
            body["start_cursor"] = start_cursor
        return await self._request("POST", "/search", json=body)
