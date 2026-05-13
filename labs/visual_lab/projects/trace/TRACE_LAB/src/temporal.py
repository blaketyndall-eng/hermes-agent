"""Temporal pacing analysis for TRACE Imaging Lab.

TRACE sequences should feel emotionally cumulative rather than visually random.
This module studies pacing drift across ordered image sequences.
"""

from __future__ import annotations

from typing import Dict, List



def calculate_sequence_pressure(
    foreground_dominance: float,
    edge_darkness: float,
    spatial_isolation: float,
) -> float:
    """Estimate cumulative emotional pressure."""
    pressure = (
        foreground_dominance * 0.45
        + edge_darkness * 0.35
        + spatial_isolation * 0.20
    )

    return round(pressure, 4)



def calculate_memory_density(
    anchor_density: float,
    shadow_density: float,
    environment_bias: float,
) -> float:
    """Estimate how memory-heavy a frame feels."""
    density = (
        anchor_density * 0.5
        + shadow_density * 0.3
        + environment_bias * 0.2
    )

    return round(density, 4)



def classify_temporal_phase(index: int, total: int) -> str:
    """Assign a pacing phase to a frame in a sequence."""
    if total <= 1:
        return "isolated"

    progress = index / (total - 1)

    if progress < 0.25:
        return "arrival"

    if progress < 0.55:
        return "immersion"

    if progress < 0.8:
        return "fragmentation"

    return "aftermath"



def estimate_temporal_drift(
    pressures: List[float],
) -> Dict[str, float]:
    """Estimate sequence pacing behavior."""
    if len(pressures) < 2:
        return {
            "pressure_delta": 0.0,
            "average_pressure": pressures[0] if pressures else 0.0,
        }

    delta = pressures[-1] - pressures[0]
    average = sum(pressures) / len(pressures)

    return {
        "pressure_delta": round(delta, 4),
        "average_pressure": round(average, 4),
    }
