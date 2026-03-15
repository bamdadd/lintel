"""Tests for Telegram inline keyboards."""

from __future__ import annotations

import pytest

from lintel.telegram.keyboards import build_approval_keyboard, parse_callback_data


class TestBuildApprovalKeyboard:
    def test_produces_inline_keyboard(self) -> None:
        kb = build_approval_keyboard("req-123")
        assert "inline_keyboard" in kb
        rows = kb["inline_keyboard"]
        assert len(rows) == 1
        assert len(rows[0]) == 2

    def test_approve_button(self) -> None:
        kb = build_approval_keyboard("req-123")
        approve_btn = kb["inline_keyboard"][0][0]
        assert "Approve" in approve_btn["text"]
        assert approve_btn["callback_data"] == "a:req-123"

    def test_reject_button(self) -> None:
        kb = build_approval_keyboard("req-123")
        reject_btn = kb["inline_keyboard"][0][1]
        assert "Reject" in reject_btn["text"]
        assert reject_btn["callback_data"] == "r:req-123"

    def test_callback_data_under_64_bytes(self) -> None:
        long_id = "x" * 100
        kb = build_approval_keyboard(long_id)
        for row in kb["inline_keyboard"]:
            for btn in row:
                assert len(btn["callback_data"].encode("utf-8")) <= 64

    def test_round_trip_with_parse(self) -> None:
        kb = build_approval_keyboard("abc-456")
        approve_data = kb["inline_keyboard"][0][0]["callback_data"]
        reject_data = kb["inline_keyboard"][0][1]["callback_data"]
        assert parse_callback_data(approve_data) == ("approve", "abc-456")
        assert parse_callback_data(reject_data) == ("reject", "abc-456")


class TestParseCallbackData:
    def test_parse_approve(self) -> None:
        assert parse_callback_data("a:req-123") == ("approve", "req-123")

    def test_parse_reject(self) -> None:
        assert parse_callback_data("r:req-123") == ("reject", "req-123")

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            parse_callback_data("")

    def test_unknown_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown"):
            parse_callback_data("x:req-123")

    def test_no_colon_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            parse_callback_data("nocolon")
