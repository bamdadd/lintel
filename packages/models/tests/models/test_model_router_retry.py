"""Tests for litellm call-level retry on transient auth/SSO errors."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lintel.models.router import (
    DefaultModelRouter,
    _is_transient_llm_error,
)
from lintel.models.types import ModelPolicy


class TestIsTransientLlmError:
    def test_sso_token_expired(self) -> None:
        exc = Exception(
            "litellm.APIConnectionError: Error when retrieving token from sso: "
            "Token has expired and refresh failed"
        )
        assert _is_transient_llm_error(exc) is True

    def test_token_expired(self) -> None:
        assert _is_transient_llm_error(Exception("token expired")) is True

    def test_refresh_failed(self) -> None:
        assert _is_transient_llm_error(Exception("refresh failed")) is True

    def test_sso_keyword(self) -> None:
        assert _is_transient_llm_error(Exception("SSO auth error")) is True

    def test_api_connection_error(self) -> None:
        assert _is_transient_llm_error(Exception("APIConnectionError")) is True

    def test_rate_limit(self) -> None:
        assert _is_transient_llm_error(Exception("rate limit exceeded (429)")) is True

    def test_503_error(self) -> None:
        assert _is_transient_llm_error(Exception("HTTP 503 Service Unavailable")) is True

    def test_non_transient_error(self) -> None:
        assert _is_transient_llm_error(Exception("validation error: bad input")) is False

    def test_permission_denied(self) -> None:
        assert _is_transient_llm_error(Exception("permission denied")) is False


def _mock_response() -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = "ok"
    resp.choices[0].message.tool_calls = None
    resp.usage.prompt_tokens = 10
    resp.usage.completion_tokens = 5
    resp.model = "test/model"
    return resp


class TestLitellmRetry:
    async def test_succeeds_on_first_try(self) -> None:
        router = DefaultModelRouter(enable_cache=False)
        policy = ModelPolicy("openai", "gpt-4o", 4096, 0.0)

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=_mock_response()):
            result = await router.call_model(policy, [{"role": "user", "content": "hi"}])
            assert result["content"] == "ok"

    async def test_retries_on_transient_sso_error(self) -> None:
        router = DefaultModelRouter(enable_cache=False)
        policy = ModelPolicy("openai", "gpt-4o", 4096, 0.0)

        mock_acompletion = AsyncMock(
            side_effect=[
                Exception("APIConnectionError: Token has expired and refresh failed"),
                _mock_response(),
            ]
        )

        with (
            patch("litellm.acompletion", mock_acompletion),
            patch("lintel.models.router.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await router.call_model(policy, [{"role": "user", "content": "hi"}])
            assert result["content"] == "ok"
            assert mock_acompletion.call_count == 2

    async def test_does_not_retry_non_transient_error(self) -> None:
        router = DefaultModelRouter(enable_cache=False)
        policy = ModelPolicy("openai", "gpt-4o", 4096, 0.0)

        mock_acompletion = AsyncMock(
            side_effect=Exception("validation error: missing required field")
        )

        with (
            patch("litellm.acompletion", mock_acompletion),
            pytest.raises(Exception, match="validation error"),
        ):
            await router.call_model(policy, [{"role": "user", "content": "hi"}])
        assert mock_acompletion.call_count == 1

    async def test_exhausts_retries_then_raises(self) -> None:
        router = DefaultModelRouter(enable_cache=False)
        policy = ModelPolicy("openai", "gpt-4o", 4096, 0.0)

        sso_error = Exception("SSO token expired")
        mock_acompletion = AsyncMock(side_effect=sso_error)

        with (
            patch("litellm.acompletion", mock_acompletion),
            patch("lintel.models.router.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(Exception, match="SSO token expired"),
        ):
            await router.call_model(policy, [{"role": "user", "content": "hi"}])
        # 1 initial + 2 retries = 3 total
        assert mock_acompletion.call_count == 3

    async def test_retry_backoff_increases(self) -> None:
        router = DefaultModelRouter(enable_cache=False)
        policy = ModelPolicy("openai", "gpt-4o", 4096, 0.0)

        mock_acompletion = AsyncMock(
            side_effect=[
                Exception("SSO token expired"),
                Exception("SSO token expired"),
                _mock_response(),
            ]
        )
        mock_sleep = AsyncMock()

        with (
            patch("litellm.acompletion", mock_acompletion),
            patch("lintel.models.router.asyncio.sleep", mock_sleep),
        ):
            await router.call_model(policy, [{"role": "user", "content": "hi"}])
            # First retry: 5.0 * 2^0 = 5.0, second: 5.0 * 2^1 = 10.0
            assert mock_sleep.call_count == 2
            assert mock_sleep.call_args_list[0].args[0] == pytest.approx(5.0)
            assert mock_sleep.call_args_list[1].args[0] == pytest.approx(10.0)
