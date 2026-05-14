"""Tests for the TTL + mtime-keyed cache on discover_memory_providers().

W2-T23
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import plugins.memory as mem_plugin
from plugins.memory import (
    _invalidate_memory_provider_cache,
    discover_memory_providers,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_provider(available: bool = True) -> MagicMock:
    """Return a mock MemoryProvider whose is_available() returns *available*."""
    p = MagicMock()
    p.is_available.return_value = available
    return p


def _fake_provider_dirs(tmp_path: Path, count: int = 2) -> list:
    """Create *count* minimal provider directories under *tmp_path*."""
    dirs = []
    for i in range(count):
        d = tmp_path / f"provider{i}"
        d.mkdir()
        (d / "__init__.py").write_text(f"# provider {i}\n")
        (d / "plugin.yaml").write_text(f"description: Provider {i}\n")
        dirs.append((f"provider{i}", d))
    return dirs


# ---------------------------------------------------------------------------
# test_discover_memory_providers_cached_within_ttl
# ---------------------------------------------------------------------------

class TestCachedWithinTTL:
    """_load_provider_from_dir should be called only once for two calls that
    fall within the TTL and see the same mtime state."""

    def test_load_called_once(self, tmp_path: Path) -> None:
        _invalidate_memory_provider_cache()

        provider_dirs = _fake_provider_dirs(tmp_path, count=2)
        fake_provider = _make_fake_provider(available=True)

        call_count = {"n": 0}

        def fake_load(path: Path):
            call_count["n"] += 1
            return fake_provider

        with (
            patch.object(mem_plugin, "_iter_provider_dirs", return_value=provider_dirs),
            patch.object(mem_plugin, "_load_provider_from_dir", side_effect=fake_load),
        ):
            result1 = discover_memory_providers()
            result2 = discover_memory_providers()

        # Both calls should return the same data.
        assert result1 == result2
        assert len(result1) == 2

        # _load_provider_from_dir should have been called only for the first
        # (cache-miss) pass — 2 providers × 1 call = 2.
        assert call_count["n"] == 2, (
            f"Expected 2 total _load_provider_from_dir calls (one discovery pass "
            f"for 2 providers), got {call_count['n']}"
        )


# ---------------------------------------------------------------------------
# test_discover_memory_providers_invalidates_on_mtime_change
# ---------------------------------------------------------------------------

class TestInvalidatesOnMtimeChange:
    """When the mtime of a provider directory changes between two calls (even
    within the TTL), the cache must be bypassed and discovery re-run."""

    def test_load_called_twice_on_mtime_change(self, tmp_path: Path) -> None:
        _invalidate_memory_provider_cache()

        provider_dirs = _fake_provider_dirs(tmp_path, count=1)
        fake_provider = _make_fake_provider(available=True)

        load_call_count = {"n": 0}

        def fake_load(path: Path):
            load_call_count["n"] += 1
            return fake_provider

        # Track how many times _mtime_hash is called so we can bump the mtime
        # on the second computation.
        hash_call_count = {"n": 0}
        original_mtime_hash = mem_plugin._mtime_hash

        def fake_mtime_hash(dirs):
            hash_call_count["n"] += 1
            if hash_call_count["n"] == 1:
                return "hash_v1"
            return "hash_v2"  # different hash → cache miss on second call

        with (
            patch.object(mem_plugin, "_iter_provider_dirs", return_value=provider_dirs),
            patch.object(mem_plugin, "_load_provider_from_dir", side_effect=fake_load),
            patch.object(mem_plugin, "_mtime_hash", side_effect=fake_mtime_hash),
        ):
            discover_memory_providers()   # first call — cache miss
            discover_memory_providers()   # second call — mtime hash changed, cache miss

        # Each discovery pass covers 1 provider, so 2 passes = 2 calls.
        assert load_call_count["n"] == 2, (
            f"Expected 2 _load_provider_from_dir calls (mtime changed between "
            f"calls), got {load_call_count['n']}"
        )


# ---------------------------------------------------------------------------
# test_invalidate_memory_provider_cache_forces_reload
# ---------------------------------------------------------------------------

class TestInvalidateForcesReload:
    """_invalidate_memory_provider_cache() must cause the next call to
    discover_memory_providers() to re-run discovery even within the TTL."""

    def test_invalidate_forces_reload(self, tmp_path: Path) -> None:
        _invalidate_memory_provider_cache()

        provider_dirs = _fake_provider_dirs(tmp_path, count=1)
        fake_provider = _make_fake_provider(available=True)

        call_count = {"n": 0}

        def fake_load(path: Path):
            call_count["n"] += 1
            return fake_provider

        with (
            patch.object(mem_plugin, "_iter_provider_dirs", return_value=provider_dirs),
            patch.object(mem_plugin, "_load_provider_from_dir", side_effect=fake_load),
        ):
            discover_memory_providers()      # first call — cache miss, populates cache
            assert call_count["n"] == 1

            discover_memory_providers()      # second call — cache hit, no reload
            assert call_count["n"] == 1, "Expected cache hit on second call"

            _invalidate_memory_provider_cache()

            discover_memory_providers()      # third call — cache was cleared, reload
            assert call_count["n"] == 2, (
                f"Expected reload after _invalidate_memory_provider_cache(), "
                f"got call_count={call_count['n']}"
            )
