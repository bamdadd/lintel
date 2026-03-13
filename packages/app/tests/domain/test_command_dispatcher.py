"""Tests for CommandDispatcher protocol and InMemoryCommandDispatcher."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from lintel.domain.command_dispatcher import InMemoryCommandDispatcher


@dataclass(frozen=True)
class FakeCommand:
    value: str


@dataclass(frozen=True)
class AnotherCommand:
    count: int


async def test_dispatch_calls_registered_handler() -> None:
    dispatcher = InMemoryCommandDispatcher()
    results: list[str] = []

    async def handle_fake(cmd: FakeCommand) -> str:
        results.append(cmd.value)
        return f"handled:{cmd.value}"

    dispatcher.register(FakeCommand, handle_fake)
    result = await dispatcher.dispatch(FakeCommand(value="hello"))

    assert results == ["hello"]
    assert result == "handled:hello"


async def test_dispatch_raises_for_unregistered_command() -> None:
    dispatcher = InMemoryCommandDispatcher()

    with pytest.raises(ValueError, match="No handler for FakeCommand"):
        await dispatcher.dispatch(FakeCommand(value="oops"))


async def test_dispatch_multiple_command_types() -> None:
    dispatcher = InMemoryCommandDispatcher()
    fake_results: list[str] = []
    another_results: list[int] = []

    async def handle_fake(cmd: FakeCommand) -> None:
        fake_results.append(cmd.value)

    async def handle_another(cmd: AnotherCommand) -> None:
        another_results.append(cmd.count)

    dispatcher.register(FakeCommand, handle_fake)
    dispatcher.register(AnotherCommand, handle_another)

    await dispatcher.dispatch(FakeCommand(value="a"))
    await dispatcher.dispatch(AnotherCommand(count=42))

    assert fake_results == ["a"]
    assert another_results == [42]
