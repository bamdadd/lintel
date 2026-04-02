"""Tests for architecture decision domain model."""

from __future__ import annotations

import pytest

from lintel.domain.architecture import ADRRegistry, ADRStatus, ArchitectureLayer


class TestADRRegistry:
    def test_propose_creates_adr(self) -> None:
        reg = ADRRegistry()
        adr = reg.propose("Use PostgreSQL", "Need relational DB", "PostgreSQL")
        assert adr.title == "Use PostgreSQL"
        assert adr.status == ADRStatus.PROPOSED
        assert adr.context == "Need relational DB"
        assert adr.decision == "PostgreSQL"

    def test_accept(self) -> None:
        reg = ADRRegistry()
        adr = reg.propose("Use PostgreSQL", "Need relational DB", "PostgreSQL")
        accepted = reg.accept(adr.adr_id)
        assert accepted.status == ADRStatus.ACCEPTED
        assert accepted.adr_id == adr.adr_id

    def test_deprecate(self) -> None:
        reg = ADRRegistry()
        adr = reg.propose("Use MySQL", "Legacy", "MySQL")
        deprecated = reg.deprecate(adr.adr_id, "Replaced by PostgreSQL")
        assert deprecated.status == ADRStatus.DEPRECATED
        assert deprecated.consequences == "Replaced by PostgreSQL"

    def test_supersede(self) -> None:
        reg = ADRRegistry()
        old = reg.propose("Use MySQL", "Legacy", "MySQL")
        new = reg.propose("Use PostgreSQL", "Better", "PostgreSQL")
        superseded = reg.supersede(old.adr_id, new.adr_id)
        assert superseded.status == ADRStatus.SUPERSEDED
        assert superseded.superseded_by == new.adr_id

    def test_supersede_nonexistent_new_raises(self) -> None:
        reg = ADRRegistry()
        adr = reg.propose("Use MySQL", "Legacy", "MySQL")
        with pytest.raises(KeyError):
            reg.supersede(adr.adr_id, "nonexistent-id")

    def test_get_returns_none_for_missing(self) -> None:
        reg = ADRRegistry()
        assert reg.get("no-such-id") is None

    def test_list_all(self) -> None:
        reg = ADRRegistry()
        reg.propose("A", "", "")
        reg.propose("B", "", "")
        assert len(reg.list()) == 2

    def test_list_with_filter(self) -> None:
        reg = ADRRegistry()
        adr = reg.propose("A", "", "")
        reg.propose("B", "", "")
        reg.accept(adr.adr_id)
        assert len(reg.list(status_filter=ADRStatus.ACCEPTED)) == 1
        assert len(reg.list(status_filter=ADRStatus.PROPOSED)) == 1

    def test_search(self) -> None:
        reg = ADRRegistry()
        reg.propose("Use PostgreSQL", "relational database", "pg")
        reg.propose("Use Redis", "caching layer", "redis")
        results = reg.search("postgres")
        assert len(results) == 1
        assert results[0].title == "Use PostgreSQL"

    def test_search_case_insensitive(self) -> None:
        reg = ADRRegistry()
        reg.propose("Use PostgreSQL", "relational", "pg")
        assert len(reg.search("POSTGRESQL")) == 1

    def test_propose_with_alternatives(self) -> None:
        reg = ADRRegistry()
        adr = reg.propose("Use PG", "", "", alternatives=("MySQL", "SQLite"))
        assert adr.alternatives == ("MySQL", "SQLite")

    def test_propose_with_author(self) -> None:
        reg = ADRRegistry()
        adr = reg.propose("Use PG", "", "", author="alice")
        assert adr.author == "alice"

    def test_accept_nonexistent_raises(self) -> None:
        reg = ADRRegistry()
        with pytest.raises(KeyError):
            reg.accept("no-such-id")


class TestArchitectureLayer:
    def test_add_and_get_layer(self) -> None:
        reg = ADRRegistry()
        layer = ArchitectureLayer(
            layer_name="data",
            components=("postgres", "redis"),
            decisions=("adr-1",),
            constraints=("must encrypt at rest",),
        )
        reg.add_layer(layer)
        retrieved = reg.get_layer("data")
        assert retrieved is not None
        assert retrieved.layer_name == "data"
        assert retrieved.components == ("postgres", "redis")

    def test_get_layer_missing(self) -> None:
        reg = ADRRegistry()
        assert reg.get_layer("missing") is None
