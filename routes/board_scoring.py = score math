def calculate_score(features):

    score = 0

    if features.get("motherboard"):
        score += 5

    if features.get("ram"):
        score += 4

    if features.get("power_board"):
        score -= 3

    return max(score, 0)
