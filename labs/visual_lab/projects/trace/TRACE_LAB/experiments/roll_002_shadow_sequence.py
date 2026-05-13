"""Roll 002: Shadow Sequence.

Process a sequence of images using:
- a base behavior profile
- controlled drift
- roll-aware execution

This is the first TRACE experiment where images influence a sequence-level
behavior model instead of being processed independently.
"""

import argparse
import json
from pathlib import Path

from src.drift import build_roll_drift_sequence
from src.export import create_contact_sheet, export_versions, write_experiment_log
from src.ingest import load_image
from src.profile_drift import apply_drift_to_profile
from src.profiles import load_profile, shadow_params_from_profile
from src.run_manager import create_run_directory, write_run_summary
from src.shadow import apply_shadow_crush
from src.texture import add_shadow_texture
from src.utils import ensure_dir, list_image_files, safe_stem

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input" / "phone"
RUNS_ROOT = ROOT / "runs"


EXPERIMENT_ID = "ROLL_002_SHADOW_SEQUENCE"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TRACE roll-aware shadow sequence")
    parser.add_argument("--profile", required=True, type=str)
    parser.add_argument("--drift", required=True, type=str)
    return parser.parse_args()


def load_json_relative(path_value: str) -> dict:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    args = parse_args()

    profile = load_profile(ROOT / args.profile)
    drift_profile = load_json_relative(args.drift)

    image_paths = list_image_files(INPUT_DIR)
    if not image_paths:
        print(f"No images found in: {INPUT_DIR}")
        return

    drift_sequence = build_roll_drift_sequence(
        total_images=len(image_paths),
        drift_rules=drift_profile.get("drift_rules", {}),
    )

    run_dir = create_run_directory(
        RUNS_ROOT,
        experiment_id=EXPERIMENT_ID,
        version="v1",
    )

    outputs_dir = ensure_dir(run_dir / "outputs")
    contacts_dir = ensure_dir(run_dir / "contact_sheets")
    logs_dir = ensure_dir(run_dir / "logs")

    log_rows = []

    for index, image_path in enumerate(image_paths):
        image = load_image(image_path)
        stem = safe_stem(image_path.name)

        drift_values = drift_sequence[index]
        drifted_profile = apply_drift_to_profile(profile, drift_values)
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

        versions = {
            "original": image,
            "trace_sequence": processed,
        }

        export_versions(versions, outputs_dir, stem)

        create_contact_sheet(
            versions,
            contacts_dir / f"{stem}_contact_sheet.jpg",
        )

        log_rows.append(
            {
                "filename": image_path.name,
                "version": "trace_sequence",
                "shadow_strength": params["crush_strength"],
                "contrast_level": params["contrast_boost"],
                "noise_level": params["noise_level"],
                "notes": f"Drift values: {drift_values}",
            }
        )

    write_experiment_log(
        log_rows,
        logs_dir / "roll_002_shadow_sequence_log.csv",
    )

    drift_export = {
        "profile": profile,
        "drift_profile": drift_profile,
        "drift_sequence": drift_sequence,
    }

    with (logs_dir / "drift_sequence.json").open("w", encoding="utf-8") as file:
        json.dump(drift_export, file, indent=2)
        file.write("\n")

    write_run_summary(
        run_dir,
        experiment_id=EXPERIMENT_ID,
        title="Roll-aware TRACE shadow sequence",
        image_count=len(image_paths),
    )

    print("TRACE roll-aware sequence complete.")
    print(f"Run folder: {run_dir}")


if __name__ == "__main__":
    main()
