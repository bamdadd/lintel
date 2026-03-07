"""Command dispatcher — routes commands to registered async handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class InMemoryCommandDispatcher:
    """In-memory command bus that dispatches commands to registered async handlers."""

    def __init__(self) -> None:
        self._handlers: dict[type, Callable[..., object]] = {}

    def register(self, command_type: type, handler: Callable[..., object]) -> None:
        self._handlers[command_type] = handler

    async def dispatch(self, command: object) -> object:
        handler = self._handlers.get(type(command))
        if handler is None:
            raise ValueError(f"No handler for {type(command).__name__}")
        return await handler(command)
