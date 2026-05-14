"""Tests for agent/prompt_caching.py — Anthropic cache control injection."""

import copy
import pytest

from agent.prompt_caching import (
    _apply_cache_marker,
    apply_anthropic_cache_control,
)


MARKER = {"type": "ephemeral"}


class TestApplyCacheMarker:
    def test_tool_message_gets_top_level_marker_on_native_anthropic(self):
        """Native Anthropic path: cache_control injected top-level (adapter moves it inside tool_result)."""
        msg = {"role": "tool", "content": "result"}
        _apply_cache_marker(msg, MARKER, native_anthropic=True)
        assert msg["cache_control"] == MARKER

    def test_tool_message_skips_marker_on_openrouter(self):
        """OpenRouter path: top-level cache_control on role:tool is invalid and causes silent hang."""
        msg = {"role": "tool", "content": "result"}
        _apply_cache_marker(msg, MARKER, native_anthropic=False)
        assert "cache_control" not in msg

    def test_none_content_gets_top_level_marker(self):
        msg = {"role": "assistant", "content": None}
        _apply_cache_marker(msg, MARKER)
        assert msg["cache_control"] == MARKER

    def test_empty_string_content_gets_top_level_marker(self):
        """Empty text blocks cannot have cache_control (Anthropic rejects them)."""
        msg = {"role": "assistant", "content": ""}
        _apply_cache_marker(msg, MARKER)
        assert msg["cache_control"] == MARKER
        # Must NOT wrap into [{"type": "text", "text": "", "cache_control": ...}]
        assert msg["content"] == ""

    def test_string_content_wrapped_in_list(self):
        msg = {"role": "user", "content": "Hello"}
        _apply_cache_marker(msg, MARKER)
        assert isinstance(msg["content"], list)
        assert len(msg["content"]) == 1
        assert msg["content"][0]["type"] == "text"
        assert msg["content"][0]["text"] == "Hello"
        assert msg["content"][0]["cache_control"] == MARKER

    def test_list_content_last_item_gets_marker(self):
        msg = {
            "role": "user",
            "content": [
                {"type": "text", "text": "First"},
                {"type": "text", "text": "Second"},
            ],
        }
        _apply_cache_marker(msg, MARKER)
        assert "cache_control" not in msg["content"][0]
        assert msg["content"][1]["cache_control"] == MARKER

    def test_empty_list_content_no_crash(self):
        msg = {"role": "user", "content": []}
        # Should not crash on empty list
        _apply_cache_marker(msg, MARKER)


class TestApplyAnthropicCacheControl:
    def test_empty_messages(self):
        result = apply_anthropic_cache_control([])
        assert result == []

    def test_returns_deep_copy(self):
        msgs = [{"role": "user", "content": "Hello"}]
        result = apply_anthropic_cache_control(msgs)
        assert result is not msgs
        assert result[0] is not msgs[0]
        # Original should be unmodified
        assert "cache_control" not in msgs[0].get("content", "")

    def test_system_message_gets_marker(self):
        msgs = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hi"},
        ]
        result = apply_anthropic_cache_control(msgs)
        # System message should have cache_control
        sys_content = result[0]["content"]
        assert isinstance(sys_content, list)
        assert sys_content[0]["cache_control"]["type"] == "ephemeral"

    def test_last_3_non_system_get_markers(self):
        msgs = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "msg2"},
            {"role": "user", "content": "msg3"},
            {"role": "assistant", "content": "msg4"},
        ]
        result = apply_anthropic_cache_control(msgs)
        # System (index 0) + last 3 non-system (indices 2, 3, 4) = 4 breakpoints
        # Index 1 (msg1) should NOT have marker
        content_1 = result[1]["content"]
        if isinstance(content_1, str):
            assert True  # No marker applied (still a string)
        else:
            assert "cache_control" not in content_1[0]

    def test_no_system_message(self):
        msgs = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = apply_anthropic_cache_control(msgs)
        # Both should get markers (4 slots available, only 2 messages)
        assert len(result) == 2

    def test_1h_ttl(self):
        msgs = [{"role": "system", "content": "System prompt"}]
        result = apply_anthropic_cache_control(msgs, cache_ttl="1h")
        sys_content = result[0]["content"]
        assert isinstance(sys_content, list)
        assert sys_content[0]["cache_control"]["ttl"] == "1h"

    def test_max_4_breakpoints(self):
        msgs = [
            {"role": "system", "content": "System"},
        ] + [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
            for i in range(10)
        ]
        result = apply_anthropic_cache_control(msgs)
        # Count how many messages have cache_control
        count = 0
        for msg in result:
            content = msg.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and "cache_control" in item:
                        count += 1
            elif "cache_control" in msg:
                count += 1
        assert count <= 4


