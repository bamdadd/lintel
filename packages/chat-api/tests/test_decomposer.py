"""Tests for idea decomposition: parsing, work item creation, and chat integration."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from lintel.chat_api.decomposer import (
    DecomposedItem,
    IdeaDecomposer,
)
from lintel.domain.types import WorkItemType

# ---------------------------------------------------------------------------
# _parse_response tests
# ---------------------------------------------------------------------------


class TestParseResponse:
    """Test LLM response parsing into DecomposedItem list."""

    def test_valid_json_array(self) -> None:
        content = json.dumps(
            [
                {
                    "title": "Add user model",
                    "description": "Create User dataclass.",
                    "work_type": "feature",
                    "order": 1,
                },
                {
                    "title": "Add user store",
                    "description": "In-memory store for users.",
                    "work_type": "feature",
                    "order": 2,
                },
            ]
        )
        items = IdeaDecomposer._parse_response(content)
        assert len(items) == 2
        assert items[0].title == "Add user model"
        assert items[0].work_type == WorkItemType.FEATURE
        assert items[0].order == 1
        assert items[1].order == 2

    def test_json_with_markdown_fences(self) -> None:
        content = (
            "```json\n"
            + json.dumps(
                [
                    {"title": "Fix bug", "description": "Fix it.", "work_type": "bug", "order": 1},
                ]
            )
            + "\n```"
        )
        items = IdeaDecomposer._parse_response(content)
        assert len(items) == 1
        assert items[0].work_type == WorkItemType.BUG

    def test_invalid_json_returns_empty(self) -> None:
        items = IdeaDecomposer._parse_response("not json at all")
        assert items == []

    def test_non_list_json_returns_empty(self) -> None:
        items = IdeaDecomposer._parse_response('{"title": "oops"}')
        assert items == []

    def test_items_sorted_by_order(self) -> None:
        content = json.dumps(
            [
                {"title": "Third", "description": "", "work_type": "task", "order": 3},
                {"title": "First", "description": "", "work_type": "task", "order": 1},
                {"title": "Second", "description": "", "work_type": "task", "order": 2},
            ]
        )
        items = IdeaDecomposer._parse_response(content)
        assert [i.title for i in items] == ["First", "Second", "Third"]

    def test_unknown_work_type_defaults_to_task(self) -> None:
        content = json.dumps(
            [
                {"title": "Something", "description": "", "work_type": "epic", "order": 1},
            ]
        )
        items = IdeaDecomposer._parse_response(content)
        assert items[0].work_type == WorkItemType.TASK

    def test_skips_items_without_title(self) -> None:
        content = json.dumps(
            [
                {"title": "", "description": "no title", "work_type": "task", "order": 1},
                {"title": "Has title", "description": "", "work_type": "task", "order": 2},
            ]
        )
        items = IdeaDecomposer._parse_response(content)
        assert len(items) == 1
        assert items[0].title == "Has title"

    def test_title_truncated_to_100_chars(self) -> None:
        content = json.dumps(
            [
                {"title": "A" * 200, "description": "", "work_type": "task", "order": 1},
            ]
        )
        items = IdeaDecomposer._parse_response(content)
        assert len(items[0].title) == 100

    def test_refactor_work_type(self) -> None:
        content = json.dumps(
            [
                {"title": "Clean up", "description": "", "work_type": "refactor", "order": 1},
            ]
        )
        items = IdeaDecomposer._parse_response(content)
        assert items[0].work_type == WorkItemType.REFACTOR


# ---------------------------------------------------------------------------
# create_work_items tests
# ---------------------------------------------------------------------------


class TestCreateWorkItems:
    """Test persisting decomposed items to the work item store."""

    async def test_creates_items_in_store(self) -> None:
        store = AsyncMock()
        items = [
            DecomposedItem(
                title="Item 1", description="Desc 1", work_type=WorkItemType.FEATURE, order=1
            ),
            DecomposedItem(
                title="Item 2", description="Desc 2", work_type=WorkItemType.TASK, order=2
            ),
        ]
        ids = await IdeaDecomposer.create_work_items(items, "proj-1", store)
        assert len(ids) == 2
        assert store.add.call_count == 2

        # Verify first created work item
        first_call = store.add.call_args_list[0]
        work_item = first_call[0][0]
        assert work_item.title == "Item 1"
        assert work_item.project_id == "proj-1"
        assert work_item.work_type == WorkItemType.FEATURE
        assert work_item.status.value == "open"
        assert work_item.column_position == 0

    async def test_handles_store_failure_gracefully(self) -> None:
        store = AsyncMock()
        store.add.side_effect = [None, RuntimeError("store error"), None]
        items = [
            DecomposedItem(title=f"Item {i}", description="", work_type=WorkItemType.TASK, order=i)
            for i in range(3)
        ]
        ids = await IdeaDecomposer.create_work_items(items, "proj-1", store)
        # Second item failed, so only 2 IDs returned
        assert len(ids) == 2


# ---------------------------------------------------------------------------
# format_reply tests
# ---------------------------------------------------------------------------


class TestFormatReply:
    """Test reply message formatting."""

    def test_no_items_returns_help_message(self) -> None:
        reply = IdeaDecomposer.format_reply([], 0)
        assert "couldn't break" in reply

    def test_formats_items_with_count(self) -> None:
        items = [
            DecomposedItem(
                title="Add API",
                description="Create the REST API.",
                work_type=WorkItemType.FEATURE,
                order=1,
            ),
            DecomposedItem(
                title="Add tests",
                description="Write unit tests.",
                work_type=WorkItemType.TASK,
                order=2,
            ),
        ]
        reply = IdeaDecomposer.format_reply(items, 2)
        assert "**2** work items" in reply
        assert "Add API" in reply
        assert "Add tests" in reply
        assert "open" in reply.lower()


# ---------------------------------------------------------------------------
# decompose (LLM call) tests
# ---------------------------------------------------------------------------


class TestDecompose:
    """Test the full decompose flow with mocked LLM."""

    async def test_calls_llm_and_returns_items(self) -> None:
        mock_router = MagicMock()
        mock_router.select_model = AsyncMock(return_value=MagicMock())
        mock_router.call_model = AsyncMock(
            return_value={
                "content": json.dumps(
                    [
                        {
                            "title": "Add data model",
                            "description": "Create types.",
                            "work_type": "feature",
                            "order": 1,
                        },
                    ]
                ),
            }
        )

        decomposer = IdeaDecomposer(model_router=mock_router)
        items = await decomposer.decompose("Build a user management system")

        assert len(items) == 1
        assert items[0].title == "Add data model"
        mock_router.call_model.assert_called_once()

    async def test_uses_provided_model_policy(self) -> None:
        mock_router = MagicMock()
        mock_policy = MagicMock()
        mock_router.call_model = AsyncMock(return_value={"content": "[]"})

        decomposer = IdeaDecomposer(model_router=mock_router)
        await decomposer.decompose("idea", model_policy=mock_policy)

        # Should NOT call select_model when policy is provided
        mock_router.select_model.assert_not_called()
        call_args = mock_router.call_model.call_args
        assert call_args[0][0] is mock_policy

    async def test_includes_project_context_in_prompt(self) -> None:
        mock_router = MagicMock()
        mock_router.select_model = AsyncMock(return_value=MagicMock())
        mock_router.call_model = AsyncMock(return_value={"content": "[]"})

        decomposer = IdeaDecomposer(model_router=mock_router)
        await decomposer.decompose("idea", project_context="Project: lintel")

        call_args = mock_router.call_model.call_args
        messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][1]
        user_msg = messages[-1]["content"]
        assert "Project: lintel" in user_msg
