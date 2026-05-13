"""Image loading and saving helpers for TRACE Imaging Lab."""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from src.utils import ensure_dir


def load_image(path: str | Path) -> np.ndarray:
    """Load an image as an RGB NumPy array."""
    path = Path(path)
    image_bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)

    if image_bgr is None:
        raise ValueError(f"Could not load image: {path}")

    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)


def save_image(image: np.ndarray, path: str | Path, quality: int = 95) -> None:
    """Save an RGB NumPy image to disk."""
    path = Path(path)
    ensure_dir(path.parent)

    clipped = np.clip(image, 0, 255).astype(np.uint8)
    pil_image = Image.fromarray(clipped, mode="RGB")

    if path.suffix.lower() in {".jpg", ".jpeg"}:
        pil_image.save(path, quality=quality)
    else:
        pil_image.save(path)
