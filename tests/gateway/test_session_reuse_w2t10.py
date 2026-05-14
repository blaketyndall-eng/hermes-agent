"""W2-T10: tests for shared HTTP client reuse.

test_discord_image_session_reused
    Asserts that calling an image-fetch method twice on the same
    DiscordAdapter instance uses one aiohttp.ClientSession, not two.

test_yuanbao_signmanager_reuses_httpx_client_across_retries
    Asserts that SignManager.fetch() with a retryable failure creates only
    one httpx.AsyncClient even when the retry loop fires multiple times.
"""
import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import PlatformConfig


# ---------------------------------------------------------------------------
# Discord mock helpers (mirrors the pattern used across the test suite)
# ---------------------------------------------------------------------------

def _ensure_discord_mock() -> None:
    if "discord" in sys.modules and hasattr(sys.modules["discord"], "__file__"):
        return

    discord_mod = MagicMock()
    discord_mod.Intents.default.return_value = MagicMock()
    discord_mod.Client = MagicMock
    discord_mod.File = MagicMock
    discord_mod.DMChannel = type("DMChannel", (), {})
    discord_mod.Thread = type("Thread", (), {})
    discord_mod.ForumChannel = type("ForumChannel", (), {})
    discord_mod.ui = SimpleNamespace(
        View=object,
        button=lambda *a, **k: (lambda fn: fn),
        Button=object,
    )
    discord_mod.ButtonStyle = SimpleNamespace(
        success=1, primary=2, secondary=2, danger=3,
        green=1, grey=2, blurple=2, red=3,
    )
    discord_mod.Color = SimpleNamespace(
        orange=lambda: 1, green=lambda: 2, blue=lambda: 3,
        red=lambda: 4, purple=lambda: 5,
    )
    discord_mod.Interaction = object
    discord_mod.Embed = MagicMock
    discord_mod.app_commands = SimpleNamespace(
        describe=lambda **kwargs: (lambda fn: fn),
        choices=lambda **kwargs: (lambda fn: fn),
        Choice=lambda **kwargs: SimpleNamespace(**kwargs),
    )

    ext_mod = MagicMock()
    commands_mod = MagicMock()
    commands_mod.Bot = MagicMock
    ext_mod.commands = commands_mod

    sys.modules.setdefault("discord", discord_mod)
    sys.modules.setdefault("discord.ext", ext_mod)
    sys.modules.setdefault("discord.ext.commands", commands_mod)


_ensure_discord_mock()

from gateway.platforms.discord import DiscordAdapter  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_resp(status: int = 200, content_type: str = "image/png") -> MagicMock:
    """Return an async-context-manager mock that behaves like an aiohttp response."""
    resp = MagicMock()
    resp.status = status
    resp.headers = {"content-type": content_type}
    resp.read = AsyncMock(return_value=b"\x89PNG\r\n")
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _make_mock_session() -> MagicMock:
    """Return a mock aiohttp.ClientSession that tracks .get() calls."""
    session = MagicMock()
    session.closed = False
    session.close = AsyncMock()
    resp = _make_mock_resp()
    session.get = MagicMock(return_value=resp)
    return session


# ---------------------------------------------------------------------------
# Discord test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discord_image_session_reused():
    """ClientSession must be constructed once and reused on repeated fetches."""
    adapter = DiscordAdapter(PlatformConfig(enabled=True, token="***"))

    # Wire up a minimal fake discord client so send_image does not bail early.
    fake_channel = MagicMock()
    fake_channel.send = AsyncMock(return_value=MagicMock(id=42))
    fake_client = MagicMock()
    fake_client.get_channel = MagicMock(return_value=fake_channel)
    adapter._client = fake_client

    created_sessions = []

    def mock_client_session_factory(**kwargs):
        s = _make_mock_session()
        created_sessions.append(s)
        return s

    with patch(
        "gateway.platforms.base.resolve_proxy_url",
        return_value=None,
    ), patch(
        "gateway.platforms.base.proxy_kwargs_for_aiohttp",
        return_value=({}, {}),
    ), patch(
        "aiohttp.ClientSession",
        side_effect=mock_client_session_factory,
    ):
        await adapter.send_image("123", "https://example.com/a.png", caption=None)
        await adapter.send_image("123", "https://example.com/b.png", caption=None)

    # Only one ClientSession should have been created across both calls.
    assert len(created_sessions) == 1, (
        f"Expected 1 ClientSession, got {len(created_sessions)}"
    )


# ---------------------------------------------------------------------------
# Yuanbao test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_yuanbao_signmanager_reuses_httpx_client_across_retries():
    """httpx.AsyncClient must be created once even when the retry loop fires."""
    from gateway.platforms.yuanbao import SignManager

    # Reset class-level state so previous test runs do not interfere.
    SignManager._httpx_client = None

    created_clients = []

    # Build mock responses: first attempt returns retryable code, second succeeds.
    retryable_resp = MagicMock()
    retryable_resp.status_code = 200
    retryable_resp.text = ""
    retryable_resp.json = MagicMock(
        return_value={"code": SignManager.RETRYABLE_CODE, "msg": "retry me"}
    )

    success_resp = MagicMock()
    success_resp.status_code = 200
    success_resp.text = ""
    success_resp.json = MagicMock(
        return_value={
            "code": 0,
            "data": {"bot_id": "bot-1", "token": "tok", "expire_ts": 9999999999},
        }
    )

    class _MockClient:
        """Fake httpx.AsyncClient — not a context manager."""

        def __init__(self, **kwargs):
            created_clients.append(self)
            self._calls = 0
            self.is_closed = False

        async def post(self, url, **kwargs):
            self._calls += 1
            if self._calls == 1:
                return retryable_resp
            return success_resp

        async def aclose(self):
            self.is_closed = True

    with patch("httpx.AsyncClient", side_effect=_MockClient):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await SignManager.fetch(
                app_key="key",
                app_secret="secret",
                api_domain="https://api.example.com",
            )

    assert result["bot_id"] == "bot-1"
    assert len(created_clients) == 1, (
        f"Expected 1 AsyncClient, got {len(created_clients)}"
    )

    # Clean up so other tests are unaffected.
    SignManager._httpx_client = None
