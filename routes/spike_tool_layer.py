"""SPIKE Tool-Use Layer v0.5.

SPIKE may call tools when first-pass evidence is uncertain. Tool output is kept
separate from the physical identity decision so a web hit, local crop, or duplicate
view can corroborate/inform inspection but never manufacture board identity.

v0.5 adds local digital zoom and a visual-independence review. SPIKE now inspects
existing pixels around a bottleneck before reaching for outside references. A zoom
is never counted as a new photograph. Paid lookup remains skipped when physical
evidence already settled the case or when the missing evidence is a new photo.
"""
from __future__ import annotations

import re
from collections import Counter

from routes.spike_web_match import search_visual_matches
from routes.spike_local_zoom import compare_visual_source, inspect_identity_zoom


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


def _visual_independence_checks(image_paths: list[str] | None) -> list[dict]:
    if not image_paths or len(image_paths) < 2:
        return []
    checks = []
    # Case Mode is capped at six photos, so pairwise local matching remains small.
    for i in range(len(image_paths)):
        for j in range(i + 1, len(image_paths)):
            relation = compare_visual_source(image_paths[i], image_paths[j])
            checks.append({"views": [i + 1, j + 1], **relation})
    return checks


def _local_zoom_requests(identity: dict, image_paths: list[str] | None) -> list[dict]:
    if not image_paths:
        return []
    zooms = []
    for request in identity.get("requested_photos") or []:
        view = int(request.get("flagged_view") or 0)
        axis = request.get("axis")
        cut = request.get("cut")
        if view < 1 or view > len(image_paths) or axis not in {"x", "y"} or cut is None:
            continue
        zoom = inspect_identity_zoom(image_paths[view - 1], axis, cut)
        zoom["view"] = view
        zoom["request_type"] = request.get("request_type")
        zooms.append(zoom)
    return zooms


def investigate_identity(results: list[dict], image_paths: list[str] | None, identity: dict) -> dict:
    status = str(identity.get("status") or "")
    hard_physical_stop = status in _HARD_PHYSICAL_STOPS and identity.get("same_board") is False
    needs_whole_photo = (
        status == "IDENTITY_UNCERTAIN"
        and bool(identity.get("block_reconciliation"))
        and int(identity.get("whole_view_count", 0) or 0) == 0
    )
    needs_local_zoom = status == "IDENTITY_CLARIFICATION_NEEDED" and bool(identity.get("block_reconciliation"))
    needs_tools = (
        (bool(identity.get("block_reconciliation")) or status == "IDENTITY_UNCERTAIN")
        and not hard_physical_stop
        and not needs_whole_photo
        and not needs_local_zoom
    )

    if hard_physical_stop:
        packet_status = "physical_stop_settled"
    elif needs_whole_photo:
        packet_status = "identity_photo_needed"
    elif needs_local_zoom:
        packet_status = "local_zoom_review"
    else:
        packet_status = "not_needed" if not needs_tools else "tool_review_requested"

    packet = {
        "version": "SPIKE Tool-Use Layer v0.5",
        "status": packet_status,
        "trigger": status or "unknown",
        "tools_considered": [
            "physical_geometry_compare",
            "local_zoom_inspection",
            "visual_evidence_independence_check",
            "spike_glass_web_match",
            "manufacturer_reference_lookup",
            "verified_case_memory",
        ],
        "tools_used": ["physical_geometry_compare"],
        "local_zoom_inspections": [],
        "visual_independence_checks": [],
        "web_reference_searches": [],
        "reference_consensus": None,
        "identity_override": False,
        "rule": "SPIKE may zoom existing pixels before asking for another photo, but a digital zoom is never new identity evidence. External tools cannot manufacture identity, and paid lookup is skipped when physical evidence or a missing photo already determines the next step.",
    }

    # Cheap local work may run regardless of whether a paid lookup is needed.
    checks = _visual_independence_checks(image_paths)
    packet["visual_independence_checks"] = checks
    if checks:
        packet["tools_used"].append("visual_evidence_independence_check")
    if any(c.get("non_independent") for c in checks):
        packet["non_independent_view_pairs"] = [c.get("views") for c in checks if c.get("non_independent")]
        packet["visual_evidence_note"] = "At least one uploaded view appears to be a crop/zoom or near-duplicate of another. It may help inspection, but it should not multiply identity confidence."

    if hard_physical_stop:
        packet["note"] = "External reference search skipped because physical evidence already established a hard multi-board stop."
        return packet

    if needs_whole_photo:
        packet["note"] = "External reference search skipped because the uploaded views lack usable whole-board geometry. Digital zoom cannot create missing whole-board evidence; a new identity photo is required."
        return packet

    if needs_local_zoom:
        zooms = _local_zoom_requests(identity, image_paths)
        packet["local_zoom_inspections"] = zooms
        if zooms:
            packet["tools_used"].append("local_zoom_inspection")
            usable = any(z.get("status") == "inspectable_existing_pixels" for z in zooms)
            packet["status"] = "local_zoom_inspection_complete" if usable else "identity_photo_needed"
            packet["note"] = (
                "SPIKE inspected the existing pixels around the physical ambiguity before requesting anything external. The zoom remains derived evidence and cannot clear identity by itself."
                if usable
                else "SPIKE tried the local zoom first, but the existing pixels do not contain enough detail. A new targeted photo is still required."
            )
        else:
            packet["status"] = "identity_photo_needed"
            packet["note"] = "The identity request did not provide a usable zoom target, so a new targeted photo is still required."
        # A web search cannot settle physical continuity at a neck/seam, so do not spend it here.
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
