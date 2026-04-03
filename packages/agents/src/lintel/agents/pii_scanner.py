"""PII/PHI scanning for the agent pipeline.

Provides pre/post hooks that scan text entering and leaving the LLM
for personally identifiable information. Configurable actions: redact,
warn (log but pass through), or block (raise).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.contracts.types import ThreadRef
    from lintel.pii.protocols import Deidentifier, DeidentifyResult

logger = structlog.get_logger()


class PIIScanAction(StrEnum):
    REDACT = "redact"
    WARN = "warn"
    BLOCK = "block"


class PIIBlockedError(Exception):
    """Raised when PII is detected and the action is BLOCK."""

    def __init__(self, entity_count: int, risk_score: float) -> None:
        self.entity_count = entity_count
        self.risk_score = risk_score
        super().__init__(f"PII blocked: {entity_count} entities detected (risk={risk_score:.2f})")


@dataclass(frozen=True)
class PIIScanResult:
    """Result of a PII scan on a piece of text."""

    original_text: str
    cleaned_text: str
    entities_found: int
    risk_score: float
    action_taken: PIIScanAction
    was_modified: bool
    details: list[dict[str, Any]] = field(default_factory=list)


class AgentPIIScanner:
    """Scans agent pipeline text for PII/PHI.

    Wraps the existing ``Deidentifier`` protocol to provide
    pre/post hooks for the agent runtime.
    """

    def __init__(
        self,
        deidentifier: Deidentifier,
        thread_ref: ThreadRef,
        action: PIIScanAction = PIIScanAction.REDACT,
    ) -> None:
        self._deidentifier = deidentifier
        self._thread_ref = thread_ref
        self._action = action
        self._scan_log: list[PIIScanResult] = []

    @property
    def scan_log(self) -> list[PIIScanResult]:
        """All scan results accumulated during this session."""
        return list(self._scan_log)

    async def _scan_text(self, text: str, context: str) -> PIIScanResult:
        """Core scan logic shared by all scan methods."""
        if not text.strip():
            return PIIScanResult(
                original_text=text,
                cleaned_text=text,
                entities_found=0,
                risk_score=0.0,
                action_taken=self._action,
                was_modified=False,
            )

        result: DeidentifyResult = await self._deidentifier.analyze_and_anonymize(
            text, self._thread_ref
        )

        entities_found = len(result.entities_detected)
        if entities_found == 0:
            scan_result = PIIScanResult(
                original_text=text,
                cleaned_text=text,
                entities_found=0,
                risk_score=0.0,
                action_taken=self._action,
                was_modified=False,
            )
            self._scan_log.append(scan_result)
            return scan_result

        logger.warning(
            "pii_detected_in_agent_pipeline",
            context=context,
            entities_found=entities_found,
            risk_score=result.risk_score,
            action=self._action.value,
        )

        if self._action == PIIScanAction.BLOCK:
            scan_result = PIIScanResult(
                original_text=text,
                cleaned_text=text,
                entities_found=entities_found,
                risk_score=result.risk_score,
                action_taken=PIIScanAction.BLOCK,
                was_modified=False,
                details=result.entities_detected,
            )
            self._scan_log.append(scan_result)
            raise PIIBlockedError(entities_found, result.risk_score)

        if self._action == PIIScanAction.WARN:
            scan_result = PIIScanResult(
                original_text=text,
                cleaned_text=text,
                entities_found=entities_found,
                risk_score=result.risk_score,
                action_taken=PIIScanAction.WARN,
                was_modified=False,
                details=result.entities_detected,
            )
            self._scan_log.append(scan_result)
            return scan_result

        # REDACT
        scan_result = PIIScanResult(
            original_text=text,
            cleaned_text=result.sanitized_text,
            entities_found=entities_found,
            risk_score=result.risk_score,
            action_taken=PIIScanAction.REDACT,
            was_modified=True,
            details=result.entities_detected,
        )
        self._scan_log.append(scan_result)
        return scan_result

    async def scan_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Scan user messages before sending to the LLM.

        Returns a new list with content replaced if action is REDACT.
        """
        scanned: list[dict[str, Any]] = []
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str) or not content:
                scanned.append(msg)
                continue
            result = await self._scan_text(content, f"message:{msg.get('role', 'unknown')}")
            if result.was_modified:
                scanned.append({**msg, "content": result.cleaned_text})
            else:
                scanned.append(msg)
        return scanned

    async def scan_response(self, text: str) -> PIIScanResult:
        """Scan LLM response text before storing or displaying."""
        return await self._scan_text(text, "llm_response")

    async def scan_tool_io(
        self, tool_name: str, arguments: str, result: str
    ) -> tuple[PIIScanResult, PIIScanResult]:
        """Scan tool call arguments and result."""
        arg_scan = await self._scan_text(arguments, f"tool_args:{tool_name}")
        result_scan = await self._scan_text(result, f"tool_result:{tool_name}")
        return arg_scan, result_scan
