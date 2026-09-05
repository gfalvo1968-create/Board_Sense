from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import Lock
from typing import Optional

from fastapi import Request


DAILY_FREE_BOARD_LIMIT = int(os.getenv("BOARD_SENSE_DAILY_FREE_BOARD_LIMIT", "1"))
USAGE_FILE = Path(os.getenv("BOARD_SENSE_USAGE_FILE", "data/free_usage.json"))
_USAGE_LOCK = Lock()


@dataclass
class GateDecision:
    allowed: bool
    visitor_id: str
    used_today: int
    limit: int
    remaining: int
    day_utc: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "visitor_id": self.visitor_id,
            "used_today": self.used_today,
            "limit": self.limit,
            "remaining": self.remaining,
            "day_utc": self.day_utc,
            "reason": self.reason,
        }


def _utc_day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _client_ip(request: Request) -> str:
    # Prefer a trusted reverse-proxy forwarding header when present.
    # Railway and similar hosts commonly forward the original client IP.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _visitor_id(request: Request) -> str:
    # A privacy-conscious anonymous identifier. Raw IP/User-Agent are not stored.
    # The server-side salt should be set in Railway as BOARD_SENSE_VISITOR_SALT.
    salt = os.getenv("BOARD_SENSE_VISITOR_SALT", "board-sense-dev-salt-change-me")
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "unknown")
    raw = f"{salt}|{ip}|{ua}".encode("utf-8", errors="ignore")
    return sha256(raw).hexdigest()[:32]


def _referral_source(request: Request) -> str:
    explicit = request.headers.get("x-scrap-radar-source", "").strip().lower()
    if explicit:
        return explicit[:80]
    ref = request.headers.get("referer", "").lower()
    for source in ("facebook", "instagram", "tiktok", "youtube", "discord"):
        if source in ref:
            return source
    return "direct_or_unknown"


def _coarse_region(request: Request) -> dict:
    # Populate only from headers a deployment proxy/CDN may already provide.
    # No external geolocation lookup is performed and precise coordinates are not stored.
    return {
        "country": (request.headers.get("cf-ipcountry") or request.headers.get("x-country") or "").strip()[:8],
        "region": (request.headers.get("x-region") or "").strip()[:80],
        "city": (request.headers.get("x-city") or "").strip()[:80],
    }


def _load_usage() -> dict:
    if not USAGE_FILE.exists():
        return {"version": 1, "days": {}}
    try:
        with USAGE_FILE.open("r", encoding="utf-8") as f:
            payload = json.load(f)
            if isinstance(payload, dict):
                payload.setdefault("version", 1)
                payload.setdefault("days", {})
                return payload
    except (json.JSONDecodeError, OSError):
        pass
    return {"version": 1, "days": {}}


def _save_usage(payload: dict) -> None:
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = USAGE_FILE.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    temp.replace(USAGE_FILE)


def check_free_board_allowance(request: Request) -> GateDecision:
    day = _utc_day()
    visitor = _visitor_id(request)
    with _USAGE_LOCK:
        payload = _load_usage()
        used = int(payload.get("days", {}).get(day, {}).get(visitor, {}).get("boards", 0))
    remaining = max(0, DAILY_FREE_BOARD_LIMIT - used)
    return GateDecision(
        allowed=used < DAILY_FREE_BOARD_LIMIT,
        visitor_id=visitor,
        used_today=used,
        limit=DAILY_FREE_BOARD_LIMIT,
        remaining=remaining,
        day_utc=day,
        reason="free_board_available" if used < DAILY_FREE_BOARD_LIMIT else "daily_free_board_limit_reached",
    )


def record_free_board_use(request: Request, mode: str) -> GateDecision:
    day = _utc_day()
    visitor = _visitor_id(request)
    with _USAGE_LOCK:
        payload = _load_usage()
        days = payload.setdefault("days", {})
        today = days.setdefault(day, {})
        record = today.setdefault(visitor, {
            "boards": 0,
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "source": _referral_source(request),
            "location": _coarse_region(request),
            "modes": {},
        })
        record["boards"] = int(record.get("boards", 0)) + 1
        modes = record.setdefault("modes", {})
        modes[mode] = int(modes.get(mode, 0)) + 1
        record["last_seen"] = datetime.now(timezone.utc).isoformat()
        _save_usage(payload)
        used = int(record["boards"])
    return GateDecision(
        allowed=used < DAILY_FREE_BOARD_LIMIT,
        visitor_id=visitor,
        used_today=used,
        limit=DAILY_FREE_BOARD_LIMIT,
        remaining=max(0, DAILY_FREE_BOARD_LIMIT - used),
        day_utc=day,
        reason="recorded",
    )


def free_gate_payload(decision: GateDecision) -> dict:
    return {
        "status": "limit_reached",
        "message": "Your free Board Sense board analysis for today has already been used. Come back tomorrow for another free board.",
        "free_usage": decision.as_dict(),
    }
