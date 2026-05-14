"""Tests for cross-loop client cache isolation fix (#2681) and W2-T19.

Verifies that _get_cached_client() returns different AsyncOpenAI clients
when called from different event loops, preventing the httpx deadlock
that occurs when a cached async client bound to loop A is reused on loop B.

Also verifies that get_running_loop() is used (not the deprecated
get_event_loop()) so loop mismatches surface as RuntimeError rather than
silent cache poisoning.

This test file is self-contained and does not import the full tool chain,
so it can run without optional dependencies like firecrawl.
"""

import asyncio
import threading
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Minimal stubs so we can import _get_cached_client without the full tree
# ---------------------------------------------------------------------------

def _stub_resolve_provider_client(provider, model, async_mode, **kw):
    """Return a unique mock client each time, simulating AsyncOpenAI creation."""
    client = MagicMock(name=f"client-{provider}-async={async_mode}")
    client.api_key = "test"
    client.base_url = kw.get("explicit_base_url", "http://localhost:8081/v1")
    return client, model or "test-model"


@pytest.fixture(autouse=True)
def _clean_client_cache():
    """Clear the client cache before each test."""
    import agent.auxiliary_client as ac
    ac._client_cache.clear()
    yield
    ac._client_cache.clear()


class TestCrossLoopCacheIsolation:
    """Verify async clients are cached per-event-loop, not globally."""

    def test_same_loop_reuses_client(self):
        """Within a single event loop, the same client should be returned."""
        from agent.auxiliary_client import _get_cached_client

        results = {}

        async def _run():
            with patch("agent.auxiliary_client.resolve_provider_client",
                        side_effect=_stub_resolve_provider_client):
                c1, _ = _get_cached_client("custom", "m1", async_mode=True,
                                            base_url="http://localhost:8081/v1")
                c2, _ = _get_cached_client("custom", "m1", async_mode=True,
                                            base_url="http://localhost:8081/v1")
            results["c1"] = c1
            results["c2"] = c2

        asyncio.run(_run())

        assert results["c1"] is results["c2"], (
            "Same loop should return the same cached client"
        )

    def test_different_loops_get_different_clients(self):
        """Different event loops must get separate client instances."""
        from agent.auxiliary_client import _get_cached_client

        results = {}

        def _get_client_on_new_loop(name):
            async def _inner():
                with patch("agent.auxiliary_client.resolve_provider_client",
                            side_effect=_stub_resolve_provider_client):
                    client, _ = _get_cached_client("custom", "m1", async_mode=True,
                                                     base_url="http://localhost:8081/v1")
                results[name] = id(client)

            asyncio.run(_inner())

        t1 = threading.Thread(target=_get_client_on_new_loop, args=("a",))
        t2 = threading.Thread(target=_get_client_on_new_loop, args=("b",))
        t1.start(); t1.join()
        t2.start(); t2.join()

        assert results["a"] != results["b"], (
            "Different event loops got the SAME cached client — this causes "
            "httpx cross-loop deadlocks in gateway mode (#2681)"
        )

    def test_sync_clients_not_affected(self):
        """Sync clients (async_mode=False) should still be cached globally,
        since httpx.Client (sync) doesn't bind to an event loop."""
        from agent.auxiliary_client import _get_cached_client

        results = {}

        def _get_sync_client(name):
            with patch("agent.auxiliary_client.resolve_provider_client",
                        side_effect=_stub_resolve_provider_client):
                client, _ = _get_cached_client("custom", "m1", async_mode=False,
                                                 base_url="http://localhost:8081/v1")
            results[name] = id(client)

        t1 = threading.Thread(target=_get_sync_client, args=("a",))
        t2 = threading.Thread(target=_get_sync_client, args=("b",))
        t1.start(); t1.join()
        t2.start(); t2.join()

        assert results["a"] == results["b"], (
            "Sync clients should be shared across threads (no loop binding)"
        )

    def test_gateway_simulation_no_deadlock(self):
        """Simulate gateway mode: _run_async spawns a thread with asyncio.run(),
        which creates a new loop. The cached client must be created on THAT loop,
        not reused from a different one."""
        from agent.auxiliary_client import _get_cached_client

        gateway_client_id = [None]
        worker_client_id = [None]

        # Simulate: first call on "gateway loop"
        async def _gateway():
            with patch("agent.auxiliary_client.resolve_provider_client",
                        side_effect=_stub_resolve_provider_client):
                client, _ = _get_cached_client("custom", "m1", async_mode=True,
                                                 base_url="http://localhost:8081/v1")
            gateway_client_id[0] = id(client)

        asyncio.run(_gateway())

        # Simulate: _run_async spawns a thread with asyncio.run()
        def _worker():
            async def _inner():
                with patch("agent.auxiliary_client.resolve_provider_client",
                            side_effect=_stub_resolve_provider_client):
                    client, _ = _get_cached_client("custom", "m1", async_mode=True,
                                                     base_url="http://localhost:8081/v1")
                worker_client_id[0] = id(client)
            asyncio.run(_inner())

        t = threading.Thread(target=_worker)
        t.start()
        t.join()

        assert worker_client_id[0] != gateway_client_id[0], (
            "Worker thread (asyncio.run) got the gateway's cached client — "
            "this is the exact cross-loop scenario that causes httpx deadlocks. "
            "The cache must isolate clients by running loop (#2681)"
        )

    def test_closed_loop_client_discarded(self):
        """A cached client whose loop has closed should be replaced."""
        from agent.auxiliary_client import _get_cached_client

        client_ids = []

        def _run_on_new_loop():
            async def _inner():
                with patch("agent.auxiliary_client.resolve_provider_client",
                            side_effect=_stub_resolve_provider_client):
                    client, _ = _get_cached_client("custom", "m1", async_mode=True,
                                                     base_url="http://localhost:8081/v1")
                client_ids.append(id(client))

            # asyncio.run() creates a new loop, runs it, then closes it.
            # The second call creates a fresh loop — simulating the
            # closed-loop replacement scenario.
            asyncio.run(_inner())

        _run_on_new_loop()  # loop A (created and closed by asyncio.run)
        _run_on_new_loop()  # loop B (new loop — cached_loop.is_closed() on A)

        assert client_ids[0] != client_ids[1], (
            "Client from closed loop should not be reused"
        )


