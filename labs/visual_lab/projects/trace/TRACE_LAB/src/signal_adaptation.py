"""Signal-responsive primitive adaptation for TRACE Imaging Lab.

This module maps lightweight environment signals into small behavior primitive
adjustments. The goal is subtle scene responsiveness, not automatic styling.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    """Clamp primitive intensity into the normal range."""
    return max(minimum, min(maximum, value))


def primitive_offsets_from_signals(signals: Dict[str, float]) -> Dict[str, float]:
    """Convert image signals into restrained primitive offsets.

    The offsets are intentionally small. TRACE should respond to the scene
    without visibly announcing that it adapted.
    """
    darkness = signals.get("darkness_level", 0.5)
    shadow_coverage = signals.get("shadow_coverage", 0.3)
    highlight_concentration = signals.get("highlight_concentration", 0.05)
    color_ambiguity = signals.get("color_ambiguity", 0.08)

    offsets = {
        "darkness_confidence": 0.0,
        "shadow_texture": 0.0,
        "environmental_ambiguity": 0.0,
        "memory_anchor": 0.0,
    }

    if darkness > 0.55:
        offsets["darkness_confidence"] += 0.025
    elif darkness < 0.35:
        offsets["darkness_confidence"] -= 0.02

    if shadow_coverage > 0.45:
        offsets["shadow_texture"] += 0.015
    elif shadow_coverage < 0.20:
        offsets["shadow_texture"] -= 0.01

    if color_ambiguity > 0.10:
        offsets["environmental_ambiguity"] += 0.025

    if highlight_concentration > 0.06:
        offsets["memory_anchor"] += 0.02

    return {key: round(value, 4) for key, value in offsets.items()}


def apply_signal_offsets_to_profile(
    profile: Dict[str, Any],
    offsets: Dict[str, float],
) -> Dict[str, Any]:
    """Apply signal-derived offsets to matching profile primitives."""
    adjusted = deepcopy(profile)

    for layer_name in ("scene", "camera"):
        layer = adjusted.setdefault(layer_name, {})
        for primitive, offset in offsets.items():
            if primitive not in layer:
                continue
            layer[primitive] = round(clamp(float(layer[primitive]) + float(offset)), 4)

    return adjusted
