"""Roll 009: Temporal Pacing.

TRACE studies whether emotional realism emerges through sequence accumulation
rather than isolated frame quality.
"""

import json
from pathlib import Path

from src.anchors import analyze_memory_anchors
from src.environment import load_environment
from src.ingest import load_image
from src.run_manager import create_run_directory
from src.signals import extract_environment_signals
from src.spatial import extract_spatial_signals
from src.temporal import (
    calculate_memory_density,
    calculate_sequence_pressure,
    classify_temporal_phase,
    estimate_temporal_drift,
)
from src.utils import ensure_dir, list_image_files

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input" / "phone"
RUNS_ROOT = ROOT / "runs"

EXPERIMENT_ID = "ROLL_009_TEMPORAL_PACING"
ENVIRONMENT_PATH = ROOT / "environments" / "convenience_store_environment.json"


def main() -> None:
    environment = load_environment(ENVIRONMENT_PATH)
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

    sequence_pressures = []
    temporal_log = []

    environment_bias = float(environment.get("bias_strength", 0.5))

    for index, image_path in enumerate(image_paths):
        image = load_image(image_path)

        signals = extract_environment_signals(image)
        spatial = extract_spatial_signals(image)
        anchors = analyze_memory_anchors(image)

        sequence_pressure = calculate_sequence_pressure(
            foreground_dominance=spatial["foreground_dominance"],
            edge_darkness=spatial["edge_darkness"],
            spatial_isolation=spatial["spatial_isolation"],
        )

        memory_density = calculate_memory_density(
            anchor_density=anchors["summary"].get("anchor_density", 0.0),
            shadow_density=signals.get("shadow_density", 0.0),
            environment_bias=environment_bias,
        )

        phase = classify_temporal_phase(index, len(image_paths))

        sequence_pressures.append(sequence_pressure)

        temporal_log.append(
            {
                "frame": image_path.name,
                "phase": phase,
                "sequence_pressure": sequence_pressure,
                "memory_density": memory_density,
                "signals": signals,
                "spatial": spatial,
                "anchors": anchors.get("summary", {}),
            }
        )

    pacing_summary = estimate_temporal_drift(sequence_pressures)

    with (logs_dir / "temporal_pacing_log.json").open("w", encoding="utf-8") as file:
        json.dump(
            {
                "summary": pacing_summary,
                "frames": temporal_log,
            },
            file,
            indent=2,
        )
        file.write("\n")

    summary_path = run_dir / "summary.md"
    summary_path.write_text(
        """# TRACE Temporal Pacing Summary

This experiment studies:

- emotional accumulation
- sequence pressure
- memory density
- pacing drift
- perceptual phases

Important review questions:

- Did pressure accumulate naturally?
- Did the sequence feel emotionally coherent?
- Did darkness and ambiguity drift gradually?
- Did later frames feel emotionally heavier?
- Did the roll preserve memory continuity?

TRACE should increasingly optimize:

sequence emotional realism

rather than:

single-frame polish.
""",
        encoding="utf-8",
    )

    print("TRACE temporal pacing experiment complete.")
    print(f"Run folder: {run_dir}")


if __name__ == "__main__":
    main()
