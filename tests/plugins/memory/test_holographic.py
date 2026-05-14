"""Tests for plugins/memory/holographic/holographic.py."""

import pytest

pytest.importorskip("numpy", reason="numpy required for holographic tests")

from plugins.memory.holographic.holographic import encode_atom  # noqa: E402


class TestEncodeAtomCached:
    """Verify that lru_cache is active and correct on encode_atom."""

    def test_encode_atom_cached(self):
        """Second call with identical args returns the same object (cache hit)."""
        first = encode_atom("hello", 1024)
        second = encode_atom("hello", 1024)
        assert first is second, (
            "Expected encode_atom to return the cached object on repeated calls "
            "with identical arguments, but got two distinct objects."
        )

    def test_encode_atom_cached_default_dim(self):
        """Cache hit works when both calls use the default dim omitted."""
        a = encode_atom("world")
        b = encode_atom("world")
        # Identical call signatures must return the same cached object.
        assert a is b

    def test_encode_atom_cached_different_words_are_distinct(self):
        """Different words produce distinct vectors (no false cache collision)."""
        v1 = encode_atom("apple", 64)
        v2 = encode_atom("orange", 64)
        assert v1 is not v2

    def test_encode_atom_cached_different_dims_are_distinct(self):
        """Same word with different dims returns distinct cached entries."""
        v32 = encode_atom("token", 32)
        v64 = encode_atom("token", 64)
        assert v32 is not v64
        assert len(v32) == 32
        assert len(v64) == 64


class TestEncodeAtomDeterminism:
    """Verify caching does not change the observable output values."""

    def test_encode_atom_determinism(self):
        """Cached result matches a freshly-computed reference value."""
        import hashlib
        import struct
        import math
        import numpy as np

        word = "determinism_check"
        dim = 64

        # Independently reproduce the algorithm from the source.
        TWO_PI = 2.0 * math.pi
        values_per_block = 16
        blocks_needed = math.ceil(dim / values_per_block)
        uint16_values: list[int] = []
        for i in range(blocks_needed):
            digest = hashlib.sha256(f"{word}:{i}".encode()).digest()
            uint16_values.extend(struct.unpack("<16H", digest))
        expected = np.array(uint16_values[:dim], dtype=np.float64) * (TWO_PI / 65536.0)

        cached = encode_atom(word, dim)
        assert cached.shape == expected.shape
        assert (cached == expected).all(), (
            "encode_atom output after caching does not match the reference "
            "computed without caching."
        )

    def test_encode_atom_determinism_across_calls(self):
        """Multiple calls return numerically identical arrays."""
        import numpy as np

        v1 = encode_atom("repeat", 128)
        v2 = encode_atom("repeat", 128)
        assert np.array_equal(v1, v2)
