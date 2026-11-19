"""Non-destructive, anonymous HTTP security checks against Board Sense staging.

Run: python scripts/staging_http_security_check.py
Checks only five GET routes, does not upload a photo, consume a scan or read user data.
Never run these tests against the production domain.
"""
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "https://boardsensestaging-staging.up.railway.app"
HEADERS = {"User-Agent": "ScrapRadarLaunchSecuritySmoke/1.0"}
MAX_BODY = 8192

def get(path):
    request = Request(BASE + path, headers=HEADERS)
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, response.headers, response.read(MAX_BODY)
    except HTTPError as exc:
        return exc.code, exc.headers, exc.read(MAX_BODY)

def check(condition, detail):
    if not condition:
        raise AssertionError(detail)

def main():
    checks = 0

    status, headers, body = get("/health")
    check(status == 200, f"/health returned HTTP {status}, expected 200")
    check(json.loads(body).get("status") == "ok", "Health response did not say ok")
    print("PASS staging /health HTTP 200")
    checks += 1

    status, headers, body = get("/free-usage")
    check(status == 200, f"/free-usage returned HTTP {status}, expected 200")
    data = json.loads(body)
    usage = data.get("free_usage", {})
    check(data.get("status") == "success" and isinstance(usage, dict), "Quota response invalid")
    check("visitor_id" not in usage and "visitor_id" not in data, "Public quota leaks visitor ID")
    check(headers.get("Cache-Control", "").lower().replace(" ", "").find("no-store") >= 0,
          "Quota response missing no-store")
    check(headers.get("X-Content-Type-Options", "").lower() == "nosniff",
          "Quota response missing nosniff")
    check(headers.get("Referrer-Policy", "").lower() == "no-referrer",
          "Quota response missing no-referrer")
    print("PASS staging /free-usage HTTP 200, no visitor hash, no-store/nosniff/referrer protection")
    checks += 1

    for path in (
        "/blueprints/nonexistent-safe-probe.jpg",
        "/multi-board-crops/nonexistent-safe-probe.jpg",
    ):
        status, _, body = get(path)
        check(status == 404, f"{path} returned HTTP {status}, expected 404")
        # FastAPI's application-level 404 JSON, not Starlette StaticFiles' own file 404.
        try:
            result = json.loads(body)
        except (ValueError, UnicodeError):
            raise AssertionError(f"{path} served through a static file path, not application 404") from None
        check(result == {"detail": "Not Found"}, f"{path} returned unexpected 404 payload")
        print(f"PASS staging {path} is an unmounted route (HTTP 404 JSON)")
        checks += 1

    status, _, _ = get("/irm/sources")
    check(status in (401, 503), f"/irm/sources returned HTTP {status}; expected admin denial")
    print(f"PASS staging /irm/sources rejects anonymous access (HTTP {status})")
    checks += 1

    print(f"STAGING READ-ONLY SECURITY CHECKS: {checks}/{checks} PASS")

if __name__ == "__main__":
    try:
        main()
    except (AssertionError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"STAGING SECURITY CHECK FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
