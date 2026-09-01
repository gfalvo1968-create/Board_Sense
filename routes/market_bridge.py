"""Board Sense bridge to Scrap Radar's central market API.

Only this backend bridge needs to know Scrap Radar's deployed API URL. The
frontend and Recovery Lab consume Board Sense's stable /market-intelligence
route instead of hard-coding another service address.
"""

import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from fastapi import APIRouter

router = APIRouter()

TIMEOUT_SECONDS = 8


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
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {
            "status": data.get("status", "unknown"),
            "source": "Scrap Radar",
            "upstream_source": data.get("source"),
            "updated_at": data.get("updated_at"),
            "metals": data.get("metals", {}),
            "scrap_grades": data.get("scrap_grades", {}),
            "materials": data.get("materials", []),
            "note": data.get("note"),
        }
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
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
