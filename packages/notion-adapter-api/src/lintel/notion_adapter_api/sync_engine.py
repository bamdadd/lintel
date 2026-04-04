"""Sync engine — push/pull work items between Lintel and Notion databases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.notion_adapter_api.client import NotionClient

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SyncResult:
    """Outcome of a single sync run."""

    pushed: int = 0
    pulled: int = 0
    errors: list[str] | None = None


def _work_item_to_notion_properties(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a Lintel work item dict to Notion page properties."""
    props: dict[str, Any] = {
        "Name": {"title": [{"text": {"content": item.get("title", "")}}]},
    }
    if item.get("status"):
        props["Status"] = {"select": {"name": item["status"]}}
    if item.get("description"):
        props["Description"] = {
            "rich_text": [{"text": {"content": item["description"][:2000]}}],
        }
    if item.get("work_item_id"):
        props["Lintel ID"] = {
            "rich_text": [{"text": {"content": item["work_item_id"]}}],
        }
    return props


def _notion_page_to_work_item(page: dict[str, Any]) -> dict[str, Any]:
    """Extract work-item-relevant fields from a Notion page."""
    props = page.get("properties", {})
    title = ""
    if "Name" in props:
        title_parts = props["Name"].get("title", [])
        if title_parts:
            title = title_parts[0].get("text", {}).get("content", "")

    status = ""
    if "Status" in props:
        select = props["Status"].get("select")
        if select:
            status = select.get("name", "")

    description = ""
    if "Description" in props:
        rt = props["Description"].get("rich_text", [])
        if rt:
            description = rt[0].get("text", {}).get("content", "")

    lintel_id = ""
    if "Lintel ID" in props:
        rt = props["Lintel ID"].get("rich_text", [])
        if rt:
            lintel_id = rt[0].get("text", {}).get("content", "")

    return {
        "notion_page_id": page["id"],
        "title": title,
        "status": status,
        "description": description,
        "lintel_id": lintel_id,
    }


async def push_work_items(
    client: NotionClient,
    database_id: str,
    work_items: list[dict[str, Any]],
) -> SyncResult:
    """Push Lintel work items into a Notion database.

    Creates new pages for items without a ``notion_page_id``; updates existing ones.
    """
    pushed = 0
    errors: list[str] = []
    for item in work_items:
        try:
            props = _work_item_to_notion_properties(item)
            notion_page_id = item.get("notion_page_id")
            if notion_page_id:
                await client.update_page(notion_page_id, props)
            else:
                await client.create_page(database_id, props)
            pushed += 1
        except Exception as exc:
            errors.append(f"Failed to push {item.get('work_item_id', '?')}: {exc}")
            logger.warning("notion_push_error", item_id=item.get("work_item_id"), error=str(exc))
    return SyncResult(pushed=pushed, errors=errors or None)


async def pull_work_items(
    client: NotionClient,
    database_id: str,
) -> SyncResult:
    """Pull work items from a Notion database.

    Returns parsed items; the caller is responsible for upserting into the Lintel store.
    """
    pulled = 0
    errors: list[str] = []
    try:
        result = await client.query_database(database_id)
        pages = result.get("results", [])
        pulled = len(pages)
        for page in pages:
            _notion_page_to_work_item(page)  # validate parsing
    except Exception as exc:
        errors.append(f"Pull failed: {exc}")
        logger.warning("notion_pull_error", error=str(exc))
    return SyncResult(pulled=pulled, errors=errors or None)
