"""Roll 010: Recurrence Analysis.

TRACE studies whether believable sequences contain recurring behavioral motifs:
repeated darkness patterns, spatial pressure, anchor density, and environmental
ambiguity.
"""

import json
from pathlib import Path

from src.anchors import analyze_memory_anchors
from src.ingest import load_image
from src.recurrence import (
    create_behavior_signature,
    summarize_recurrence,
)
from src.run_manager import create_run_directory
from src.signals import extract_environment_signals
from src.spatial import extract_spatial_signals
from src.temporal import classify_temporal_phase
from src.utils import ensure_dir, list_image_files

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input" / "phone"
RUNS_ROOT = ROOT / "runs"

EXPERIMENT_ID = "ROLL_010_RECURRENCE_ANALYSIS"


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

    logs_dir = ensure_dir(run_dir / "logs")

    signatures = []
    frame_log = []

    for index, image_path in enumerate(image_paths):
        image = load_image(image_path)

        environment_signals = extract_environment_signals(image)
        spatial_signals = extract_spatial_signals(image)
        anchor_analysis = analyze_memory_anchors(image)

        signature = create_behavior_signature(
            environment_signals,
            spatial_signals,
            anchor_analysis.get("summary", {}),
        )

        phase = classify_temporal_phase(index, len(image_paths))

        signatures.append(signature)

        frame_log.append(
            {
                "frame": image_path.name,
                "phase": phase,
                "signature": signature,
                "environment_signals": environment_signals,
                "spatial_signals": spatial_signals,
                "anchor_summary": anchor_analysis.get("summary", {}),
            }
        )

    recurrence_summary = summarize_recurrence(signatures)

    with (logs_dir / "recurrence_analysis.json").open("w", encoding="utf-8") as file:
        json.dump(
            {
                "summary": recurrence_summary,
                "frames": frame_log,
            },
            file,
            indent=2,
        )
        file.write("\n")

    summary_path = run_dir / "summary.md"
    summary_path.write_text(
        """# TRACE Recurrence Analysis Summary

This experiment studies recurring behavioral motifs across a sequence.

Current motifs include:

- darkness behavior
- shadow coverage
- spatial isolation
- foreground pressure
- anchor density
- color ambiguity

Review goals:

- Did the sequence feel environmentally coherent?
- Did recurrence remain subtle?
- Did repeated motifs improve memory realism?
- Did the roll avoid mechanical repetition?
- Did the world feel emotionally continuous?

TRACE should increasingly preserve:

subconscious environmental recurrence

rather than:

obvious visual repetition.
""",
        encoding="utf-8",
    )

    print("TRACE recurrence analysis complete.")
    print(f"Run folder: {run_dir}")


if __name__ == "__main__":
    main()
