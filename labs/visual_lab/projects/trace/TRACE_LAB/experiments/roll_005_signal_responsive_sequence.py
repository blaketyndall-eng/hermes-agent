"""Roll 005: Signal-Responsive Sequence.

Combine:
- environment signals
- behavior profiles
- environment adaptation
- controlled drift
- roll-aware execution

This experiment is the first TRACE pipeline where images subtly influence their
own primitive behavior through lightweight signal extraction.
"""

import json
from pathlib import Path

from src.drift import build_roll_drift_sequence
from src.environment import apply_environment_bias, load_environment
from src.export import export_versions
from src.ingest import load_image
from src.profile_drift import apply_drift_to_profile
from src.profiles import load_profile, shadow_params_from_profile
from src.run_manager import create_run_directory
from src.shadow import apply_shadow_crush
from src.signal_adaptation import (
    apply_signal_offsets_to_profile,
    primitive_offsets_from_signals,
)
from src.signals import extract_environment_signals
from src.texture import add_shadow_texture
from src.utils import ensure_dir, list_image_files, safe_stem

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input" / "phone"
RUNS_ROOT = ROOT / "runs"

EXPERIMENT_ID = "ROLL_005_SIGNAL_RESPONSIVE_SEQUENCE"


PROFILE_PATH = ROOT / "profiles" / "night_walk_profile.json"
ENVIRONMENT_PATH = ROOT / "environments" / "convenience_store_environment.json"
DRIFT_PATH = ROOT / "profiles" / "drift_profiles" / "subtle_night_drift.json"


def main() -> None:
    profile = load_profile(PROFILE_PATH)
    environment = load_environment(ENVIRONMENT_PATH)
    drift_profile = load_environment(DRIFT_PATH)

    image_paths = list_image_files(INPUT_DIR)

    if not image_paths:
        print(f"No images found in: {INPUT_DIR}")
        return

    run_dir = create_run_directory(
        RUNS_ROOT,
        experiment_id=EXPERIMENT_ID,
        version="v1",
    )

    outputs_dir = ensure_dir(run_dir / "outputs")
    logs_dir = ensure_dir(run_dir / "logs")

    drift_sequence = build_roll_drift_sequence(
        total_images=len(image_paths),
        drift_rules=drift_profile.get("drift_rules", {}),
    )

    signal_log = []

    base_environment_profile = apply_environment_bias(profile, environment)

    for index, image_path in enumerate(image_paths):
        image = load_image(image_path)
        stem = safe_stem(image_path.name)

        signals = extract_environment_signals(image)
        signal_offsets = primitive_offsets_from_signals(signals)

        signal_adjusted_profile = apply_signal_offsets_to_profile(
            base_environment_profile,
            signal_offsets,
        )

        drifted_profile = apply_drift_to_profile(
            signal_adjusted_profile,
            drift_sequence[index],
        )

        params = shadow_params_from_profile(drifted_profile)

        processed = apply_shadow_crush(
            image,
            crush_strength=params["crush_strength"],
            contrast_boost=params["contrast_boost"],
        )

        processed = add_shadow_texture(
            processed,
            noise_level=params["noise_level"],
            shadow_threshold=params["shadow_threshold"],
        )

        export_versions(
            {
                "original": image,
                "signal_responsive": processed,
            },
            outputs_dir,
            stem,
        )

        signal_log.append(
            {
                "filename": image_path.name,
                "signals": signals,
                "signal_offsets": signal_offsets,
                "drift_values": drift_sequence[index],
                "final_params": params,
            }
        )

    with (logs_dir / "signal_response_log.json").open("w", encoding="utf-8") as file:
        json.dump(signal_log, file, indent=2)
        file.write("\n")

    summary_path = run_dir / "summary.md"
    summary_path.write_text(
        """# TRACE Signal-Responsive Sequence Summary

This run combined:

- environment signals
- profile adaptation
- controlled drift
- roll-aware execution

Generated artifact:
- logs/signal_response_log.json

Key review questions:

- Did signal adaptation remain subtle?
- Did environments feel more believable?
- Did darkness behavior improve?
- Did adaptation become too deterministic?
- Did the sequence retain emotional coherence?

Important:

TRACE should respond to environments without visibly announcing adaptation.
""",
        encoding="utf-8",
    )

    print("TRACE signal-responsive sequence complete.")
    print(f"Run folder: {run_dir}")


if __name__ == "__main__":
    main()
