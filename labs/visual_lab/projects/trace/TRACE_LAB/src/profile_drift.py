"""Profile + drift composition helpers for TRACE Imaging Lab.

These utilities combine a base behavior profile with per-image drift values.
The output is still a behavior profile, but with tiny sequence-aware offsets.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    """Clamp a primitive intensity into the normal 0.0 to 1.0 range."""
    return max(minimum, min(maximum, value))


def apply_drift_to_profile(
    profile: Dict[str, Any],
    drift_values: Dict[str, float],
    target_layer: str = "camera",
) -> Dict[str, Any]:
    """Return a copy of a profile with per-image drift applied.

    Drift values are keyed by primitive name, for example:

    ```json
    {
      "darkness_confidence": 0.01,
      "shadow_texture": -0.005
    }
    ```

    The current implementation applies these offsets to the camera layer. Later
    versions can route primitives across scene, circulation, and roll layers.
    """
    drifted = deepcopy(profile)
    layer = drifted.setdefault(target_layer, {})

    for primitive, offset in drift_values.items():
        current_value = float(layer.get(primitive, 0.0))
        layer[primitive] = round(clamp(current_value + float(offset)), 4)

    return drifted
