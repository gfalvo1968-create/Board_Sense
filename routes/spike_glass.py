"""Spike Glass visual recognition layer for Board Sense.

Spike Glass answers a different question from whole-board grading:
"What am I looking at?"

It converts Board Sense visual/component evidence and reference-library matches
into ranked recognition candidates. These are evidence-based likely matches,
not guaranteed manufacturer/model identification.

v0.3 broadens component-family recognition and adds ambiguity handling so one
visual clue cannot dominate the result too easily.
"""


def _candidate(label, family, score, evidence, action="", caution=""):
    return {
        "label": label,
        "family": family,
        "score": max(0, int(score)),
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

    if features.get("ram") or visual.get("possible_ram"):
        evidence = ["long narrow board geometry", "memory-module pattern"]
        score = 86
        if features.get("gold_fingers") or visual.get("gold_finger_edge"):
            evidence.append("gold edge contacts")
            score += 6
        candidates.append(_candidate(
            "RAM / Memory Module", "board", score, evidence,
            "Keep separate from mixed low-grade boards; inspect gold fingers and IC population.",
            "Confirm the long DIMM/SODIMM-style form before assigning a memory grade."
        ))

    # Power-board recognition now requires filtered power evidence rather than
    # generic round shapes. Contact pads are deliberately excluded.
    if power.get("possible_power_board") or dominant == "power_components":
        score = 66 + min(18, int(power.get("power_score", 0)) * 3)
        evidence = []
        if cap_count:
            evidence.append(f"{cap_count} filtered capacitor-like round components")
            score += min(6, cap_count)
        if block_count:
            evidence.append(f"{block_count} power block / transformer / relay-like regions")
            score += min(8, block_count * 2)
        if power_ratio > logic_ratio:
            evidence.append("power-component evidence exceeds logic-component evidence")
        candidates.append(_candidate(
            "Power / Supply Board", "board", min(score, 94), evidence,
            "Favor copper, transformer and aluminum recovery; be conservative about precious-metal assumptions.",
            "Do not treat plated keypad/contact circles as capacitors."
        ))

    if motherboard.get("possible_motherboard"):
        evidence = ["motherboard-scale layout"]
        score = 76
        if motherboard.get("large_board"):
            evidence.append("large board footprint")
            score += 4
        if features.get("processor"):
            evidence.append("processor-rich region")
            score += 6
        if ic_count >= 4:
            evidence.append(f"{ic_count} IC-like packages")
            score += 4
        candidates.append(_candidate(
            "Motherboard / Main Logic Board", "board", min(score, 92), evidence,
            "Inspect sockets, gold contacts, IC density and removable processors before bulk grading."
        ))

    if features.get("gold_fingers") or visual.get("gold_finger_edge"):
        candidates.append(_candidate(
            "Gold Finger / Edge Connector", "component", 88,
            ["gold-colored edge contact pattern"],
            "Keep gold-finger material segregated when practical; value depends on plating thickness and base material.",
            "Gold color alone does not prove plating thickness or karat purity."
        ))

    # New: keypad/contact-board recognition. This is especially useful for phone,
    # remote-control, appliance, and button-interface boards with many flat round
    # plated contacts that previously looked like capacitors.
    if contact_count >= 3:
        score = 70 + min(20, contact_count * 2)
        evidence = [f"{contact_count} plated/contact-pad candidates"]
        if cap_count <= max(1, contact_count // 3):
            evidence.append("flat contact pattern dominates over true capacitor-like shapes")
            score += 4
        candidates.append(_candidate(
            "Keypad / Plated Contact Board", "board_feature", min(score, 94), evidence,
            "Treat the circles as contact surfaces, not capacitors; inspect the rest of the board for ICs and connectors before grading.",
            "Contact color can include copper, nickel, or gold flash; value depends on actual plating."
        ))

    # New: individual IC-package family recognition.
    if ic_count >= 1:
        score = 66 + min(18, ic_count * 3)
        evidence = [f"{ic_count} rectangular IC-like package candidates"]
        if dominant == "logic_ic":
            evidence.append("logic ICs dominate the major component population")
            score += 6
        candidates.append(_candidate(
            "IC / Logic Package", "component", min(score, 91), evidence,
            "Use package style, markings, board function and age before estimating recovery value.",
            "A dark rectangular package is not automatically a high-value processor or BGA."
        ))

    # New: capacitor-family recognition only when filtered round candidates exist.
    if cap_count >= 1:
        score = 62 + min(18, cap_count * 3)
        evidence = [f"{cap_count} filtered cylindrical/round component candidates"]
        if block_count:
            evidence.append("power-component context also present")
        candidates.append(_candidate(
            "Capacitor / Power Component Cluster", "component", min(score, 88), evidence,
            "Check whether parts are aluminum electrolytic, polymer, ceramic, or another family before sorting.",
            "Round pads, mounting holes and printed circles are filtered separately and should not be counted as capacitors."
        ))

    # New: transformer/relay/power-block family recognition.
    if block_count >= 1:
        score = 68 + min(18, block_count * 5)
        candidates.append(_candidate(
            "Transformer / Relay / Power Block", "component", min(score, 90),
            [f"{block_count} large block-like power regions", "rectangular high-area component silhouette"],
            "Inspect for copper windings, steel cores, aluminum heat sinks and relay contacts before recovery.",
            "This is a family-level identification, not an exact part number."
        ))

    if features.get("large_ic_chips") and ic_count >= 2:
        candidates.append(_candidate(
            "IC-Rich Logic Area", "component_region", 78,
            [f"{ic_count} IC-like rectangular packages", "component discriminator confirmed logic-style shapes"],
            "Use package type and board context before assigning precious-metal value."
        ))

    # Mixed boards deserve their own recognition instead of forcing a pure power
    # or pure logic answer when the evidence is genuinely split.
    if dominant == "mixed" and ic_count >= 2 and (cap_count + block_count) >= 2:
        candidates.append(_candidate(
            "Mixed Logic / Power Board", "board", 74,
            [f"{ic_count} IC-like packages", f"{cap_count + block_count} filtered power-component candidates"],
            "Sort by board function and recoverable components rather than relying on a single broad board family."
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

    # Merge duplicate labels, keeping the strongest candidate and combining evidence.
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
        raw_confidence = min(95, max(30, top["score"]))
        margin = top["score"] - second["score"] if second else 25

        # Close races should look like close races. This prevents Spike Glass from
        # displaying 90% certainty when two very different candidates are tied.
        if margin <= 3:
            confidence = min(raw_confidence, 72)
            status = "ambiguous_match"
        elif margin <= 7:
            confidence = min(raw_confidence, 82)
            status = "likely_match"
        else:
            confidence = raw_confidence
            status = "likely_match" if confidence >= 70 else "possible_match"
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
        "mode": "Spike Glass v0.3",
        "note": "Recognition candidates are evidence-based likely matches. Close scores are intentionally shown more cautiously rather than forced into a confident answer.",
    }
