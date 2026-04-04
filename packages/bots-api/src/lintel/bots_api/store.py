"""In-memory bot store."""

from lintel.domain.types import Bot


class InMemoryBotStore:
    """Simple in-memory store for bots."""

    def __init__(self) -> None:
        self._bots: dict[str, Bot] = {}

    async def add(self, bot: Bot) -> None:
        self._bots[bot.bot_id] = bot

    async def get(self, bot_id: str) -> Bot | None:
        return self._bots.get(bot_id)

    async def list_all(self) -> list[Bot]:
        return list(self._bots.values())

    async def update(self, bot: Bot) -> None:
        self._bots[bot.bot_id] = bot

    async def remove(self, bot_id: str) -> None:
        del self._bots[bot_id]
