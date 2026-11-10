"""Fail-closed paid Board Sense allowance policy (development only).

This is a small policy boundary, NOT an exposed API or a production quota
implementation. A future integration must supply a server-verified subscription
decision (from the trusted Scrap Radar backend) and an atomic DB reservation.
No browser-provided 'paid' flag, plan header or local counter may grant access.
Existing anonymous sampler in free_usage_gate.py remains unchanged.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Mapping
from uuid import UUID

DAILY_PAID_CASE_LIMIT = 25
MAX_DECISION_AGE = timedelta(minutes=5)


@dataclass(frozen=True)
class PaidDecision:
    allowed: bool
    reason: str
    limit: int = DAILY_PAID_CASE_LIMIT
    used_today: int = 0
    remaining: int = 0

    def as_dict(self):
        return dict(allowed=self.allowed, reason=self.reason, limit=self.limit,
                    used_today=self.used_today, remaining=self.remaining)


def _verified_member(customer_id, entitlement, now):
    if not isinstance(entitlement, Mapping):
        return False
    try:
        owner = str(UUID(str(customer_id)))
        member = str(UUID(str(entitlement.get("customer_id"))))
    except (ValueError, TypeError, AttributeError):
        return False
    checked = entitlement.get("verified_at")
    if not isinstance(checked, datetime) or checked.tzinfo is None:
        return False
    if not isinstance(now, datetime) or now.tzinfo is None:
        return False
    return bool(
        owner == member
        and entitlement.get("trusted_source") == "server_to_server"
        and entitlement.get("board_sense") is True
        and entitlement.get("paid_access_enabled") is True
        and entitlement.get("environment") == "live"
        and timedelta(0) <= now - checked <= MAX_DECISION_AGE
    )


def reserve_paid_case(customer_id, entitlement, atomic_reserve, now=None):
    """Only a verified paid customer may enter the atomic daily quota claim.

    atomic_reserve(customer_uuid, utc_day, limit) must commit exactly one
    case under a database lock/transaction and return (allowed, used_today).
    If the provider/DB fails, deny. A claim is one BOARD CASE regardless of
    photos; caller invokes once, before compute, and never per photograph.
    """
    current = now if now is not None else datetime.now(timezone.utc)
    if not _verified_member(customer_id, entitlement, current):
        return PaidDecision(False, "membership_not_verified")
    if not callable(atomic_reserve):
        return PaidDecision(False, "quota_backend_unavailable")
    day = current.astimezone(timezone.utc).date().isoformat()
    try:
        granted, used = atomic_reserve(str(UUID(str(customer_id))), day,
                                        DAILY_PAID_CASE_LIMIT)
        if type(granted) is not bool or type(used) is not int:
            raise ValueError("Invalid quota response")
        if used < 0 or used > DAILY_PAID_CASE_LIMIT or (granted and used == 0):
            raise ValueError("Invalid quota count")
    except (ValueError, TypeError, RuntimeError, OSError, TimeoutError):
        return PaidDecision(False, "quota_backend_unavailable")
    return PaidDecision(granted, "recorded" if granted else "daily_paid_case_limit_reached",
                        used_today=used,
                        remaining=max(0, DAILY_PAID_CASE_LIMIT-used))
