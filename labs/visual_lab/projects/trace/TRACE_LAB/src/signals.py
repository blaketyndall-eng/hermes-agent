"""Environment signal extraction for TRACE Imaging Lab.

These helpers estimate simple visual signals from an image.
They are intentionally lightweight and inspectable.

This is not ML scene classification.
It is behavior-oriented image measurement.
"""

from __future__ import annotations

from typing import Dict

import cv2
import numpy as np


def extract_luminance(image: np.ndarray) -> np.ndarray:
    """Return grayscale luminance from an RGB image."""
    return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0


def estimate_darkness_level(image: np.ndarray) -> float:
    """Estimate how dark the image is overall.

    Returns 0.0 for very bright images and closer to 1.0 for darker images.
    """
    luminance = extract_luminance(image)
    mean_luminance = float(np.mean(luminance))
    return round(1.0 - mean_luminance, 4)


def estimate_shadow_coverage(image: np.ndarray, threshold: float = 0.28) -> float:
    """Estimate what fraction of the image is in shadow."""
    luminance = extract_luminance(image)
    coverage = float(np.mean(luminance < threshold))
    return round(coverage, 4)


def estimate_highlight_concentration(image: np.ndarray, threshold: float = 0.82) -> float:
    """Estimate what fraction of the image is bright highlight."""
    luminance = extract_luminance(image)
    concentration = float(np.mean(luminance > threshold))
    return round(concentration, 4)


def estimate_contrast_level(image: np.ndarray) -> float:
    """Estimate simple image contrast using luminance standard deviation."""
    luminance = extract_luminance(image)
    contrast = float(np.std(luminance))
    return round(contrast, 4)


def estimate_color_ambiguity(image: np.ndarray) -> float:
    """Estimate mixed-light ambiguity using channel disagreement.

    Higher values suggest stronger disagreement between RGB channels, which can
    indicate mixed or unstable lighting.
    """
    image_f = image.astype(np.float32) / 255.0
    channel_std = np.std(image_f, axis=2)
    ambiguity = float(np.mean(channel_std))
    return round(ambiguity, 4)


def extract_environment_signals(image: np.ndarray) -> Dict[str, float]:
    """Extract a compact set of behavior-oriented environment signals."""
    return {
        "darkness_level": estimate_darkness_level(image),
        "shadow_coverage": estimate_shadow_coverage(image),
        "highlight_concentration": estimate_highlight_concentration(image),
        "contrast_level": estimate_contrast_level(image),
        "color_ambiguity": estimate_color_ambiguity(image),
    }
