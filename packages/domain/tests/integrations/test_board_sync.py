"""Tests for board sync domain model."""

from __future__ import annotations

from datetime import UTC, datetime

from lintel.domain.integrations.board_sync import (
    BoardSyncConfig,
    BoardSyncEngine,
    ExternalBoardProvider,
    ExternalWorkItem,
    SyncDirection,
)


class TestExternalBoardProvider:
    def test_values(self) -> None:
        assert ExternalBoardProvider.JIRA == "jira"
        assert ExternalBoardProvider.NOTION == "notion"
        assert ExternalBoardProvider.LINEAR == "linear"
        assert ExternalBoardProvider.GITHUB_PROJECTS == "github_projects"


class TestSyncDirection:
    def test_values(self) -> None:
        assert SyncDirection.PULL == "pull"
        assert SyncDirection.PUSH == "push"
        assert SyncDirection.BIDIRECTIONAL == "bidirectional"


class TestBoardSyncConfig:
    def test_defaults(self) -> None:
        cfg = BoardSyncConfig(
            config_id="cfg-1",
            project_id="proj-1",
            provider=ExternalBoardProvider.JIRA,
            external_board_id="BOARD-1",
        )
        assert cfg.sync_direction == SyncDirection.PULL
        assert cfg.field_mapping == {}
        assert cfg.last_synced_at is None

    def test_frozen(self) -> None:
        cfg = BoardSyncConfig(
            config_id="cfg-1",
            project_id="proj-1",
            provider=ExternalBoardProvider.JIRA,
            external_board_id="BOARD-1",
        )
        try:
            cfg.config_id = "other"  # type: ignore[misc]
            msg = "Should be frozen"
            raise AssertionError(msg)
        except AttributeError:
            pass


class TestExternalWorkItem:
    def test_defaults(self) -> None:
        item = ExternalWorkItem(
            external_id="ext-1",
            provider=ExternalBoardProvider.NOTION,
            title="Do a thing",
        )
        assert item.description == ""
        assert item.status == ""
        assert item.labels == ()
        assert item.updated_at is None

    def test_full(self) -> None:
        now = datetime.now(tz=UTC)
        item = ExternalWorkItem(
            external_id="ext-2",
            provider=ExternalBoardProvider.LINEAR,
            title="Fix bug",
            description="It's broken",
            status="in progress",
            assignee="alice",
            labels=("bug", "urgent"),
            url="https://linear.app/issue/123",
            updated_at=now,
        )
        assert item.assignee == "alice"
        assert item.updated_at == now


class TestBoardSyncEngine:
    def setup_method(self) -> None:
        self.engine = BoardSyncEngine()

    def test_sync_pull_returns_empty(self) -> None:
        cfg = BoardSyncConfig(
            config_id="c1",
            project_id="p1",
            provider=ExternalBoardProvider.JIRA,
            external_board_id="B1",
        )
        assert self.engine.sync_pull(cfg) == []

    def test_map_status_jira(self) -> None:
        assert self.engine.map_status("To Do", ExternalBoardProvider.JIRA) == "open"
        assert self.engine.map_status("In Progress", ExternalBoardProvider.JIRA) == "in_progress"
        assert self.engine.map_status("Done", ExternalBoardProvider.JIRA) == "closed"

    def test_map_status_linear(self) -> None:
        assert self.engine.map_status("backlog", ExternalBoardProvider.LINEAR) == "open"
        assert self.engine.map_status("In Review", ExternalBoardProvider.LINEAR) == "in_review"
        assert self.engine.map_status("canceled", ExternalBoardProvider.LINEAR) == "closed"

    def test_map_status_unknown_defaults_open(self) -> None:
        assert self.engine.map_status("weird_status", ExternalBoardProvider.JIRA) == "open"

    def test_diff_create(self) -> None:
        items = [
            ExternalWorkItem(
                external_id="ext-1",
                provider=ExternalBoardProvider.JIRA,
                title="New item",
            ),
        ]
        result = self.engine.diff(local_items={}, external_items=items)
        assert len(result.to_create) == 1
        assert result.to_create[0].external_id == "ext-1"
        assert result.to_update == ()
        assert result.to_delete == ()

    def test_diff_update(self) -> None:
        items = [
            ExternalWorkItem(
                external_id="ext-1",
                provider=ExternalBoardProvider.JIRA,
                title="Updated",
            ),
        ]
        result = self.engine.diff(
            local_items={"ext-1": "local-1"},
            external_items=items,
        )
        assert result.to_create == ()
        assert len(result.to_update) == 1
        assert result.to_delete == ()

    def test_diff_delete(self) -> None:
        result = self.engine.diff(
            local_items={"ext-gone": "local-2"},
            external_items=[],
        )
        assert result.to_create == ()
        assert result.to_update == ()
        assert result.to_delete == ("local-2",)

    def test_diff_mixed(self) -> None:
        items = [
            ExternalWorkItem(
                external_id="ext-1",
                provider=ExternalBoardProvider.NOTION,
                title="Existing",
            ),
            ExternalWorkItem(
                external_id="ext-2",
                provider=ExternalBoardProvider.NOTION,
                title="Brand new",
            ),
        ]
        result = self.engine.diff(
            local_items={"ext-1": "local-1", "ext-old": "local-old"},
            external_items=items,
        )
        assert len(result.to_create) == 1
        assert result.to_create[0].external_id == "ext-2"
        assert len(result.to_update) == 1
        assert result.to_update[0].external_id == "ext-1"
        assert result.to_delete == ("local-old",)
