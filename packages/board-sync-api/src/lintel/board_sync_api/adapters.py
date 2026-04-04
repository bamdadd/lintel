"""External provider adapters for Jira and Notion.

These adapters define the interface and provide stub implementations.
Real API clients depend on the Jira adapter (68fc091c) and Notion adapter (2e601cb4)
work items being completed first.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import Any

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
# Notion adapter (stub)
# ---------------------------------------------------------------------------


class NotionAdapter(SyncAdapter):
    """Stub Notion adapter — returns empty results until real client is wired."""

    async def pull_items(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        logger.info("notion_pull_stub: board=%s", config.get("board_id"))
        return []

    async def push_item(self, config: dict[str, Any], item: dict[str, Any]) -> str:
        logger.info("notion_push_stub: item=%s", item.get("work_item_id"))
        return item.get("external_id", "")

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
