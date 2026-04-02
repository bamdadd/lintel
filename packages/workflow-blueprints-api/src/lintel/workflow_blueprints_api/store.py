"""In-memory workflow blueprint store."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.domain.types import WorkflowBlueprint


def _blueprint_to_dict(bp: WorkflowBlueprint) -> dict[str, Any]:
    """Convert a WorkflowBlueprint dataclass to a JSON-friendly dict."""
    d = asdict(bp)
    d["nodes"] = [dict(n) for n in d["nodes"]]
    for n in d["nodes"]:
        n["depends_on"] = list(n["depends_on"])
    return d


class InMemoryWorkflowBlueprintStore:
    """Simple in-memory store for workflow blueprints."""

    def __init__(self) -> None:
        self._blueprints: dict[str, WorkflowBlueprint] = {}

    async def get(self, blueprint_id: str) -> dict[str, Any] | None:
        bp = self._blueprints.get(blueprint_id)
        if bp is None:
            return None
        return _blueprint_to_dict(bp)

    async def list_all(self) -> list[dict[str, Any]]:
        return [_blueprint_to_dict(bp) for bp in self._blueprints.values()]

    async def add(self, bp: WorkflowBlueprint) -> dict[str, Any]:
        self._blueprints[bp.blueprint_id] = bp
        return _blueprint_to_dict(bp)

    async def update(self, blueprint_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        bp = self._blueprints.get(blueprint_id)
        if bp is None:
            return None
        data = asdict(bp)
        data.update(updates)
        # Reconstruct tuples from lists
        if "nodes" in updates:
            from lintel.domain.types import BlueprintNode

            data["nodes"] = tuple(
                BlueprintNode(
                    node_id=n["node_id"],
                    name=n["name"],
                    node_type=n["node_type"],
                    description=n.get("description", ""),
                    config=n.get("config", {}),
                    depends_on=tuple(n.get("depends_on", ())),
                    timeout_seconds=n.get("timeout_seconds", 300),
                    retry_count=n.get("retry_count", 0),
                )
                for n in updates["nodes"]
            )
        elif isinstance(data["nodes"], list):
            data["nodes"] = tuple(data["nodes"])
        updated = WorkflowBlueprint(**data)
        self._blueprints[blueprint_id] = updated
        return _blueprint_to_dict(updated)

    async def remove(self, blueprint_id: str) -> bool:
        if blueprint_id not in self._blueprints:
            return False
        del self._blueprints[blueprint_id]
        return True
