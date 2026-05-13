"""Roll helpers for TRACE Imaging Lab.

A roll is a coherent behavioral sequence of images.
It is not simply a folder of processed files.
"""

import json
from pathlib import Path
from typing import Any, Dict

from src.utils import ensure_dir


def create_roll_structure(root: str | Path, roll_id: str) -> Path:
    """Create a TRACE roll folder structure."""
    root = ensure_dir(root)
    roll_dir = root / roll_id

    ensure_dir(roll_dir)
    ensure_dir(roll_dir / "images")
    ensure_dir(roll_dir / "evaluations")
    ensure_dir(roll_dir / "exports")

    return roll_dir


def load_roll_manifest(path: str | Path) -> Dict[str, Any]:
    """Load a roll manifest from JSON."""
    path = Path(path)

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_roll_summary(
    roll_dir: str | Path,
    roll_id: str,
    profile: str,
    image_count: int,
) -> Path:
    """Create a starter summary file for a roll."""
    roll_dir = Path(roll_dir)
    summary_path = roll_dir / "roll_summary.md"

    content = f"""# TRACE Roll Summary

Roll ID:
{roll_id}

Profile:
{profile}

Image Count:
{image_count}

---

# Sequence Notes

_To be filled after sequence review._

## Sequence coherence

## Environmental continuity

## Controlled drift

## Emotional continuity

## Strongest memory pressure image

---

# Sequence Failures

Document:

- preset repetition
- random drift
- inconsistent darkness
- fake texture
- environmental collapse

---

# Future Roll Direction

Suggested next roll:

Reason:
"""

    summary_path.write_text(content, encoding="utf-8")
    return summary_path