# ---------------------------------------------------------------------------
# W2-T19: get_running_loop tests
# ---------------------------------------------------------------------------

class TestGetRunningLoopUsage:
    """Verify W2-T19: get_running_loop() replaces deprecated get_event_loop()."""

    def test_async_client_cache_uses_running_loop(self):
        """In an async context, two calls with same params reuse the cached client.

        With get_running_loop() both calls see the SAME running loop, so the
        cache hit succeeds. This was broken with get_event_loop() because that
        could return different (or closed) loop objects on each call.
        """
        from agent.auxiliary_client import _get_cached_client

        results = {}

        async def _run():
            with patch("agent.auxiliary_client.resolve_provider_client",
                        side_effect=_stub_resolve_provider_client):
                c1, _ = _get_cached_client("openai", "gpt-4o", async_mode=True,
                                            base_url="https://api.openai.com/v1")
                c2, _ = _get_cached_client("openai", "gpt-4o", async_mode=True,
                                            base_url="https://api.openai.com/v1")
            results["c1"] = c1
            results["c2"] = c2

        asyncio.run(_run())

        assert results["c1"] is results["c2"], (
            "Cache should reuse client when both calls share the same running loop. "
            "If this fails, get_running_loop() is returning different loop objects, "
            "indicating the deprecated get_event_loop() regression is back."
        )

    def test_get_running_loop_raises_outside_coroutine(self):
        """Calling _get_cached_client(async_mode=True) from sync context raises RuntimeError.

        This is the correct behavior: async_mode=True means the caller asserts
        it is in a coroutine. Surfacing the error is better than silently
        obtaining a wrong/closed loop via the deprecated get_event_loop().
        """
        from agent.auxiliary_client import _get_cached_client

        with pytest.raises(RuntimeError, match="no running event loop"):
            with patch("agent.auxiliary_client.resolve_provider_client",
                        side_effect=_stub_resolve_provider_client):
                _get_cached_client("openai", "gpt-4o", async_mode=True,
                                   base_url="https://api.openai.com/v1")
