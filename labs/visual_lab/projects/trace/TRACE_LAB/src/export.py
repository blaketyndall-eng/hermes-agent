"""Export helpers for TRACE Imaging Lab."""

import csv
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.ingest import save_image
from src.utils import ensure_dir


def create_contact_sheet(
    versions: Dict[str, np.ndarray],
    output_path: str | Path,
    tile_width: int = 320,
    label_height: int = 36,
) -> None:
    """Create a horizontal contact sheet comparing image versions.

    Args:
        versions: Mapping of version name to RGB NumPy image.
        output_path: Where to save the contact sheet.
        tile_width: Width for each image tile.
        label_height: Height reserved for text labels.
    """
    output_path = Path(output_path)
    ensure_dir(output_path.parent)

    pil_tiles: List[Image.Image] = []

    for label, image in versions.items():
        image_uint8 = np.clip(image, 0, 255).astype(np.uint8)
        pil_image = Image.fromarray(image_uint8, mode="RGB")

        aspect = pil_image.height / pil_image.width
        tile_height = int(tile_width * aspect)
        resized = pil_image.resize((tile_width, tile_height), Image.Resampling.LANCZOS)

        tile = Image.new("RGB", (tile_width, tile_height + label_height), "white")
        tile.paste(resized, (0, label_height))

        draw = ImageDraw.Draw(tile)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        draw.text((10, 10), label, fill="black", font=font)
        pil_tiles.append(tile)

    if not pil_tiles:
        return

    sheet_width = tile_width * len(pil_tiles)
    sheet_height = max(tile.height for tile in pil_tiles)
    sheet = Image.new("RGB", (sheet_width, sheet_height), "white")

    x = 0
    for tile in pil_tiles:
        sheet.paste(tile, (x, 0))
        x += tile_width

    sheet.save(output_path)


def write_experiment_log(rows: Iterable[dict], output_path: str | Path) -> None:
    """Write experiment metadata rows to a CSV file."""
    output_path = Path(output_path)
    ensure_dir(output_path.parent)

    fieldnames = [
        "filename",
        "version",
        "shadow_strength",
        "contrast_level",
        "noise_level",
        "notes",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def export_versions(
    versions: Dict[str, np.ndarray],
    output_dir: str | Path,
    filename_stem: str,
) -> None:
    """Save each image version to the output folder."""
    output_dir = ensure_dir(output_dir)

    for version_name, image in versions.items():
        save_image(image, output_dir / f"{filename_stem}_{version_name}.jpg")
