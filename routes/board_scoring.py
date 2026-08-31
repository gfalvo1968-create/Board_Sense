# routes/board_scoring.py


def calculate_score(features):
    """Calculate a recovery score from recovery-bearing observations only.

    Board identity and equipment geometry are intentionally excluded. Being a
    motherboard can help answer what the board is, but it cannot by itself add
    economic recovery points. Recovery score asks a different question: what
    value-bearing material/features are physically supported?
    """
    score = 0

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

    # Power-heavy topology can lower recovery attractiveness, but identity does
    # not cancel that penalty. If valuable logic/material evidence is also
    # present, its positive evidence remains in the score above.
    if features.get("power_board"):
        score -= 3

    return max(int(score), 0)
