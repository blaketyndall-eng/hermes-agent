import threading
import time
from types import SimpleNamespace

import pytest

import agent.usage_pricing as _up_module
from agent.usage_pricing import (
    _CacheEntry,
    _PRICING_CACHE,
    _TTL_FRESH,
    _TTL_STALE,
    CanonicalUsage,
    estimate_usage_cost,
    get_pricing_entry,
    normalize_usage,
)


def test_normalize_usage_anthropic_keeps_cache_buckets_separate():
    usage = SimpleNamespace(
        input_tokens=1000,
        output_tokens=500,
        cache_read_input_tokens=2000,
        cache_creation_input_tokens=400,
    )

    normalized = normalize_usage(usage, provider="anthropic", api_mode="anthropic_messages")

    assert normalized.input_tokens == 1000
    assert normalized.output_tokens == 500
    assert normalized.cache_read_tokens == 2000
    assert normalized.cache_write_tokens == 400
    assert normalized.prompt_tokens == 3400


def test_normalize_usage_openai_subtracts_cached_prompt_tokens():
    usage = SimpleNamespace(
        prompt_tokens=3000,
        completion_tokens=700,
        prompt_tokens_details=SimpleNamespace(cached_tokens=1800),
    )

    normalized = normalize_usage(usage, provider="openai", api_mode="chat_completions")

    assert normalized.input_tokens == 1200
    assert normalized.cache_read_tokens == 1800
    assert normalized.output_tokens == 700


def test_normalize_usage_openai_reads_top_level_anthropic_cache_fields():
    """Some OpenAI-compatible proxies (OpenRouter, Vercel AI Gateway, Cline) expose
    Anthropic-style cache token counts at the top level of the usage object when
    routing Claude models, instead of nesting them in prompt_tokens_details.

    Regression guard for the bug fixed in cline/cline#10266 — before this fix,
    the chat-completions branch of normalize_usage() only read
    prompt_tokens_details.cache_write_tokens and completely missed the
    cache_creation_input_tokens case, so cache writes showed as 0 and reflected
    inputTokens were overstated by the cache-write amount.
    """
    usage = SimpleNamespace(
        prompt_tokens=1000,
        completion_tokens=200,
        prompt_tokens_details=SimpleNamespace(cached_tokens=500),
        cache_creation_input_tokens=300,
    )

    normalized = normalize_usage(usage, provider="openrouter", api_mode="chat_completions")

    # Expected: cache read from prompt_tokens_details.cached_tokens (preferred),
    # cache write from top-level cache_creation_input_tokens (fallback).
    assert normalized.cache_read_tokens == 500
    assert normalized.cache_write_tokens == 300
    # input_tokens = prompt_total - cache_read - cache_write = 1000 - 500 - 300 = 200
    assert normalized.input_tokens == 200
    assert normalized.output_tokens == 200


def test_normalize_usage_openai_reads_top_level_cache_read_when_details_missing():
    """Some proxies expose only top-level Anthropic-style fields with no
    prompt_tokens_details object. Regression guard for cline/cline#10266.
    """
    usage = SimpleNamespace(
        prompt_tokens=1000,
        completion_tokens=200,
        cache_read_input_tokens=500,
        cache_creation_input_tokens=300,
    )

    normalized = normalize_usage(usage, provider="openrouter", api_mode="chat_completions")

    assert normalized.cache_read_tokens == 500
    assert normalized.cache_write_tokens == 300
    assert normalized.input_tokens == 200


def test_normalize_usage_openai_prefers_prompt_tokens_details_over_top_level():
    """When both prompt_tokens_details and top-level Anthropic fields are
    present, we prefer the OpenAI-standard nested fields. Top-level Anthropic
    fields are only a fallback when the nested ones are absent/zero.
    """
    usage = SimpleNamespace(
        prompt_tokens=1000,
        completion_tokens=200,
        prompt_tokens_details=SimpleNamespace(cached_tokens=600, cache_write_tokens=150),
        # Intentionally different values — proving we ignore these when details exist.
        cache_read_input_tokens=999,
        cache_creation_input_tokens=999,
    )

    normalized = normalize_usage(usage, provider="openrouter", api_mode="chat_completions")

    assert normalized.cache_read_tokens == 600
    assert normalized.cache_write_tokens == 150


