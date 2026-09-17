"""SPIKE Tool-Use Layer v0.4.

SPIKE may call outside tools when first-pass evidence is uncertain. Tool output is
kept separate from the physical identity decision so a web hit can corroborate but
never manufacture board identity.

v0.4 works smarter, not harder: paid lookup is skipped when either hard physical
evidence already settled the case or the missing evidence is a new whole-board photo.
A web result cannot replace geometry that was never captured in the uploaded views.
"""
from __future__ import annotations

import re
from collections import Counter

from routes.spike_web_match import search_visual_matches


_STOP = {
    "board", "motherboard", "logic", "main", "pcb", "system",
    "replacement", "genuine", "new", "used", "for", "with", "and", "the", "a", "an",
    "ebay", "amazon", "aliexpress", "walmart", "etsy", "tested", "dead",
}


_HARD_PHYSICAL_STOPS = {
    "MULTIPLE_BOARDS_IN_FRAME_SUSPECTED",
    "MULTIPLE_BOARDS_SUSPECTED",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9._+-]{2,}", (text or "").lower())
    return {w for w in words if w not in _STOP and not w.isdigit()}


def _query_for_result(result: dict) -> str:
    """Use text filtering only when SPIKE has genuinely specific evidence.

    Generic classifier labels such as "Dense Logic Board" or "IC / Logic Package"
    are intentionally excluded because feeding them into Google Lens can suppress
    the image-first visual matches we actually need for front/back identity work.
    """
    bits = []

    for key in ("visible_markings", "part_markings", "model_markings"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            bits.append(value.strip())
        elif isinstance(value, (list, tuple)):
            bits.extend(str(x).strip() for x in value if str(x).strip())

    subtype = result.get("equipment_subtype") or {}
    sub = str(subtype.get("subtype") or subtype.get("type") or "").strip()
    if sub and (any(ch.isdigit() for ch in sub) or "-" in sub or "/" in sub):
        bits.append(sub)

    query = " ".join(bits).strip()
    return query[:220]


def _reference_consensus(searches: list[dict]) -> dict:
    searched = [s for s in searches if s.get("status") == "searched"]
    if len(searched) < 2:
        return {
            "status": "insufficient_reference_views",
            "support": "none",
            "common_tokens": [],
            "rule": "At least two independently searched case views are needed before web references can corroborate same-board identity.",
        }

    per_view = []
    for search in searched:
        token_pool = set()
        for match in search.get("matches") or []:
            token_pool |= _tokens(f"{match.get('title') or ''} {match.get('source') or ''}")
        per_view.append(token_pool)

    common = set.intersection(*per_view) if per_view else set()
    useful = sorted(common)
    support = "reference_corroboration" if len(useful) >= 2 else "weak_reference_overlap"
    return {
        "status": "reference_overlap_checked",
        "support": support,
        "common_tokens": useful[:12],
        "rule": "Shared web-reference terms can corroborate a physical match, but cannot by themselves override a single-frame multiple-board warning.",
    }


def investigate_identity(results: list[dict], image_paths: list[str] | None, identity: dict) -> dict:
    status = str(identity.get("status") or "")
    hard_physical_stop = status in _HARD_PHYSICAL_STOPS and identity.get("same_board") is False
    needs_whole_photo = (
        status == "IDENTITY_UNCERTAIN"
        and bool(identity.get("block_reconciliation"))
        and int(identity.get("whole_view_count", 0) or 0) == 0
    )
    needs_tools = (
        (bool(identity.get("block_reconciliation")) or status == "IDENTITY_UNCERTAIN")
        and not hard_physical_stop
        and not needs_whole_photo
    )

    if hard_physical_stop:
        packet_status = "physical_stop_settled"
    elif needs_whole_photo:
        packet_status = "identity_photo_needed"
    else:
        packet_status = "not_needed" if not needs_tools else "tool_review_requested"

    packet = {
        "version": "SPIKE Tool-Use Layer v0.4",
        "status": packet_status,
        "trigger": status or "unknown",
        "tools_considered": [
            "physical_geometry_compare",
            "spike_glass_web_match",
            "manufacturer_reference_lookup",
            "verified_case_memory",
        ],
        "tools_used": ["physical_geometry_compare"],
        "web_reference_searches": [],
        "reference_consensus": None,
        "identity_override": False,
        "rule": "SPIKE may use external tools to resolve uncertainty, but no external result may manufacture identity. Paid lookup is skipped when physical evidence already settled the case or when a new whole-board photo is the missing evidence.",
    }

    if hard_physical_stop:
        packet["note"] = "External reference search skipped because physical evidence already established a hard multi-board stop."
        return packet

    if needs_whole_photo:
        packet["note"] = "External reference search skipped because the uploaded views lack usable whole-board geometry. A new identity photo is the evidence needed to continue."
        return packet

    if not needs_tools:
        return packet

    if not image_paths or len(image_paths) != len(results):
        packet["status"] = "tool_review_incomplete"
        packet["note"] = "Image paths were unavailable for Spike Glass Web Match."
        return packet

    searches = []
    for result, path in list(zip(results, image_paths))[:2]:
        query = _query_for_result(result)
        found = search_visual_matches(path, query=query or None, limit=6)
        found["view"] = int(result.get("view_number") or len(searches) + 1)
        searches.append(found)

    packet["web_reference_searches"] = searches
    if any(s.get("status") == "searched" for s in searches):
        packet["tools_used"].append("spike_glass_web_match")
    elif searches and all(s.get("status") == "provider_not_configured" for s in searches):
        packet["status"] = "web_provider_not_configured"

    packet["reference_consensus"] = _reference_consensus(searches)
    return packet
