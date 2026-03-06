"""Tests for Block Kit builders."""

from __future__ import annotations

from lintel.infrastructure.channels.slack.block_kit import (
    build_approval_blocks,
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
        blocks = build_approval_blocks("merge", "summary", "cb-1")
        assert "merge" in blocks[0]["text"]["text"]

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
            "coder", "implementing", "Working...",
            metadata={"model": "claude-sonnet", "tokens": "1234"},
        )
        assert len(blocks) == 3
        assert blocks[2]["type"] == "context"
        assert len(blocks[2]["elements"]) == 2

    def test_no_metadata_block_when_none(self) -> None:
        blocks = build_status_blocks("coder", "implementing", "Working...")
        assert len(blocks) == 2