def test_openrouter_models_api_pricing_is_converted_from_per_token_to_per_million(monkeypatch):
    monkeypatch.setattr(
        "agent.usage_pricing.fetch_model_metadata",
        lambda: {
            "anthropic/claude-opus-4.6": {
                "pricing": {
                    "prompt": "0.000005",
                    "completion": "0.000025",
                    "input_cache_read": "0.0000005",
                    "input_cache_write": "0.00000625",
                }
            }
        },
    )

    entry = get_pricing_entry(
        "anthropic/claude-opus-4.6",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
    )

    assert float(entry.input_cost_per_million) == 5.0
    assert float(entry.output_cost_per_million) == 25.0
    assert float(entry.cache_read_cost_per_million) == 0.5
    assert float(entry.cache_write_cost_per_million) == 6.25


def test_estimate_usage_cost_marks_subscription_routes_included():
    result = estimate_usage_cost(
        "gpt-5.3-codex",
        CanonicalUsage(input_tokens=1000, output_tokens=500),
        provider="openai-codex",
        base_url="https://chatgpt.com/backend-api/codex",
    )

    assert result.status == "included"
    assert float(result.amount_usd) == 0.0


def test_estimate_usage_cost_refuses_cache_pricing_without_official_cache_rate(monkeypatch):
    monkeypatch.setattr(
        "agent.usage_pricing.fetch_model_metadata",
        lambda: {
            "google/gemini-2.5-pro": {
                "pricing": {
                    "prompt": "0.00000125",
                    "completion": "0.00001",
                }
            }
        },
    )

    result = estimate_usage_cost(
        "google/gemini-2.5-pro",
        CanonicalUsage(input_tokens=1000, output_tokens=500, cache_read_tokens=100),
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
    )

    assert result.status == "unknown"


def test_custom_endpoint_models_api_pricing_is_supported(monkeypatch):
    monkeypatch.setattr(
        "agent.usage_pricing.fetch_endpoint_model_metadata",
        lambda base_url, api_key=None: {
            "zai-org/GLM-5-TEE": {
                "pricing": {
                    "prompt": "0.0000005",
                    "completion": "0.000002",
                }
            }
        },
    )

    entry = get_pricing_entry(
        "zai-org/GLM-5-TEE",
        provider="custom",
        base_url="https://llm.chutes.ai/v1",
        api_key="test-key",
    )

    assert float(entry.input_cost_per_million) == 0.5
    assert float(entry.output_cost_per_million) == 2.0


def test_deepseek_v4_pro_pricing_entry_exists():
    """Regression test: deepseek-v4-pro must have a pricing entry.

    Before this fix, deepseek-v4-pro sessions showed as unknown cost
    in hermes insights because the _OFFICIAL_DOCS_PRICING table had no
    entry for that model.  See #24218.
    """
    entry = get_pricing_entry(
        "deepseek-v4-pro",
        provider="deepseek",
    )

    assert entry is not None
    assert entry.input_cost_per_million is not None
    assert entry.output_cost_per_million is not None
    assert float(entry.input_cost_per_million) == 1.74
    assert float(entry.output_cost_per_million) == 3.48
    assert float(entry.cache_read_cost_per_million) == 0.0145


def test_deepseek_v4_pro_estimate_usage_cost():
    """Ensure deepseek-v4-pro sessions get a dollar estimate, not unknown."""
    result = estimate_usage_cost(
        "deepseek-v4-pro",
        CanonicalUsage(input_tokens=1000000, output_tokens=500000),
        provider="deepseek",
    )

    assert result.status == "estimated"
    assert result.amount_usd is not None
    # 1M input × $1.74/M + 500K output × $3.48/M = $1.74 + $1.74 = $3.48
    assert float(result.amount_usd) == 3.48


# ---------------------------------------------------------------------------
# SWR cache tests
# ---------------------------------------------------------------------------

_SWR_CACHE_KEY = "endpoint:https://test.example.com/v1"
_OLD_METADATA = {"old-model": {"pricing": {"prompt": "0.000001", "completion": "0.000002"}}}
_NEW_METADATA = {"old-model": {"pricing": {"prompt": "0.000003", "completion": "0.000006"}}}


@pytest.fixture(autouse=False)
def clean_swr_cache():
    """Remove any leftover SWR cache entry created by SWR tests."""
    _PRICING_CACHE.pop(_SWR_CACHE_KEY, None)
    yield
    _PRICING_CACHE.pop(_SWR_CACHE_KEY, None)


