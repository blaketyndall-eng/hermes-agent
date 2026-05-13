"""Roll 003: Environment Sequence.

Combine:
- behavior profiles
- environment adaptation
- controlled drift
- roll-aware execution

This experiment explores how environment-specific behavior can influence a
sequence while preserving coherence and subtlety.
"""

import argparse
from pathlib import Path

from src.drift import build_roll_drift_sequence
from src.environment import apply_environment_bias, load_environment
from src.ingest import load_image
from src.profile_drift import apply_drift_to_profile
from src.profiles import load_profile, shadow_params_from_profile
from src.run_manager import create_run_directory
from src.shadow import apply_shadow_crush
from src.texture import add_shadow_texture
from src.utils import ensure_dir, list_image_files, safe_stem
from src.export import export_versions

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input" / "phone"
RUNS_ROOT = ROOT / "runs"


EXPERIMENT_ID = "ROLL_003_ENVIRONMENT_SEQUENCE"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TRACE environment-aware sequence")
    parser.add_argument("--profile", required=True, type=str)
    parser.add_argument("--environment", required=True, type=str)
    parser.add_argument("--drift", required=True, type=str)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    profile = load_profile(ROOT / args.profile)
    environment = load_environment(ROOT / args.environment)
    drift_profile = load_environment(ROOT / args.drift)

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

    drift_sequence = build_roll_drift_sequence(
        total_images=len(image_paths),
        drift_rules=drift_profile.get("drift_rules", {}),
    )

    base_environment_profile = apply_environment_bias(profile, environment)

    for index, image_path in enumerate(image_paths):
        image = load_image(image_path)
        stem = safe_stem(image_path.name)

        drift_values = drift_sequence[index]

        final_profile = apply_drift_to_profile(
            base_environment_profile,
            drift_values,
        )

        params = shadow_params_from_profile(final_profile)

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

        versions = {
            "original": image,
            "environment_sequence": processed,
        }

        export_versions(versions, outputs_dir, stem)

    print("TRACE environment-aware sequence complete.")
    print(f"Run folder: {run_dir}")


if __name__ == "__main__":
    main()
