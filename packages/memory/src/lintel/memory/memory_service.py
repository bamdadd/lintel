"""MemoryService -- main coordinator for the memory subsystem."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog

from lintel.memory.embedding_service import EmbeddingService
from lintel.memory.models import MemoryChunk, MemoryFact, MemoryType
from lintel.memory.providers.base import VectorStoreProvider
from lintel.memory.repository import MemoryRepository

log = structlog.get_logger(__name__)


class MemoryService:
    """Orchestrates embedding generation, vector storage, and Postgres persistence."""

    COLLECTIONS: list[str] = [
        "long_term_memory",
        "episodic_memory",
        "project_facts",
    ]
    VECTOR_SIZE: int = 1536  # text-embedding-3-small dimensions

    def __init__(
        self,
        repository: MemoryRepository,
        vector_store: VectorStoreProvider,
        embedding_service: EmbeddingService,
    ) -> None:
        self._repository = repository
        self._vector_store = vector_store
        self._embedding_service = embedding_service

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Ensure all required vector-store collections exist."""
        for name in self.COLLECTIONS:
            await self._vector_store.ensure_collection(name, self.VECTOR_SIZE)
        log.info("memory_service_initialized", collections=self.COLLECTIONS)

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    async def store_memory(
        self,
        project_id: UUID,
        content: str,
        memory_type: MemoryType,
        fact_type: str,
        source_workflow_id: UUID | None = None,
    ) -> MemoryFact:
        """Generate an embedding, persist the fact, and index it."""
        embedding = await self._embedding_service.embed(content)

        fact_id = uuid4()
        embedding_id = str(fact_id)

        fact = MemoryFact(
            id=fact_id,
            project_id=project_id,
            memory_type=memory_type,
            fact_type=fact_type,
            content=content,
            embedding_id=embedding_id,
            source_workflow_id=source_workflow_id,
        )

        collection = self._collection_for(memory_type)
        await self._vector_store.store_embedding(
            collection=collection,
            id=embedding_id,
            vector=embedding,
            payload={
                "project_id": str(project_id),
                "fact_id": str(fact_id),
                "fact_type": fact_type,
                "memory_type": memory_type.value,
            },
        )

        fact = await self._repository.save(fact)
        log.info(
            "memory_stored",
            fact_id=str(fact_id),
            memory_type=memory_type.value,
            collection=collection,
        )
        return fact

    async def recall(
        self,
        project_id: UUID,
        query: str,
        memory_type: MemoryType | None = None,
        top_k: int = 5,
    ) -> list[MemoryChunk]:
        """Search for memories relevant to *query*."""
        query_embedding = await self._embedding_service.embed(query)

        collections = (
            [self._collection_for(memory_type)] if memory_type is not None else self.COLLECTIONS
        )

        all_chunks: list[MemoryChunk] = []
        filters = {"project_id": str(project_id)}

        for collection in collections:
            scored_points = await self._vector_store.search(
                collection=collection,
                query_vector=query_embedding,
                top_k=top_k,
                filters=filters,
            )

            for point in scored_points:
                fact_id_str = point.payload.get("fact_id")
                if fact_id_str is None:
                    continue
                fact = await self._repository.get(UUID(fact_id_str))
                if fact is None:
                    continue
                all_chunks.append(MemoryChunk(fact=fact, score=point.score, rank=0))

        # Sort by descending score and assign ranks.
        all_chunks.sort(key=lambda c: c.score, reverse=True)
        for rank, chunk in enumerate(all_chunks, start=1):
            chunk.rank = rank

        # Trim to top_k after merging across collections.
        result = all_chunks[:top_k]
        log.info(
            "memory_recall",
            project_id=str(project_id),
            query_len=len(query),
            results=len(result),
        )
        return result

    async def consolidate_from_workflow(
        self,
        workflow_id: UUID,
        project_id: UUID,
        summary_text: str,
    ) -> list[MemoryFact]:
        """Store or deduplicate a workflow summary as episodic memory.

        Near-duplicates (cosine similarity > 0.95) are updated in place
        rather than creating a new entry.
        """
        embedding = await self._embedding_service.embed(summary_text)
        collection = self._collection_for(MemoryType.EPISODIC)

        # Check for near-duplicates.
        candidates = await self._vector_store.search(
            collection=collection,
            query_vector=embedding,
            top_k=1,
            filters={"project_id": str(project_id)},
        )

        results: list[MemoryFact] = []

        if candidates and candidates[0].score > 0.95:
            # Update the existing fact.
            existing_id = candidates[0].payload.get("fact_id")
            if existing_id:
                existing = await self._repository.get(UUID(existing_id))
                if existing is not None:
                    existing.content = summary_text
                    existing.source_workflow_id = workflow_id
                    existing.updated_at = datetime.now(UTC)
                    await self._repository.update(existing)

                    # Update the embedding in the vector store.
                    await self._vector_store.store_embedding(
                        collection=collection,
                        id=existing.embedding_id or str(existing.id),
                        vector=embedding,
                        payload={
                            "project_id": str(project_id),
                            "fact_id": str(existing.id),
                            "fact_type": existing.fact_type,
                            "memory_type": MemoryType.EPISODIC.value,
                        },
                    )
                    log.info(
                        "memory_consolidated_update",
                        fact_id=str(existing.id),
                        workflow_id=str(workflow_id),
                    )
                    results.append(existing)
                    return results

        # No near-duplicate -- store as new episodic memory.
        fact = await self.store_memory(
            project_id=project_id,
            content=summary_text,
            memory_type=MemoryType.EPISODIC,
            fact_type="workflow_summary",
            source_workflow_id=workflow_id,
        )
        results.append(fact)
        log.info(
            "memory_consolidated_new",
            fact_id=str(fact.id),
            workflow_id=str(workflow_id),
        )
        return results

    async def delete_memory(self, memory_id: UUID) -> bool:
        """Remove a memory from both Postgres and the vector store."""
        fact = await self._repository.get(memory_id)
        if fact is None:
            log.warning("memory_delete_not_found", memory_id=str(memory_id))
            return False

        collection = self._collection_for(fact.memory_type)
        if fact.embedding_id:
            await self._vector_store.delete(collection, fact.embedding_id)

        deleted = await self._repository.delete(memory_id)
        log.info("memory_deleted", memory_id=str(memory_id), deleted=deleted)
        return deleted

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collection_for(memory_type: MemoryType) -> str:
        mapping = {
            MemoryType.LONG_TERM: "long_term_memory",
            MemoryType.EPISODIC: "episodic_memory",
        }
        return mapping.get(memory_type, "project_facts")
