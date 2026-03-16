"""ArtifactStore protocol and ArtifactRef model for abstract artifact storage."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel


class ArtifactRef(BaseModel):
    """Reference to a stored artifact with storage metadata."""

    artifact_id: str
    storage_backend: Literal["postgres", "s3"]
    location: str
    size_bytes: int
    content_type: str
    pipeline_run_id: str


@runtime_checkable
class ArtifactStore(Protocol):
    """Abstract artifact content storage.

    Implementations decide where to persist artifact bytes (inline in Postgres
    or in an object store like S3/MinIO) and record metadata so content can be
    retrieved later.
    """

    async def store(
        self,
        artifact_id: str,
        content: bytes,
        metadata: dict[str, object],
    ) -> str:
        """Persist artifact content and return a location URI."""
        ...

    async def retrieve(self, artifact_id: str) -> bytes:
        """Fetch artifact content by ID."""
        ...

    async def list_refs(self, pipeline_run_id: str) -> list[ArtifactRef]:
        """List artifact references for a pipeline run."""
        ...
