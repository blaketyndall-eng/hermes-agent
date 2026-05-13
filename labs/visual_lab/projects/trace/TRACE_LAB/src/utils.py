"""Utility helpers for TRACE Imaging Lab."""

from pathlib import Path
from typing import List

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}


def ensure_dir(path: str | Path) -> Path:
    """Create a directory if it does not already exist and return it as a Path."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_image_files(folder: str | Path) -> List[Path]:
    """Return all supported image files in a folder, sorted by name."""
    folder = Path(folder)
    if not folder.exists():
        return []

    return sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    )


def safe_stem(filename: str | Path) -> str:
    """Return a filesystem-safe-ish stem for output naming."""
    return Path(filename).stem.replace(" ", "_")
