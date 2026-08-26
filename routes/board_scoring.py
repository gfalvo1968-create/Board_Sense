# routes/board_scoring.py


def calculate_score(features):
    """Calculate recovery score from detected board features."""

    score = 0

    if features.get("motherboard"):
        score += 5

    if features.get("memory_module") or features.get("ram"):
        score += 5

    if features.get("gold_fingers"):
        score += 3

    if features.get("large_ic_chips"):
        score += 3

    if features.get("dense_component_board"):
        score += 2

    if features.get("processor"):
        score += 6

    if features.get("power_board"):
        score -= 3

    return max(int(score), 0)
