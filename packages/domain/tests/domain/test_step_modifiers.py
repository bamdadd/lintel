"""Tests for step modifiers (ensure, on_failure, try)."""

from __future__ import annotations

import pytest

from lintel.domain.step_modifiers import with_ensure, with_on_failure, with_try


async def test_with_ensure_runs_cleanup_on_success() -> None:
    calls: list[str] = []

    async def main(state: dict) -> dict:
        calls.append("main")
        return {**state, "result": "ok"}

    async def cleanup(state: dict) -> dict:
        calls.append("cleanup")
        return state

    wrapped = with_ensure(main, cleanup)
    result = await wrapped({"input": "x"})

    assert calls == ["main", "cleanup"]
    assert result["result"] == "ok"


async def test_with_ensure_runs_cleanup_on_failure() -> None:
    calls: list[str] = []

    async def main(state: dict) -> dict:
        calls.append("main")
        raise RuntimeError("boom")

    async def cleanup(state: dict) -> dict:
        calls.append("cleanup")
        return state

    wrapped = with_ensure(main, cleanup)
    with pytest.raises(RuntimeError, match="boom"):
        await wrapped({"input": "x"})

    assert calls == ["main", "cleanup"]


async def test_with_on_failure_runs_fallback_on_error() -> None:
    async def main(state: dict) -> dict:
        raise RuntimeError("fail")

    async def fallback(state: dict) -> dict:
        return {**state, "fallback": True}

    wrapped = with_on_failure(main, fallback)
    result = await wrapped({"input": "x"})

    assert result["fallback"] is True


async def test_with_on_failure_skips_fallback_on_success() -> None:
    async def main(state: dict) -> dict:
        return {**state, "ok": True}

    async def fallback(state: dict) -> dict:
        return {**state, "fallback": True}

    wrapped = with_on_failure(main, fallback)
    result = await wrapped({"input": "x"})

    assert result["ok"] is True
    assert "fallback" not in result


async def test_with_try_suppresses_errors() -> None:
    async def main(state: dict) -> dict:
        raise RuntimeError("ignored")

    wrapped = with_try(main)
    result = await wrapped({"input": "x"})

    assert result == {"input": "x"}


async def test_with_try_passes_through_on_success() -> None:
    async def main(state: dict) -> dict:
        return {**state, "done": True}

    wrapped = with_try(main)
    result = await wrapped({"input": "x"})

    assert result["done"] is True
