"""Memory anchor analysis for TRACE Imaging Lab.

Memory anchors are small visual areas that may carry disproportionate emotional
or perceptual weight: isolated highlights, glow sources, reflections, hands,
faces, signage, cigarettes, headlights, or other visually sticky details.

This first version stays lightweight and only detects luminance-based highlight
anchors. Later versions can add face/object-aware analysis if needed.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import cv2
import numpy as np

from src.signals import extract_luminance


def find_highlight_anchor_candidates(
    image: np.ndarray,
    threshold: float = 0.84,
    min_area: int = 12,
) -> List[Dict]:
    """Find bright connected regions that may act as memory anchors.

    Args:
        image: RGB image as a NumPy array.
        threshold: Luminance threshold for bright regions.
        min_area: Minimum connected-component area in pixels.

    Returns:
        A list of candidate dictionaries with bounding boxes and area.
    """
    luminance = extract_luminance(image)
    mask = (luminance >= threshold).astype(np.uint8)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)

    candidates: List[Dict] = []

    for label_id in range(1, num_labels):
        x, y, w, h, area = stats[label_id]
        if int(area) < min_area:
            continue

        centroid_x, centroid_y = centroids[label_id]
        candidates.append(
            {
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h),
                "area": int(area),
                "centroid": [round(float(centroid_x), 2), round(float(centroid_y), 2)],
            }
        )

    candidates.sort(key=lambda item: item["area"], reverse=True)
    return candidates


def summarize_anchor_candidates(candidates: List[Dict], image_shape: Tuple[int, ...]) -> Dict:
    """Summarize anchor candidate density and scale."""
    height, width = image_shape[:2]
    image_area = max(width * height, 1)
    total_anchor_area = sum(candidate["area"] for candidate in candidates)

    return {
        "anchor_count": len(candidates),
        "total_anchor_area_ratio": round(total_anchor_area / image_area, 5),
        "largest_anchor_area_ratio": round((candidates[0]["area"] / image_area) if candidates else 0.0, 5),
    }


def analyze_memory_anchors(image: np.ndarray) -> Dict:
    """Analyze simple highlight-based memory anchors in an image."""
    candidates = find_highlight_anchor_candidates(image)
    summary = summarize_anchor_candidates(candidates, image.shape)

    return {
        "summary": summary,
        "candidates": candidates[:20],
    }
