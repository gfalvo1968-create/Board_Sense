# routes/board_confidence.py


def calculate_confidence(
    score,
    features=None,
    visual=None,
    motherboard=None,
    power=None,
):
    """Estimate confidence from score plus corroborating evidence."""

    features = features or {}
    visual = visual or {}
    motherboard = motherboard or {}
    power = power or {}

    if score >= 10:
        confidence = 78
    elif score >= 5:
        confidence = 66
    elif score > 0:
        confidence = 54
    else:
        confidence = 40

    positive_signals = sum(
        1
        for value in (
            features.get("motherboard", False),
            features.get("ram", False),
            features.get("memory_module", False),
            features.get("power_board", False),
            features.get("gold_fingers", False),
            features.get("large_ic_chips", False),
            features.get("dense_component_board", False),
            features.get("processor", False),
            visual.get("possible_ram", False),
            visual.get("gold_finger_edge", False),
            visual.get("possible_large_ic_chips", False),
            motherboard.get("possible_motherboard", False),
            motherboard.get("large_board", False),
            power.get("possible_power_board", False),
        )
        if value
    )

    confidence += min(positive_signals * 3, 18)

    if features.get("ram") and visual.get("possible_ram"):
        confidence += 5

    if features.get("motherboard") and motherboard.get("possible_motherboard"):
        confidence += 5

    if features.get("gold_fingers") and visual.get("gold_finger_edge"):
        confidence += 4

    if features.get("large_ic_chips") and visual.get("possible_large_ic_chips"):
        confidence += 4

    if features.get("power_board") and power.get("possible_power_board"):
        confidence += 5

    component_count = int(features.get("component_count", 0) or 0)
    if component_count >= 8:
        confidence += 3
    elif component_count >= 4:
        confidence += 2

    if score == 0 and positive_signals == 0:
        confidence = 35

    return max(25, min(int(round(confidence)), 97))
