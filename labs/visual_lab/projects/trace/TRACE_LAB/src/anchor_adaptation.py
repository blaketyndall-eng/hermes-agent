"""Anchor-responsive adaptation for TRACE Imaging Lab.

Memory anchors should gently influence behavior without creating cinematic
spotlighting or obvious subject weighting.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    """Clamp primitive intensity into the normal range."""
    return max(minimum, min(maximum, value))


def primitive_offsets_from_anchor_analysis(anchor_analysis: Dict[str, Any]) -> Dict[str, float]:
    """Convert anchor analysis into restrained primitive offsets.

    Current logic is intentionally conservative:
    - many/larger anchors slightly increase memory_anchor
    - strong anchor presence slightly increases darkness confidence, preserving
      the contrast between anchor and surrounding dark environment
    """
    summary = anchor_analysis.get("summary", {})
    anchor_count = float(summary.get("anchor_count", 0))
    total_area_ratio = float(summary.get("total_anchor_area_ratio", 0.0))
    largest_area_ratio = float(summary.get("largest_anchor_area_ratio", 0.0))

    offsets = {
        "memory_anchor": 0.0,
        "darkness_confidence": 0.0,
        "shadow_texture": 0.0,
    }

    if anchor_count >= 3:
        offsets["memory_anchor"] += 0.015

    if total_area_ratio > 0.015:
        offsets["memory_anchor"] += 0.015

    if largest_area_ratio > 0.008:
        offsets["darkness_confidence"] += 0.01

    if anchor_count == 0:
        offsets["memory_anchor"] -= 0.01

    return {key: round(value, 4) for key, value in offsets.items()}


def apply_anchor_offsets_to_profile(
    profile: Dict[str, Any],
    offsets: Dict[str, float],
) -> Dict[str, Any]:
    """Apply anchor-derived primitive offsets to a profile copy."""
    adjusted = deepcopy(profile)

    for layer_name in ("scene", "camera"):
        layer = adjusted.setdefault(layer_name, {})
        for primitive, offset in offsets.items():
            if primitive not in layer:
                continue
            layer[primitive] = round(clamp(float(layer[primitive]) + float(offset)), 4)

    return adjusted
