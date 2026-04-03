"""Tests for Block Kit builders."""

from __future__ import annotations

from typing import Any

from lintel.slack.block_kit import (
    build_approval_blocks,
    build_board_blocks,
    build_stage_blocks,
    build_status_blocks,
)


class TestBuildApprovalBlocks:
    def test_returns_header_divider_section_actions(self) -> None:
        blocks = build_approval_blocks("spec_approval", "Review the spec", "cb-123")
        assert len(blocks) == 4
        assert blocks[0]["type"] == "header"
        assert blocks[1]["type"] == "divider"
        assert blocks[2]["type"] == "section"
        assert blocks[3]["type"] == "actions"

    def test_header_contains_gate_type(self) -> None:
        blocks = build_approval_blocks("pr", "summary", "cb-1")
        assert "pr" in blocks[0]["text"]["text"]

    def test_actions_contain_approve_and_reject_buttons(self) -> None:
        blocks = build_approval_blocks("spec", "summary", "cb-1")
        elements = blocks[3]["elements"]
        assert len(elements) == 2
        assert elements[0]["action_id"] == "approve:spec:cb-1"
        assert elements[0]["style"] == "primary"
        assert elements[1]["action_id"] == "reject:spec:cb-1"
        assert elements[1]["style"] == "danger"

    def test_summary_in_section(self) -> None:
        blocks = build_approval_blocks("spec", "Please review this plan", "cb-1")
        assert blocks[2]["text"]["text"] == "Please review this plan"


class TestBuildStatusBlocks:
    def test_returns_agent_and_summary_sections(self) -> None:
        blocks = build_status_blocks("coder", "implementing", "Writing code...")
        assert len(blocks) == 2
        assert blocks[0]["type"] == "section"
        assert blocks[1]["type"] == "section"

    def test_includes_agent_name_and_phase(self) -> None:
        blocks = build_status_blocks("reviewer", "reviewing", "LGTM")
        text = blocks[0]["text"]["text"]
        assert "reviewer" in text
        assert "reviewing" in text

    def test_truncates_long_summary(self) -> None:
        long_summary = "x" * 5000
        blocks = build_status_blocks("coder", "implementing", long_summary)
        assert len(blocks[1]["text"]["text"]) <= 3000

    def test_includes_metadata_context(self) -> None:
        blocks = build_status_blocks(
            "coder",
            "implementing",
            "Working...",
            metadata={"model": "claude-sonnet", "tokens": "1234"},
        )
        assert len(blocks) == 3
        assert blocks[2]["type"] == "context"
        assert len(blocks[2]["elements"]) == 2

    def test_no_metadata_block_when_none(self) -> None:
        blocks = build_status_blocks("coder", "implementing", "Working...")
        assert len(blocks) == 2


class TestBuildStageBlocks:
    def test_basic_stage_blocks(self) -> None:
        blocks = build_stage_blocks("implement", "succeeded", "run-abc123")
        assert len(blocks) >= 2
        text = blocks[0]["text"]["text"]
        assert "Implement" in text
        assert "succeeded" in text

    def test_includes_duration(self) -> None:
        blocks = build_stage_blocks("review", "succeeded", "run-1", duration_ms=5000)
        text = blocks[0]["text"]["text"]
        assert "5.0s" in text

    def test_includes_error_block(self) -> None:
        blocks = build_stage_blocks("implement", "failed", "run-1", error="Syntax error on line 42")
        block_texts = [b.get("text", {}).get("text", "") for b in blocks]
        assert any("Syntax error" in t for t in block_texts)

    def test_includes_pr_url(self) -> None:
        blocks = build_stage_blocks(
            "merge", "succeeded", "run-1", pr_url="https://github.com/org/repo/pull/99"
        )
        block_texts = [b.get("text", {}).get("text", "") for b in blocks]
        assert any("pull/99" in t for t in block_texts)

    def test_context_block_has_run_id(self) -> None:
        blocks = build_stage_blocks("research", "running", "run-abcd1234")
        context = [b for b in blocks if b["type"] == "context"]
        assert len(context) == 1
        assert "run-abcd" in context[0]["elements"][0]["text"]

    def test_emoji_for_succeeded(self) -> None:
        blocks = build_stage_blocks("test", "succeeded", "run-1")
        assert ":white_check_mark:" in blocks[0]["text"]["text"]

    def test_emoji_for_failed(self) -> None:
        blocks = build_stage_blocks("test", "failed", "run-1")
        assert ":x:" in blocks[0]["text"]["text"]


def _wi(
    title: str = "Add dark mode",
    status: str = "open",
    work_type: str = "feature",
    work_item_id: str = "wi-1",
) -> dict[str, Any]:
    return {
        "work_item_id": work_item_id,
        "title": title,
        "status": status,
        "work_type": work_type,
    }


def _all_text(blocks: list[dict[str, Any]]) -> str:
    """Extract all text content from blocks (sections, context elements, headers)."""
    parts: list[str] = []
    for b in blocks:
        t = b.get("text", {})
        if isinstance(t, dict):
            parts.append(t.get("text", ""))
        for el in b.get("elements", []):
            if isinstance(el, dict):
                parts.append(el.get("text", ""))
    return " ".join(parts)


class TestBuildBoardBlocks:
    def test_empty_board(self) -> None:
        blocks = build_board_blocks([])
        texts = _all_text(blocks)
        assert "empty" in texts.lower()

    def test_groups_by_status(self) -> None:
        items = [
            _wi(title="Alpha", status="open", work_item_id="wi-1"),
            _wi(title="Beta", status="in_progress", work_item_id="wi-2"),
            _wi(title="Gamma", status="in_review", work_item_id="wi-3"),
            _wi(title="Delta", status="merged", work_item_id="wi-4"),
        ]
        blocks = build_board_blocks(items)
        texts = _all_text(blocks)
        assert "Open" in texts
        assert "In Progress" in texts
        assert "In Review" in texts
        assert "Done" in texts

    def test_max_items_per_column(self) -> None:
        items = [_wi(title=f"Item {i}", status="open", work_item_id=f"wi-{i}") for i in range(8)]
        blocks = build_board_blocks(items, max_per_column=5)
        texts = _all_text(blocks)
        assert "+3 more" in texts

    def test_includes_work_type_tag(self) -> None:
        items = [_wi(title="Fix login", work_type="bug")]
        blocks = build_board_blocks(items)
        texts = _all_text(blocks)
        assert ":bug:" in texts

    def test_skips_empty_columns(self) -> None:
        items = [_wi(title="Alpha", status="in_progress")]
        blocks = build_board_blocks(items)
        texts = _all_text(blocks)
        assert "Open" not in texts
        assert "In Progress" in texts

    def test_has_header(self) -> None:
        items = [_wi()]
        blocks = build_board_blocks(items)
        assert blocks[0]["type"] == "header"

    def test_merged_and_closed_grouped_as_done(self) -> None:
        items = [
            _wi(title="Alpha", status="merged", work_item_id="wi-1"),
            _wi(title="Zeta", status="closed", work_item_id="wi-2"),
        ]
        blocks = build_board_blocks(items)
        texts = _all_text(blocks)
        assert "Done" in texts
        assert "Alpha" in texts
        assert "Zeta" in texts
