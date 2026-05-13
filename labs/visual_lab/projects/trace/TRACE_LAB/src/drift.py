"""Controlled drift helpers for TRACE Imaging Lab.

Drift introduces restrained sequence variation across a roll.
The goal is coherence without mechanical sameness.
"""

from __future__ import annotations

import math
import random
from typing import Dict, List


random.seed(42)


def slow_wave(index: int, total: int, min_offset: float, max_offset: float) -> float:
    """Generate a smooth sinusoidal drift value."""
    if total <= 1:
        return 0.0

    midpoint = (max_offset + min_offset) / 2.0
    amplitude = (max_offset - min_offset) / 2.0

    position = index / (total - 1)
    value = midpoint + amplitude * math.sin(position * math.pi * 2)
    return round(value, 4)


def soft_noise(min_offset: float, max_offset: float) -> float:
    """Generate restrained random drift."""
    return round(random.uniform(min_offset, max_offset), 4)


def late_rise(index: int, total: int, min_offset: float, max_offset: float) -> float:
    """Gradually increase intensity later in the sequence."""
    if total <= 1:
        return min_offset

    position = index / (total - 1)
    curve = position ** 2
    value = min_offset + ((max_offset - min_offset) * curve)
    return round(value, 4)


def calculate_roll_drift(
    image_index: int,
    total_images: int,
    drift_rules: Dict,
) -> Dict[str, float]:
    """Calculate primitive drift values for one image in a roll."""
    output: Dict[str, float] = {}

    for primitive, config in drift_rules.items():
        min_offset = config.get("min_offset", 0.0)
        max_offset = config.get("max_offset", 0.0)
        curve = config.get("curve", "soft_noise")

        if curve == "slow_wave":
            value = slow_wave(
                image_index,
                total_images,
                min_offset,
                max_offset,
            )
        elif curve == "late_rise":
            value = late_rise(
                image_index,
                total_images,
                min_offset,
                max_offset,
            )
        else:
            value = soft_noise(min_offset, max_offset)

        output[primitive] = value

    return output


def build_roll_drift_sequence(
    total_images: int,
    drift_rules: Dict,
) -> List[Dict[str, float]]:
    """Generate drift values for an entire roll."""
    sequence = []

    for index in range(total_images):
        sequence.append(
            calculate_roll_drift(index, total_images, drift_rules)
        )

    return sequence
