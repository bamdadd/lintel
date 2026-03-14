"""Tests for DefaultModelRouter response caching."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from lintel.contracts.types import ModelPolicy
from lintel.models.router import DefaultModelRouter


def _policy(temperature: float = 0.0) -> ModelPolicy:
    return ModelPolicy("ollama", "llama3.1:8b", 4096, temperature)


def _messages() -> list[dict[str, str]]:
    return [{"role": "user", "content": "hello"}]


def _mock_response(content: str = "response") -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = None
    choice = MagicMock()
    choice.message = msg
    choice.delta = None
    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    resp.model = "llama3.1:8b"
    return resp


async def test_cache_hit_returns_cached_result() -> None:
    """Second identical call returns cached result without calling litellm."""
    router = DefaultModelRouter(enable_cache=True)
    policy = _policy(temperature=0.0)
    messages = _messages()

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _mock_response("hello")

        r1 = await router.call_model(policy, messages)
        r2 = await router.call_model(policy, messages)

    assert r1["content"] == "hello"
    assert r2["content"] == "hello"
    mock_llm.assert_called_once()
    assert router.cache_stats == {"hits": 1, "misses": 1, "size": 1}


async def test_cache_disabled() -> None:
    """Cache disabled means every call hits litellm."""
    router = DefaultModelRouter(enable_cache=False)
    policy = _policy(temperature=0.0)

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _mock_response()
        await router.call_model(policy, _messages())
        await router.call_model(policy, _messages())

    assert mock_llm.call_count == 2
    assert router.cache_stats["hits"] == 0


async def test_nonzero_temperature_skips_cache() -> None:
    """Non-zero temperature calls are not cached."""
    router = DefaultModelRouter(enable_cache=True)
    policy = _policy(temperature=0.7)

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _mock_response()
        await router.call_model(policy, _messages())
        await router.call_model(policy, _messages())

    assert mock_llm.call_count == 2


async def test_tool_calls_skip_cache() -> None:
    """Calls with tools are not cached."""
    router = DefaultModelRouter(enable_cache=True)
    policy = _policy(temperature=0.0)
    tools = [{"type": "function", "function": {"name": "test"}}]

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _mock_response()
        await router.call_model(policy, _messages(), tools=tools)
        await router.call_model(policy, _messages(), tools=tools)

    assert mock_llm.call_count == 2


async def test_cache_eviction() -> None:
    """Oldest entry evicted when cache is full."""
    router = DefaultModelRouter(enable_cache=True, cache_max_size=2)
    policy = _policy()

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _mock_response()

        # Fill cache with 3 different messages → oldest should be evicted
        for i in range(3):
            await router.call_model(policy, [{"role": "user", "content": f"msg{i}"}])

    assert router.cache_stats["size"] == 2


async def test_sqlite_cache_persists(tmp_path: object) -> None:
    """SQLite cache persists responses across router instances."""
    import pathlib

    db_path = str(pathlib.Path(str(tmp_path)) / "cache.db")
    policy = _policy(temperature=0.0)
    messages = _messages()

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _mock_response("persisted")
        router1 = DefaultModelRouter(enable_cache=True, cache_db_path=db_path)
        await router1.call_model(policy, messages)

    # New router instance with same DB — should find cached response
    router2 = DefaultModelRouter(enable_cache=True, cache_db_path=db_path)
    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm2:
        result = await router2.call_model(policy, messages)

    mock_llm2.assert_not_called()
    assert result["content"] == "persisted"
    assert router2.cache_stats["hits"] == 1


async def test_ollama_keep_alive_passed() -> None:
    """Ollama calls include keep_alive parameter."""
    router = DefaultModelRouter(ollama_keep_alive="45m")
    policy = _policy()

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _mock_response()
        # Disable cache so it actually calls litellm
        router._enable_cache = False
        await router.call_model(policy, _messages())

    call_kwargs = mock_llm.call_args.kwargs
    assert call_kwargs["keep_alive"] == "45m"
