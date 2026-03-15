"""In-memory team store."""

from lintel.domain.types import Team


class InMemoryTeamStore:
    """Simple in-memory store for teams."""

    def __init__(self) -> None:
        self._teams: dict[str, Team] = {}

    async def add(self, team: Team) -> None:
        self._teams[team.team_id] = team

    async def get(self, team_id: str) -> Team | None:
        return self._teams.get(team_id)

    async def list_all(self) -> list[Team]:
        return list(self._teams.values())

    async def update(self, team: Team) -> None:
        self._teams[team.team_id] = team

    async def remove(self, team_id: str) -> None:
        del self._teams[team_id]
