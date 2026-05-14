"""Tests for the mtime-keyed YAML parse cache added in W2-T24.

Covers both plugins/memory/__init__.py and plugins/context_engine/__init__.py
which have identical (but independent) implementations.

W2-T24
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import plugins.memory as mem_plugin
import plugins.context_engine as ctx_plugin
from plugins.memory import _invalidate_plugin_yaml_cache as mem_invalidate_yaml
from plugins.context_engine import _invalidate_plugin_yaml_cache as ctx_invalidate_yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# plugins.memory — yaml cache tests
# ---------------------------------------------------------------------------

class TestMemoryPluginYamlCache:

    def setup_method(self):
        mem_invalidate_yaml()

    def test_plugin_yaml_cached_on_unchanged_mtime(self, tmp_path: Path) -> None:
        """yaml.safe_load is called only once when mtime does not change."""
        yaml_file = tmp_path / "plugin.yaml"
        _write_yaml(yaml_file, "description: Test provider\n")

        with patch.object(mem_plugin.yaml, "safe_load", wraps=mem_plugin.yaml.safe_load) as mock_load:
            result1 = mem_plugin._load_plugin_yaml(yaml_file)
            result2 = mem_plugin._load_plugin_yaml(yaml_file)

        assert result1 == {"description": "Test provider"}
        assert result1 == result2
        assert mock_load.call_count == 1, (
            f"Expected yaml.safe_load to be called once (cache hit on second call), "
            f"got {mock_load.call_count}"
        )

    def test_plugin_yaml_reparsed_on_mtime_change(self, tmp_path: Path) -> None:
        """yaml.safe_load is called again when the file mtime changes."""
        yaml_file = tmp_path / "plugin.yaml"
        _write_yaml(yaml_file, "description: First version\n")

        with patch.object(mem_plugin.yaml, "safe_load", wraps=mem_plugin.yaml.safe_load) as mock_load:
            result1 = mem_plugin._load_plugin_yaml(yaml_file)

            # Modify the file; bump mtime explicitly so st_mtime_ns definitely advances.
            _write_yaml(yaml_file, "description: Second version\n")
            new_mtime = yaml_file.stat().st_mtime + 1
            os.utime(yaml_file, (new_mtime, new_mtime))

            result2 = mem_plugin._load_plugin_yaml(yaml_file)

        assert result1 == {"description": "First version"}
        assert result2 == {"description": "Second version"}
        assert mock_load.call_count == 2, (
            f"Expected yaml.safe_load to be called twice (mtime changed), "
            f"got {mock_load.call_count}"
        )

    def test_invalidate_plugin_yaml_cache_clears_entries(self, tmp_path: Path) -> None:
        """_invalidate_plugin_yaml_cache() forces a re-parse on next call."""
        yaml_file = tmp_path / "plugin.yaml"
        _write_yaml(yaml_file, "description: Cached\n")

        with patch.object(mem_plugin.yaml, "safe_load", wraps=mem_plugin.yaml.safe_load) as mock_load:
            mem_plugin._load_plugin_yaml(yaml_file)
            assert mock_load.call_count == 1

            mem_invalidate_yaml()

            mem_plugin._load_plugin_yaml(yaml_file)
            assert mock_load.call_count == 2, (
                "Expected re-parse after cache invalidation"
            )

    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        """A non-existent path returns {} without raising."""
        result = mem_plugin._load_plugin_yaml(tmp_path / "nonexistent.yaml")
        assert result == {}


# ---------------------------------------------------------------------------
# plugins.context_engine — yaml cache tests (mirror)
# ---------------------------------------------------------------------------

class TestContextEnginePluginYamlCache:

    def setup_method(self):
        ctx_invalidate_yaml()

    def test_plugin_yaml_cached_on_unchanged_mtime(self, tmp_path: Path) -> None:
        """yaml.safe_load is called only once when mtime does not change."""
        yaml_file = tmp_path / "plugin.yaml"
        _write_yaml(yaml_file, "description: Test engine\n")

        with patch.object(ctx_plugin.yaml, "safe_load", wraps=ctx_plugin.yaml.safe_load) as mock_load:
            result1 = ctx_plugin._load_plugin_yaml(yaml_file)
            result2 = ctx_plugin._load_plugin_yaml(yaml_file)

        assert result1 == {"description": "Test engine"}
        assert result1 == result2
        assert mock_load.call_count == 1, (
            f"Expected yaml.safe_load to be called once (cache hit on second call), "
            f"got {mock_load.call_count}"
        )

    def test_plugin_yaml_reparsed_on_mtime_change(self, tmp_path: Path) -> None:
        """yaml.safe_load is called again when the file mtime changes."""
        yaml_file = tmp_path / "plugin.yaml"
        _write_yaml(yaml_file, "description: Engine v1\n")

        with patch.object(ctx_plugin.yaml, "safe_load", wraps=ctx_plugin.yaml.safe_load) as mock_load:
            result1 = ctx_plugin._load_plugin_yaml(yaml_file)

            _write_yaml(yaml_file, "description: Engine v2\n")
            new_mtime = yaml_file.stat().st_mtime + 1
            os.utime(yaml_file, (new_mtime, new_mtime))

            result2 = ctx_plugin._load_plugin_yaml(yaml_file)

        assert result1 == {"description": "Engine v1"}
        assert result2 == {"description": "Engine v2"}
        assert mock_load.call_count == 2, (
            f"Expected yaml.safe_load to be called twice (mtime changed), "
            f"got {mock_load.call_count}"
        )

    def test_invalidate_plugin_yaml_cache_clears_entries(self, tmp_path: Path) -> None:
        """_invalidate_plugin_yaml_cache() forces a re-parse on next call."""
        yaml_file = tmp_path / "plugin.yaml"
        _write_yaml(yaml_file, "description: Cached engine\n")

        with patch.object(ctx_plugin.yaml, "safe_load", wraps=ctx_plugin.yaml.safe_load) as mock_load:
            ctx_plugin._load_plugin_yaml(yaml_file)
            assert mock_load.call_count == 1

            ctx_invalidate_yaml()

            ctx_plugin._load_plugin_yaml(yaml_file)
            assert mock_load.call_count == 2, (
                "Expected re-parse after cache invalidation"
            )

    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        """A non-existent path returns {} without raising."""
        result = ctx_plugin._load_plugin_yaml(tmp_path / "nonexistent.yaml")
        assert result == {}
