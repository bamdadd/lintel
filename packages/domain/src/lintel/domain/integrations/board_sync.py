"""Domain model for syncing work items from external project management tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class ExternalBoardProvider(StrEnum):
    """Supported external board providers."""

    JIRA = "jira"
    NOTION = "notion"
    LINEAR = "linear"
    GITHUB_PROJECTS = "github_projects"


class SyncDirection(StrEnum):
    """Direction of synchronisation between Lintel and external board."""

    PULL = "pull"
    PUSH = "push"
    BIDIRECTIONAL = "bidirectional"


@dataclass(frozen=True)
class BoardSyncConfig:
    """Configuration for syncing a Lintel project with an external board."""

    config_id: str
    project_id: str
    provider: ExternalBoardProvider
    external_board_id: str
    sync_direction: SyncDirection = SyncDirection.PULL
    field_mapping: dict[str, str] = field(default_factory=dict)
    last_synced_at: datetime | None = None


@dataclass(frozen=True)
class ExternalWorkItem:
    """A work item fetched from an external board provider."""

    external_id: str
    provider: ExternalBoardProvider
    title: str
    description: str = ""
    status: str = ""
    assignee: str = ""
    labels: tuple[str, ...] = ()
    url: str = ""
    updated_at: datetime | None = None


@dataclass(frozen=True)
class SyncDiff:
    """Result of diffing local work items against external ones."""

    to_create: tuple[ExternalWorkItem, ...]
    to_update: tuple[ExternalWorkItem, ...]
    to_delete: tuple[str, ...]  # local IDs no longer present externally


# Default status mappings per provider
_STATUS_MAPS: dict[ExternalBoardProvider, dict[str, str]] = {
    ExternalBoardProvider.JIRA: {
        "to do": "open",
        "in progress": "in_progress",
        "in review": "in_review",
        "done": "closed",
    },
    ExternalBoardProvider.NOTION: {
        "not started": "open",
        "in progress": "in_progress",
        "done": "closed",
    },
    ExternalBoardProvider.LINEAR: {
        "backlog": "open",
        "todo": "open",
        "in progress": "in_progress",
        "in review": "in_review",
        "done": "closed",
        "canceled": "closed",
    },
    ExternalBoardProvider.GITHUB_PROJECTS: {
        "todo": "open",
        "in progress": "in_progress",
        "done": "closed",
    },
}


class BoardSyncEngine:
    """Domain logic for syncing work items from external boards.

    This is a pure domain service -- no actual API calls. Concrete provider
    adapters are expected to supply ``ExternalWorkItem`` lists.
    """

    def sync_pull(self, config: BoardSyncConfig) -> list[ExternalWorkItem]:
        """Return external work items that should be pulled.

        In production this would delegate to a provider adapter. Here we
        return an empty list as a no-op placeholder -- callers override
        with real adapter results.
        """
        _ = config
        return []

    def map_status(
        self,
        external_status: str,
        provider: ExternalBoardProvider,
    ) -> str:
        """Map an external status string to a Lintel WorkItemStatus value."""
        provider_map = _STATUS_MAPS.get(provider, {})
        return provider_map.get(external_status.lower(), "open")

    def diff(
        self,
        local_items: dict[str, str],
        external_items: list[ExternalWorkItem],
    ) -> SyncDiff:
        """Compute the diff between local and external work items.

        Args:
            local_items: Mapping of external_id -> local work-item id for
                items already synced.
            external_items: Work items fetched from the external board.

        Returns:
            A ``SyncDiff`` describing what needs to be created, updated,
            or deleted locally.
        """
        external_ids = {item.external_id for item in external_items}

        to_create: list[ExternalWorkItem] = []
        to_update: list[ExternalWorkItem] = []
        for item in external_items:
            if item.external_id in local_items:
                to_update.append(item)
            else:
                to_create.append(item)

        to_delete = [
            local_id for ext_id, local_id in local_items.items() if ext_id not in external_ids
        ]

        return SyncDiff(
            to_create=tuple(to_create),
            to_update=tuple(to_update),
            to_delete=tuple(to_delete),
        )
