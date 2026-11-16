"""Store user-supplied board images without trusting their filenames or size."""

from pathlib import Path
from contextlib import contextmanager
from uuid import uuid4
from time import perf_counter

from fastapi import HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 32_000_000
READ_CHUNK_BYTES = 1024 * 1024
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}
UPLOAD_BODY_LIMITS = {
    "/upload": 12 * 1024 * 1024,
    "/analyze": 12 * 1024 * 1024,
    "/analyze-pair": 24 * 1024 * 1024,
    "/analyze-spike-pair": 24 * 1024 * 1024,
    "/analyze-case": 64 * 1024 * 1024,
}


class _BodyTooLarge(Exception):
    pass


class UploadBodyLimitMiddleware:
    """Reject oversized multipart bodies as they arrive, before form parsing."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        limit = UPLOAD_BODY_LIMITS.get(scope.get("path"))
        if scope.get("type") != "http" or scope.get("method") != "POST" or limit is None:
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = 0
        error = JSONResponse(status_code=413, content={"detail": "Upload exceeds the request size limit"})
        if declared > limit:
            return await error(scope, receive, send)

        seen = 0
        response_started = False
        # Staging upload transport diagnostics: elapsed time and byte counts
        # only. Never print filenames, image contents, addresses, or tokens.
        diagnostic = scope.get("path") == "/analyze"
        started = perf_counter()
        first_chunk = False
        if diagnostic:
            print(f"[SPIKE Transport] request entered middleware; declared_bytes={declared}", flush=True)

        async def bounded_receive():
            nonlocal seen, first_chunk
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if diagnostic and not first_chunk:
                    first_chunk = True
                    print(f"[SPIKE Transport] first_chunk elapsed={perf_counter()-started:.2f}s", flush=True)
                if diagnostic and not message.get("more_body", False):
                    print(f"[SPIKE Transport] upload_body_complete bytes={seen} elapsed={perf_counter()-started:.2f}s", flush=True)
                if seen > limit:
                    raise _BodyTooLarge()
            elif diagnostic and message["type"] == "http.disconnect":
                print(f"[SPIKE Transport] disconnected bytes={seen} elapsed={perf_counter()-started:.2f}s", flush=True)
            return message

        async def tracked_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, bounded_receive, tracked_send)
        except _BodyTooLarge:
            if response_started:
                raise
            await error(scope, receive, send)


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


@contextmanager
def validated_board_images(uploads, directory: Path):
    """Validate every view first; always remove private originals after use."""
    paths = []
    try:
        for upload in uploads:
            paths.append(save_board_image(upload, directory))
        yield paths
    finally:
        for path in paths:
            path.unlink(missing_ok=True)
