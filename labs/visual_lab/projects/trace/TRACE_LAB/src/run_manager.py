"""Run management helpers for TRACE Imaging Lab.

A run is a timestamped experiment artifact containing outputs, contact sheets,
logs, a copied manifest, and a human-readable summary file.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.utils import ensure_dir


def create_run_directory(
    runs_root: str | Path,
    experiment_id: str,
    version: str = "v1",
) -> Path:
    """Create a timestamped run directory.

    Example:
        runs/2026-05-13_142530_trace_001_shadow_v1/
    """
    runs_root = ensure_dir(runs_root)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    safe_experiment = experiment_id.lower().replace(" ", "_")
    run_name = f"{timestamp}_{safe_experiment}_{version}"

    run_dir = runs_root / run_name
    ensure_dir(run_dir)
    ensure_dir(run_dir / "outputs")
    ensure_dir(run_dir / "contact_sheets")
    ensure_dir(run_dir / "logs")
    ensure_dir(run_dir / "scoring")

    return run_dir


def load_manifest(path: str | Path) -> Dict[str, Any]:
    """Load an experiment manifest from JSON."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_manifest_copy(manifest: Dict[str, Any], run_dir: str | Path) -> Path:
    """Write a copy of the manifest into the run directory."""
    run_dir = Path(run_dir)
    output_path = run_dir / "manifest.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)
        file.write("\n")

    return output_path


def write_run_summary(
    run_dir: str | Path,
    experiment_id: str,
    title: str,
    image_count: int,
) -> Path:
    """Create a starter summary file for human review."""
    run_dir = Path(run_dir)
    summary_path = run_dir / "summary.md"

    content = f"""# TRACE Run Summary

Experiment: {experiment_id}

Title: {title}

Image count: {image_count}

---

# Generated Artifacts

- outputs/
- contact_sheets/
- logs/
- scoring/
- manifest.json

---

# Human Observations

_To be filled after reviewing contact sheets._

## Strongest behavior

## Weakest behavior

## Most believable output

## Most phone-like output

## Most memorable output

---

# Failure Notes

Document any over-processing, muddy blacks, fake texture, or loss of subject detail.

---

# Next Experiment Recommendation

_To be filled after review._
"""

    summary_path.write_text(content, encoding="utf-8")
    return summary_path
