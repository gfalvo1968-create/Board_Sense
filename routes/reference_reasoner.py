"""Board Sense reference knowledge reasoner.

Turns detected visual signals into useful matches from the JSON reference library.
It does not claim exact chip identity from pixels; it uses the reference sheets to
explain likely recovery categories and sorting advice supported by detected evidence.
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


def build_reference_matches(features, visual, motherboard, power, board_type):
    knowledge = get_knowledge()
    matches = []

    gold = bool(features.get("gold_fingers") or visual.get("gold_finger_edge"))
    dense = bool(features.get("dense_component_board"))
    large_ics = bool(features.get("large_ic_chips") or visual.get("possible_large_ic_chips"))
    processor = bool(features.get("processor"))
    telecom_like = gold and dense and large_ics and not power.get("possible_power_board", False)

    # Gold-finger knowledge. Choose a conservative match unless density supports
    # the higher-quality card category.
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

    # IC knowledge. Image analysis can support package-family guidance, but not
    # exact metallurgy, so use conservative likely categories.
    if large_ics or processor:
        ic_rules = knowledge.get("ic_chips", [])
        target = "BGA Chip" if processor else "Plastic IC Chip"
        for item in ic_rules:
            if item.get("category") == target:
                reason = (
                    "Large central surface-mounted package detected"
                    if processor
                    else "Multiple large dark rectangular IC-like packages detected"
                )
                matches.append(_compact_match(item, reason))
                break

    # Telecom is a pattern match, not an exact equipment identification.
    if telecom_like:
        telecom_rules = knowledge.get("Telecom_boards", [])
        for item in telecom_rules:
            if item.get("category") == "High Grade Telecom Board":
                matches.append(
                    _compact_match(
                        item,
                        "Dense IC layout plus gold edge contacts resembles high-grade telecom architecture",
                    )
                )
                break

    return {
        "matches": matches,
        "match_count": len(matches),
        "telecom_pattern": telecom_like,
        "board_type_context": board_type.get("type", "General PCB"),
    }
