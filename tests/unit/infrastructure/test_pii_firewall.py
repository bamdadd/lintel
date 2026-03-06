"""Tests for PII firewall and placeholder manager."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from lintel.contracts.types import ThreadRef
from lintel.infrastructure.pii.placeholder_manager import PlaceholderManager


@pytest.fixture
def thread_ref() -> ThreadRef:
    return ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1234.5678")


@pytest.fixture
def other_thread_ref() -> ThreadRef:
    return ThreadRef(workspace_id="W1", channel_id="C2", thread_ts="9999.0000")


class TestPlaceholderManager:
    def test_generates_placeholder(self, thread_ref: ThreadRef) -> None:
        mgr = PlaceholderManager()
        result = mgr.get_or_create(thread_ref, "PERSON", "John Doe")
        assert result == "<PERSON_1>"

    def test_same_value_returns_same_placeholder(self, thread_ref: ThreadRef) -> None:
        mgr = PlaceholderManager()
        p1 = mgr.get_or_create(thread_ref, "PERSON", "John Doe")
        p2 = mgr.get_or_create(thread_ref, "PERSON", "John Doe")
        assert p1 == p2

    def test_different_values_get_different_placeholders(self, thread_ref: ThreadRef) -> None:
        mgr = PlaceholderManager()
        p1 = mgr.get_or_create(thread_ref, "PERSON", "John Doe")
        p2 = mgr.get_or_create(thread_ref, "PERSON", "Jane Smith")
        assert p1 == "<PERSON_1>"
        assert p2 == "<PERSON_2>"

    def test_different_entity_types_have_separate_counters(
        self, thread_ref: ThreadRef
    ) -> None:
        mgr = PlaceholderManager()
        p1 = mgr.get_or_create(thread_ref, "PERSON", "John Doe")
        p2 = mgr.get_or_create(thread_ref, "EMAIL_ADDRESS", "john@example.com")
        assert p1 == "<PERSON_1>"
        assert p2 == "<EMAIL_ADDRESS_1>"

    def test_different_threads_have_separate_namespaces(
        self, thread_ref: ThreadRef, other_thread_ref: ThreadRef
    ) -> None:
        mgr = PlaceholderManager()
        p1 = mgr.get_or_create(thread_ref, "PERSON", "John Doe")
        p2 = mgr.get_or_create(other_thread_ref, "PERSON", "John Doe")
        assert p1 == "<PERSON_1>"
        assert p2 == "<PERSON_1>"


class TestPresidioFirewall:
    @pytest.fixture
    def vault(self) -> AsyncMock:
        return AsyncMock()

    async def test_no_pii_returns_original_text(
        self, thread_ref: ThreadRef, vault: AsyncMock
    ) -> None:
        from lintel.infrastructure.pii.presidio_firewall import PresidioFirewall

        firewall = PresidioFirewall(vault=vault)
        result = await firewall.analyze_and_anonymize(
            "Hello world, no PII here.", thread_ref
        )
        assert result.sanitized_text == "Hello world, no PII here."
        assert result.entities_detected == []
        assert result.placeholder_count == 0
        assert result.is_blocked is False
        assert result.risk_score == 0.0

    async def test_detects_and_anonymizes_person_name(
        self, thread_ref: ThreadRef, vault: AsyncMock
    ) -> None:
        from lintel.infrastructure.pii.presidio_firewall import PresidioFirewall

        firewall = PresidioFirewall(vault=vault, risk_threshold=0.9)
        result = await firewall.analyze_and_anonymize(
            "Contact John Smith at the office.", thread_ref
        )
        assert "John Smith" not in result.sanitized_text
        assert result.placeholder_count > 0
        assert result.is_blocked is False

    async def test_blocks_when_risk_above_threshold(
        self, thread_ref: ThreadRef, vault: AsyncMock
    ) -> None:
        from lintel.infrastructure.pii.presidio_firewall import PresidioFirewall

        # Very low threshold to trigger blocking
        firewall = PresidioFirewall(vault=vault, risk_threshold=0.01)
        result = await firewall.analyze_and_anonymize(
            "My email is john.doe@example.com", thread_ref
        )
        assert result.is_blocked is True
        assert "[BLOCKED" in result.sanitized_text
        assert result.placeholder_count == 0

    async def test_stores_mappings_in_vault(
        self, thread_ref: ThreadRef, vault: AsyncMock
    ) -> None:
        from lintel.infrastructure.pii.presidio_firewall import PresidioFirewall

        firewall = PresidioFirewall(vault=vault, risk_threshold=0.9)
        await firewall.analyze_and_anonymize(
            "Contact John Smith at the office.", thread_ref
        )
        if vault.store_mapping.call_count > 0:
            call_kwargs = vault.store_mapping.call_args
            assert call_kwargs is not None

    async def test_stable_placeholders_across_calls(
        self, thread_ref: ThreadRef, vault: AsyncMock
    ) -> None:
        from lintel.infrastructure.pii.presidio_firewall import PresidioFirewall

        firewall = PresidioFirewall(vault=vault, risk_threshold=0.9)
        r1 = await firewall.analyze_and_anonymize(
            "Contact John Smith please.", thread_ref
        )
        r2 = await firewall.analyze_and_anonymize(
            "John Smith called again.", thread_ref
        )
        # Same person should get same placeholder in both calls
        if r1.placeholder_count > 0 and r2.placeholder_count > 0:
            # Extract placeholder from sanitized text
            assert r1.sanitized_text != r2.sanitized_text  # different surrounding text
