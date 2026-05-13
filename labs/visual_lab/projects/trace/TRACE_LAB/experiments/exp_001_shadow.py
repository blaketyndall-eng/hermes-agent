"""Experiment 001: Shadow.

Study how different shadow treatments affect:
- atmosphere
- believability
- phone avoidance
- texture preservation
"""

from pathlib import Path

from src.export import (
    create_contact_sheet,
    export_versions,
    write_experiment_log,
)
from src.ingest import load_image
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


def main() -> None:
    ensure_dir(OUTPUT_DIR)
    ensure_dir(CONTACT_DIR)

    image_paths = list_image_files(INPUT_DIR)

    if not image_paths:
        print(f"No images found in: {INPUT_DIR}")
        return

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
                0.12,
                1.03,
                0.015,
                "Balanced TRACE shadow preservation",
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
