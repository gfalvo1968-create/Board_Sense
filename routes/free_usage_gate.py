from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
from ipaddress import ip_address
import json
import os
from pathlib import Path
from threading import Lock
from urllib import parse, request as urlrequest

from fastapi import Request


DAILY_FREE_BOARD_LIMIT = int(os.getenv("BOARD_SENSE_DAILY_FREE_BOARD_LIMIT", "1"))
USAGE_FILE = Path(os.getenv("BOARD_SENSE_USAGE_FILE", "data/free_usage.json"))
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://plcecfxejriiorzwqbfc.supabase.co").rstrip("/")
SUPABASE_SECRET = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY") or ""
BOARD_SENSE_ENV = os.getenv("BOARD_SENSE_ENV", os.getenv("RAILWAY_ENVIRONMENT_NAME", "development")).lower()
BOARD_SENSE_TESTER_KEY = os.getenv("BOARD_SENSE_TESTER_KEY", "").strip()
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
    # Railway documents X-Real-IP as its client address header. X-Forwarded-For
    # may contain an arbitrary first hop supplied by the caller: never use it
    # to grant another free analysis.
    if os.getenv("RAILWAY_ENVIRONMENT_NAME"):
        real_ip = request.headers.get("x-real-ip", "").strip()
        try:
            if ip_address(real_ip).is_global:
                return real_ip
        except ValueError:
            pass
    return request.client.host if request.client else "unknown"


def _visitor_id(request: Request) -> str:
    salt = os.getenv("BOARD_SENSE_VISITOR_SALT", "board-sense-dev-salt-change-me")
    raw = f"{salt}|{_client_ip(request)}|{request.headers.get('user-agent', 'unknown')}".encode("utf-8", errors="ignore")
    return sha256(raw).hexdigest()[:32]


def _is_authorized_tester(request: Request) -> bool:
    """Server-side tester bypass. Secret must come from an environment variable and request header."""
    if not BOARD_SENSE_TESTER_KEY:
        return False
    supplied = request.headers.get("x-board-sense-tester-key", "").strip()
    if not supplied:
        return False
    return hmac.compare_digest(supplied, BOARD_SENSE_TESTER_KEY)


def _tester_decision() -> GateDecision:
    return GateDecision(
        allowed=True,
        visitor_id="authorized_tester",
        used_today=0,
        limit=-1,
        remaining=-1,
        day_utc=_utc_day(),
        reason="authorized_tester_bypass",
    )


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
    return {
        "country": (request.headers.get("cf-ipcountry") or request.headers.get("x-country") or "").strip()[:8],
        "region": (request.headers.get("x-region") or "").strip()[:80],
        "city": (request.headers.get("x-city") or "").strip()[:80],
    }


def _supabase_headers() -> dict:
    headers = {
        "apikey": SUPABASE_SECRET,
        "Content-Type": "application/json",
    }
    # New sb_secret_ keys are opaque, not JWTs. Sending one as a bearer token
    # makes the Supabase gateway reject it as an invalid JWT.
    if not SUPABASE_SECRET.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {SUPABASE_SECRET}"
    return headers


def _supabase_ready() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SECRET)


def _is_production() -> bool:
    return BOARD_SENSE_ENV == "production" or os.getenv("RAILWAY_ENVIRONMENT_NAME", "").lower() == "production"


def _supabase_get_used(day: str, visitor: str) -> int:
    query = parse.urlencode({
        "select": "board_count",
        "usage_date": f"eq.{day}",
        "visitor_hash": f"eq.{visitor}",
        "limit": "1",
    })
    req = urlrequest.Request(
        f"{SUPABASE_URL}/rest/v1/board_sense_public_daily_usage?{query}",
        headers=_supabase_headers(),
        method="GET",
    )
    with urlrequest.urlopen(req, timeout=5) as response:
        rows = json.loads(response.read().decode("utf-8"))
    return int(rows[0].get("board_count", 0)) if rows else 0


def _supabase_claim(request: Request, visitor: str) -> tuple[bool, int]:
    payload = {
        "p_visitor_hash": visitor,
        "p_limit": DAILY_FREE_BOARD_LIMIT,
    }
    req = urlrequest.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/claim_board_sense_free_use",
        data=json.dumps(payload).encode("utf-8"),
        headers=_supabase_headers(),
        method="POST",
    )
    with urlrequest.urlopen(req, timeout=5) as response:
        rows = json.loads(response.read().decode("utf-8"))
    row = rows[0] if isinstance(rows, list) and rows else rows
    return bool(row.get("allowed")), int(row.get("used_today", 0))


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


def _local_check(day: str, visitor: str) -> int:
    with _USAGE_LOCK:
        payload = _load_usage()
        return int(payload.get("days", {}).get(day, {}).get(visitor, {}).get("boards", 0))


def _local_claim(request: Request, day: str, visitor: str, mode: str) -> tuple[bool, int]:
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
        used = int(record.get("boards", 0))
        if used >= DAILY_FREE_BOARD_LIMIT:
            return False, used
        used += 1
        record["boards"] = used
        modes = record.setdefault("modes", {})
        modes[mode] = int(modes.get(mode, 0)) + 1
        record["last_seen"] = datetime.now(timezone.utc).isoformat()
        _save_usage(payload)
        return True, used


def _backend_unavailable(day: str, visitor: str) -> GateDecision:
    return GateDecision(
        allowed=False,
        visitor_id=visitor,
        used_today=0,
        limit=DAILY_FREE_BOARD_LIMIT,
        remaining=0,
        day_utc=day,
        reason="usage_backend_unavailable",
    )


def check_free_board_allowance(request: Request) -> GateDecision:
    if _is_authorized_tester(request):
        return _tester_decision()
    day = _utc_day()
    visitor = _visitor_id(request)
    if _is_production() and not _supabase_ready():
        return _backend_unavailable(day, visitor)
    try:
        used = _supabase_get_used(day, visitor) if _supabase_ready() else _local_check(day, visitor)
    except Exception:
        if _is_production():
            return _backend_unavailable(day, visitor)
        used = _local_check(day, visitor)
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
    if _is_authorized_tester(request):
        return _tester_decision()
    day = _utc_day()
    visitor = _visitor_id(request)
    if _is_production() and not _supabase_ready():
        return _backend_unavailable(day, visitor)
    try:
        allowed, used = _supabase_claim(request, visitor) if _supabase_ready() else _local_claim(request, day, visitor, mode)
    except Exception:
        if _is_production():
            return _backend_unavailable(day, visitor)
        allowed, used = _local_claim(request, day, visitor, mode)
    return GateDecision(
        allowed=allowed,
        visitor_id=visitor,
        used_today=used,
        limit=DAILY_FREE_BOARD_LIMIT,
        remaining=max(0, DAILY_FREE_BOARD_LIMIT - used),
        day_utc=day,
        reason="recorded" if allowed else "daily_free_board_limit_reached",
    )


def free_gate_payload(decision: GateDecision) -> dict:
    if decision.reason == "usage_backend_unavailable":
        message = "Board Sense public access is temporarily unavailable. Please try again shortly."
        status = "temporarily_unavailable"
    else:
        message = "Your free Board Sense board analysis for today has already been used. Come back tomorrow for another free board."
        status = "limit_reached"
    return {
        "status": status,
        "message": message,
        "free_usage": decision.as_dict(),
    }
