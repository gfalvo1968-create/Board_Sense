# signal_engine.py

from routes.board_scoring import calculate_score


def light_from_strength(strength: int):
    if strength >= 3:
        return "green"

    if strength >= 1:
        return "orange"

    return "red"


def evaluate_signals(board_data):
    """
    Evaluate board signals using the central Board Sense scoring engine.
    """

    score = calculate_score(board_data)

    signals = {}

    gold_strength = 3 if board_data.get("gold_fingers") else 0
    chip_strength = 3 if board_data.get("large_ic_chips") else 0
    server_strength = 3 if board_data.get("server_grade") else 0

    low_value = board_data.get("low_value_board", False)

    signals["gold_fingers"] = light_from_strength(gold_strength)
    signals["large_ic_chips"] = light_from_strength(chip_strength)
    signals["server_grade"] = light_from_strength(server_strength)
    signals["low_value_board"] = "red" if low_value else "green"

    jackpot = (
        signals["gold_fingers"] == "green"
        and signals["large_ic_chips"] == "green"
        and not low_value
    )

    if jackpot:
        recommendation = (
            "JACKPOT - this board should be reviewed in Pay_Dirt."
        )
    elif score >= 10:
        recommendation = (
            "High value board - strong recovery candidate."
        )
    elif score >= 5:
        recommendation = (
            "Medium value board - inspect before selling."
        )
    else:
        recommendation = (
            "Low signal board - likely scrap or training material."
        )

    return {
        "score": score,
        "signals": signals,
        "jackpot": jackpot,
        "recommendation": recommendation,
    }
