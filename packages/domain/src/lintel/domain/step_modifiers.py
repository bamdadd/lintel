"""Concourse-style step modifiers: ensure, on_failure, try."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine


def with_ensure(
    node_fn: Callable[..., Coroutine[object, object, dict[str, object]]],
    cleanup_fn: Callable[..., Coroutine[object, object, dict[str, object]]],
) -> Callable[..., Coroutine[object, object, dict[str, object]]]:
    """Run cleanup_fn regardless of node_fn outcome."""

    async def wrapped(state: dict[str, object]) -> dict[str, object]:
        try:
            return await node_fn(state)
        finally:
            await cleanup_fn(state)

    return wrapped


def with_on_failure(
    node_fn: Callable[..., Coroutine[object, object, dict[str, object]]],
    fallback_fn: Callable[..., Coroutine[object, object, dict[str, object]]],
) -> Callable[..., Coroutine[object, object, dict[str, object]]]:
    """Run fallback_fn only if node_fn raises."""

    async def wrapped(state: dict[str, object]) -> dict[str, object]:
        try:
            return await node_fn(state)
        except Exception:
            return await fallback_fn(state)

    return wrapped


def with_try(
    node_fn: Callable[..., Coroutine[object, object, dict[str, object]]],
) -> Callable[..., Coroutine[object, object, dict[str, object]]]:
    """Suppress errors, continue pipeline with unchanged state."""

    async def wrapped(state: dict[str, object]) -> dict[str, object]:
        try:
            return await node_fn(state)
        except Exception:
            return state

    return wrapped
