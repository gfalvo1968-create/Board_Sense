# routes/board_scoring.py


def calculate_score(features):
    """Calculate recovery score from detected board features.

    A structurally confirmed motherboard gets a medium-grade floor. Power
    circuitry on a motherboard is a subsystem, so it must not drag the whole
    board back into the low-grade power-board bucket.
    """
    score = 0
    is_motherboard = bool(features.get("motherboard"))

    if is_motherboard:
        score += 9
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

    # Only penalize a power-board signal when the board has not already been
    # structurally identified as a motherboard/main logic board.
    if features.get("power_board") and not is_motherboard:
        score -= 3

    return max(int(score), 0)
