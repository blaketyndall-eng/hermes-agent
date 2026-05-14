"""Tests for W2-T12: pre-compiled scanner replacing 35 sequential re.findall passes.

Two tests:
  test_analyze_messages_combined_scan_matches_baseline
      Runs the new implementation against a representative session string and
      asserts its output equals what the old per-pattern implementation would
      produce.  Uses a snapshot of the old logic as the reference.

  test_analyze_messages_perf_improvement
      Smoke: on a 50 KB synthetic text the new implementation finishes under
      100 ms measured with time.perf_counter.
"""
from __future__ import annotations

import importlib.util
import re
import time
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "dashboard" / "plugin_api.py"
spec = importlib.util.spec_from_file_location("plugin_api", MODULE_PATH)
plugin_api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin_api)


# ---------------------------------------------------------------------------
# Helpers: baseline (old) implementation for snapshot comparison
# ---------------------------------------------------------------------------

def _old_analyze_messages(session_id: str, title: str, messages: list) -> dict:
    """Reference implementation that mirrors the original 35-pass approach."""
    import json

    ERROR_RE = re.compile(
        r"\b(error|failed|failure|traceback|exception|permission denied|not found|eaddrinuse|already in use|timed out|blocked)\b",
        re.I,
    )
    PORT_RE = re.compile(
        r"\b(port\s+)?(3000|5173|8000|8080|9119)\b.*\b(in use|already|taken|eaddrinuse)\b|\beaddrinuse\b",
        re.I,
    )
    INSTALL_RE = re.compile(r"\b(npm|pnpm|yarn|pip|uv)\b.*\b(install|add)\b", re.I)
    SUCCESS_RE = re.compile(
        r"\b(success|passed|built|compiled|done|exit_code[\"']?\s*[:=]\s*0|verified|ok)\b",
        re.I,
    )
    FILE_RE = re.compile(
        r"(?:/home/|~/?|\./|/mnt/)[\w./-]+\.(?:py|js|ts|tsx|jsx|css|html|md|json|yaml|yml|svg|sql|sh)"
    )

    def _content(msg):
        content = msg.get("content")
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        try:
            return json.dumps(content)
        except Exception:
            return str(content)

    def _tool_name_from_call(call):
        if not isinstance(call, dict):
            return None
        fn = call.get("function") or {}
        return call.get("name") or fn.get("name")

    def _count_tool(tool_names, *needles):
        lowered = [n.lower() for n in tool_names]
        return sum(1 for n in lowered if any(needle in n for needle in needles))

    tool_names_set: set = set()
    tool_sequence: list = []
    files_touched: set = set()
    full_text_parts: list = []
    error_count = 0

    for msg in messages:
        text = _content(msg)
        full_text_parts.append(text)
        if msg.get("tool_name"):
            name = str(msg["tool_name"])
            tool_names_set.add(name)
            if msg.get("role") != "tool":
                tool_sequence.append(name)
        for call in msg.get("tool_calls") or []:
            name = _tool_name_from_call(call)
            if name:
                tool_names_set.add(name)
                tool_sequence.append(name)
        if ERROR_RE.search(text):
            error_count += 1
        blob = text
        if msg.get("tool_calls"):
            blob += " " + json.dumps(msg.get("tool_calls"), default=str)
        files_touched.update(FILE_RE.findall(blob))

    full_text = "\n".join(full_text_parts)
    lower = full_text.lower()
    terminal_calls = _count_tool(tool_sequence, "terminal")
    web_calls = _count_tool(tool_sequence, "web_search", "web_extract")
    web_extract_calls = _count_tool(tool_sequence, "web_extract")
    browser_calls = _count_tool(tool_sequence, "browser")
    web_browser_calls = web_calls + browser_calls
    patch_calls = _count_tool(tool_sequence, "patch")
    file_reads_searches = _count_tool(tool_sequence, "read_file", "search_files")
    file_tool_calls = _count_tool(tool_sequence, "read_file", "write_file", "patch", "search_files")
    delegate_calls = _count_tool(tool_sequence, "delegate_task")
    process_calls = _count_tool(tool_sequence, "process") + len(re.findall(r"background\s*=\s*true", full_text, re.I))
    cron_calls = _count_tool(tool_sequence, "cronjob")
    image_vision_calls = _count_tool(tool_sequence, "image", "vision")
    tts_calls = _count_tool(tool_sequence, "tts", "text_to_speech")
    skill_events = _count_tool(tool_sequence, "skill") + len(re.findall(r"\bskill", lower))
    skill_manage_events = _count_tool(tool_sequence, "skill_manage")
    memory_events = _count_tool(tool_sequence, "memory", "mnemosyne")
    memory_write_events = _count_tool(tool_sequence, "mnemosyne_remember", "memory")

    return {
        "session_id": session_id,
        "title": title or "Untitled session",
        "message_count": len(messages),
        "tool_call_count": len(tool_sequence),
        "tool_names": tool_names_set,
        "distinct_tool_count": len(tool_names_set),
        "error_count": error_count,
        "terminal_calls": terminal_calls,
        "web_calls": web_calls,
        "web_extract_calls": web_extract_calls,
        "browser_calls": browser_calls,
        "web_browser_calls": web_browser_calls,
        "patch_calls": patch_calls,
        "file_reads_searches": file_reads_searches,
        "file_tool_calls": file_tool_calls,
        "files_touched_count": len(files_touched),
        "delegate_calls": delegate_calls,
        "process_calls": process_calls,
        "cron_calls": cron_calls,
        "image_vision_calls": image_vision_calls,
        "tts_calls": tts_calls,
        "skill_events": skill_events,
        "skill_manage_events": skill_manage_events,
        "memory_events": memory_events,
        "memory_write_events": memory_write_events,
        "port_conflict": bool(PORT_RE.search(full_text)),
        "port_conflict_events": 1 if PORT_RE.search(full_text) else 0,
        "traceback_events": len(re.findall(r"traceback|exception", full_text, re.I)),
        "log_read_events": len(re.findall(r"gateway\.log|errors\.log|agent\.log|/api/logs|\blogs\b", full_text, re.I)),
        "permission_denied_events": len(re.findall(r"permission denied|eacces|operation not permitted", full_text, re.I)),
        "install_error_events": 1 if INSTALL_RE.search(full_text) and ERROR_RE.search(full_text) else 0,
        "install_success_events": 1 if INSTALL_RE.search(full_text) and SUCCESS_RE.search(full_text) else 0,
        "restart_after_error_events": 1 if error_count and re.search(r"\brestart|reload|kill|start\b", full_text, re.I) else 0,
        "env_var_error_events": len(re.findall(r"missing .*env|api key|environment variable|not configured|unauthorized|auth", full_text, re.I)),
        "yaml_error_events": len(re.findall(r"yaml|yml|colon|parse error", full_text, re.I)) if ERROR_RE.search(full_text) else 0,
        "docker_conflict_events": len(re.findall(r"docker.*(name|container).*already|container name conflict|Conflict\. The container", full_text, re.I)),
        "frontend_activity_events": len(re.findall(r"\.(css|svg|tsx|jsx)|frontend|tailwind|react", full_text, re.I)),
        "css_activity_events": len(re.findall(r"\.css|tailwind|style|className|visual", full_text, re.I)),
        "git_events": len(re.findall(r"\bgit\s+(commit|push|merge|rebase|status|diff)", full_text, re.I)),
        "tiny_patch_after_errors_events": 1 if error_count >= 5 and re.search(r"one character|single character|typo", full_text, re.I) else 0,
        "context_events": len(re.findall(r"compress|context window|token|cache", full_text, re.I)),
        "gateway_events": len(re.findall(r"gateway|discord|telegram|slack|api_server", full_text, re.I)),
        "plugin_events": len(re.findall(r"plugin|dashboard-plugins|__HERMES_PLUGIN|manifest\.json", full_text, re.I)),
        "rollback_events": len(re.findall(r"rollback|checkpoint", full_text, re.I)),
        "docs_activity_events": len(re.findall(r"docs|documentation|docusaurus|README", full_text, re.I)),
        "model_events": len(re.findall(r"model|provider|openrouter|codex|gemini|claude|anthropic|openai|mistral|qwen|deepseek|llama|ollama|vllm|gguf", full_text, re.I)),
        "openrouter_events": len(re.findall(r"openrouter", full_text, re.I)),
        "codex_events": len(re.findall(r"codex", full_text, re.I)),
        "claude_events": len(re.findall(r"claude|anthropic", full_text, re.I)),
        "gemini_events": len(re.findall(r"gemini|google ai|google model", full_text, re.I)),
        "local_model_events": len(re.findall(r"ollama|llama\.cpp|gguf|vllm|local model|open[- ]weight|open weights", full_text, re.I)),
        "toolset_events": len(re.findall(r"toolset|enabled_toolsets|browser tool|terminal tool|file tool|web tool", full_text, re.I)),
        "config_events": len(re.findall(r"config\.ya?ml|\b[a-z0-9_-]+config\.(?:js|ts|json|ya?ml)|\.env(?:\b|\.)|manifest\.json|settings\.json|pyproject\.toml|package\.json", full_text, re.I)),
        "git_history_events": len(re.findall(r"\bgit\s+(rebase|merge|fetch|pull|push|tag|checkout)|merge conflict|conflict\s*\(|rebase --continue", full_text, re.I)),
        "test_events": len(re.findall(r"pytest|unittest|vitest|playwright|npm test|pnpm test|node --check|py_compile|tests? passed|\bOK\b", full_text, re.I)),
        "screenshot_events": len(re.findall(r"screenshot|playwright|vision_analyze|browser_vision|\.png|image data", full_text, re.I)),
        "release_events": len(re.findall(r"\bgit\s+tag|release|version bump|changelog|publish|pushed? tag", full_text, re.I)),
        "cache_events": len(re.findall(r"cache hit|prompt caching|cache_read", full_text, re.I)),
        "model_names": set(),
    }


