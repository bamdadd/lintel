"""Postgres persistence for memory facts using asyncpg."""

from __future__ import annotations

from uuid import UUID  # noqa: TC003

import asyncpg  # noqa: TC002
import structlog

from lintel.memory.models import MemoryFact, MemoryType

log = structlog.get_logger(__name__)


class MemoryRepository:
    """CRUD operations for :class:`MemoryFact` rows in Postgres."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save(self, fact: MemoryFact) -> MemoryFact:
        """Insert a new memory fact and return it."""
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                """
                INSERT INTO memory_facts
                    (id, project_id, memory_type, fact_type, content,
                     embedding_id, source_workflow_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                fact.id,
                fact.project_id,
                fact.memory_type.value,
                fact.fact_type,
                fact.content,
                fact.embedding_id,
                fact.source_workflow_id,
                fact.created_at,
                fact.updated_at,
            )
        log.debug("memory_fact_saved", fact_id=str(fact.id))
        return fact

    async def get(self, fact_id: UUID) -> MemoryFact | None:
        """Fetch a single fact by primary key."""
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            row = await conn.fetchrow(
                "SELECT * FROM memory_facts WHERE id = $1",
                fact_id,
            )
        if row is None:
            return None
        return self._row_to_fact(row)

    async def list_by_project(
        self,
        project_id: UUID,
        memory_type: MemoryType | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MemoryFact], int]:
        """Return a page of facts for *project_id* and the total count."""
        offset = (page - 1) * page_size

        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            if memory_type is not None:
                rows = await conn.fetch(
                    """
                    SELECT * FROM memory_facts
                    WHERE project_id = $1 AND memory_type = $2
                    ORDER BY created_at DESC
                    LIMIT $3 OFFSET $4
                    """,
                    project_id,
                    memory_type.value,
                    page_size,
                    offset,
                )
                total = await conn.fetchval(
                    """
                    SELECT count(*) FROM memory_facts
                    WHERE project_id = $1 AND memory_type = $2
                    """,
                    project_id,
                    memory_type.value,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM memory_facts
                    WHERE project_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    project_id,
                    page_size,
                    offset,
                )
                total = await conn.fetchval(
                    """
                    SELECT count(*) FROM memory_facts
                    WHERE project_id = $1
                    """,
                    project_id,
                )

        facts = [self._row_to_fact(r) for r in rows]
        return facts, int(total)

    async def delete(self, fact_id: UUID) -> bool:
        """Delete a fact by id.  Returns ``True`` if a row was removed."""
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            result = await conn.execute(
                "DELETE FROM memory_facts WHERE id = $1",
                fact_id,
            )
        deleted: bool = result == "DELETE 1"
        log.debug("memory_fact_deleted", fact_id=str(fact_id), deleted=deleted)
        return deleted

    async def find_by_embedding_id(self, embedding_id: str) -> MemoryFact | None:
        """Look up a fact by its vector-store embedding id."""
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            row = await conn.fetchrow(
                "SELECT * FROM memory_facts WHERE embedding_id = $1",
                embedding_id,
            )
        if row is None:
            return None
        return self._row_to_fact(row)

    async def update(self, fact: MemoryFact) -> MemoryFact:
        """Persist changes to an existing fact."""
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                """
                UPDATE memory_facts
                SET project_id = $2,
                    memory_type = $3,
                    fact_type = $4,
                    content = $5,
                    embedding_id = $6,
                    source_workflow_id = $7,
                    updated_at = $8
                WHERE id = $1
                """,
                fact.id,
                fact.project_id,
                fact.memory_type.value,
                fact.fact_type,
                fact.content,
                fact.embedding_id,
                fact.source_workflow_id,
                fact.updated_at,
            )
        log.debug("memory_fact_updated", fact_id=str(fact.id))
        return fact

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_fact(row: asyncpg.Record) -> MemoryFact:
        return MemoryFact(
            id=row["id"],
            project_id=row["project_id"],
            memory_type=MemoryType(row["memory_type"]),
            fact_type=row["fact_type"],
            content=row["content"],
            embedding_id=row["embedding_id"],
            source_workflow_id=row["source_workflow_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
