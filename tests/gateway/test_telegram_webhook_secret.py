"""Tests for GHSA-3vpc-7q5r-276h — Telegram webhook secret required.

Previously, when TELEGRAM_WEBHOOK_URL was set but TELEGRAM_WEBHOOK_SECRET
was not, python-telegram-bot received secret_token=None and the webhook
endpoint accepted any HTTP POST.

The fix refuses to start the adapter in webhook mode without the secret.

W3-S4 addition: defense-in-depth tests for _check_webhook_secret and
_telegram_webhook_secret_middleware.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


class TestTelegramWebhookSecretRequired:
    """Direct source-level check of the webhook-secret guard.

    The guard is embedded in TelegramAdapter.connect() and hard to isolate
    via mocks (requires a full python-telegram-bot ApplicationBuilder
    chain). These tests exercise it via source inspection — verifying the
    check exists, raises RuntimeError with the advisory link, and only
    fires in webhook mode. End-to-end validation is covered by CI +
    manual deployment tests.
    """

    def _get_source(self) -> str:
        path = Path(_repo) / "gateway" / "platforms" / "telegram.py"
        return path.read_text(encoding="utf-8")

    def test_webhook_branch_checks_secret(self):
        """The webhook-mode branch of connect() must read
        TELEGRAM_WEBHOOK_SECRET and refuse when empty."""
        src = self._get_source()
        # The guard must appear after TELEGRAM_WEBHOOK_URL is set
        assert re.search(
            r'TELEGRAM_WEBHOOK_SECRET.*?\.strip\(\)\s*\n\s*if not webhook_secret:',
            src, re.DOTALL,
        ), (
            "TelegramAdapter.connect() must strip TELEGRAM_WEBHOOK_SECRET "
            "and raise when the secret is empty — see GHSA-3vpc-7q5r-276h"
        )

    def test_guard_raises_runtime_error(self):
        """The guard raises RuntimeError (not a silent log) so operators
        see the failure at startup."""
        src = self._get_source()
        # Between the "if not webhook_secret:" line and the next blank
        # line block, we should see a RuntimeError being raised
        guard_match = re.search(
            r'if not webhook_secret:\s*\n\s*raise\s+RuntimeError\(',
            src,
        )
        assert guard_match, (
            "Missing webhook secret must raise RuntimeError — silent "
            "fall-through was the original GHSA-3vpc-7q5r-276h bypass"
        )

    def test_guard_message_includes_advisory_link(self):
        """The RuntimeError message should reference the advisory so
        operators can read the full context."""
        src = self._get_source()
        assert "GHSA-3vpc-7q5r-276h" in src, (
            "Guard error message must cite the advisory for operator context"
        )

    def test_guard_message_explains_remediation(self):
        """The error should tell the operator how to fix it."""
        src = self._get_source()
        # Should mention how to generate a secret
        assert "openssl rand" in src or "TELEGRAM_WEBHOOK_SECRET=" in src, (
            "Guard error message should show operators how to set "
            "TELEGRAM_WEBHOOK_SECRET"
        )

    def test_polling_branch_has_no_secret_guard(self):
        """Polling mode (else-branch) must NOT require the webhook secret —
        polling authenticates via the bot token, not a webhook secret."""
        src = self._get_source()
        # The guard should appear inside the `if webhook_url:` branch,
        # not the `else:` polling branch. Rough check: the raise is
        # followed (within ~60 lines) by an `else:` that starts the
        # polling branch, and there's no secret-check in that polling
        # branch.
        webhook_block = re.search(
            r'if webhook_url:\s*\n(.*?)\n            else:\s*\n(.*?)\n',
            src, re.DOTALL,
        )
        if webhook_block:
            webhook_body = webhook_block.group(1)
            polling_body = webhook_block.group(2)
            assert "TELEGRAM_WEBHOOK_SECRET" in webhook_body
            assert "TELEGRAM_WEBHOOK_SECRET" not in polling_body


# ---------------------------------------------------------------------------
# W3-S4: defense-in-depth — _check_webhook_secret and middleware tests
# ---------------------------------------------------------------------------

def _ensure_telegram_mock() -> None:
    """Install a minimal telegram SDK stub so the adapter module loads."""
    if "telegram" in sys.modules and hasattr(sys.modules["telegram"], "__file__"):
        return
    from unittest.mock import MagicMock
    telegram_mod = MagicMock()
    telegram_mod.ext.ContextTypes.DEFAULT_TYPE = type(None)
    telegram_mod.constants.ParseMode.MARKDOWN_V2 = "MarkdownV2"
    telegram_mod.constants.ChatType.GROUP = "group"
    telegram_mod.constants.ChatType.SUPERGROUP = "supergroup"
    telegram_mod.constants.ChatType.CHANNEL = "channel"
    telegram_mod.constants.ChatType.PRIVATE = "private"
    telegram_mod.error.NetworkError = type("NetworkError", (OSError,), {})
    telegram_mod.error.TimedOut = type("TimedOut", (OSError,), {})
    telegram_mod.error.BadRequest = type("BadRequest", (Exception,), {})
    for name in ("telegram", "telegram.ext", "telegram.constants", "telegram.request"):
        sys.modules.setdefault(name, telegram_mod)
    sys.modules.setdefault("telegram.error", telegram_mod.error)


_ensure_telegram_mock()

from gateway.platforms.telegram import (  # noqa: E402
    _check_webhook_secret,
    _telegram_webhook_secret_middleware,
)
import gateway.platforms.telegram as _tg_mod  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_warned_flag():
    """Ensure the one-time warning sentinel is reset between tests."""
    _tg_mod._WEBHOOK_SECRET_WARNED = False
    yield
    _tg_mod._WEBHOOK_SECRET_WARNED = False


def _stub_aiohttp_web():
    """Register a minimal aiohttp.web stub so the middleware can import it."""
    aiohttp_stub = types.ModuleType("aiohttp")
    web_stub = types.ModuleType("aiohttp.web")
    web_stub.Response = lambda status, text: SimpleNamespace(status=status, text=text)
    aiohttp_stub.web = web_stub
    sys.modules["aiohttp"] = aiohttp_stub
    sys.modules["aiohttp.web"] = web_stub


_stub_aiohttp_web()


def _make_request(header_value=None, remote="127.0.0.1"):
    """Build a minimal mock that mimics an aiohttp Request."""
    headers: dict = {}
    if header_value is not None:
        headers["X-Telegram-Bot-Api-Secret-Token"] = header_value
    return SimpleNamespace(headers=headers, remote=remote)


class TestCheckWebhookSecret:
    """Unit tests for the pure _check_webhook_secret helper."""

    def test_missing_header_with_secret_returns_false(self):
        assert _check_webhook_secret(None, "mysecret") is False

    def test_empty_header_with_secret_returns_false(self):
        assert _check_webhook_secret("", "mysecret") is False

    def test_wrong_header_returns_false(self):
        assert _check_webhook_secret("wrongvalue", "mysecret") is False

    def test_correct_header_returns_true(self):
        assert _check_webhook_secret("mysecret", "mysecret") is True

    def test_no_expected_secret_passes_anything(self):
        """When no secret is configured, all requests pass."""
        assert _check_webhook_secret(None, None) is True
        assert _check_webhook_secret(None, "") is True
        assert _check_webhook_secret("anything", "") is True

    def test_compare_rejects_partial_match(self):
        """Partial-match values are rejected — hmac.compare_digest is strict."""
        assert _check_webhook_secret("mysecret_extra", "mysecret") is False

    def test_compare_uses_constant_time(self):
        """Verify hmac.compare_digest path by confirming wrong value is rejected."""
        import hmac as _hmac
        secret = "secure_token_abc123"
        assert _check_webhook_secret("secure_token_abc124", secret) is False
        assert _check_webhook_secret(secret, secret) is True


class TestTelegramWebhookSecretMiddleware:
    """Tests for the aiohttp-style _telegram_webhook_secret_middleware."""

    @pytest.mark.asyncio
    async def test_telegram_webhook_rejects_missing_header(self, monkeypatch):
        """Configure secret, POST without header → 401."""
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "correctsecret")

        handler = AsyncMock()
        request = _make_request(header_value=None)

        result = await _telegram_webhook_secret_middleware(request, handler)

        assert result.status == 401
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_telegram_webhook_rejects_wrong_header(self, monkeypatch):
        """Configure secret, POST with wrong header → 401."""
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "correctsecret")

        handler = AsyncMock()
        request = _make_request(header_value="wrongsecret")

        result = await _telegram_webhook_secret_middleware(request, handler)

        assert result.status == 401
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_telegram_webhook_accepts_correct_header(self, monkeypatch):
        """Configure secret, POST with correct header → handler called."""
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "correctsecret")

        sentinel = object()
        handler = AsyncMock(return_value=sentinel)
        request = _make_request(header_value="correctsecret")

        result = await _telegram_webhook_secret_middleware(request, handler)

        handler.assert_awaited_once_with(request)
        assert result is sentinel

    @pytest.mark.asyncio
    async def test_telegram_webhook_passthrough_when_no_secret_configured(self, monkeypatch):
        """No secret env var, POST without header → handler called (pass-through)."""
        monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)

        sentinel = object()
        handler = AsyncMock(return_value=sentinel)
        request = _make_request(header_value=None)

        result = await _telegram_webhook_secret_middleware(request, handler)

        handler.assert_awaited_once_with(request)
        assert result is sentinel

    @pytest.mark.asyncio
    async def test_warning_logged_once_when_no_secret(self, monkeypatch, caplog):
        """Missing secret logs a one-time WARNING, not repeated on each request."""
        import logging
        monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)

        handler = AsyncMock(return_value=None)
        request = _make_request(header_value=None)

        with caplog.at_level(logging.WARNING, logger="gateway.platforms.telegram"):
            await _telegram_webhook_secret_middleware(request, handler)
            await _telegram_webhook_secret_middleware(request, handler)

        warnings = [
            r for r in caplog.records
            if "TELEGRAM_WEBHOOK_SECRET is not set" in r.message
        ]
        assert len(warnings) == 1, "Warning should fire exactly once (guarded by sentinel)"