def test_pricing_fresh_returns_cached_without_fetch(monkeypatch, clean_swr_cache):
    """A cache entry younger than _TTL_FRESH must be returned without calling
    the fetcher at all."""
    call_count = 0

    def fake_fetcher():
        nonlocal call_count
        call_count += 1
        return _OLD_METADATA

    # Prime the cache with a fresh timestamp.
    _PRICING_CACHE[_SWR_CACHE_KEY] = _CacheEntry(
        value=_OLD_METADATA,
        fetched_at=time.monotonic(),  # age ≈ 0 → fresh
    )

    monkeypatch.setattr(
        "agent.usage_pricing.fetch_endpoint_model_metadata",
        lambda base_url, api_key=None: fake_fetcher(),
    )

    result = get_pricing_entry(
        "old-model",
        provider="custom",
        base_url="https://test.example.com/v1",
        api_key="key",
    )

    # The fetcher must not have been called.
    assert call_count == 0
    # Value returned from the cache.
    assert result is not None


def test_pricing_stale_returns_cached_and_kicks_off_refresh(monkeypatch, clean_swr_cache):
    """When the entry is between _TTL_FRESH and _TTL_STALE the old value is
    returned immediately, a background refresh is started, and after it
    completes the cache holds the new value."""
    # refresh_written is set AFTER _background_refresh writes the new value into
    # _PRICING_CACHE, so checking it avoids the race between fake_fetcher()
    # returning and the cache write completing.
    refresh_written = threading.Event()
    call_count = 0

    def fake_fetcher():
        nonlocal call_count
        call_count += 1
        return _NEW_METADATA

    # Wrap _background_refresh to signal after the cache write.
    _original_bg_refresh = _up_module._background_refresh

    def _instrumented_bg_refresh(key, fetcher):
        _original_bg_refresh(key, fetcher)
        refresh_written.set()

    monkeypatch.setattr(_up_module, "_background_refresh", _instrumented_bg_refresh)
    monkeypatch.setattr(
        "agent.usage_pricing.fetch_endpoint_model_metadata",
        lambda base_url, api_key=None: fake_fetcher(),
    )

    # Simulate a stale entry: age is halfway between _TTL_FRESH and _TTL_STALE.
    stale_age = (_TTL_FRESH + _TTL_STALE) / 2
    _PRICING_CACHE[_SWR_CACHE_KEY] = _CacheEntry(
        value=_OLD_METADATA,
        fetched_at=time.monotonic() - stale_age,
    )

    result = get_pricing_entry(
        "old-model",
        provider="custom",
        base_url="https://test.example.com/v1",
        api_key="key",
    )

    # (a) Returned value is the OLD (stale) value — no blocking.
    assert result is not None
    # The pricing entry we get back should be derived from _OLD_METADATA
    # (input = 0.000001 × 1e6 = 1.0 per million).
    assert float(result.input_cost_per_million) == pytest.approx(1.0)

    # (b) A background refresh was triggered.  Wait up to 5 s for the background
    # thread to complete (including the cache-write), then check call count.
    refresh_written.wait(timeout=5.0)
    assert call_count == 1, "Background fetcher should have been called exactly once"

    # (c) After background refresh, cache has the new value.
    cached_entry = _PRICING_CACHE.get(_SWR_CACHE_KEY)
    assert cached_entry is not None
    assert cached_entry.value is _NEW_METADATA


def test_pricing_too_stale_block_fetches(monkeypatch, clean_swr_cache):
    """When the entry is older than _TTL_STALE the call must block on the
    fetcher and return the new value synchronously."""
    call_count = 0

    def fake_fetcher():
        nonlocal call_count
        call_count += 1
        return _NEW_METADATA

    monkeypatch.setattr(
        "agent.usage_pricing.fetch_endpoint_model_metadata",
        lambda base_url, api_key=None: fake_fetcher(),
    )

    # Simulate a too-stale entry: age is well beyond _TTL_STALE.
    _PRICING_CACHE[_SWR_CACHE_KEY] = _CacheEntry(
        value=_OLD_METADATA,
        fetched_at=time.monotonic() - (_TTL_STALE + 60),
    )

    result = get_pricing_entry(
        "old-model",
        provider="custom",
        base_url="https://test.example.com/v1",
        api_key="key",
    )

    # Fetcher must have been called synchronously (before the function returned).
    assert call_count == 1
    # The result is derived from _NEW_METADATA (input = 0.000003 × 1e6 = 3.0).
    assert result is not None
    assert float(result.input_cost_per_million) == pytest.approx(3.0)
