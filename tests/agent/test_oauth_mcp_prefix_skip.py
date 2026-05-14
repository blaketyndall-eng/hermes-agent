"""W2-T17: test that MCP-prefixed messages are skipped on subsequent turns.

Verifies the O(N) -> O(new_messages) optimisation in build_anthropic_kwargs:
once a message dict is flagged with _MCP_PREFIX_FLAG, subsequent calls to
build_anthropic_kwargs must not re-process it.
"""

import pytest

from agent.anthropic_adapter import (
    _MCP_PREFIX_FLAG,
    _MCP_TOOL_PREFIX,
    build_anthropic_kwargs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool_call(name: str, call_id: str) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": "{}"},
    }


def _make_assistant_msg(tool_name: str, index: int) -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [_make_tool_call(tool_name, f"call_{index}")],
    }


def _make_tool_result_msg(call_id: str) -> dict:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": "ok",
    }


def _build_history(n_turns: int) -> list:
    """Build a realistic message history with n_turns of tool use."""
    msgs = [{"role": "user", "content": "start"}]
    for i in range(n_turns):
        msgs.append(_make_assistant_msg(f"some_tool", i))
        msgs.append(_make_tool_result_msg(f"call_{i}"))
    return msgs


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOauthPrefixOnlyScansNewMessages:
    """Core optimisation test: second call only touches the 1 new message."""

    def test_oauth_prefix_only_scans_new_messages(self):
        """Build 100-msg history, call once, append 1 msg, call again.

        After the first call every existing message must carry _MCP_PREFIX_FLAG.
        After the second call only the newly-appended message should be newly
        flagged — the rest must not have had their names double-prefixed.
        """
        messages = _build_history(50)  # 1 user + 50*(assistant+tool) = 101 msgs
        assert len(messages) == 101

        # ── First call ──────────────────────────────────────────────────────
        build_anthropic_kwargs(
            model="claude-opus-4-6",
            messages=messages,
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            is_oauth=True,
        )

        # Every message dict must now be flagged.
        unflagged_after_first = [m for m in messages if not m.get(_MCP_PREFIX_FLAG)]
        assert unflagged_after_first == [], (
            f"{len(unflagged_after_first)} messages were not flagged after first call"
        )

        # Tool names in assistant messages should be prefixed exactly once.
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        for m in assistant_msgs:
            for tc in m.get("tool_calls") or []:
                name = tc["function"]["name"]
                assert name.startswith(_MCP_TOOL_PREFIX), f"name not prefixed: {name}"
                # Must not be double-prefixed.
                assert not name.startswith(_MCP_TOOL_PREFIX * 2), (
                    f"name double-prefixed: {name}"
                )

        # ── Append exactly one new assistant message ────────────────────────
        new_msg = _make_assistant_msg("brand_new_tool", 999)
        messages.append(new_msg)

        # Record which messages are still unflagged (should be exactly the new one).
        unflagged_before_second = [m for m in messages if not m.get(_MCP_PREFIX_FLAG)]
        assert len(unflagged_before_second) == 1
        assert unflagged_before_second[0] is new_msg

        # ── Second call ─────────────────────────────────────────────────────
        build_anthropic_kwargs(
            model="claude-opus-4-6",
            messages=messages,
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            is_oauth=True,
        )

        # All messages flagged after second call.
        unflagged_after_second = [m for m in messages if not m.get(_MCP_PREFIX_FLAG)]
        assert unflagged_after_second == []

        # The new message's tool name must be prefixed.
        new_tc_name = new_msg["tool_calls"][0]["function"]["name"]
        assert new_tc_name == _MCP_TOOL_PREFIX + "brand_new_tool"

        # Previously-prefixed names must not have gained an extra prefix.
        for m in assistant_msgs:
            for tc in m.get("tool_calls") or []:
                name = tc["function"]["name"]
                assert not name.startswith(_MCP_TOOL_PREFIX * 2), (
                    f"double-prefix detected after second call: {name}"
                )

    def test_non_oauth_does_not_set_flag(self):
        """When is_oauth=False the flag must not be written to message dicts."""
        messages = _build_history(5)
        build_anthropic_kwargs(
            model="claude-opus-4-6",
            messages=messages,
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            is_oauth=False,
        )
        for m in messages:
            assert _MCP_PREFIX_FLAG not in m, (
                f"Flag unexpectedly set when is_oauth=False: {m}"
            )

    def test_tool_names_prefixed_exactly_once_across_many_calls(self):
        """Repeated calls (simulating a long session) must not accumulate prefixes."""
        messages = [{"role": "user", "content": "go"}]
        messages.append(_make_assistant_msg("run_query", 0))
        messages.append(_make_tool_result_msg("call_0"))

        for _ in range(10):
            build_anthropic_kwargs(
                model="claude-opus-4-6",
                messages=messages,
                tools=None,
                max_tokens=4096,
                reasoning_config=None,
                is_oauth=True,
            )

        tc_name = messages[1]["tool_calls"][0]["function"]["name"]
        assert tc_name == _MCP_TOOL_PREFIX + "run_query", (
            f"Expected single prefix, got: {tc_name}"
        )

    def test_flag_absent_from_anthropic_messages_sent_to_api(self):
        """The _MCP_PREFIX_FLAG must not appear in any dict returned in kwargs['messages'].

        kwargs['messages'] is what gets forwarded to the Anthropic SDK.
        """
        messages = _build_history(5)
        kwargs = build_anthropic_kwargs(
            model="claude-opus-4-6",
            messages=messages,
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            is_oauth=True,
        )
        for anthropic_msg in kwargs["messages"]:
            assert _MCP_PREFIX_FLAG not in anthropic_msg, (
                f"Private flag leaked into API payload: {anthropic_msg}"
            )
            content = anthropic_msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        assert _MCP_PREFIX_FLAG not in block, (
                            f"Private flag leaked into content block: {block}"
                        )
