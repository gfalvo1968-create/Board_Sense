"""Board Sense reference knowledge reasoner.

Combines detector evidence with the JSON reference library. The engine reports
weighted hypotheses and supporting/contradicting evidence instead of pretending
that one visual clue proves an exact board identity.
"""

from routes.reference_loader import get_knowledge


def _compact_match(item, reason):
    return {
        "category": item.get("category", "Unknown"),
        "grade": item.get("grade", "UNKNOWN"),
        "value_rank": item.get("value_rank", 0),
        "reason": reason,
        "material_signals": item.get("material_signals", []),
        "sorting_advice": item.get("sorting_advice", ""),
        "notes": item.get("notes", ""),
    }


def _add(hypotheses, name, points, reason):
    item = hypotheses.setdefault(name, {"score": 0, "evidence": [], "against": []})
    item["score"] += points
    if points >= 0:
        item["evidence"].append(reason)
    else:
        item["against"].append(reason)


def _normalize_hypotheses(hypotheses):
    ranked = []
    for name, data in hypotheses.items():
        raw = data["score"]
        confidence = max(0, min(100, int(round(50 + (raw * 7)))))
        ranked.append({
            "type": name,
            "evidence_score": raw,
            "hypothesis_confidence": confidence,
            "evidence": data["evidence"],
            "against": data["against"],
        })
    ranked.sort(key=lambda x: x["evidence_score"], reverse=True)
    return ranked


