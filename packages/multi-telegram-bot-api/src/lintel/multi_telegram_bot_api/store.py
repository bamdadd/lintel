"""In-memory store for Telegram bots."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from uuid import uuid4


@dataclasses.dataclass
class TelegramBot:
    bot_id: str = dataclasses.field(default_factory=lambda: uuid4().hex)
    name: str = ""
    bot_token: str = ""
    webhook_secret: str = ""
    channel_bindings: list[str] = dataclasses.field(default_factory=list)
    enabled: bool = True
    created_at: str = dataclasses.field(default_factory=lambda: datetime.now(tz=UTC).isoformat())


class InMemoryTelegramBotStore:
    """Simple in-memory store for Telegram bots."""

    def __init__(self) -> None:
        self._bots: dict[str, TelegramBot] = {}

    async def add(self, bot: TelegramBot) -> None:
        if bot.bot_id in self._bots:
            msg = f"TelegramBot {bot.bot_id} already exists"
            raise KeyError(msg)
        self._bots[bot.bot_id] = bot

    async def get(self, bot_id: str) -> TelegramBot | None:
        return self._bots.get(bot_id)

    async def list_all(self) -> list[TelegramBot]:
        return list(self._bots.values())

    async def update(self, bot_id: str, fields: dict[str, object]) -> TelegramBot | None:
        bot = self._bots.get(bot_id)
        if bot is None:
            return None
        updated = dataclasses.replace(bot, **fields)  # type: ignore[arg-type]
        self._bots[bot_id] = updated
        return updated

    async def remove(self, bot_id: str) -> bool:
        if bot_id not in self._bots:
            return False
        del self._bots[bot_id]
        return True
