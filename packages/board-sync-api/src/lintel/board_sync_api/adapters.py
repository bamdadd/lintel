"""External provider adapters for Jira and Notion.

Adapters translate between Lintel work-item dicts and external system API calls.
The Notion adapter delegates to :class:`NotionClient` from ``lintel-notion-adapter-api``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import Any

from lintel.notion_adapter_api.client import NotionClient
from lintel.notion_adapter_api.sync_engine import (
    _notion_page_to_work_item,
    _work_item_to_notion_properties,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status mapping tables
# ---------------------------------------------------------------------------

JIRA_STATUS_TO_LINTEL: dict[str, str] = {
    "To Do": "open",
    "In Progress": "in_progress",
    "In Review": "review",
    "Done": "done",
    "Closed": "done",
}

LINTEL_STATUS_TO_JIRA: dict[str, str] = {
    "open": "To Do",
    "in_progress": "In Progress",
    "review": "In Review",
    "done": "Done",
}

NOTION_STATUS_TO_LINTEL: dict[str, str] = {
    "Not started": "open",
    "In progress": "in_progress",
    "Done": "done",
}

LINTEL_STATUS_TO_NOTION: dict[str, str] = {
    "open": "Not started",
    "in_progress": "In progress",
    "done": "Done",
}


# ---------------------------------------------------------------------------
# Abstract adapter
# ---------------------------------------------------------------------------


class SyncAdapter(ABC):
    """Base class for external board provider adapters."""

    @abstractmethod
    async def pull_items(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch items from the external system.

        Returns a list of dicts with keys: external_id, title, description, status, priority.
        """

    @abstractmethod
    async def push_item(self, config: dict[str, Any], item: dict[str, Any]) -> str:
        """Push/update an item in the external system.

        Returns the external_id of the created/updated item.
        """

    @abstractmethod
    def map_status_inbound(self, external_status: str) -> str:
        """Map external status → Lintel WorkItemStatus string."""

    @abstractmethod
    def map_status_outbound(self, lintel_status: str) -> str:
        """Map Lintel WorkItemStatus string → external status."""


# ---------------------------------------------------------------------------
# Jira adapter (stub)
# ---------------------------------------------------------------------------


class JiraAdapter(SyncAdapter):
    """Stub Jira adapter — returns empty results until real client is wired."""

    async def pull_items(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        logger.info("jira_pull_stub: board=%s", config.get("board_id"))
        return []

    async def push_item(self, config: dict[str, Any], item: dict[str, Any]) -> str:
        logger.info("jira_push_stub: item=%s", item.get("work_item_id"))
        return item.get("external_id", "")

    def map_status_inbound(self, external_status: str) -> str:
        return JIRA_STATUS_TO_LINTEL.get(external_status, "open")

    def map_status_outbound(self, lintel_status: str) -> str:
        return LINTEL_STATUS_TO_JIRA.get(lintel_status, "To Do")


# ---------------------------------------------------------------------------
# Notion adapter — wired to NotionClient
# ---------------------------------------------------------------------------


class NotionAdapter(SyncAdapter):
    """Notion adapter backed by :class:`NotionClient`."""

    async def _get_client(self, config: dict[str, Any]) -> NotionClient:
        """Build a :class:`NotionClient` from the sync config's API key."""
        api_key: str = config.get("api_key", "")
        if not api_key:
            msg = "Notion sync config is missing 'api_key'"
            raise ValueError(msg)
        return NotionClient(api_key=api_key)

    async def pull_items(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Query the Notion database and return normalised work-item dicts."""
        database_id: str = config.get("external_database_id", "")
        if not database_id:
            msg = "Notion sync config is missing 'external_database_id'"
            raise ValueError(msg)

        # Build an incremental filter when we have a last_synced timestamp
        filter_obj: dict[str, Any] | None = None
        last_synced = config.get("last_synced", "")
        if last_synced:
            filter_obj = {
                "timestamp": "last_edited_time",
                "last_edited_time": {"after": last_synced},
            }

        async with await self._get_client(config) as client:
            pages = await client.query_database_all(
                database_id,
                filter_obj=filter_obj,
            )

        items: list[dict[str, Any]] = []
        for page in pages:
            parsed = _notion_page_to_work_item(page)
            parsed["external_id"] = page["id"]
            parsed["status"] = self.map_status_inbound(parsed.get("status", ""))
            items.append(parsed)
        return items

    async def push_item(self, config: dict[str, Any], item: dict[str, Any]) -> str:
        """Create or update a Notion page for the given work item."""
        database_id: str = config.get("external_database_id", "")
        if not database_id:
            msg = "Notion sync config is missing 'external_database_id'"
            raise ValueError(msg)

        props = _work_item_to_notion_properties(item)
        external_id = item.get("external_id", "")

        async with await self._get_client(config) as client:
            if external_id:
                result = await client.update_page(external_id, props)
            else:
                result = await client.create_page(database_id, props)

        return result.get("id", external_id)

    def map_status_inbound(self, external_status: str) -> str:
        return NOTION_STATUS_TO_LINTEL.get(external_status, "open")

    def map_status_outbound(self, lintel_status: str) -> str:
        return LINTEL_STATUS_TO_NOTION.get(lintel_status, "Not started")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ADAPTERS: dict[str, type[SyncAdapter]] = {
    "jira": JiraAdapter,
    "notion": NotionAdapter,
}


def get_adapter(provider: str) -> SyncAdapter:
    """Return an adapter instance for the given provider name."""
    cls = ADAPTERS.get(provider)
    if cls is None:
        msg = f"Unknown sync provider: {provider}"
        raise ValueError(msg)
    return cls()
