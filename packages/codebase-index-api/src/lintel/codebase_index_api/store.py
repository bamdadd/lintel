"""In-memory codebase index store."""

from __future__ import annotations

from typing import Any


class InMemoryCodebaseIndexStore:
    """Simple in-memory store for codebase indices and entries."""

    def __init__(self) -> None:
        self._indices: dict[str, dict[str, Any]] = {}
        self._entries: dict[str, dict[str, Any]] = {}

    # --- Index CRUD ---

    async def add_index(self, data: dict[str, Any]) -> dict[str, Any]:
        self._indices[data["index_id"]] = data
        return data

    async def get_index(self, index_id: str) -> dict[str, Any] | None:
        return self._indices.get(index_id)

    async def list_indices(self) -> list[dict[str, Any]]:
        return list(self._indices.values())

    async def list_indices_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [d for d in self._indices.values() if d.get("project_id") == project_id]

    async def update_index(self, index_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        existing = self._indices.get(index_id)
        if existing is None:
            return None
        merged = {**existing, **data}
        self._indices[index_id] = merged
        return merged

    async def remove_index(self, index_id: str) -> bool:
        removed = self._indices.pop(index_id, None) is not None
        # Also remove associated entries
        self._entries = {
            eid: e for eid, e in self._entries.items() if e.get("index_id") != index_id
        }
        return removed

    # --- Entry CRUD ---

    async def add_entry(self, data: dict[str, Any]) -> dict[str, Any]:
        self._entries[data["entry_id"]] = data
        return data

    async def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        return self._entries.get(entry_id)

    async def list_entries_by_index(self, index_id: str) -> list[dict[str, Any]]:
        return [e for e in self._entries.values() if e.get("index_id") == index_id]

    # --- Search ---

    async def search(self, index_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Naive keyword search — real implementation would use vector similarity."""
        results: list[dict[str, Any]] = []
        q_lower = query.lower()
        for entry in self._entries.values():
            if entry.get("index_id") != index_id:
                continue
            content = entry.get("content", "").lower()
            if q_lower in content:
                results.append(
                    {
                        "entry_id": entry["entry_id"],
                        "index_id": entry["index_id"],
                        "file_path": entry.get("file_path", ""),
                        "content": entry.get("content", ""),
                        "score": 1.0,
                        "language": entry.get("language", ""),
                        "start_line": entry.get("start_line", 0),
                        "end_line": entry.get("end_line", 0),
                    }
                )
            if len(results) >= limit:
                break
        return results
