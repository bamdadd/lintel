"""Presidio-based PII detection and anonymization. Fail-closed."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog
from presidio_analyzer import AnalyzerEngine, RecognizerResult

from lintel.infrastructure.pii.placeholder_manager import PlaceholderManager

if TYPE_CHECKING:
    from lintel.contracts.protocols import PIIVault
    from lintel.contracts.types import ThreadRef

logger = structlog.get_logger()

DEFAULT_RISK_THRESHOLD = 0.6


@dataclass(frozen=True)
class DeidentifyResultImpl:
    sanitized_text: str
    entities_detected: list[dict[str, Any]]
    placeholder_count: int
    is_blocked: bool
    risk_score: float


class PresidioFirewall:
    """Implements Deidentifier protocol with Microsoft Presidio."""

    def __init__(
        self,
        vault: PIIVault,
        risk_threshold: float = DEFAULT_RISK_THRESHOLD,
    ) -> None:
        self._analyzer = AnalyzerEngine()
        self._register_custom_recognizers()
        self._vault = vault
        self._risk_threshold = risk_threshold
        self._placeholder_mgr = PlaceholderManager()

    def _register_custom_recognizers(self) -> None:
        from lintel.infrastructure.pii.custom_recognizers import (
            create_api_key_recognizer,
            create_connection_string_recognizer,
        )

        registry = self._analyzer.registry
        registry.add_recognizer(create_api_key_recognizer())
        registry.add_recognizer(create_connection_string_recognizer())

    async def analyze_and_anonymize(
        self,
        text: str,
        thread_ref: ThreadRef,
        language: str = "en",
    ) -> DeidentifyResultImpl:
        results: list[RecognizerResult] = await asyncio.to_thread(
            self._analyzer.analyze,
            text=text,
            language=language,
            entities=None,
        )

        entities = [
            {
                "type": r.entity_type,
                "start": r.start,
                "end": r.end,
                "score": r.score,
            }
            for r in results
        ]

        if not results:
            return DeidentifyResultImpl(
                sanitized_text=text,
                entities_detected=[],
                placeholder_count=0,
                is_blocked=False,
                risk_score=0.0,
            )

        risk_score = max(r.score for r in results)

        if risk_score > self._risk_threshold:
            logger.warning(
                "pii_blocked",
                thread_ref=str(thread_ref),
                risk_score=risk_score,
                entity_count=len(results),
            )
            return DeidentifyResultImpl(
                sanitized_text="[BLOCKED: PII risk too high]",
                entities_detected=entities,
                placeholder_count=0,
                is_blocked=True,
                risk_score=risk_score,
            )

        sanitized = text
        placeholder_count = 0

        for result in sorted(results, key=lambda r: r.start, reverse=True):
            raw_value = text[result.start : result.end]
            placeholder = self._placeholder_mgr.get_or_create(
                thread_ref,
                result.entity_type,
                raw_value,
            )
            sanitized = sanitized[: result.start] + placeholder + sanitized[result.end :]
            placeholder_count += 1

            await self._vault.store_mapping(
                thread_ref=thread_ref,
                placeholder=placeholder,
                entity_type=result.entity_type,
                raw_value=raw_value,
            )

        logger.info(
            "pii_anonymized",
            thread_ref=str(thread_ref),
            entity_count=len(results),
            placeholder_count=placeholder_count,
        )

        return DeidentifyResultImpl(
            sanitized_text=sanitized,
            entities_detected=entities,
            placeholder_count=placeholder_count,
            is_blocked=False,
            risk_score=risk_score,
        )
