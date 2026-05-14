"""Test: _async_compress_context does not block the asyncio event loop.

If run_conversation is invoked from an async context (e.g. a gateway server),
the synchronous _compress_context — which makes a 10-60s LLM call inside
ContextCompressor.compress — blocks the event loop entirely. The async
variant must hand the blocking work off so other coroutines keep running.
"""

import asyncio
import os
import time
from unittest.mock import MagicMock, patch

import pytest


def _make_agent():
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
        from run_agent import AIAgent
        agent = AIAgent(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            model="test/model",
            quiet_mode=True,
            session_db=None,
            session_id="original-session",
            skip_context_files=True,
            skip_memory=True,
        )

    compressor = MagicMock()

    def _slow_compress(*args, **kwargs):
        # Simulates the blocking LLM call inside ContextCompressor.compress.
        time.sleep(0.5)
        return [{"role": "user", "content": "[CONTEXT COMPACTION] summary"}]

    compressor.compress.side_effect = _slow_compress
    compressor.compression_count = 1
    compressor.last_prompt_tokens = 0
    compressor.last_completion_tokens = 0
    compressor._last_summary_error = None
    compressor._last_aux_model_failure_model = None
    compressor._last_aux_model_failure_error = None
    agent.context_compressor = compressor
    return agent


def test_async_compress_context_does_not_block_loop():
    agent = _make_agent()
    messages = [{"role": "user", "content": f"m{i}"} for i in range(5)]
    flag = {"set": False, "set_at": None}

    async def sentinel():
        await asyncio.sleep(0.01)
        flag["set"] = True
        flag["set_at"] = time.monotonic()

    async def driver():
        start = time.monotonic()
        sentinel_task = asyncio.create_task(sentinel())
        compress_task = asyncio.create_task(
            agent._async_compress_context(messages, "sys", approx_tokens=100)
        )
        # Give the sentinel a chance to run while compress is still blocking
        # in its worker thread.
        await asyncio.sleep(0.05)
        sentinel_fired_early = flag["set"]
        sentinel_lag = (
            (flag["set_at"] - start) if flag["set_at"] is not None else None
        )
        compressed, _new_sys = await compress_task
        await sentinel_task
        return sentinel_fired_early, sentinel_lag, compressed

    sentinel_fired_early, sentinel_lag, compressed = asyncio.run(driver())

    assert sentinel_fired_early, (
        "sentinel coroutine did not run while _async_compress_context "
        "was executing — event loop appears blocked"
    )
    assert sentinel_lag is not None and sentinel_lag < 0.1, (
        f"sentinel fired but with lag {sentinel_lag!r}s — expected <0.1s, "
        "suggesting the loop was partially blocked"
    )
    assert compressed, "compression should still return results"


def test_async_compress_context_returns_same_shape_as_sync():
    """The async variant must return (messages, system_prompt) — same as sync."""
    agent = _make_agent()
    messages = [{"role": "user", "content": "m"}]

    async def driver():
        return await agent._async_compress_context(
            messages, "sys", approx_tokens=100
        )

    result = asyncio.run(driver())
    assert isinstance(result, tuple), f"expected tuple, got {type(result)}"
    assert len(result) == 2, f"expected 2-tuple, got len={len(result)}"
    compressed, new_system_prompt = result
    assert isinstance(compressed, list)
    assert isinstance(new_system_prompt, str)
