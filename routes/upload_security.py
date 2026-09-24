"""Store user-supplied board images without trusting their filenames or size."""

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from PIL import Image


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 32_000_000
READ_CHUNK_BYTES = 1024 * 1024
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}


def save_board_image(upload: UploadFile, directory: Path) -> Path:
    """Save a bounded, decodable image under a generated name in directory."""
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Unsupported image type")

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}{suffix}"
    created = False
    try:
        size = 0
        with path.open("xb") as output:
            created = True
            while chunk := upload.file.read(READ_CHUNK_BYTES):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Image exceeds the 10 MB limit")
                output.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Image is empty")

        try:
            with Image.open(path) as image:
                if image.format not in ALLOWED_FORMATS:
                    raise HTTPException(status_code=415, detail="Unsupported image type")
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise HTTPException(status_code=413, detail="Image dimensions are too large")
                image.verify()
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
            raise HTTPException(status_code=400, detail="Invalid image") from exc
        return path
    except Exception:
        if created:
            path.unlink(missing_ok=True)
        raise
