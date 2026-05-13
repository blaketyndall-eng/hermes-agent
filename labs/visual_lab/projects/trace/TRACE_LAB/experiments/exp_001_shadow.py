"""Experiment 001: Shadow.

Study how different shadow treatments affect:
- atmosphere
- believability
- phone avoidance
- texture preservation

Optional profile usage:
    python experiments/exp_001_shadow.py --profile profiles/night_walk_profile.json

Run mode:
    By default, outputs are written to a timestamped run folder under runs/.
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
from src.run_manager import create_run_directory, write_run_summary
from src.shadow import (
    apply_shadow_crush,
    apply_shadow_lift,
    apply_trace_shadow_profile,
)
from src.texture import add_shadow_texture
from src.utils import ensure_dir, list_image_files, safe_stem

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input" / "phone"
LEGACY_OUTPUT_DIR = ROOT / "data" / "output" / "exp_001_shadow"
RUNS_ROOT = ROOT / "runs"
EXPERIMENT_ID = "TRACE_001_SHADOW"
EXPERIMENT_TITLE = "Experiment 001: Shadow"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for Experiment 001."""
    parser = argparse.ArgumentParser(description="Run TRACE Experiment 001: Shadow")
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Optional path to a TRACE behavior profile JSON file.",
    )
    parser.add_argument(
        "--legacy-output",
        action="store_true",
        help="Write to data/output/exp_001_shadow instead of a timestamped run folder.",
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


def resolve_output_paths(args: argparse.Namespace, profile) -> tuple[Path, Path, Path, Path | None]:
    """Return output, contact, log, and optional run directory paths."""
    if args.legacy_output:
        output_dir = LEGACY_OUTPUT_DIR
        contact_dir = output_dir / "contact_sheets"
        log_path = output_dir / "exp_001_shadow_log.csv"
        ensure_dir(output_dir)
        ensure_dir(contact_dir)
        return output_dir, contact_dir, log_path, None

    profile_suffix = profile.get("profile_id", "default") if profile else "default"
    run_dir = create_run_directory(
        RUNS_ROOT,
        experiment_id=f"{EXPERIMENT_ID.lower()}_{profile_suffix}",
        version="v1",
    )
    output_dir = run_dir / "outputs"
    contact_dir = run_dir / "contact_sheets"
    log_path = run_dir / "logs" / "exp_001_shadow_log.csv"
    return output_dir, contact_dir, log_path, run_dir


def main() -> None:
    args = parse_args()
    profile, trace_params = resolve_profile(args.profile)
    output_dir, contact_dir, log_path, run_dir = resolve_output_paths(args, profile)

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

        export_versions(versions, output_dir, stem)

        create_contact_sheet(
            versions,
            contact_dir / f"{stem}_contact_sheet.jpg",
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

    write_experiment_log(log_rows, log_path)

    if run_dir:
        write_run_summary(
            run_dir=run_dir,
            experiment_id=EXPERIMENT_ID,
            title=EXPERIMENT_TITLE,
            image_count=len(image_paths),
        )

    print("Experiment complete.")
    print(f"Outputs saved to: {output_dir}")
    if run_dir:
        print(f"Run folder: {run_dir}")


if __name__ == "__main__":
    main()
