"""Optional Cloudflare origin check. Activate only after proxy/header setup."""
import hmac
import os

from fastapi.responses import JSONResponse

HEADER = "x-scrap-radar-origin-key"
PROTECTED_PATHS = {"/upload", "/analyze", "/analyze-pair", "/analyze-spike-pair", "/analyze-case", "/free-usage"}


def trusted_cloudflare_proxy(request):
    expected = os.getenv("BOARD_SENSE_ORIGIN_KEY", "").strip()
    supplied = request.headers.get(HEADER, "")
    return len(expected) >= 32 and hmac.compare_digest(supplied.encode(), expected.encode())


class OriginProtectionMiddleware:
    """Reject direct analysis calls before multipart parsing when enabled."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "").rstrip("/")
        if scope.get("type") == "http" and (path in PROTECTED_PATHS or path.startswith("/irm/")):
            expected = os.getenv("BOARD_SENSE_ORIGIN_KEY", "").strip()
            if expected:
                supplied = dict(scope.get("headers", [])).get(HEADER.encode(), b"")
                if len(expected) < 32 or not hmac.compare_digest(supplied, expected.encode()):
                    status = 503 if len(expected) < 32 else 403
                    return await JSONResponse(status_code=status, content={"detail": "Use the public Board Sense address"})(scope, receive, send)
        await self.app(scope, receive, send)
