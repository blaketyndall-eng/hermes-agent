"""Spatial-responsive adaptation for TRACE Imaging Lab.

Spatial signals influence how TRACE preserves incomplete space, foreground
pressure, and environmental collapse.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))



def primitive_offsets_from_spatial_signals(signals: Dict[str, float]) -> Dict[str, float]:
    """Convert spatial signals into restrained primitive offsets."""
    foreground = signals.get("foreground_dominance", 0.0)
    isolation = signals.get("spatial_isolation", 0.0)
    edge_darkness = signals.get("edge_darkness", 0.0)
    background_retention = signals.get("background_retention", 0.0)

    offsets = {
        "darkness_confidence": 0.0,
        "foreground_pressure": 0.0,
        "environmental_ambiguity": 0.0,
    }

    if foreground > 0.08:
        offsets["foreground_pressure"] += 0.02

    if isolation > 0.05:
        offsets["darkness_confidence"] += 0.02
        offsets["environmental_ambiguity"] += 0.01

    if edge_darkness > 0.55:
        offsets["darkness_confidence"] += 0.015

    if background_retention > 0.08:
        offsets["environmental_ambiguity"] -= 0.01

    return {key: round(value, 4) for key, value in offsets.items()}



def apply_spatial_offsets_to_profile(
    profile: Dict[str, Any],
    offsets: Dict[str, float],
) -> Dict[str, Any]:
    """Apply spatial offsets to a profile copy."""
    adjusted = deepcopy(profile)

    for layer_name in ("scene", "camera"):
        layer = adjusted.setdefault(layer_name, {})

        for primitive, offset in offsets.items():
            if primitive not in layer:
                continue

            layer[primitive] = round(
                clamp(float(layer[primitive]) + float(offset)),
                4,
            )

    return adjusted
