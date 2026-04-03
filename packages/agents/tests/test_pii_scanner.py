"""Tests for PII/PHI scanning in the agent pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from lintel.agents.pii_scanner import (
    AgentPIIScanner,
    PIIBlockedError,
    PIIScanAction,
)
from lintel.contracts.types import ThreadRef


@dataclass
class FakeDeidentifyResult:
    sanitized_text: str
    entities_detected: list[dict[str, Any]]
    placeholder_count: int
    is_blocked: bool
    risk_score: float


class FakeDeidentifier:
    """In-memory deidentifier that detects 'SSN' and 'email' keywords."""

    def __init__(self, detect: bool = False, entities: list[dict[str, Any]] | None = None) -> None:
        self._detect = detect
        self._entities = entities or []

    async def analyze_and_anonymize(
        self, text: str, thread_ref: ThreadRef, language: str = "en"
    ) -> FakeDeidentifyResult:
        if self._detect:
            return FakeDeidentifyResult(
                sanitized_text=text.replace("123-45-6789", "<SSN_1>"),
                entities_detected=self._entities
                or [{"type": "US_SSN", "start": 0, "end": 11, "score": 0.9}],
                placeholder_count=1,
                is_blocked=False,
                risk_score=0.9,
            )
        return FakeDeidentifyResult(
            sanitized_text=text,
            entities_detected=[],
            placeholder_count=0,
            is_blocked=False,
            risk_score=0.0,
        )


THREAD_REF = ThreadRef(workspace_id="ws", channel_id="ch", thread_ts="ts")


class TestAgentPIIScanner:
    async def test_scan_clean_text_passes_through(self) -> None:
        scanner = AgentPIIScanner(
            FakeDeidentifier(detect=False),  # type: ignore[arg-type]
            THREAD_REF,
        )
        result = await scanner.scan_response("Hello world")
        assert not result.was_modified
        assert result.entities_found == 0
        assert result.cleaned_text == "Hello world"

    async def test_scan_empty_text(self) -> None:
        scanner = AgentPIIScanner(
            FakeDeidentifier(detect=True),  # type: ignore[arg-type]
            THREAD_REF,
        )
        result = await scanner.scan_response("")
        assert not result.was_modified
        assert result.entities_found == 0

    async def test_redact_action_replaces_text(self) -> None:
        scanner = AgentPIIScanner(
            FakeDeidentifier(detect=True),  # type: ignore[arg-type]
            THREAD_REF,
            action=PIIScanAction.REDACT,
        )
        result = await scanner.scan_response("SSN is 123-45-6789")
        assert result.was_modified
        assert "<SSN_1>" in result.cleaned_text
        assert result.entities_found == 1
        assert result.risk_score == 0.9

    async def test_warn_action_logs_but_passes_through(self) -> None:
        scanner = AgentPIIScanner(
            FakeDeidentifier(detect=True),  # type: ignore[arg-type]
            THREAD_REF,
            action=PIIScanAction.WARN,
        )
        result = await scanner.scan_response("SSN is 123-45-6789")
        assert not result.was_modified
        assert result.entities_found == 1
        assert result.action_taken == PIIScanAction.WARN

    async def test_block_action_raises(self) -> None:
        scanner = AgentPIIScanner(
            FakeDeidentifier(detect=True),  # type: ignore[arg-type]
            THREAD_REF,
            action=PIIScanAction.BLOCK,
        )
        with pytest.raises(PIIBlockedError, match="PII blocked"):
            await scanner.scan_response("SSN is 123-45-6789")

    async def test_scan_messages_redacts_user_content(self) -> None:
        scanner = AgentPIIScanner(
            FakeDeidentifier(detect=True),  # type: ignore[arg-type]
            THREAD_REF,
            action=PIIScanAction.REDACT,
        )
        messages = [
            {"role": "system", "content": "You are a helper."},
            {"role": "user", "content": "My SSN is 123-45-6789"},
        ]
        # System message has no PII — deidentifier returns detect=True for all text
        # but our fake replaces "123-45-6789" specifically
        scanned = await scanner.scan_messages(messages)
        assert len(scanned) == 2
        # The user message should have SSN redacted
        assert "<SSN_1>" in scanned[1]["content"]

    async def test_scan_messages_preserves_non_string_content(self) -> None:
        scanner = AgentPIIScanner(
            FakeDeidentifier(detect=True),  # type: ignore[arg-type]
            THREAD_REF,
        )
        messages: list[dict[str, Any]] = [{"role": "assistant", "content": None}]
        scanned = await scanner.scan_messages(messages)
        assert scanned[0]["content"] is None

    async def test_scan_tool_io(self) -> None:
        scanner = AgentPIIScanner(
            FakeDeidentifier(detect=True),  # type: ignore[arg-type]
            THREAD_REF,
            action=PIIScanAction.REDACT,
        )
        arg_scan, result_scan = await scanner.scan_tool_io(
            "sandbox_read_file",
            '{"path": "/workspace/123-45-6789.txt"}',
            "File content with 123-45-6789",
        )
        assert arg_scan.was_modified
        assert result_scan.was_modified

    async def test_scan_log_accumulates(self) -> None:
        scanner = AgentPIIScanner(
            FakeDeidentifier(detect=True),  # type: ignore[arg-type]
            THREAD_REF,
        )
        await scanner.scan_response("text with 123-45-6789")
        await scanner.scan_response("more text with 123-45-6789")
        assert len(scanner.scan_log) == 2

    async def test_block_still_logs_before_raising(self) -> None:
        scanner = AgentPIIScanner(
            FakeDeidentifier(detect=True),  # type: ignore[arg-type]
            THREAD_REF,
            action=PIIScanAction.BLOCK,
        )
        with pytest.raises(PIIBlockedError):
            await scanner.scan_response("SSN 123-45-6789")
        assert len(scanner.scan_log) == 1
        assert scanner.scan_log[0].action_taken == PIIScanAction.BLOCK
