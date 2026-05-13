"""Experiment 001: Shadow.

Study how different shadow treatments affect:
- atmosphere
- believability
- phone avoidance
- texture preservation

Optional profile usage:
    python experiments/exp_001_shadow.py --profile profiles/night_walk_profile.json
"""

import argparse
from pathlib import Path

from src.export import (
    create_contact_sheet,
    export_versions,
    write_experiment_log,
)
from src.ingest import load_image
from src.profiles import load_profile, shadow_params_from_profile
from src.shadow import (
    apply_shadow_crush,
    apply_shadow_lift,
    apply_trace_shadow_profile,
)
from src.texture import add_shadow_texture
from src.utils import ensure_dir, list_image_files, safe_stem

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input" / "phone"
OUTPUT_DIR = ROOT / "data" / "output" / "exp_001_shadow"
CONTACT_DIR = OUTPUT_DIR / "contact_sheets"
LOG_PATH = OUTPUT_DIR / "exp_001_shadow_log.csv"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for Experiment 001."""
    parser = argparse.ArgumentParser(description="Run TRACE Experiment 001: Shadow")
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Optional path to a TRACE behavior profile JSON file.",
    )
    return parser.parse_args()


def resolve_profile(profile_path: str | None):
    """Load a profile when provided and return profile-derived parameters."""
    if not profile_path:
        return None, {
            "crush_strength": 0.12,
            "contrast_boost": 1.03,
            "noise_level": 0.015,
            "shadow_threshold": 100,
        }

    path = Path(profile_path)
    if not path.is_absolute():
        path = ROOT / path

    profile = load_profile(path)
    params = shadow_params_from_profile(profile)
    return profile, params


def main() -> None:
    args = parse_args()
    profile, trace_params = resolve_profile(args.profile)

    ensure_dir(OUTPUT_DIR)
    ensure_dir(CONTACT_DIR)

    image_paths = list_image_files(INPUT_DIR)

    if not image_paths:
        print(f"No images found in: {INPUT_DIR}")
        return

    if profile:
        print(f"Using profile: {profile.get('profile_id', args.profile)}")
        print(f"TRACE candidate params: {trace_params}")

    log_rows = []

    for image_path in image_paths:
        print(f"Processing: {image_path.name}")

        image = load_image(image_path)
        stem = safe_stem(image_path.name)

        versions = {
            "original": image,
            "phone_flat": apply_shadow_lift(image, lift_amount=0.14),
            "crush": apply_shadow_crush(
                image,
                crush_strength=0.24,
                contrast_boost=1.10,
            ),
        }

        versions["texture"] = add_shadow_texture(
            versions["crush"],
            noise_level=0.03,
            shadow_threshold=115,
        )

        if profile:
            profile_crush = apply_shadow_crush(
                image,
                crush_strength=trace_params["crush_strength"],
                contrast_boost=trace_params["contrast_boost"],
            )
            versions["trace_candidate"] = add_shadow_texture(
                profile_crush,
                noise_level=trace_params["noise_level"],
                shadow_threshold=int(trace_params["shadow_threshold"]),
            )
        else:
            versions["trace_candidate"] = apply_trace_shadow_profile(image)

        export_versions(versions, OUTPUT_DIR, stem)

        create_contact_sheet(
            versions,
            CONTACT_DIR / f"{stem}_contact_sheet.jpg",
        )

        metadata = {
            "original": (0.00, 1.00, 0.00, "Baseline reference"),
            "phone_flat": (0.14, 0.96, 0.00, "Lifted shadows, phone-like cleanup"),
            "crush": (0.24, 1.10, 0.00, "Deeper blacks and stronger contrast"),
            "texture": (0.24, 1.10, 0.03, "Added restrained shadow texture"),
            "trace_candidate": (
                trace_params["crush_strength"],
                trace_params["contrast_boost"],
                trace_params["noise_level"],
                "Profile-guided TRACE shadow preservation" if profile else "Balanced TRACE shadow preservation",
            ),
        }

        for version_name, values in metadata.items():
            shadow_strength, contrast_level, noise_level, notes = values

            log_rows.append(
                {
                    "filename": image_path.name,
                    "version": version_name,
                    "shadow_strength": shadow_strength,
                    "contrast_level": contrast_level,
                    "noise_level": noise_level,
                    "notes": notes,
                }
            )

    write_experiment_log(log_rows, LOG_PATH)

    print("Experiment complete.")
    print(f"Outputs saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
