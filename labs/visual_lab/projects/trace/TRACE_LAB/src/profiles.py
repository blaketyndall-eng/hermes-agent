"""Behavior profile helpers for TRACE Imaging Lab.

Profiles are not presets. They are weighted behavior descriptions that can guide
experiment parameters and future roll-level processing.
"""

import json
from pathlib import Path
from typing import Any, Dict


def load_profile(path: str | Path) -> Dict[str, Any]:
    """Load a TRACE behavior profile from JSON."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_behavior_intensity(profile: Dict[str, Any], layer: str, primitive: str, default: float = 0.0) -> float:
    """Read a primitive intensity from a profile.

    Args:
        profile: Loaded behavior profile.
        layer: Profile layer, such as scene, camera, circulation, or roll.
        primitive: Primitive name, such as darkness_confidence.
        default: Value returned when the primitive is not present.
    """
    value = profile.get(layer, {}).get(primitive, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def shadow_params_from_profile(profile: Dict[str, Any]) -> Dict[str, float]:
    """Map behavior-profile values to Experiment 001 shadow parameters.

    This is intentionally simple and inspectable. It converts the abstract
    primitive language into concrete starter values for the current shadow lab.
    Later experiments can use richer mappings.
    """
    darkness = get_behavior_intensity(profile, "camera", "darkness_confidence", 0.5)
    texture = get_behavior_intensity(profile, "camera", "shadow_texture", 0.25)

    crush_strength = 0.08 + (darkness * 0.12)
    contrast_boost = 1.0 + (darkness * 0.06)
    noise_level = 0.005 + (texture * 0.035)
    shadow_threshold = 95 + int(texture * 35)

    return {
        "crush_strength": round(crush_strength, 4),
        "contrast_boost": round(contrast_boost, 4),
        "noise_level": round(noise_level, 4),
        "shadow_threshold": shadow_threshold,
    }
