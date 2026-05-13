"""Environment adaptation helpers for TRACE Imaging Lab.

Environment profiles gently bias behavioral primitives based on the emotional
and visual tendencies of a scene category.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    """Clamp a value into the valid primitive range."""
    return max(minimum, min(maximum, value))


def load_environment(path: str | Path) -> Dict[str, Any]:
    """Load an environment profile JSON file."""
    path = Path(path)

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def apply_environment_bias(
    profile: Dict[str, Any],
    environment: Dict[str, Any],
    target_layers: tuple[str, ...] = ("scene", "camera"),
) -> Dict[str, Any]:
    """Apply environment primitive offsets to a profile.

    The environment gently nudges primitive intensities instead of overriding
    them completely.
    """
    adjusted = deepcopy(profile)
    biases = environment.get("environment_biases", {})

    for layer_name in target_layers:
        layer = adjusted.setdefault(layer_name, {})

        for primitive, offset in biases.items():
            if primitive not in layer:
                continue

            current_value = float(layer[primitive])
            layer[primitive] = round(
                clamp(current_value + float(offset)),
                4,
            )

    return adjusted
