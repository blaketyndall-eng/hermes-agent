"""Roll 007: Anchor-Responsive Sequence.

Combine:
- environment signals
- memory-anchor analysis
- behavior profiles
- environment adaptation
- controlled drift
- roll-aware execution

This experiment explores how visually persistent regions influence sequence
behavior while remaining subtle and emotionally grounded.
"""

import json
from pathlib import Path

from src.anchor_adaptation import (
    apply_anchor_offsets_to_profile,
    primitive_offsets_from_anchor_analysis,
)
from src.anchors import analyze_memory_anchors
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

EXPERIMENT_ID = "ROLL_007_ANCHOR_RESPONSIVE_SEQUENCE"

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

    base_environment_profile = apply_environment_bias(profile, environment)

    run_log = []

    for index, image_path in enumerate(image_paths):
        image = load_image(image_path)
        stem = safe_stem(image_path.name)

        signals = extract_environment_signals(image)
        signal_offsets = primitive_offsets_from_signals(signals)

        anchor_analysis = analyze_memory_anchors(image)
        anchor_offsets = primitive_offsets_from_anchor_analysis(anchor_analysis)

        profile_after_signals = apply_signal_offsets_to_profile(
            base_environment_profile,
            signal_offsets,
        )

        profile_after_anchors = apply_anchor_offsets_to_profile(
            profile_after_signals,
            anchor_offsets,
        )

        final_profile = apply_drift_to_profile(
            profile_after_anchors,
            drift_sequence[index],
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

        export_versions(
            {
                "original": image,
                "anchor_responsive": processed,
            },
            outputs_dir,
            stem,
        )

        run_log.append(
            {
                "filename": image_path.name,
                "signals": signals,
                "signal_offsets": signal_offsets,
                "anchor_summary": anchor_analysis.get("summary", {}),
                "anchor_offsets": anchor_offsets,
                "drift_values": drift_sequence[index],
                "final_params": params,
            }
        )

    with (logs_dir / "anchor_response_log.json").open("w", encoding="utf-8") as file:
        json.dump(run_log, file, indent=2)
        file.write("\n")

    summary_path = run_dir / "summary.md"
    summary_path.write_text(
        """# TRACE Anchor-Responsive Sequence Summary

This run combined:

- environment signals
- memory-anchor analysis
- environment adaptation
- controlled drift
- roll-aware execution

Generated artifact:
- logs/anchor_response_log.json

Key review questions:

- Did anchor regions improve emotional persistence?
- Did darkness remain believable?
- Did adaptation remain restrained?
- Did highlights feel physically grounded?
- Did sequence coherence survive adaptation layering?

Important:

TRACE should preserve emotional anchor tension without creating cinematic emphasis.
""",
        encoding="utf-8",
    )

    print("TRACE anchor-responsive sequence complete.")
    print(f"Run folder: {run_dir}")


if __name__ == "__main__":
    main()
