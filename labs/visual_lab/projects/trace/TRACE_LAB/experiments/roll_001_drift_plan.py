"""Roll 001: Drift Plan.

This experiment does not process images yet.
It creates a reviewable drift plan for a roll so we can inspect sequence behavior
before applying it to image outputs.

Usage:
    python experiments/roll_001_drift_plan.py \
      --roll rolls/late_walk_roll_v1/manifest.json \
      --drift profiles/drift_profiles/subtle_night_drift.json
"""

import argparse
import json
from pathlib import Path

from src.drift import build_roll_drift_sequence
from src.rolls import load_roll_manifest
from src.run_manager import create_run_directory
from src.utils import ensure_dir

ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "runs"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for roll drift planning."""
    parser = argparse.ArgumentParser(description="Create a TRACE roll drift plan")
    parser.add_argument(
        "--roll",
        type=str,
        required=True,
        help="Path to a roll manifest JSON file.",
    )
    parser.add_argument(
        "--drift",
        type=str,
        required=True,
        help="Path to a drift profile JSON file.",
    )
    return parser.parse_args()


def load_json_relative(path_value: str) -> dict:
    """Load JSON from a path relative to TRACE_LAB root unless absolute."""
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    args = parse_args()

    roll_path = Path(args.roll)
    if not roll_path.is_absolute():
        roll_path = ROOT / roll_path

    roll_manifest = load_roll_manifest(roll_path)
    drift_profile = load_json_relative(args.drift)

    roll_id = roll_manifest.get("roll_id", "unknown_roll")
    target_image_count = int(roll_manifest.get("target_image_count", 24))
    drift_rules = drift_profile.get("drift_rules", {})

    drift_sequence = build_roll_drift_sequence(
        total_images=target_image_count,
        drift_rules=drift_rules,
    )

    run_dir = create_run_directory(
        RUNS_ROOT,
        experiment_id=f"ROLL_DRIFT_PLAN_{roll_id}",
        version="v1",
    )
    plan_dir = ensure_dir(run_dir / "drift_plan")

    plan = {
        "roll_id": roll_id,
        "roll_manifest": roll_manifest,
        "drift_profile": drift_profile,
        "target_image_count": target_image_count,
        "drift_sequence": drift_sequence,
    }

    plan_path = plan_dir / "drift_plan.json"
    with plan_path.open("w", encoding="utf-8") as file:
        json.dump(plan, file, indent=2)
        file.write("\n")

    summary_path = run_dir / "summary.md"
    summary_path.write_text(
        f"""# TRACE Roll Drift Plan Summary

Roll ID:
{roll_id}

Drift Profile:
{drift_profile.get('drift_profile_id', args.drift)}

Target Image Count:
{target_image_count}

Generated Artifact:
- drift_plan/drift_plan.json

---

# Review Questions

- Does the drift feel subtle enough?
- Are any primitive offsets too aggressive?
- Does the sequence risk feeling random?
- Does the plan support coherence without uniformity?

---

# Next Step

If the drift plan looks restrained, wire these per-image offsets into profile-aware image processing.
""",
        encoding="utf-8",
    )

    print("Roll drift plan generated.")
    print(f"Run folder: {run_dir}")
    print(f"Plan: {plan_path}")


if __name__ == "__main__":
    main()
