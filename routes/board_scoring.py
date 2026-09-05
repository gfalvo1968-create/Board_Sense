# routes/board_scoring.py


def calculate_score(features):
    """Calculate a recovery score from recovery-bearing observations only.

    Board identity and equipment geometry are intentionally excluded. Being a
    motherboard can help answer what the board is, but it cannot by itself add
    economic recovery points. Recovery score asks a different question: what
    value-bearing material/features are physically supported?

    Dense logic population is treated as independent physical evidence because
    many populated IC packages materially change sorting/recovery opportunity.
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

    component_count = int(features.get("component_count", 0) or 0)
    component_density = float(features.get("component_density", 0.0) or 0.0)

    # Population bonuses are intentionally modest. They raise a clearly dense
    # board out of the sparse-LOW bucket without pretending image recognition
    # proves precious-metal chemistry.
    if component_count >= 18 or component_density >= 0.065:
        score += 4
    elif component_count >= 10 or component_density >= 0.035:
        score += 2

    # Power-heavy topology can lower recovery attractiveness, but identity does
    # not cancel that penalty. If valuable logic/material evidence is also
    # present, its positive evidence remains in the score above.
    if features.get("power_board"):
        score -= 3

    return max(int(score), 0)
