"""Roll 004: Environment Signal Analysis.

Analyze a sequence of images and extract behavior-oriented environment signals.

This experiment does not alter images.
It studies environmental tendencies before adaptive behavior execution.
"""

import csv
from pathlib import Path

from src.ingest import load_image
from src.run_manager import create_run_directory
from src.signals import extract_environment_signals
from src.utils import ensure_dir, list_image_files

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input" / "phone"
RUNS_ROOT = ROOT / "runs"

EXPERIMENT_ID = "ROLL_004_SIGNAL_ANALYSIS"


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

    analysis_dir = ensure_dir(run_dir / "signal_analysis")
    csv_path = analysis_dir / "environment_signals.csv"

    rows = []

    for image_path in image_paths:
        image = load_image(image_path)
        signals = extract_environment_signals(image)

        row = {
            "filename": image_path.name,
            **signals,
        }

        rows.append(row)

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "filename",
                "darkness_level",
                "shadow_coverage",
                "highlight_concentration",
                "contrast_level",
                "color_ambiguity",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)

    summary_path = run_dir / "summary.md"
    summary_path.write_text(
        """# TRACE Environment Signal Summary

This run extracted lightweight behavioral environment signals from the input sequence.

Generated artifact:
- signal_analysis/environment_signals.csv

Review goals:

- identify recurring environmental tendencies
- compare darkness behavior across the roll
- study highlight concentration
- observe mixed-light ambiguity
- prepare future adaptive behavior execution

Important:

These signals are not aesthetic labels.
They are lightweight behavioral clues.
""",
        encoding="utf-8",
    )

    print("TRACE environment signal analysis complete.")
    print(f"Run folder: {run_dir}")


if __name__ == "__main__":
    main()
