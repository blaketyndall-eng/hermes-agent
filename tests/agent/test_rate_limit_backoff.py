"""Tests for W1-T04: jittered_backoff wired into auxiliary_client retry paths.

TDD: these tests are written FIRST. They will FAIL until the implementation
lands in agent/auxiliary_client.py and agent/retry_utils.py.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from agent.retry_utils import _parse_retry_after, jittered_backoff


# ---------------------------------------------------------------------------
# Unit tests for _parse_retry_after
# ---------------------------------------------------------------------------

class TestParseRetryAfter:
    """Tests for _parse_retry_after helper (integer-seconds and HTTP-date)."""

    def test_integer_seconds_string(self):
        """'Retry-After: 30' should return 30.0."""
        resp = SimpleNamespace(headers={"retry-after": "30"})
        assert _parse_retry_after(resp) == 30.0

    def test_integer_seconds_float_string(self):
        """'Retry-After: 2.5' should return 2.5."""
        resp = SimpleNamespace(headers={"retry-after": "2.5"})
        assert _parse_retry_after(resp) == 2.5

    def test_http_date_format(self):
        """HTTP-date Retry-After should return a positive float (seconds until retry)."""
        from datetime import datetime, timezone, timedelta
        future = datetime.now(tz=timezone.utc) + timedelta(seconds=10)
        http_date = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
        resp = SimpleNamespace(headers={"retry-after": http_date})
        result = _parse_retry_after(resp)
        assert result is not None
        assert 0 < result <= 15.0, f"Expected ~10s, got {result}"

    def test_none_response_returns_none(self):
        """None response should return None gracefully."""
        assert _parse_retry_after(None) is None

    def test_missing_header_returns_none(self):
        """Response with no Retry-After header should return None."""
        resp = SimpleNamespace(headers={})
        assert _parse_retry_after(resp) is None

    def test_case_insensitive_header(self):
        """Header lookup should work regardless of case."""
        resp = SimpleNamespace(headers={"Retry-After": "5"})
        assert _parse_retry_after(resp) == 5.0

    def test_invalid_value_returns_none(self):
        """Unparseable Retry-After value should return None (no crash)."""
        resp = SimpleNamespace(headers={"retry-after": "bogus-not-a-date-or-number"})
        assert _parse_retry_after(resp) is None

    def test_zero_value_returns_zero(self):
        """Retry-After: 0 is valid (server says retry immediately)."""
        resp = SimpleNamespace(headers={"retry-after": "0"})
        assert _parse_retry_after(resp) == 0.0

    def test_dict_like_headers_object(self):
        """Simulate lowercase-key dict headers (most common httpx/requests case)."""
        resp = SimpleNamespace(headers={"retry-after": "7"})
        assert _parse_retry_after(resp) == 7.0


# ---------------------------------------------------------------------------
# Integration tests: sync retry path uses time.sleep with jittered backoff
# ---------------------------------------------------------------------------

class _RateLimitError(Exception):
    """Synthetic rate-limit error whose class name triggers _is_rate_limit_error."""
    def __init__(self, msg="rate limit", retry_after_header=None):
        super().__init__(msg)
        if retry_after_header is not None:
            self.response = SimpleNamespace(headers={"retry-after": str(retry_after_header)})
        else:
            self.response = SimpleNamespace(headers={})


class TestSyncRateLimitBackoff:
    """Verify the sync credential-pool rate-limit retry block calls time.sleep
    with a non-zero jittered delay.
    """

    def _make_rate_limit_error(self, retry_after_header=None):
        """Build a mock exception that _is_rate_limit_error will recognise."""
        return _RateLimitError(retry_after_header=retry_after_header)

    def test_jittered_backoff_is_called_on_rate_limit_sync(self, monkeypatch):
        """time.sleep called with non-zero delay on 429 in sync path."""
        from agent import auxiliary_client

        sleep_calls = []
        monkeypatch.setattr("agent.auxiliary_client.time.sleep",
                            lambda d: sleep_calls.append(d))

        rate_err = self._make_rate_limit_error()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_client.chat.completions.create.side_effect = [rate_err, mock_response]

        with patch("agent.auxiliary_client._recoverable_pool_provider", return_value="test-pool"), \
             patch("agent.auxiliary_client._is_rate_limit_error",
                   side_effect=lambda e: isinstance(e, type(rate_err))), \
             patch("agent.auxiliary_client._is_auth_error", return_value=False), \
             patch("agent.auxiliary_client._is_payment_error", return_value=False), \
             patch("agent.auxiliary_client._recover_provider_pool", return_value=False), \
             patch("agent.auxiliary_client._validate_llm_response",
                   side_effect=lambda r, t: r):
            try:
                auxiliary_client._retry_rate_limit_sync(mock_client, {}, "test-task")
            except Exception:
                pass

        assert len(sleep_calls) >= 1, "time.sleep should have been called at least once"
        assert all(d > 0 for d in sleep_calls), f"All delays must be > 0, got: {sleep_calls}"

    def test_retry_after_honored_sync(self, monkeypatch):
        """Sync: Retry-After: 2.5 causes sleep >= 2.5s."""
        from agent import auxiliary_client

        sleep_calls = []
        monkeypatch.setattr("agent.auxiliary_client.time.sleep",
                            lambda d: sleep_calls.append(d))

        rate_err = self._make_rate_limit_error(retry_after_header=2.5)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_client.chat.completions.create.side_effect = [rate_err, mock_response]

        with patch("agent.auxiliary_client._recoverable_pool_provider", return_value="test-pool"), \
             patch("agent.auxiliary_client._is_rate_limit_error",
                   side_effect=lambda e: isinstance(e, type(rate_err))), \
             patch("agent.auxiliary_client._is_auth_error", return_value=False), \
             patch("agent.auxiliary_client._is_payment_error", return_value=False), \
             patch("agent.auxiliary_client._recover_provider_pool", return_value=False), \
             patch("agent.auxiliary_client._validate_llm_response",
                   side_effect=lambda r, t: r):
            try:
                auxiliary_client._retry_rate_limit_sync(mock_client, {}, "test-task")
            except Exception:
                pass

        assert len(sleep_calls) >= 1
        assert any(d >= 2.5 for d in sleep_calls), \
            f"Expected at least one sleep >= 2.5s (Retry-After), got {sleep_calls}"

    def test_retry_after_capped_sync(self, monkeypatch):
        """Sync: Retry-After: 600 is capped; sleep stays <= jittered_backoff output."""
        from agent import auxiliary_client

        sleep_calls = []
        monkeypatch.setattr("agent.auxiliary_client.time.sleep",
                            lambda d: sleep_calls.append(d))

        rate_err = self._make_rate_limit_error(retry_after_header=600)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_client.chat.completions.create.side_effect = [rate_err, mock_response]

        with patch("agent.auxiliary_client._recoverable_pool_provider", return_value="test-pool"), \
             patch("agent.auxiliary_client._is_rate_limit_error",
                   side_effect=lambda e: isinstance(e, type(rate_err))), \
             patch("agent.auxiliary_client._is_auth_error", return_value=False), \
             patch("agent.auxiliary_client._is_payment_error", return_value=False), \
             patch("agent.auxiliary_client._recover_provider_pool", return_value=False), \
             patch("agent.auxiliary_client._validate_llm_response",
                   side_effect=lambda r, t: r):
            try:
                auxiliary_client._retry_rate_limit_sync(mock_client, {}, "test-task")
            except Exception:
                pass

        assert len(sleep_calls) >= 1
        assert all(d < 600 for d in sleep_calls), \
            f"600s Retry-After should be capped, got {sleep_calls}"
        assert all(d > 0 for d in sleep_calls), f"All delays must be > 0, got: {sleep_calls}"


# ---------------------------------------------------------------------------
# Integration tests: async retry path uses asyncio.sleep with jittered backoff
# ---------------------------------------------------------------------------

class TestAsyncRateLimitBackoff:
    """Verify the async credential-pool rate-limit retry block uses asyncio.sleep."""

    def _make_rate_limit_error(self, retry_after_header=None):
        return _RateLimitError(retry_after_header=retry_after_header)

    @pytest.mark.asyncio
    async def test_jittered_backoff_is_called_on_rate_limit_async(self, monkeypatch):
        """asyncio.sleep called with non-zero delay on 429 in async path."""
        from agent import auxiliary_client

        sleep_calls = []

        async def fake_async_sleep(d):
            sleep_calls.append(d)

        monkeypatch.setattr("agent.auxiliary_client.asyncio.sleep", fake_async_sleep)

        rate_err = self._make_rate_limit_error()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_client.chat.completions.create = AsyncMock(side_effect=[rate_err, mock_response])

        with patch("agent.auxiliary_client._recoverable_pool_provider", return_value="test-pool"), \
             patch("agent.auxiliary_client._is_rate_limit_error",
                   side_effect=lambda e: isinstance(e, type(rate_err))), \
             patch("agent.auxiliary_client._is_auth_error", return_value=False), \
             patch("agent.auxiliary_client._is_payment_error", return_value=False), \
             patch("agent.auxiliary_client._recover_provider_pool", return_value=False), \
             patch("agent.auxiliary_client._validate_llm_response",
                   side_effect=lambda r, t: r):
            try:
                await auxiliary_client._retry_rate_limit_async(mock_client, {}, "test-task")
            except Exception:
                pass

        assert len(sleep_calls) >= 1, "asyncio.sleep should have been called at least once"
        assert all(d > 0 for d in sleep_calls), f"All delays must be > 0, got: {sleep_calls}"

    @pytest.mark.asyncio
    async def test_retry_after_honored_async(self, monkeypatch):
        """Async: Retry-After: 2.5 causes asyncio.sleep >= 2.5s."""
        from agent import auxiliary_client

        sleep_calls = []

        async def fake_async_sleep(d):
            sleep_calls.append(d)

        monkeypatch.setattr("agent.auxiliary_client.asyncio.sleep", fake_async_sleep)

        rate_err = self._make_rate_limit_error(retry_after_header=2.5)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_client.chat.completions.create = AsyncMock(side_effect=[rate_err, mock_response])

        with patch("agent.auxiliary_client._recoverable_pool_provider", return_value="test-pool"), \
             patch("agent.auxiliary_client._is_rate_limit_error",
                   side_effect=lambda e: isinstance(e, type(rate_err))), \
             patch("agent.auxiliary_client._is_auth_error", return_value=False), \
             patch("agent.auxiliary_client._is_payment_error", return_value=False), \
             patch("agent.auxiliary_client._recover_provider_pool", return_value=False), \
             patch("agent.auxiliary_client._validate_llm_response",
                   side_effect=lambda r, t: r):
            try:
                await auxiliary_client._retry_rate_limit_async(mock_client, {}, "test-task")
            except Exception:
                pass

        assert len(sleep_calls) >= 1
        assert any(d >= 2.5 for d in sleep_calls), \
            f"Expected at least one sleep >= 2.5s (Retry-After), got {sleep_calls}"

    @pytest.mark.asyncio
    async def test_retry_after_capped_async(self, monkeypatch):
        """Async: Retry-After: 600 is capped; asyncio.sleep stays < 600."""
        from agent import auxiliary_client

        sleep_calls = []

        async def fake_async_sleep(d):
            sleep_calls.append(d)

        monkeypatch.setattr("agent.auxiliary_client.asyncio.sleep", fake_async_sleep)

        rate_err = self._make_rate_limit_error(retry_after_header=600)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_client.chat.completions.create = AsyncMock(side_effect=[rate_err, mock_response])

        with patch("agent.auxiliary_client._recoverable_pool_provider", return_value="test-pool"), \
             patch("agent.auxiliary_client._is_rate_limit_error",
                   side_effect=lambda e: isinstance(e, type(rate_err))), \
             patch("agent.auxiliary_client._is_auth_error", return_value=False), \
             patch("agent.auxiliary_client._is_payment_error", return_value=False), \
             patch("agent.auxiliary_client._recover_provider_pool", return_value=False), \
             patch("agent.auxiliary_client._validate_llm_response",
                   side_effect=lambda r, t: r):
            try:
                await auxiliary_client._retry_rate_limit_async(mock_client, {}, "test-task")
            except Exception:
                pass

        assert len(sleep_calls) >= 1
        assert all(d < 600 for d in sleep_calls), \
            f"600s Retry-After should be capped, got {sleep_calls}"
        assert all(d > 0 for d in sleep_calls), f"All delays must be > 0, got: {sleep_calls}"
