"""Spatial tension analysis for TRACE Imaging Lab.

TRACE studies how direct flash and imperfect exposure alter spatial perception.
This module extracts lightweight spatial-behavior signals without depth ML.
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from src.signals import extract_luminance


def estimate_foreground_dominance(image: np.ndarray) -> float:
    """Estimate how visually dominant the image center is.

    Uses a center-weighted luminance comparison against edge regions.
    Higher values suggest foreground pressure or flash isolation.
    """
    luminance = extract_luminance(image)
    height, width = luminance.shape

    center = luminance[
        height // 4 : (height * 3) // 4,
        width // 4 : (width * 3) // 4,
    ]

    edge_mask = np.ones_like(luminance, dtype=bool)
    edge_mask[
        height // 4 : (height * 3) // 4,
        width // 4 : (width * 3) // 4,
    ] = False

    edges = luminance[edge_mask]

    center_mean = float(np.mean(center))
    edge_mean = float(np.mean(edges))

    dominance = max(center_mean - edge_mean, 0.0)
    return round(dominance, 4)


def estimate_background_retention(image: np.ndarray) -> float:
    """Estimate how much detail survives in darker image regions."""
    luminance = extract_luminance(image)

    dark_regions = luminance[luminance < 0.35]
    if len(dark_regions) == 0:
        return 0.0

    retention = float(np.std(dark_regions))
    return round(retention, 4)


def estimate_spatial_isolation(image: np.ndarray) -> float:
    """Estimate how spatially detached the foreground feels.

    Higher values suggest stronger separation between bright foreground and
    collapsed background.
    """
    foreground = estimate_foreground_dominance(image)
    retention = estimate_background_retention(image)

    isolation = max(foreground - retention, 0.0)
    return round(isolation, 4)


def estimate_edge_darkness(image: np.ndarray) -> float:
    """Estimate darkness pressure around image edges."""
    luminance = extract_luminance(image)
    height, width = luminance.shape

    border = 24

    top = luminance[:border, :]
    bottom = luminance[-border:, :]
    left = luminance[:, :border]
    right = luminance[:, -border:]

    edges = np.concatenate([
        top.flatten(),
        bottom.flatten(),
        left.flatten(),
        right.flatten(),
    ])

    darkness = 1.0 - float(np.mean(edges))
    return round(darkness, 4)


def extract_spatial_signals(image: np.ndarray) -> Dict[str, float]:
    """Extract lightweight spatial-tension signals."""
    return {
        "foreground_dominance": estimate_foreground_dominance(image),
        "background_retention": estimate_background_retention(image),
        "spatial_isolation": estimate_spatial_isolation(image),
        "edge_darkness": estimate_edge_darkness(image),
    }
