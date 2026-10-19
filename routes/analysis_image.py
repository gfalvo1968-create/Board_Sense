"""Bound the whole-board working image before pixel-scale detectors run."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageOps

MAX_ANALYSIS_SIDE = 1600


@contextmanager
def board_analysis_image(image_path):
    """Keep existing small inputs unchanged; orient and downsample large views.

    Every detector and its blueprint sees the same pixels and coordinates.
    Loose-processor OCR uses its own path and retains its original input.
    """
    with Image.open(image_path) as source:
        orientation = source.getexif().get(274, 1)
        if max(source.size) <= MAX_ANALYSIS_SIDE and orientation == 1:
            yield image_path
            return
        working = ImageOps.exif_transpose(source).convert("RGB")
        working.thumbnail((MAX_ANALYSIS_SIDE, MAX_ANALYSIS_SIDE), Image.Resampling.LANCZOS)
        with TemporaryDirectory(prefix="board-analysis-") as directory:
            path = Path(directory) / "working.png"
            working.save(path, format="PNG")
            yield str(path)