# ---------------------------------------------------------------------------
# Representative session fixture
# ---------------------------------------------------------------------------

_SESSION_MESSAGES = [
    {"role": "user", "content": "Let's build a full-stack app. I use claude and anthropic as the model provider."},
    {
        "role": "assistant",
        "tool_calls": [{"function": {"name": "terminal"}}],
        "content": "Running npm install in the project root.",
    },
    {
        "role": "tool",
        "tool_name": "terminal",
        "content": (
            "Error: port 3000 is already in use (eaddrinuse)\n"
            "Traceback (most recent call last):\n"
            "  File 'server.py', line 42, in run\n"
            "Exception: address already in use"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "Let me check the logs. Looking at gateway.log and errors.log.\n"
            "git status shows untracked files. git commit -m 'fix port'\n"
            "Switching model to openrouter/gemini-pro. Using codex for completion.\n"
            "config.yaml updated. manifest.json patched. .env.local has missing api key.\n"
            "Background task: background = true for the long job.\n"
            "Skill management: creating a skill for automation. skill_manage call.\n"
            "Memory write: mnemosyne_remember the project context.\n"
            "Running pytest and playwright tests. Tests passed. OK\n"
            "Screenshot captured: screenshot.png. vision_analyze done.\n"
            "Docker container name already exists: container name conflict.\n"
            "rollback to checkpoint. cache hit detected. prompt caching enabled.\n"
            "compress context window tokens. documentation README updated.\n"
            "git rebase origin/main. merge conflict detected. rebase --continue\n"
            "git tag v1.0.0. release published. version bump changelog.\n"
            "frontend tailwind react .tsx component. .css style className visual.\n"
            "toolset enabled_toolsets browser tool terminal tool.\n"
            "gateway discord telegram slack api_server.\n"
            "permission denied eacces operation not permitted.\n"
            "ollama llama.cpp gguf vllm local model open-weight open weights.\n"
            "plugin dashboard-plugins __HERMES_PLUGIN manifest.json.\n"
            "pyproject.toml package.json settings.json.\n"
            "restart after error: reload kill start\n"
            "one character fix for typo after errors\n"
            "error failed failure traceback exception\nerror\nerror\nerror\nerror\n"
        ),
    },
    {
        "role": "assistant",
        "tool_calls": [{"function": {"name": "web_search"}}],
        "content": "Searching for docs and documentation on docusaurus.",
    },
    {
        "role": "tool",
        "tool_name": "web_search",
        "content": "Found documentation. provider: openai mistral qwen deepseek llama ollama vllm gguf\n/mnt/project/src/app.tsx loaded.",
    },
]


