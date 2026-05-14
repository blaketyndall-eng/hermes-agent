"""Tests for bounded LRU/TTL caches on FeishuAdapter (W2-T13)."""

import unittest
from unittest.mock import patch


class TestBoundedTTLDict(unittest.TestCase):
    """Unit tests for the _BoundedTTLDict helper directly."""

    def _make(self, maxsize=5, ttl=60.0):
        from gateway.platforms.feishu import _BoundedTTLDict
        return _BoundedTTLDict(maxsize=maxsize, ttl=ttl)

    def test_basic_set_get(self):
        d = self._make()
        d["k"] = "v"
        self.assertEqual(d.get("k"), "v")

    def test_miss_returns_default(self):
        d = self._make()
        self.assertIsNone(d.get("missing"))
        self.assertEqual(d.get("missing", "fallback"), "fallback")

    def test_contains_true_for_live_entry(self):
        d = self._make()
        d["x"] = 1
        self.assertIn("x", d)

    def test_contains_false_for_absent(self):
        d = self._make()
        self.assertNotIn("y", d)

    def test_evicts_oldest_when_full(self):
        d = self._make(maxsize=3)
        d["a"] = 1
        d["b"] = 2
        d["c"] = 3
        d["d"] = 4  # should evict "a"
        self.assertNotIn("a", d)
        self.assertIn("b", d)
        self.assertIn("c", d)
        self.assertIn("d", d)
        self.assertEqual(len(d), 3)

    def test_len_never_exceeds_maxsize(self):
        maxsize = 10
        d = self._make(maxsize=maxsize)
        for i in range(maxsize + 20):
            d[str(i)] = i
            self.assertLessEqual(len(d), maxsize)

    def test_pop_removes_and_returns_value(self):
        d = self._make()
        d["k"] = "val"
        result = d.pop("k", None)
        self.assertEqual(result, "val")
        self.assertNotIn("k", d)

    def test_pop_missing_returns_default(self):
        d = self._make()
        self.assertIsNone(d.pop("gone", None))


class TestFeishuMessageTextCacheBounded(unittest.TestCase):
    """test_feishu_message_text_cache_bounded: insert maxsize+5, assert bounded."""

    def test_feishu_message_text_cache_bounded(self):
        from gateway.config import PlatformConfig
        from gateway.platforms.feishu import FeishuAdapter

        adapter = FeishuAdapter(PlatformConfig())
        maxsize = 2000

        # Insert maxsize + 5 entries
        for i in range(maxsize + 5):
            adapter._message_text_cache[f"msg_{i}"] = f"text_{i}"

        # Cache must never exceed maxsize
        self.assertLessEqual(len(adapter._message_text_cache), maxsize)

        # The oldest entries should have been evicted
        for i in range(5):
            self.assertNotIn(f"msg_{i}", adapter._message_text_cache)

        # The newest entries should still be present
        self.assertIn(f"msg_{maxsize + 4}", adapter._message_text_cache)
        self.assertIn(f"msg_{maxsize + 3}", adapter._message_text_cache)


class TestFeishuChatInfoCacheBounded(unittest.TestCase):
    """Verify _chat_info_cache maxsize=500 eviction."""

    def test_chat_info_cache_bounded(self):
        from gateway.config import PlatformConfig
        from gateway.platforms.feishu import FeishuAdapter

        adapter = FeishuAdapter(PlatformConfig())
        maxsize = 500

        for i in range(maxsize + 5):
            adapter._chat_info_cache[f"chat_{i}"] = {"chat_id": f"chat_{i}"}

        self.assertLessEqual(len(adapter._chat_info_cache), maxsize)
        self.assertNotIn("chat_0", adapter._chat_info_cache)
        self.assertIn(f"chat_{maxsize + 4}", adapter._chat_info_cache)


class TestFeishuChatInfoCacheTTLExpires(unittest.TestCase):
    """test_feishu_chat_info_cache_ttl_expires: monkeypatch time.monotonic past TTL."""

    def test_feishu_chat_info_cache_ttl_expires(self):
        from gateway.config import PlatformConfig
        from gateway.platforms.feishu import FeishuAdapter

        adapter = FeishuAdapter(PlatformConfig())

        base_time = 1_000_000.0

        with patch("gateway.platforms.feishu.time") as mock_time:
            # time.monotonic is used by _BoundedTTLDict for expiry
            mock_time.monotonic.return_value = base_time
            mock_time.time.return_value = base_time

            adapter._chat_info_cache["oc_abc"] = {"chat_id": "oc_abc", "name": "test"}
            self.assertIn("oc_abc", adapter._chat_info_cache)

            # Advance monotonic past the 3600s TTL
            mock_time.monotonic.return_value = base_time + 3601.0
            mock_time.time.return_value = base_time + 3601.0

            # Entry should now be a miss (expired)
            result = adapter._chat_info_cache.get("oc_abc")
            self.assertIsNone(result)
            self.assertNotIn("oc_abc", adapter._chat_info_cache)


class TestFeishuSenderNameCacheBounded(unittest.TestCase):
    """Verify _sender_name_cache maxsize=1000 eviction."""

    def test_sender_name_cache_bounded(self):
        from gateway.config import PlatformConfig
        from gateway.platforms.feishu import FeishuAdapter

        adapter = FeishuAdapter(PlatformConfig())
        maxsize = 1000

        for i in range(maxsize + 5):
            adapter._sender_name_cache[f"ou_{i:06d}"] = f"User {i}"

        self.assertLessEqual(len(adapter._sender_name_cache), maxsize)
        self.assertNotIn("ou_000000", adapter._sender_name_cache)
        self.assertIn(f"ou_{maxsize + 4:06d}", adapter._sender_name_cache)

    def test_sender_name_cache_ttl_expires(self):
        from gateway.config import PlatformConfig
        from gateway.platforms.feishu import FeishuAdapter

        adapter = FeishuAdapter(PlatformConfig())
        base_time = 2_000_000.0

        with patch("gateway.platforms.feishu.time") as mock_time:
            mock_time.monotonic.return_value = base_time
            mock_time.time.return_value = base_time

            adapter._sender_name_cache["ou_abc"] = "Alice"
            self.assertIn("ou_abc", adapter._sender_name_cache)

            # Advance past 10-minute TTL (600s)
            mock_time.monotonic.return_value = base_time + 601.0
            mock_time.time.return_value = base_time + 601.0

            result = adapter._sender_name_cache.get("ou_abc")
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
