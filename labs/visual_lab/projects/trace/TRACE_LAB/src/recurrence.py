"""Recurrence analysis for TRACE Imaging Lab.

TRACE studies how sequences feel coherent through repeated visual behaviors:
light sources, darkness patterns, anchor density, spatial pressure, and other
subtle motifs.

This module intentionally avoids semantic object detection. It focuses on
recurring behavioral signals.
"""

from __future__ import annotations

from typing import Dict, List


def bucket_value(value: float, low: float, high: float) -> str:
    """Bucket a numeric signal into low / medium / high."""
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "medium"


def create_behavior_signature(
    environment_signals: Dict[str, float],
    spatial_signals: Dict[str, float],
    anchor_summary: Dict[str, float],
) -> Dict[str, str]:
    """Create a compact behavioral signature for one frame."""
    return {
        "darkness": bucket_value(environment_signals.get("darkness_level", 0.0), 0.35, 0.65),
        "shadow_coverage": bucket_value(environment_signals.get("shadow_coverage", 0.0), 0.20, 0.50),
        "color_ambiguity": bucket_value(environment_signals.get("color_ambiguity", 0.0), 0.06, 0.13),
        "foreground_pressure": bucket_value(spatial_signals.get("foreground_dominance", 0.0), 0.03, 0.10),
        "spatial_isolation": bucket_value(spatial_signals.get("spatial_isolation", 0.0), 0.02, 0.08),
        "anchor_presence": bucket_value(float(anchor_summary.get("anchor_count", 0)), 1.0, 4.0),
    }


def signature_key(signature: Dict[str, str]) -> str:
    """Convert a behavior signature into a stable string key."""
    return "|".join(f"{key}:{value}" for key, value in sorted(signature.items()))


def summarize_recurrence(signatures: List[Dict[str, str]]) -> Dict:
    """Summarize repeated behavioral signatures across a sequence."""
    counts: Dict[str, int] = {}

    for signature in signatures:
        key = signature_key(signature)
        counts[key] = counts.get(key, 0) + 1

    repeated = {
        key: count
        for key, count in counts.items()
        if count > 1
    }

    return {
        "total_frames": len(signatures),
        "unique_signatures": len(counts),
        "repeated_signatures": repeated,
        "recurrence_ratio": round((len(repeated) / max(len(counts), 1)), 4),
    }
