"""In-memory pipeline store and StoreProvider instance."""

from lintel.api_support.provider import StoreProvider
from lintel.workflows.types import PipelineRun


class InMemoryPipelineStore:
    """Simple in-memory store for pipeline runs."""

    def __init__(self) -> None:
        self._runs: dict[str, PipelineRun] = {}

    async def add(self, run: PipelineRun) -> None:
        self._runs[run.run_id] = run

    async def get(self, run_id: str) -> PipelineRun | None:
        return self._runs.get(run_id)

    async def list_all(
        self,
        *,
        project_id: str | None = None,
    ) -> list[PipelineRun]:
        runs = list(self._runs.values())
        if project_id is not None:
            runs = [r for r in runs if r.project_id == project_id]
        return runs

    async def update(self, run: PipelineRun) -> None:
        self._runs[run.run_id] = run

    async def remove(self, run_id: str) -> None:
        del self._runs[run_id]


pipeline_store_provider: StoreProvider[InMemoryPipelineStore] = StoreProvider()
