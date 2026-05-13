"""Roll 006: Memory Anchor Analysis.

Analyze highlight-based memory anchors across a sequence.

This experiment studies what visually persistent details may contribute to:
- memory pressure
- emotional realism
- environmental believability

without using heavy semantic scene understanding.
"""

import json
from pathlib import Path

from src.anchors import analyze_memory_anchors
from src.ingest import load_image
from src.run_manager import create_run_directory
from src.signals import extract_environment_signals
from src.utils import ensure_dir, list_image_files

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input" / "phone"
RUNS_ROOT = ROOT / "runs"

EXPERIMENT_ID = "ROLL_006_MEMORY_ANCHOR_ANALYSIS"


def main() -> None:
    image_paths = list_image_files(INPUT_DIR)

    if not image_paths:
        print(f"No images found in: {INPUT_DIR}")
        return

    run_dir = create_run_directory(
        RUNS_ROOT,
        experiment_id=EXPERIMENT_ID,
        version="v1",
    )

    analysis_dir = ensure_dir(run_dir / "anchor_analysis")

    results = []

    for image_path in image_paths:
        image = load_image(image_path)

        environment_signals = extract_environment_signals(image)
        anchor_analysis = analyze_memory_anchors(image)

        results.append(
            {
                "filename": image_path.name,
                "environment_signals": environment_signals,
                "anchor_analysis": anchor_analysis,
            }
        )

    output_path = analysis_dir / "memory_anchor_analysis.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)
        file.write("\n")

    summary_path = run_dir / "summary.md"
    summary_path.write_text(
        """# TRACE Memory Anchor Analysis Summary

This run analyzed lightweight memory-anchor candidates across a sequence.

Generated artifact:
- anchor_analysis/memory_anchor_analysis.json

Current implementation studies:

- isolated highlight regions
- bright connected areas
- anchor density
- anchor scale

Review goals:

- Which images contain strong isolated anchors?
- Do anchors correlate with emotional persistence?
- Does darkness amplify anchor strength?
- Do environments create different anchor behavior?

Important:

TRACE treats anchors as perceptual clues, not cinematic focal points.
""",
        encoding="utf-8",
    )

    print("TRACE memory anchor analysis complete.")
    print(f"Run folder: {run_dir}")


if __name__ == "__main__":
    main()
