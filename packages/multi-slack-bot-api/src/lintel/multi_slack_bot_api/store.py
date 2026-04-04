"""In-memory store for Slack bots."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class BotScope(StrEnum):
    chat_write = "chat:write"
    channels_read = "channels:read"
    channels_history = "channels:history"
    commands = "commands"
    reactions_read = "reactions:read"
    reactions_write = "reactions:write"
    files_read = "files:read"
    files_write = "files:write"
    users_read = "users:read"


@dataclasses.dataclass
class SlackBot:
    bot_id: str = dataclasses.field(default_factory=lambda: uuid4().hex)
    name: str = ""
    workspace_id: str = ""
    bot_token: str = ""
    signing_secret: str = ""
    app_id: str = ""
    scopes: list[str] = dataclasses.field(default_factory=list)
    project_bindings: list[str] = dataclasses.field(default_factory=list)
    workflow_bindings: list[str] = dataclasses.field(default_factory=list)
    channel_bindings: list[str] = dataclasses.field(default_factory=list)
    enabled: bool = True
    created_at: str = dataclasses.field(default_factory=lambda: datetime.now(tz=UTC).isoformat())


class InMemorySlackBotStore:
    """Simple in-memory store for Slack bots."""

    def __init__(self) -> None:
        self._bots: dict[str, SlackBot] = {}

    async def add(self, bot: SlackBot) -> None:
        if bot.bot_id in self._bots:
            msg = f"SlackBot {bot.bot_id} already exists"
            raise KeyError(msg)
        self._bots[bot.bot_id] = bot

    async def get(self, bot_id: str) -> SlackBot | None:
        return self._bots.get(bot_id)

    async def list_all(self, workspace_id: str | None = None) -> list[SlackBot]:
        items = list(self._bots.values())
        if workspace_id is not None:
            items = [b for b in items if b.workspace_id == workspace_id]
        return items

    async def update(self, bot_id: str, fields: dict[str, object]) -> SlackBot | None:
        bot = self._bots.get(bot_id)
        if bot is None:
            return None
        updated = dataclasses.replace(bot, **fields)  # type: ignore[arg-type]
        self._bots[bot_id] = updated
        return updated

    async def find_by_signing_secret(self, signing_secret: str) -> SlackBot | None:
        for bot in self._bots.values():
            if bot.signing_secret == signing_secret and bot.enabled:
                return bot
        return None

    async def find_by_token(self, bot_token: str) -> SlackBot | None:
        for bot in self._bots.values():
            if bot.bot_token == bot_token and bot.enabled:
                return bot
        return None

    async def remove(self, bot_id: str) -> bool:
        if bot_id not in self._bots:
            return False
        del self._bots[bot_id]
        return True
