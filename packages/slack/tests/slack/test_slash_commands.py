"""Tests for Slack slash command handler."""

from __future__ import annotations

from typing import Any

from lintel.slack.slash_commands import (
    build_create_response,
    build_error_response,
    build_help_response,
    build_status_response,
    parse_slash_command,
)


class TestParseSlashCommand:
    def test_parse_board(self) -> None:
        cmd = parse_slash_command("/lintel board")
        assert cmd.subcommand == "board"
        assert cmd.args == ""

    def test_parse_help(self) -> None:
        cmd = parse_slash_command("/lintel help")
        assert cmd.subcommand == "help"

    def test_parse_empty_defaults_to_help(self) -> None:
        cmd = parse_slash_command("/lintel")
        assert cmd.subcommand == "help"

    def test_parse_status_with_id(self) -> None:
        cmd = parse_slash_command("/lintel status WI-abc123")
        assert cmd.subcommand == "status"
        assert cmd.args == "WI-abc123"

    def test_parse_create_with_type_and_title(self) -> None:
        cmd = parse_slash_command("/lintel create bug Fix login timeout")
        assert cmd.subcommand == "create"
        assert cmd.args == "bug Fix login timeout"

    def test_parse_strips_whitespace(self) -> None:
        cmd = parse_slash_command("/lintel  board  ")
        assert cmd.subcommand == "board"

    def test_parse_unknown_subcommand(self) -> None:
        cmd = parse_slash_command("/lintel foobar")
        assert cmd.subcommand == "foobar"

    def test_parse_bare_text(self) -> None:
        cmd = parse_slash_command("board")
        assert cmd.subcommand == "board"


class TestBuildHelpResponse:
    def test_contains_all_commands(self) -> None:
        blocks = build_help_response()
        texts = _all_text(blocks)
        assert "/lintel board" in texts
        assert "/lintel status" in texts
        assert "/lintel help" in texts
        assert "/lintel create" in texts

    def test_has_header(self) -> None:
        blocks = build_help_response()
        assert blocks[0]["type"] == "header"


class TestBuildStatusResponse:
    def test_found_item(self) -> None:
        item = {
            "work_item_id": "wi-abc12345",
            "title": "Fix login",
            "status": "in_progress",
            "work_type": "bug",
            "pr_url": "",
        }
        blocks = build_status_response(item, "wi-abc12345")
        texts = _all_text(blocks)
        assert "Fix login" in texts
        assert "in_progress" in texts
        assert "bug" in texts

    def test_found_item_with_pr(self) -> None:
        item = {
            "work_item_id": "wi-xyz",
            "title": "Add feature",
            "status": "in_review",
            "work_type": "feature",
            "pr_url": "https://github.com/org/repo/pull/99",
        }
        blocks = build_status_response(item, "wi-xyz")
        texts = _all_text(blocks)
        assert "pull/99" in texts

    def test_not_found(self) -> None:
        blocks = build_status_response(None, "wi-missing")
        texts = _all_text(blocks)
        assert "not found" in texts.lower()


class TestBuildCreateResponse:
    def test_confirmation(self) -> None:
        blocks = build_create_response("Fix login timeout", "bug", "wi-new123")
        texts = _all_text(blocks)
        assert "Fix login timeout" in texts
        assert "bug" in texts
        assert "wi-new123" in texts


class TestBuildErrorResponse:
    def test_error_message(self) -> None:
        blocks = build_error_response("Something went wrong")
        texts = _all_text(blocks)
        assert "Something went wrong" in texts


def _all_text(blocks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for b in blocks:
        t = b.get("text", {})
        if isinstance(t, dict):
            parts.append(t.get("text", ""))
        for el in b.get("elements", []):
            if isinstance(el, dict):
                parts.append(el.get("text", ""))
    return " ".join(parts)
