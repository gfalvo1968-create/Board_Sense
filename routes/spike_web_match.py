"""SPIKE Glass Web Match v0.1.

Optional external visual-reference lookup for Board Sense. The provider is deliberately
an evidence source, never an identity oracle. It is active only when SERPAPI_KEY is
configured. Results from Google Lens via SerpApi are returned as reference candidates
and must be reconciled with physical board geometry before they can affect identity.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import requests
from PIL import Image


SERP_IMAGE_URL = "https://serpapi.com/image"
SERP_SEARCH_URL = "https://serpapi.com/search"


def _prepare_upload(image_path: str) -> str:
    """Return a temporary JPEG at or below SerpApi's 500 KB upload ceiling."""
    src = Image.open(image_path).convert("RGB")
    fd, out_path = tempfile.mkstemp(prefix="spike_web_", suffix=".jpg")
    os.close(fd)
    quality = 88
    max_side = 1800
    if max(src.size) > max_side:
        scale = max_side / float(max(src.size))
        src = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))))

    while True:
        src.save(out_path, "JPEG", quality=quality, optimize=True)
        if Path(out_path).stat().st_size <= 490_000 or quality <= 42:
            break
        quality -= 8
    return out_path


def search_visual_matches(image_path: str, query: str | None = None, limit: int = 6) -> dict:
    key = (os.getenv("SERPAPI_KEY") or "").strip()
    base = {
        "provider": "SerpApi Google Lens",
        "mode": "spike_glass_web_match",
        "status": "provider_not_configured" if not key else "pending",
        "matches": [],
        "query": query or "",
        "rule": "External visual matches are supporting evidence only. They cannot override contradictory physical geometry by themselves.",
    }
    if not key:
        return base

    temp_path = None
    try:
        temp_path = _prepare_upload(image_path)
        with open(temp_path, "rb") as fh:
            upload = requests.post(
                SERP_IMAGE_URL,
                files={"image": ("spike.jpg", fh, "image/jpeg")},
                data={"api_key": key},
                timeout=30,
            )
        upload.raise_for_status()
        upload_data = upload.json()
        image_id = upload_data.get("image_id")
        if not image_id:
            base.update({"status": "provider_error", "error": upload_data.get("error") or "Image upload returned no image_id."})
            return base

        params = {
            "engine": "google_lens",
            "image_id": image_id,
            "type": "visual_matches",
            "hl": "en",
            "country": "us",
            "api_key": key,
        }
        if query:
            params["q"] = query
        response = requests.get(SERP_SEARCH_URL, params=params, timeout=35)
        response.raise_for_status()
        data = response.json()
        raw = data.get("visual_matches") or []
        matches = []
        for item in raw[: max(1, int(limit))]:
            matches.append(
                {
                    "title": item.get("title"),
                    "source": item.get("source"),
                    "link": item.get("link"),
                    "thumbnail": item.get("thumbnail"),
                }
            )
        base.update({"status": "searched", "matches": matches, "match_count": len(matches)})
        return base
    except Exception as exc:
        base.update({"status": "provider_error", "error": str(exc)})
        return base
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass
