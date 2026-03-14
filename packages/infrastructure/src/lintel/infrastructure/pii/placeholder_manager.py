"""Stable placeholder generation per thread."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.contracts.types import ThreadRef


class PlaceholderManager:
    """Generates stable placeholders like <PERSON_1>, <EMAIL_2> per thread."""

    def __init__(self) -> None:
        self._mappings: dict[str, dict[tuple[str, str], str]] = {}
        self._counters: dict[str, dict[str, int]] = {}

    def get_or_create(
        self,
        thread_ref: ThreadRef,
        entity_type: str,
        raw_value: str,
    ) -> str:
        stream = thread_ref.stream_id
        key = (entity_type, raw_value)

        if stream not in self._mappings:
            self._mappings[stream] = {}
            self._counters[stream] = {}

        if key in self._mappings[stream]:
            return self._mappings[stream][key]

        if entity_type not in self._counters[stream]:
            self._counters[stream][entity_type] = 0

        self._counters[stream][entity_type] += 1
        placeholder = f"<{entity_type}_{self._counters[stream][entity_type]}>"
        self._mappings[stream][key] = placeholder
        return placeholder