class TestApplyAnthropicCacheControlAliasing:
    """Targeted shallow-copy contract: unmodified messages share references
    with the input; modified messages are independent copies; the input list
    and dicts are never mutated."""

    def _build_long_session(self, n_total: int = 200):
        msgs = [{"role": "system", "content": "You are helpful"}]
        for i in range(n_total - 1):
            role = "user" if i % 2 == 0 else "assistant"
            msgs.append(
                {
                    "role": role,
                    "content": [
                        {"type": "text", "text": f"turn {i} block 0"},
                        {"type": "text", "text": f"turn {i} block 1"},
                    ],
                }
            )
        return msgs

    def test_id_isolation_marked_vs_unmarked(self):
        msgs = self._build_long_session(n_total=200)
        result = apply_anthropic_cache_control(msgs)

        assert result is not msgs
        assert len(result) == len(msgs)

        non_sys = [i for i, m in enumerate(msgs) if m.get("role") != "system"]
        marked = {0, *non_sys[-3:]}

        for i, (orig, new) in enumerate(zip(msgs, result)):
            if i in marked:
                assert new is not orig, f"marked index {i} should be a copy"
                if isinstance(orig.get("content"), list) and isinstance(
                    new.get("content"), list
                ):
                    assert new["content"] is not orig["content"]
                    for a, b in zip(orig["content"], new["content"]):
                        if isinstance(a, dict):
                            assert a is not b
            else:
                assert new is orig, f"unmarked index {i} should share reference"

    def test_no_mutation_of_input(self):
        import copy as _copy

        msgs = self._build_long_session(n_total=50)
        snapshot = _copy.deepcopy(msgs)
        _ = apply_anthropic_cache_control(msgs)
        assert msgs == snapshot, "input api_messages must not be mutated"

    def test_behavioral_parity_with_deepcopy_reference(self):
        import copy as _copy

        def _reference_impl(api_messages, cache_ttl="5m", native_anthropic=False):
            messages = _copy.deepcopy(api_messages)
            if not messages:
                return messages
            marker = {"type": "ephemeral"}
            if cache_ttl == "1h":
                marker["ttl"] = "1h"
            breakpoints_used = 0
            if messages[0].get("role") == "system":
                _apply_cache_marker(
                    messages[0], marker, native_anthropic=native_anthropic
                )
                breakpoints_used += 1
            remaining = 4 - breakpoints_used
            non_sys = [
                i
                for i in range(len(messages))
                if messages[i].get("role") != "system"
            ]
            for idx in non_sys[-remaining:]:
                _apply_cache_marker(
                    messages[idx], marker, native_anthropic=native_anthropic
                )
            return messages

        scenarios = [
            self._build_long_session(n_total=200),
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
                {"role": "tool", "content": "result", "tool_call_id": "x"},
            ],
            [{"role": "user", "content": "only one"}],
            [
                {"role": "user", "content": [{"type": "text", "text": "a"}]},
                {"role": "assistant", "content": None},
            ],
        ]
        for msgs in scenarios:
            for ttl in ("5m", "1h"):
                for native in (False, True):
                    a = apply_anthropic_cache_control(
                        msgs, cache_ttl=ttl, native_anthropic=native
                    )
                    b = _reference_impl(
                        msgs, cache_ttl=ttl, native_anthropic=native
                    )
                    assert a == b, (
                        f"parity mismatch ttl={ttl} native={native} "
                        f"scenario_len={len(msgs)}"
                    )
