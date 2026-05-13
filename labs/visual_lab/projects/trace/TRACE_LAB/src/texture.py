"""Texture helpers for TRACE Imaging Lab.

Texture here should remain subtle and physically believable.
The goal is not fake film grain.
"""

import cv2
import numpy as np


def add_shadow_texture(
    image: np.ndarray,
    noise_level: float = 0.025,
    shadow_threshold: int = 110,
) -> np.ndarray:
    """Add restrained texture mostly into shadow regions.

    Texture is concentrated in darker areas because modern phones often clean
    shadows aggressively. TRACE preserves a little instability there.
    """
    image_f = image.astype(np.float32) / 255.0

    gray = cv2.cvtColor((image_f * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    shadow_mask = gray < shadow_threshold

    noise = np.random.normal(0, noise_level, image_f.shape).astype(np.float32)

    blurred_mask = cv2.GaussianBlur(
        shadow_mask.astype(np.float32),
        (0, 0),
        sigmaX=3,
    )

    blended = image_f + (noise * blurred_mask[..., None])

    return np.clip(blended * 255.0, 0, 255).astype(np.uint8)
