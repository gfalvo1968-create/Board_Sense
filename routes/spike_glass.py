"""Spike Glass visual recognition layer for Board Sense.

Spike Glass answers a different question from whole-board grading:
"What am I looking at?"

It converts Board Sense visual/component evidence and reference-library matches
into ranked recognition candidates. These are evidence-based likely matches,
not guaranteed manufacturer/model identification.
"""


def _candidate(label, family, score, evidence, action=""):
    return {
        "label": label,
        "family": family,
        "score": max(0, int(score)),
        "evidence": evidence,
        "action": action,
    }


def recognize(features, visual, motherboard, power, components, reference_intelligence):
    candidates = []

    if features.get("ram") or visual.get("possible_ram"):
        evidence = ["long narrow board geometry", "memory-module pattern"]
        if features.get("gold_fingers") or visual.get("gold_finger_edge"):
            evidence.append("gold edge contacts")
        candidates.append(_candidate(
            "RAM / Memory Module", "board", 92, evidence,
            "Keep separate from mixed low-grade boards; inspect gold fingers and IC population."
        ))

    if power.get("possible_power_board") or components.get("dominant_family") == "power_components":
        score = 72 + min(18, power.get("power_score", 0) * 3)
        evidence = []
        if components.get("capacitor_like", 0):
            evidence.append(f"{components.get('capacitor_like')} capacitor-like round components")
        if components.get("transformer_relay_like", 0):
            evidence.append(f"{components.get('transformer_relay_like')} large block/transformer/relay-like regions")
        candidates.append(_candidate(
            "Power / Supply Board", "board", score, evidence,
            "Favor copper, transformer and aluminum recovery; be conservative about precious-metal assumptions."
        ))

    if motherboard.get("possible_motherboard"):
        evidence = ["motherboard-scale layout"]
        if motherboard.get("large_board"):
            evidence.append("large board footprint")
        if features.get("processor"):
            evidence.append("processor-rich region")
        candidates.append(_candidate(
            "Motherboard / Main Logic Board", "board", 82, evidence,
            "Inspect sockets, gold contacts, IC density and removable processors before bulk grading."
        ))

    if features.get("gold_fingers") or visual.get("gold_finger_edge"):
        candidates.append(_candidate(
            "Gold Finger / Edge Connector", "component", 88,
            ["gold-colored edge contact pattern"],
            "Keep gold-finger material segregated when practical; value depends on plating thickness and base material."
        ))

    if features.get("large_ic_chips") and components.get("ic_like", 0) >= 2:
        candidates.append(_candidate(
            "IC-Rich Logic Area", "component", 78,
            [f"{components.get('ic_like')} IC-like rectangular packages", "component discriminator confirmed logic-style shapes"],
            "Use package type and board context before assigning precious-metal value."
        ))

    # Promote useful names already supported by the reference knowledge library.
    for match in reference_intelligence.get("matches", []):
        label = match.get("category")
        if not label:
            continue
        rank = match.get("value_rank", 0) or 0
        candidates.append(_candidate(
            label,
            "reference_match",
            55 + min(35, int(rank) * 3),
            [match.get("reason", "reference-library evidence")],
            match.get("sorting_advice", "")
        ))

    # Merge duplicate labels, keeping the strongest candidate and combined evidence.
    merged = {}
    for item in candidates:
        key = item["label"].lower()
        if key not in merged or item["score"] > merged[key]["score"]:
            merged[key] = item
        else:
            for evidence in item["evidence"]:
                if evidence not in merged[key]["evidence"]:
                    merged[key]["evidence"].append(evidence)

    ranked = sorted(merged.values(), key=lambda item: item["score"], reverse=True)
    top = ranked[0] if ranked else None

    if top:
        confidence = min(95, max(30, top["score"]))
        status = "likely_match" if confidence >= 70 else "possible_match"
    else:
        confidence = 0
        status = "no_strong_match"

    return {
        "status": status,
        "top_match": top,
        "candidates": ranked[:5],
        "confidence": confidence,
        "mode": "Spike Glass v0.1",
        "note": "Recognition candidates are evidence-based likely matches, not guaranteed manufacturer/model identification.",
    }
