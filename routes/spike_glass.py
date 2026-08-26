"""Spike Glass visual recognition layer for Board Sense.

Spike Glass answers a different question from whole-board grading:
"What am I looking at?"

v0.4 makes confidence evidence-weighted and contradiction-aware. A family can
still appear as a candidate, but weak or contradictory evidence cannot easily
turn into a 90% answer.
"""


def _candidate(label, family, score, evidence, action="", caution=""):
    return {
        "label": label,
        "family": family,
        "score": max(0, min(95, int(score))),
        "evidence": evidence,
        "action": action,
        "caution": caution,
    }


def recognize(features, visual, motherboard, power, components, reference_intelligence):
    candidates = []

    ic_count = int(components.get("ic_like", 0))
    cap_count = int(components.get("capacitor_like", 0))
    contact_count = int(components.get("contact_pad_like", 0))
    block_count = int(components.get("transformer_relay_like", 0))
    dominant = components.get("dominant_family", "unknown")
    logic_ratio = float(components.get("logic_component_ratio", 0.0))
    power_ratio = float(components.get("power_component_ratio", 0.0))

    # RAM should need more than one broad geometry clue.
    if features.get("ram") or visual.get("possible_ram"):
        evidence = []
        score = 58
        if visual.get("possible_ram"):
            evidence.append("long narrow memory-module-like geometry")
            score += 8
        if features.get("gold_fingers") or visual.get("gold_finger_edge"):
            evidence.append("gold edge contacts")
            score += 12
        if ic_count >= 4:
            evidence.append(f"{ic_count} IC-like packages support a populated memory-style board")
            score += 8
        if block_count >= 2 or dominant == "power_components":
            score -= 14
            evidence.append("power-component evidence conflicts with a clean RAM interpretation")
        candidates.append(_candidate(
            "RAM / Memory Module", "board", score, evidence,
            "Keep separate from mixed low-grade boards; inspect gold fingers and IC population.",
            "Confirm DIMM/SODIMM-style geometry, repeated memory ICs and edge contacts before assigning a memory grade."
        ))

    # Power-board recognition requires filtered power evidence. Contact pads are
    # deliberately excluded, and logic/contact-heavy boards actively reduce score.
    if power.get("possible_power_board") or dominant == "power_components" or (cap_count + block_count) >= 3:
        evidence = []
        score = 48
        if power.get("possible_power_board"):
            score += min(14, int(power.get("power_score", 0)) * 2)
            evidence.append("independent power-board detector produced supporting evidence")
        if cap_count:
            evidence.append(f"{cap_count} filtered capacitor-like components")
            score += min(12, cap_count * 2)
        if block_count:
            evidence.append(f"{block_count} transformer/relay/power-block-like regions")
            score += min(18, block_count * 6)
        if power_ratio > logic_ratio + 0.15:
            score += 8
            evidence.append("power-component evidence clearly exceeds logic-component evidence")
        if ic_count >= 4 and logic_ratio >= power_ratio:
            score -= 14
            evidence.append("logic IC population conflicts with a pure power-board interpretation")
        if contact_count >= 3 and contact_count > cap_count:
            score -= 12
            evidence.append("plated contact pads outnumber capacitor-like regions")
        candidates.append(_candidate(
            "Power / Supply Board", "board", score, evidence,
            "Favor copper, transformer and aluminum recovery; be conservative about precious-metal assumptions.",
            "A power-board call should be supported by actual power parts, not round pads, holes or contact circles."
        ))

    if motherboard.get("possible_motherboard"):
        evidence = ["motherboard-scale layout detector fired"]
        score = 62
        if motherboard.get("large_board"):
            evidence.append("large board footprint")
            score += 8
        if features.get("processor"):
            evidence.append("processor-rich region")
            score += 10
        if ic_count >= 4:
            evidence.append(f"{ic_count} IC-like packages")
            score += min(10, ic_count)
        if dominant == "power_components" and power_ratio > logic_ratio:
            score -= 12
            evidence.append("power-component dominance conflicts with main-logic-board interpretation")
        candidates.append(_candidate(
            "Motherboard / Main Logic Board", "board", score, evidence,
            "Inspect sockets, gold contacts, IC density and removable processors before bulk grading."
        ))

    if features.get("gold_fingers") or visual.get("gold_finger_edge"):
        score = 72
        evidence = ["gold-colored edge contact pattern"]
        if visual.get("gold_finger_edge") and features.get("gold_fingers"):
            score += 10
            evidence.append("two independent gold-finger signals agree")
        candidates.append(_candidate(
            "Gold Finger / Edge Connector", "component", score, evidence,
            "Keep gold-finger material segregated when practical; value depends on plating thickness and base material.",
            "Gold color alone does not prove plating thickness or karat purity."
        ))

    if contact_count >= 3:
        score = 62 + min(20, contact_count * 2)
        evidence = [f"{contact_count} plated/contact-pad candidates"]
        if cap_count <= max(1, contact_count // 3):
            evidence.append("flat contact pattern dominates over capacitor-like shapes")
            score += 8
        if ic_count:
            evidence.append("supporting electronics are present around the contact pattern")
            score += 4
        candidates.append(_candidate(
            "Keypad / Plated Contact Board", "board_feature", score, evidence,
            "Treat the circles as contact surfaces, not capacitors; inspect the rest of the board for ICs and connectors before grading.",
            "Contact color can include copper, nickel or gold flash; value depends on actual plating."
        ))

    if ic_count >= 1:
        score = 58 + min(20, ic_count * 3)
        evidence = [f"{ic_count} rectangular IC-like package candidates"]
        if dominant == "logic_ic":
            evidence.append("logic ICs dominate the major component population")
            score += 8
        if power_ratio > logic_ratio + 0.25:
            score -= 8
            evidence.append("stronger power evidence lowers confidence in a logic-dominant interpretation")
        candidates.append(_candidate(
            "IC / Logic Package", "component", score, evidence,
            "Use package style, markings, board function and age before estimating recovery value.",
            "A dark rectangular package is not automatically a high-value processor or BGA."
        ))

    if cap_count >= 1:
        score = 54 + min(18, cap_count * 3)
        evidence = [f"{cap_count} filtered cylindrical/round component candidates"]
        if block_count:
            evidence.append("power-component context also present")
            score += min(8, block_count * 2)
        if contact_count > cap_count:
            score -= 8
            evidence.append("contact-pad population is stronger than capacitor evidence")
        candidates.append(_candidate(
            "Capacitor / Power Component Cluster", "component", score, evidence,
            "Check whether parts are aluminum electrolytic, polymer, ceramic or another family before sorting.",
            "Round pads, mounting holes and printed circles should not be counted as capacitors."
        ))

    if block_count >= 1:
        score = 60 + min(20, block_count * 5)
        candidates.append(_candidate(
            "Transformer / Relay / Power Block", "component", score,
            [f"{block_count} large block-like power regions", "rectangular high-area component silhouette"],
            "Inspect for copper windings, steel cores, aluminum heat sinks and relay contacts before recovery.",
            "This is a family-level identification, not an exact part number."
        ))

    if features.get("large_ic_chips") and ic_count >= 2:
        candidates.append(_candidate(
            "IC-Rich Logic Area", "component_region", 70 + min(12, ic_count),
            [f"{ic_count} IC-like rectangular packages", "visual and component evidence agree on a logic-style area"],
            "Use package type and board context before assigning precious-metal value."
        ))

    if dominant == "mixed" and ic_count >= 2 and (cap_count + block_count) >= 2:
        candidates.append(_candidate(
            "Mixed Logic / Power Board", "board", 72,
            [f"{ic_count} IC-like packages", f"{cap_count + block_count} filtered power-component candidates"],
            "Sort by board function and recoverable components rather than relying on a single broad board family."
        ))

    # Reference-library names are supporting witnesses, not automatic winners.
    # They need visual/component evidence elsewhere in the candidate set to earn
    # very high confidence.
    for match in reference_intelligence.get("matches", []):
        label = match.get("category")
        if not label:
            continue
        rank = int(match.get("value_rank", 0) or 0)
        candidates.append(_candidate(
            label,
            "reference_match",
            50 + min(24, rank * 2),
            [match.get("reason", "reference-library evidence")],
            match.get("sorting_advice", ""),
            "Reference knowledge supports recognition but does not replace visual confirmation."
        ))

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
    second = ranked[1] if len(ranked) > 1 else None

    if top:
        raw_confidence = min(95, max(25, top["score"]))
        margin = top["score"] - second["score"] if second else 25

        # Confidence needs both score and separation from competing explanations.
        if margin <= 3:
            confidence = min(raw_confidence, 68)
            status = "ambiguous_match"
        elif margin <= 7:
            confidence = min(raw_confidence, 78)
            status = "likely_match"
        elif margin <= 12:
            confidence = min(raw_confidence, 86)
            status = "likely_match"
        else:
            confidence = raw_confidence
            status = "likely_match" if confidence >= 70 else "possible_match"

        if confidence < 60:
            status = "possible_match"
    else:
        confidence = 0
        margin = 0
        status = "no_strong_match"

    return {
        "status": status,
        "top_match": top,
        "candidates": ranked[:6],
        "confidence": confidence,
        "score_margin": int(margin),
        "mode": "Spike Glass v0.4",
        "evidence_summary": {
            "ic_like": ic_count,
            "capacitor_like": cap_count,
            "contact_pad_like": contact_count,
            "power_block_like": block_count,
            "dominant_family": dominant,
            "logic_component_ratio": logic_ratio,
            "power_component_ratio": power_ratio,
        },
        "note": "Recognition candidates are evidence-weighted. Contradictory evidence and close scores intentionally reduce confidence rather than forcing a confident answer.",
    }
