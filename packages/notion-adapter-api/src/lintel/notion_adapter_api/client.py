"""Notion REST API client wrapper."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

_NOTION_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


class NotionClient:
    """Thin wrapper around the Notion REST API."""

    def __init__(self, api_key: str, *, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }

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

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{_NOTION_API_BASE}/databases/{database_id}/query",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]

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
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{_NOTION_API_BASE}/pages",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]

    async def update_page(
        self,
        page_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Update properties on an existing Notion page."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.patch(
                f"{_NOTION_API_BASE}/pages/{page_id}",
                headers=self._headers(),
                json={"properties": properties},
            )
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]

    async def get_page(self, page_id: str) -> dict[str, Any]:
        """Retrieve a single Notion page by ID."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{_NOTION_API_BASE}/pages/{page_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
