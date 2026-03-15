"""Tests for lintel.memory.models."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import ValidationError
import pytest

from lintel.memory.models import (
    MemoryChunk,
    MemoryFact,
    MemorySearchResult,
    MemoryType,
    ScoredPoint,
)

# ── MemoryType ──────────────────────────────────────────────────────


class TestMemoryType:
    def test_long_term_value(self):
        assert MemoryType.LONG_TERM.value == "long_term"

    def test_episodic_value(self):
        assert MemoryType.EPISODIC.value == "episodic"

    def test_is_str_enum(self):
        assert isinstance(MemoryType.LONG_TERM, str)
        assert MemoryType.LONG_TERM == "long_term"

    def test_from_value(self):
        assert MemoryType("long_term") is MemoryType.LONG_TERM
        assert MemoryType("episodic") is MemoryType.EPISODIC

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            MemoryType("invalid_type")


# ── MemoryFact ──────────────────────────────────────────────────────


class TestMemoryFact:
    def test_creation_with_all_fields(self):
        project_id = uuid4()
        fact_id = uuid4()
        workflow_id = uuid4()
        now = datetime.now(UTC)

        fact = MemoryFact(
            id=fact_id,
            project_id=project_id,
            memory_type=MemoryType.LONG_TERM,
            fact_type="architecture_decision",
            content="We use microservices",
            embedding_id="emb-123",
            source_workflow_id=workflow_id,
            created_at=now,
            updated_at=now,
        )

        assert fact.id == fact_id
        assert fact.project_id == project_id
        assert fact.memory_type == MemoryType.LONG_TERM
        assert fact.fact_type == "architecture_decision"
        assert fact.content == "We use microservices"
        assert fact.embedding_id == "emb-123"
        assert fact.source_workflow_id == workflow_id
        assert fact.created_at == now
        assert fact.updated_at == now

    def test_optional_fields_default_to_none(self):
        fact = MemoryFact(
            project_id=uuid4(),
            memory_type=MemoryType.EPISODIC,
            fact_type="test",
            content="test content",
        )

        assert fact.embedding_id is None
        assert fact.source_workflow_id is None

    def test_id_auto_generated(self):
        fact = MemoryFact(
            project_id=uuid4(),
            memory_type=MemoryType.LONG_TERM,
            fact_type="test",
            content="test",
        )
        assert isinstance(fact.id, UUID)

    def test_timestamps_auto_generated(self):
        fact = MemoryFact(
            project_id=uuid4(),
            memory_type=MemoryType.LONG_TERM,
            fact_type="test",
            content="test",
        )
        assert isinstance(fact.created_at, datetime)
        assert isinstance(fact.updated_at, datetime)

    def test_invalid_memory_type_rejected(self):
        with pytest.raises(ValidationError):
            MemoryFact(
                project_id=uuid4(),
                memory_type="not_a_valid_type",  # type: ignore[arg-type]
                fact_type="test",
                content="test",
            )

    def test_missing_required_fields_rejected(self):
        with pytest.raises(ValidationError):
            MemoryFact(
                memory_type=MemoryType.LONG_TERM,
                fact_type="test",
                # missing project_id and content
            )  # type: ignore[call-arg]


# ── MemoryChunk ─────────────────────────────────────────────────────


class TestMemoryChunk:
    def test_creation(self):
        fact = MemoryFact(
            project_id=uuid4(),
            memory_type=MemoryType.EPISODIC,
            fact_type="summary",
            content="workflow completed",
        )
        chunk = MemoryChunk(fact=fact, score=0.92, rank=1)

        assert chunk.fact is fact
        assert chunk.score == 0.92
        assert chunk.rank == 1

    def test_score_is_float(self):
        fact = MemoryFact(
            project_id=uuid4(),
            memory_type=MemoryType.EPISODIC,
            fact_type="note",
            content="x",
        )
        chunk = MemoryChunk(fact=fact, score=1, rank=0)
        assert isinstance(chunk.score, float)


# ── ScoredPoint ─────────────────────────────────────────────────────


class TestScoredPoint:
    def test_creation(self):
        sp = ScoredPoint(
            id="abc-123",
            score=0.85,
            payload={"project_id": "p1", "fact_type": "note"},
        )
        assert sp.id == "abc-123"
        assert sp.score == 0.85
        assert sp.payload == {"project_id": "p1", "fact_type": "note"}

    def test_empty_payload(self):
        sp = ScoredPoint(id="x", score=0.0, payload={})
        assert sp.payload == {}


# ── MemorySearchResult ──────────────────────────────────────────────


class TestMemorySearchResult:
    def test_creation(self):
        fact = MemoryFact(
            project_id=uuid4(),
            memory_type=MemoryType.LONG_TERM,
            fact_type="test",
            content="hello",
        )
        chunk = MemoryChunk(fact=fact, score=0.9, rank=1)
        result = MemorySearchResult(
            query="find hello",
            chunks=[chunk],
            total=1,
        )

        assert result.query == "find hello"
        assert len(result.chunks) == 1
        assert result.total == 1

    def test_empty_results(self):
        result = MemorySearchResult(query="nothing", chunks=[], total=0)
        assert result.chunks == []
        assert result.total == 0
