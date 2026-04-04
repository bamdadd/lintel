"""In-memory frontend target store."""

from lintel.domain.types import FrontendTarget


class InMemoryFrontendTargetStore:
    """Simple in-memory store for frontend targets."""

    def __init__(self) -> None:
        self._targets: dict[str, FrontendTarget] = {}

    async def add(self, target: FrontendTarget) -> None:
        self._targets[target.target_id] = target

    async def get(self, target_id: str) -> FrontendTarget | None:
        return self._targets.get(target_id)

    async def list_all(
        self,
        project_id: str | None = None,
        platform: str | None = None,
    ) -> list[FrontendTarget]:
        items = list(self._targets.values())
        if project_id is not None:
            items = [t for t in items if t.project_id == project_id]
        if platform is not None:
            items = [t for t in items if t.platform == platform]
        return items

    async def update(self, target: FrontendTarget) -> None:
        if target.target_id not in self._targets:
            msg = f"Frontend target {target.target_id} not found"
            raise KeyError(msg)
        self._targets[target.target_id] = target

    async def remove(self, target_id: str) -> None:
        if target_id not in self._targets:
            msg = f"Frontend target {target_id} not found"
            raise KeyError(msg)
        del self._targets[target_id]