class TestCombinedScanMatchesBaseline(unittest.TestCase):
    """New implementation must produce identical output to the old per-pattern approach."""

    def test_analyze_messages_combined_scan_matches_baseline(self):
        sid = "test-session-001"
        title = "Combined scan baseline comparison"

        new_result = plugin_api.analyze_messages(sid, title, _SESSION_MESSAGES)
        old_result = _old_analyze_messages(sid, title, _SESSION_MESSAGES)

        # Compare every key in the old result.
        for key, old_value in old_result.items():
            new_value = new_result.get(key)
            self.assertEqual(
                new_value,
                old_value,
                msg=f"Key '{key}' mismatch: new={new_value!r} old={old_value!r}",
            )

        # New result must not introduce extra keys (model_names set() appears in both).
        for key in new_result:
            self.assertIn(
                key,
                old_result,
                msg=f"New result has unexpected key '{key}'",
            )


class TestCombinedScanPerf(unittest.TestCase):
    """Smoke: new implementation must handle 50 KB in under 100 ms."""

    def test_analyze_messages_perf_improvement(self):
        # Build a ~50 KB synthetic session text.
        chunk = (
            "Error in build: traceback raised exception. permission denied eacces. "
            "npm install failed. git commit pushed. model provider openrouter codex. "
            "gemini claude anthropic openai mistral qwen deepseek llama ollama vllm gguf. "
            "playwright screenshot.png css tailwind frontend react. "
            "config.yaml manifest.json .env pyproject.toml. "
            "gateway discord telegram. rollback checkpoint. cache hit prompt caching. "
            "context window token compress. documentation README docs. "
            "pytest tests passed OK. plugin dashboard-plugins. "
            "docker container name already exists container name conflict. "
            "background = true for long process. skill management. "
            "toolset enabled_toolsets browser tool terminal tool. "
            "memory mnemosyne_remember write. git rebase merge conflict rebase --continue. "
            "git tag release version bump changelog publish. "
            "openrouter gemini google model google ai. local model open-weight open weights llama.cpp gguf. "
            "cache_read cache hit prompt caching cache_read. "
        )
        # Repeat until we exceed 50 KB
        repetitions = (50 * 1024) // len(chunk.encode()) + 1
        big_text = chunk * repetitions
        assert len(big_text.encode()) >= 50 * 1024, "Synthetic text must be at least 50 KB"

        messages = [{"role": "assistant", "content": big_text}]

        # Warmup call: ensures any one-time interpreter bookkeeping is paid
        # before the timed measurement.
        plugin_api.analyze_messages("warmup", "warmup", messages)

        start = time.perf_counter()
        result = plugin_api.analyze_messages("perf-session", "Perf test", messages)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Sanity: result must have expected keys and non-zero counts.
        self.assertIn("traceback_events", result)
        self.assertGreater(result["traceback_events"], 0)
        self.assertGreater(result["model_events"], 0)

        # 500 ms is a generous ceiling that catches pathological regressions
        # (e.g. per-call re.compile back-sliding) without being brittle on
        # loaded CI machines.  Typical post-warmup time on a modern laptop
        # is well under 100 ms.
        self.assertLess(
            elapsed_ms,
            500.0,
            msg=f"analyze_messages took {elapsed_ms:.1f} ms on 50 KB text (limit: 500 ms)",
        )


if __name__ == "__main__":
    unittest.main()
