"""Board Sense bridge to Scrap Radar's central market API.

Only this backend bridge needs to know Scrap Radar's deployed API URL. The
frontend and Recovery Lab consume Board Sense's stable /market-intelligence
route instead of hard-coding another service address.
"""

import json
import math
import os
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import HTTPError, URLError

from fastapi import APIRouter

router = APIRouter()

TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 1_000_000


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        # Do not silently send a request to a different host from this bridge.
        return None


def _check_json(value, depth=0):
    if depth > 24:
        raise ValueError("Market payload nesting is too deep")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError("Market payload contains a nonfinite number")
    if isinstance(value, dict):
        for item in value.values():
            _check_json(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _check_json(item, depth + 1)


def _validate_market_payload(data):
    if not isinstance(data, dict) or not isinstance(data.get("metals"), dict):
        raise ValueError("Market payload requires a metals object")
    if not isinstance(data.get("scrap_grades", {}), dict):
        raise ValueError("Market scrap grades must be an object")
    materials = data.get("materials", [])
    if not isinstance(materials, list) or any(not isinstance(item, dict) for item in materials):
        raise ValueError("Market materials must be an array of objects")
    _check_json(data)
    if any(not isinstance(metal, dict) for metal in data["metals"].values()):
        raise ValueError("Market metal entries must be objects")
    for metal in data["metals"].values():
        if "available" in metal and not isinstance(metal["available"], bool):
            raise ValueError("Metal availability must be a boolean")
        if metal.get("available"):
            price = metal.get("price")
            if (isinstance(price, bool) or not isinstance(price, (int, float))
                    or not math.isfinite(price) or price <= 0):
                raise ValueError("Available metal requires a positive finite numeric price")
        if "stale" in metal and not isinstance(metal["stale"], bool):
            raise ValueError("Metal stale status must be a boolean")
    status = data.get("status")
    if not isinstance(status, str) or status not in {"live", "stale", "unavailable"}:
        raise ValueError("Market status is missing or unknown")
    return data


def _scrap_radar_prices_url():
    base = os.getenv("SCRAP_RADAR_API_URL", "").strip().rstrip("/")
    return f"{base}/prices" if base else ""


def fetch_scrap_radar_market():
    url = _scrap_radar_prices_url()
    if not url:
        return {
            "status": "unconfigured",
            "source": "Scrap Radar",
            "message": "Set SCRAP_RADAR_API_URL in the Board Sense deployment environment.",
            "metals": {},
            "scrap_grades": {},
            "materials": [],
        }

    try:
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "BoardSense/1.0"})
        with build_opener(_NoRedirects()).open(request, timeout=TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                raise ValueError("Market response is not JSON")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("Market response exceeds size limit")
            data = _validate_market_payload(json.loads(raw.decode("utf-8")))
        return {
            "status": data.get("status", "unknown"),
            "source": "Scrap Radar",
            "upstream_source": data.get("source"),
            "updated_at": data.get("updated_at"),
            "checked_at": data.get("checked_at"),
            "metals": data.get("metals", {}),
            "scrap_grades": data.get("scrap_grades", {}),
            "materials": data.get("materials", []),
            "note": data.get("note"),
        }
    except (HTTPError, URLError, TimeoutError, ValueError, UnicodeError, RecursionError, OSError) as exc:
        return {
            "status": "unavailable",
            "source": "Scrap Radar",
            "message": "Scrap Radar market intelligence is temporarily unavailable.",
            "error_type": type(exc).__name__,
            "metals": {},
            "scrap_grades": {},
            "materials": [],
        }


@router.get("/market-intelligence")
def market_intelligence():
    return fetch_scrap_radar_market()
