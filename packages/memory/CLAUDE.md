# lintel-memory

Memory domain logic package for the Lintel project.

## Overview

This package provides the memory subsystem: vector store abstraction, embedding generation,
and the `MemoryService` coordinator that ties together Postgres persistence, vector search,
and embedding pipelines.

## Key Components

- **MemoryService** -- main entry point. Orchestrates storing, recalling, and consolidating
  memories across vector and relational stores.
- **MemoryFact / MemoryChunk** -- Pydantic domain models representing stored facts and
  scored search results.
- **VectorStoreProvider** -- abstract interface for vector databases (Qdrant implementation
  included).
- **EmbeddingService** -- generates embeddings via OpenAI or Ollama APIs using raw httpx
  calls (no openai SDK dependency).
- **MemoryRepository** -- asyncpg-backed Postgres persistence for memory facts.

## Package Layout

Source lives under `src/lintel/memory/` (implicit namespace package -- no `__init__.py` in
`src/lintel/`). Follows ADR-001.
