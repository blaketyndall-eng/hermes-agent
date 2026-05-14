"""Subprocess-isolated import tests for W2-T25.

Verifies that importing plugins.teams_pipeline.pipeline and
plugins.spotify.client does NOT load httpx (or its TLS stack) as a side
effect of the module import.  Each test spawns a fresh Python interpreter so
sys.modules starts clean — no cached imports from the test runner can
interfere.

The scripts use importlib.util.spec_from_file_location to load the target
.py file directly — bypassing the package __init__.py — so only the
transitive imports of the file under test can pull in httpx.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

# Absolute path to the worktree root, computed once so subprocess scripts
# can insert it onto sys.path without knowing their CWD.
_WORKTREE_ROOT = str(Path(__file__).parent.parent.resolve())


def _run_isolation_script(script: str) -> subprocess.CompletedProcess:
    """Run *script* in a subprocess and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        timeout=30,
        env={**os.environ, "PYTHONPATH": _WORKTREE_ROOT},
    )


class TestTeamsPipelineLazyHttpx:
    """httpx must not appear in sys.modules after importing teams_pipeline.pipeline."""

    def test_teams_pipeline_imports_without_httpx(self):
        # Use the worktree-relative path so the subprocess loads the modified
        # file, not whatever is installed in the editable venv.
        pipeline_path = os.path.join(_WORKTREE_ROOT, "plugins", "teams_pipeline", "pipeline.py")
        script = f"""
            import sys
            import types
            import importlib.util

            # Stub every module that pipeline.py imports at the top level so
            # the file can be loaded without the full Hermes stack.
            def _stub(name, **attrs):
                mod = types.ModuleType(name)
                for k, v in attrs.items():
                    setattr(mod, k, v)
                sys.modules[name] = mod
                # Register all parent packages too
                parts = name.split(".")
                for i in range(1, len(parts)):
                    parent_name = ".".join(parts[:i])
                    if parent_name not in sys.modules:
                        sys.modules[parent_name] = types.ModuleType(parent_name)

            _stub("agent.auxiliary_client",
                  async_call_llm=None,
                  extract_content_or_reasoning=None)
            _stub("hermes_constants",
                  get_hermes_home=lambda: __import__("pathlib").Path("/tmp"))
            _stub("plugins.teams_pipeline.meetings",
                  TeamsMeetingArtifactNotFoundError=Exception,
                  download_recording_artifact=None,
                  enrich_meeting_with_call_record=None,
                  fetch_preferred_transcript_text=None,
                  list_recording_artifacts=None,
                  resolve_meeting_reference=None)
            _stub("plugins.teams_pipeline.models",
                  MeetingArtifact=object,
                  TeamsMeetingPipelineJob=object,
                  TeamsMeetingRef=object,
                  TeamsMeetingSummaryPayload=object)
            _stub("plugins.teams_pipeline.store",
                  TeamsPipelineStore=object)
            _stub("tools.transcription_tools",
                  transcribe_audio=None)

            spec = importlib.util.spec_from_file_location(
                "plugins.teams_pipeline.pipeline",
                {pipeline_path!r},
            )
            module = importlib.util.module_from_spec(spec)
            # Register before exec so @dataclass can resolve cls.__module__
            sys.modules["plugins.teams_pipeline.pipeline"] = module
            spec.loader.exec_module(module)

            assert "httpx" not in sys.modules, (
                "httpx was imported at module level in plugins/teams_pipeline/pipeline.py; "
                "it should only be imported lazily inside the methods that use it. "
                "sys.modules keys containing 'httpx': "
                + str([k for k in sys.modules if "httpx" in k])
            )
        """
        result = _run_isolation_script(script)
        assert result.returncode == 0, (
            "Subprocess check failed — httpx was eagerly imported by "
            "plugins/teams_pipeline/pipeline.py:\n"
            f"  stdout: {result.stdout.decode(errors='replace')}\n"
            f"  stderr: {result.stderr.decode(errors='replace')}"
        )


class TestSpotifyClientLazyHttpx:
    """httpx must not appear in sys.modules after importing plugins.spotify.client."""

    def test_spotify_client_imports_without_httpx(self):
        client_path = os.path.join(_WORKTREE_ROOT, "plugins", "spotify", "client.py")
        script = f"""
            import sys
            import types
            import importlib.util

            def _stub(name, **attrs):
                mod = types.ModuleType(name)
                for k, v in attrs.items():
                    setattr(mod, k, v)
                sys.modules[name] = mod
                parts = name.split(".")
                for i in range(1, len(parts)):
                    parent_name = ".".join(parts[:i])
                    if parent_name not in sys.modules:
                        sys.modules[parent_name] = types.ModuleType(parent_name)

            _stub("hermes_cli.auth",
                  AuthError=type("AuthError", (Exception,), {{}}),
                  resolve_spotify_runtime_credentials=None)

            spec = importlib.util.spec_from_file_location(
                "plugins.spotify.client",
                {client_path!r},
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            assert "httpx" not in sys.modules, (
                "httpx was imported at module level in plugins/spotify/client.py; "
                "it should only be imported lazily inside SpotifyClient.request. "
                "sys.modules keys containing 'httpx': "
                + str([k for k in sys.modules if "httpx" in k])
            )
        """
        result = _run_isolation_script(script)
        assert result.returncode == 0, (
            "Subprocess check failed — httpx was eagerly imported by "
            "plugins/spotify/client.py:\n"
            f"  stdout: {result.stdout.decode(errors='replace')}\n"
            f"  stderr: {result.stderr.decode(errors='replace')}"
        )
