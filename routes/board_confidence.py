# routes/board_confidence.py


def calculate_confidence(score, features=None, visual=None, motherboard=None):
    """Estimate confidence from score plus corroborating evidence.

    Confidence is expressed as a percentage from 0 to 100. The score gives
    the baseline, while independent visual and structural signals can raise
    or lower certainty. This avoids treating every board with the same score
    as equally well supported.
    """

    features = features or {}
    visual = visual or {}
    motherboard = motherboard or {}

    if score >= 10:
        confidence = 78
    elif score >= 5:
        confidence = 66
    elif score > 0:
        confidence = 54
    else:
        confidence = 40

    # Count corroborating positive evidence from separate detectors.
    positive_signals = sum(
        1
        for value in (
            features.get("motherboard", False),
            features.get("ram", False),
            features.get("memory_module", False),
            features.get("gold_fingers", False),
            features.get("large_ic_chips", False),
            features.get("processor", False),
            visual.get("possible_ram", False),
            visual.get("gold_finger_edge", False),
            motherboard.get("possible_motherboard", False),
            motherboard.get("large_board", False),
        )
        if value
    )

    confidence += min(positive_signals * 3, 15)

    # Reward agreement between independent detectors.
    if features.get("ram") and visual.get("possible_ram"):
        confidence += 5

    if features.get("motherboard") and motherboard.get("possible_motherboard"):
        confidence += 5

    if features.get("gold_fingers") and visual.get("gold_finger_edge"):
        confidence += 4

    # A low score with no supporting evidence should remain uncertain.
    if score == 0 and positive_signals == 0:
        confidence = 35

    return max(25, min(int(round(confidence)), 97))
