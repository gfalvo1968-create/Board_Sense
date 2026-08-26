def classify_board_type(features, visual, motherboard, power):
    """Return a human-readable board type from combined detector evidence."""
    features = features or {}
    visual = visual or {}
    motherboard = motherboard or {}
    power = power or {}

    if features.get("ram") or visual.get("possible_ram"):
        return {
            "type": "RAM / Memory Module",
            "reason": "Long narrow geometry and memory-module signals detected.",
        }

    if power.get("possible_power_board"):
        return {
            "type": "Power / Supply Board",
            "reason": "Large round components and sparse high-power component layout detected.",
        }

    if features.get("motherboard") or motherboard.get("possible_motherboard"):
        return {
            "type": "Motherboard / Main Logic Board",
            "reason": "Large board geometry with logic-board characteristics detected.",
        }

    if features.get("processor") and features.get("dense_component_board"):
        return {
            "type": "Processor-Rich Logic Board",
            "reason": "Dense IC population with a dominant processor-like package detected.",
        }

    if features.get("dense_component_board") or features.get("large_ic_chips"):
        return {
            "type": "Dense Logic / Controller Board",
            "reason": "Multiple IC-like packages and elevated component density detected.",
        }

    if features.get("gold_fingers") or visual.get("gold_finger_edge"):
        return {
            "type": "Edge-Connector Expansion Board",
            "reason": "Gold-bearing connector material detected near the board edge.",
        }

    return {
        "type": "General PCB",
        "reason": "No stronger board-type pattern has been confirmed yet.",
    }