def build_reference_matches(features, visual, motherboard, power, board_type):
    knowledge = get_knowledge()
    matches = []
    hypotheses = {}

    gold = bool(features.get("gold_fingers") or visual.get("gold_finger_edge"))
    ram = bool(features.get("ram") or features.get("memory_module") or visual.get("possible_ram"))
    dense = bool(features.get("dense_component_board"))
    large_ics = bool(features.get("large_ic_chips") or visual.get("possible_large_ic_chips"))
    processor = bool(features.get("processor"))
    mobo = bool(features.get("motherboard") or motherboard.get("possible_motherboard"))
    large_board = bool(motherboard.get("large_board"))
    power_like = bool(features.get("power_board") or power.get("possible_power_board"))
    component_count = int(features.get("component_count", 0) or 0)
    aspect_ratio = float(visual.get("aspect_ratio", 0) or 0)
    gold_ratio = float(visual.get("gold_ratio", 0) or 0)
    large_round = int(power.get("large_round_components", 0) or 0)
    large_regions = int(power.get("large_component_regions", 0) or 0)

    # Competing board hypotheses. Positive and negative evidence can coexist.
    if ram:
        _add(hypotheses, "RAM / Memory Module", 5, "Long narrow memory-module geometry detected")
    if aspect_ratio >= 2.4:
        _add(hypotheses, "RAM / Memory Module", 3, f"High aspect ratio ({aspect_ratio:.2f}:1)")
    if gold:
        _add(hypotheses, "RAM / Memory Module", 2, "Gold edge contacts support a memory-module interpretation")
        _add(hypotheses, "Expansion / Gold Finger Card", 4, "Gold-bearing edge connector detected")
    if dense:
        _add(hypotheses, "Expansion / Gold Finger Card", 2, "Dense component population")
        _add(hypotheses, "Telecom / Network Board", 3, "Dense IC population resembles telecom logic")
        _add(hypotheses, "Motherboard / Logic Board", 2, "Dense logic population")
    if large_ics:
        _add(hypotheses, "Telecom / Network Board", 2, "Multiple large IC-like packages")
        _add(hypotheses, "Motherboard / Logic Board", 2, "Large IC packages support a logic-board interpretation")
    if processor:
        _add(hypotheses, "Motherboard / Logic Board", 4, "Large central processor-like package")
        _add(hypotheses, "Processor-Rich Logic Board", 5, "Dominant central processing package")
    if mobo:
        _add(hypotheses, "Motherboard / Logic Board", 6, "Motherboard-like size and proportions")
    if large_board:
        _add(hypotheses, "Motherboard / Logic Board", 2, "Large board geometry")
        _add(hypotheses, "Server / Enterprise Board", 2, "Large board size is consistent with server hardware")
    if dense and mobo and large_board:
        _add(hypotheses, "Server / Enterprise Board", 4, "Large motherboard geometry with dense circuitry")
    if gold and dense and large_ics and not power_like:
        _add(hypotheses, "Telecom / Network Board", 5, "Gold contacts plus dense IC layout strongly support telecom-style architecture")
    if power_like:
        _add(hypotheses, "Power / Supply Board", 7, "Power-board detector found strong power-handling characteristics")
        _add(hypotheses, "Telecom / Network Board", -4, "Power-heavy layout argues against a premium telecom logic board")
        _add(hypotheses, "Motherboard / Logic Board", -3, "Power-heavy layout argues against a typical logic motherboard")
    if large_round >= 2:
        _add(hypotheses, "Power / Supply Board", 3, f"{large_round} large round capacitor-like components detected")
    if large_regions >= 2:
        _add(hypotheses, "Power / Supply Board", 2, f"{large_regions} large power-component regions detected")
    if component_count >= 8:
        _add(hypotheses, "Telecom / Network Board", 2, f"High chip-like component count ({component_count})")
        _add(hypotheses, "Server / Enterprise Board", 2, f"High chip-like component count ({component_count})")
    elif component_count <= 2 and power_like:
        _add(hypotheses, "Power / Supply Board", 2, "Low logic-chip count with power characteristics")
    if gold_ratio >= 0.06:
        _add(hypotheses, "Expansion / Gold Finger Card", 2, f"Strong edge gold-color ratio ({gold_ratio * 100:.1f}%)")

    # Reference library matches remain conservative and explainable.
    if gold:
        gold_rules = knowledge.get("gold_fingers", [])
        target = "High Quality Gold Finger Card" if dense else "Full Gold Fingers"
        for item in gold_rules:
            if item.get("category") == target:
                reason = "Gold-bearing edge contacts detected"
                if dense:
                    reason += " with dense component population"
                matches.append(_compact_match(item, reason))
                break

    if large_ics or processor:
        ic_rules = knowledge.get("ic_chips", [])
        target = "BGA Chip" if processor else "Plastic IC Chip"
        for item in ic_rules:
            if item.get("category") == target:
                reason = "Large central surface-mounted package detected" if processor else "Multiple large dark rectangular IC-like packages detected"
                matches.append(_compact_match(item, reason))
                break

    if mobo:
        motherboard_rules = knowledge.get("motherboards", [])
        target = "High Grade Motherboard" if dense and gold else "Medium Grade Motherboard"
        for item in motherboard_rules:
            if item.get("category") == target:
                reason = "Motherboard geometry detected"
                if dense:
                    reason += " with dense component population"
                if gold:
                    reason += " and gold-bearing contacts"
                matches.append(_compact_match(item, reason))
                break

    telecom_like = gold and dense and large_ics and not power_like
    if telecom_like:
        telecom_rules = knowledge.get("Telecom_boards", [])
        for item in telecom_rules:
            if item.get("category") == "High Grade Telecom Board":
                matches.append(_compact_match(item, "Dense IC layout plus gold edge contacts resembles high-grade telecom architecture"))
                break

    ranked = _normalize_hypotheses(hypotheses)
    top = ranked[0] if ranked else None
    runner_up = ranked[1] if len(ranked) > 1 else None
    margin = (top["evidence_score"] - runner_up["evidence_score"]) if top and runner_up else (top["evidence_score"] if top else 0)

    return {
        "matches": matches,
        "match_count": len(matches),
        "hypotheses": ranked[:5],
        "top_hypothesis": top,
        "hypothesis_margin": margin,
        "telecom_pattern": telecom_like,
        "board_type_context": board_type.get("type", "General PCB"),
        "reasoning_version": "weighted-evidence-v1",
    }
