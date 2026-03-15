"""PII detection and vault protocol interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from lintel.contracts.types import ThreadRef


class DeidentifyResult(Protocol):
    sanitized_text: str
    entities_detected: list[dict[str, Any]]
    placeholder_count: int
    is_blocked: bool
    risk_score: float


class Deidentifier(Protocol):
    """PII detection and anonymization pipeline."""

    async def analyze_and_anonymize(
        self,
        text: str,
        thread_ref: ThreadRef,
        language: str = "en",
    ) -> DeidentifyResult: ...


class PIIVault(Protocol):
    """Encrypted storage for PII placeholder mappings."""

    async def store_mapping(
        self,
        thread_ref: ThreadRef,
        placeholder: str,
        entity_type: str,
        raw_value: str,
    ) -> None: ...

    async def reveal(
        self,
        thread_ref: ThreadRef,
        placeholder: str,
        revealer_id: str,
    ) -> str: ...
