"""Shadow processing profiles for TRACE Imaging Lab."""

import cv2
import numpy as np

from src.texture import add_shadow_texture


def _rgb_to_lab(image: np.ndarray):
    return cv2.cvtColor(image, cv2.COLOR_RGB2LAB)


def _lab_to_rgb(image: np.ndarray):
    return cv2.cvtColor(image, cv2.COLOR_LAB2RGB)


def apply_shadow_lift(
    image: np.ndarray,
    lift_amount: float = 0.12,
) -> np.ndarray:
    """Create a flatter, phone-like shadow response."""
    lab = _rgb_to_lab(image)
    l, a, b = cv2.split(lab)

    l_float = l.astype(np.float32) / 255.0
    lifted = np.power(l_float, 1.0 - lift_amount)

    merged = cv2.merge([
        (lifted * 255).astype(np.uint8),
        a,
        b,
    ])

    return _lab_to_rgb(merged)


def apply_shadow_crush(
    image: np.ndarray,
    crush_strength: float = 0.22,
    contrast_boost: float = 1.08,
) -> np.ndarray:
    """Deepen shadows while trying to preserve some dimensionality."""
    lab = _rgb_to_lab(image)
    l, a, b = cv2.split(lab)

    l_float = l.astype(np.float32) / 255.0

    crushed = np.power(l_float, 1.0 + crush_strength)
    crushed = np.clip((crushed - 0.5) * contrast_boost + 0.5, 0, 1)

    merged = cv2.merge([
        (crushed * 255).astype(np.uint8),
        a,
        b,
    ])

    return _lab_to_rgb(merged)


def apply_trace_shadow_profile(image: np.ndarray) -> np.ndarray:
    """Balanced TRACE-style shadow behavior.

    The target is restrained darkness preservation:
    - darker than phones
    - softer than heavy crush
    - subtle texture
    - believable dimensionality
    """
    crushed = apply_shadow_crush(
        image,
        crush_strength=0.12,
        contrast_boost=1.03,
    )

    textured = add_shadow_texture(
        crushed,
        noise_level=0.015,
        shadow_threshold=100,
    )

    return textured
