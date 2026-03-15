"""In-memory variable store."""

from lintel.domain.types import Variable


class InMemoryVariableStore:
    """Simple in-memory store for variables."""

    def __init__(self) -> None:
        self._variables: dict[str, Variable] = {}

    async def add(self, variable: Variable) -> None:
        self._variables[variable.variable_id] = variable

    async def get(self, variable_id: str) -> Variable | None:
        return self._variables.get(variable_id)

    async def list_all(
        self,
        environment_id: str | None = None,
    ) -> list[Variable]:
        items = list(self._variables.values())
        if environment_id is not None:
            items = [v for v in items if v.environment_id == environment_id]
        return items

    async def update(self, variable: Variable) -> None:
        if variable.variable_id not in self._variables:
            msg = f"Variable {variable.variable_id} not found"
            raise KeyError(msg)
        self._variables[variable.variable_id] = variable

    async def remove(self, variable_id: str) -> None:
        if variable_id not in self._variables:
            msg = f"Variable {variable_id} not found"
            raise KeyError(msg)
        del self._variables[variable_id]
